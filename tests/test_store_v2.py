"""واجهة التطبيق المصغّر الجديدة v2: الزبون، البائع، المدير، والصلاحيات."""
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from forge import config, crypto, db
from forge.modules import ledger
from forge.web import store_api


def init(token, user):
    pairs = {"auth_date": str(int(time.time())), "query_id": "AAE", "user": json.dumps(user, separators=(",", ":"))}
    chk = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    sec = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(sec, chk.encode(), hashlib.sha256).hexdigest()
    return urlencode(pairs)


@pytest.mark.anyio
async def test_store_v2_full():
    await db.init()
    seed = int(time.time() * 1000) % 700000 + 400000
    tok = f"{seed}:AAH_v2_test_token_abcdefghijklmnop"
    seller, buyer, other = seed + 1, seed + 2, seed + 3
    uname = f"v2shop_{seed}"
    async with db.Session() as s:
        s.add(db.Bot(id=seed, owner_id=seller, username=uname, name="متجر v2", token=crypto.enc(tok), template="megastore", status="active"))
        await s.commit()
    app = web.Application()
    store_api.setup_routes(app)
    c = TestClient(TestServer(app))
    await c.start_server()
    H = lambda uid, name="U": {"X-Telegram-Init-Data": init(tok, {"id": uid, "first_name": name, "language_code": "ar"})}
    B = f"/api/v2/{uname}"
    try:
        # الإقلاع
        j = await (await c.get(f"{B}/boot", headers=H(buyer))).json()
        assert j["ok"] and j["user"]["role"] == "buyer" and j["store"]["faq"] == [] and len(j["currencies"]) > 30
        codes = {x["code"] for x in j["currencies"]}
        assert {"USD", "EUR", "RUB", "TRY", "IRR", "INR", "USDT", "TON", "STARS", "SYP", "IQD", "SAR", "EGP"} <= codes
        # تفضيلات: اللغة تُحفظ في سجل العضو (نفسها التي يستخدمها البوت) والعملة
        assert (await (await c.post(f"{B}/prefs", headers=H(buyer), json={"lang": "en", "currency": "TRY"})).json())["ok"]
        j = await (await c.get(f"{B}/boot", headers=H(buyer))).json()
        assert j["user"]["lang"] == "en" and j["user"]["currency"] == "TRY"
        async with db.Session() as s:
            assert (await s.get(db.BUser, (seed, buyer))).lang == "en"
        # الكتالوج الموحّد للمتجر الشامل
        cat = await (await c.get(f"{B}/catalog?lang=ar", headers=H(buyer))).json()
        secs = {x["id"] for x in cat["sections"]}
        assert {"digital", "smm", "sms", "tgstars"} <= secs and len(cat["products"]) > 20
        smm = next(p for p in cat["products"] if p["sec"] == "smm")
        # تسعير
        q = await (await c.post(f"{B}/quote", headers=H(buyer), json={"product_id": smm["id"], "quantity": smm["min"]})).json()
        assert q["ok"] and q["total_usd"] > 0
        # شراء بلا رصيد = رفض
        r = await c.post(f"{B}/order", headers=H(buyer), json={"product_id": smm["id"], "quantity": smm["min"], "target": "https://x.com/a", "idempotency_key": f"k{seed}a"})
        assert r.status == 402
        await ledger.credit_user(seed, buyer, 50, "deposit")
        await ledger.credit_seller(seller, 50, "deposit")
        r = await c.post(f"{B}/order", headers=H(buyer), json={"product_id": smm["id"], "quantity": smm["min"], "target": "https://x.com/a", "idempotency_key": f"k{seed}b"})
        assert r.status == 200
        orders = (await (await c.get(f"{B}/orders", headers=H(buyer))).json())["data"]
        assert orders and orders[0]["tpl_key"] == "smm"
        # المحفظة: باقات ومبلغ مخصص وطرق دفع
        w = await (await c.get(f"{B}/wallet", headers=H(buyer))).json()
        assert w["ok"] and w["packages"] and w["stars_enabled"] and w["transactions"]
        r = await c.post(f"{B}/deposit/stars", headers=H(buyer), json={"usd": 0.01})
        assert r.status == 400  # أقل من الحد
        # الزبون لا يدخل لوحة البائع ولا المدير
        assert (await c.get(f"{B}/seller/overview", headers=H(buyer))).status == 403
        assert (await c.get(f"{B}/admin/overview", headers=H(buyer))).status == 403

        # ── البائع ──
        ov = await (await c.get(f"{B}/seller/overview", headers=H(seller))).json()
        assert ov["ok"] and ov["month"]["orders"] >= 1 and ov["maker_balance_usd"] < 50 and len(ov["series"]) == 14
        so = await (await c.get(f"{B}/seller/orders", headers=H(seller))).json()
        assert so["orders"][0]["cost_usd"] > 0
        # الأسعار: الهامش والإخفاء والأرضية
        pr = await (await c.get(f"{B}/seller/pricing", headers=H(seller))).json()
        assert set(pr["margins"]) >= {"smm", "sms", "digital", "tgstars"}
        assert all(x["price_usd"] + 1e-6 >= x["cost_usd"] for x in pr["items"])
        pid = pr["items"][0]["id"]
        await c.post(f"{B}/seller/pricing", headers=H(seller), json={"sec": pr["items"][0]["sec"], "product_id": pid, "hidden": True})
        cat2 = await (await c.get(f"{B}/catalog", headers=H(buyer))).json()
        assert pid not in {p["id"] for p in cat2["products"]}
        # الدفع: طريقة يدوية + باقات + مبلغ مخصص
        pay = await (await c.post(f"{B}/seller/payments", headers=H(seller), json={
            "methods": [{"name": "شام كاش", "account": "0999", "instructions": "حوّل ثم أرسل", "currency": "SYP", "min": 1, "max": 500}],
            "packages": [3, 7, 15], "custom_min": 2, "custom_max": 300, "stars_enabled": True})).json()
        assert pay["packages"] == [3.0, 7.0, 15.0] and pay["methods"][0]["currency"] == "SYP"
        w = await (await c.get(f"{B}/wallet", headers=H(buyer))).json()
        mid = w["methods"][0]["id"]
        # إيصال يدوي بعملة الطريقة
        rr = await (await c.post(f"{B}/deposit/receipt", headers=H(buyer), json={"method_id": mid, "amount": "145000", "ref": "TX-1"})).json()
        assert rr["ok"]
        rc = await (await c.get(f"{B}/seller/receipts", headers=H(seller))).json()
        assert rc["receipts"] and rc["receipts"][0]["currency"] == "SYP"
        bal0 = await ledger.get_user_balance_usd(seed, buyer)
        await c.post(f"{B}/seller/receipts", headers=H(seller), json={"receipt_id": rc["receipts"][0]["id"], "action": "approve", "amount_usd": 10})
        assert abs(await ledger.get_user_balance_usd(seed, buyer) - bal0 - 10) < 1e-6
        # المتجر: الدعم والأسئلة الاختيارية والصفحات
        st = await (await c.post(f"{B}/seller/store", headers=H(seller), json={
            "name": "نيترو", "accent": "#10b981", "support": {"username": "@help_me", "whatsapp": "+963 999", "links": [{"label": "موقعنا", "url": "https://x.y"}]},
            "faq_enabled": True, "faq": [{"q": "متى يصل الطلب؟", "a": "خلال دقائق"}], "terms": "الشروط…", "help": "المساعدة…"})).json()
        assert st["store"]["support"]["username"] == "help_me" and st["store"]["faq"]
        b2 = await (await c.get(f"{B}/boot", headers=H(buyer))).json()
        assert b2["store"]["name"] == "نيترو" and b2["store"]["faq"] and b2["store"]["terms"]
        # تسويق
        mk = await (await c.post(f"{B}/seller/marketing", headers=H(seller), json={"action": "coupon_save", "code": "vip10", "type": "percent", "value": 10})).json()
        assert any(x["code"] == "VIP10" for x in mk["coupons"])
        # زبائن: إضافة رصيد
        cu = await (await c.post(f"{B}/seller/customers", headers=H(seller), json={"uid": buyer, "action": "credit", "amount_usd": 1})).json()
        assert cu["ok"]
        cl = await (await c.get(f"{B}/seller/customers", headers=H(seller))).json()
        assert any(x["uid"] == buyer for x in cl["customers"])
        # بائع آخر لا يرى لوحة هذا المتجر
        assert (await c.get(f"{B}/seller/overview", headers=H(other))).status == 403

        # ── المدير ──
        admin = config.ADMIN_ID
        ao = await (await c.get(f"{B}/admin/overview", headers=H(admin))).json()
        assert ao["ok"] and "sellers_balance_usd" in ao
        ac = await (await c.post(f"{B}/admin/catalog", headers=H(admin), json={"sec": "smm", "item_id": "ig_likes_hq", "ps": "777", "cost": 0.2})).json()
        assert next(x for x in ac["catalog"]["smm"] if x["id"] == "ig_likes_hq")["ps"] == "777"
        ap = await (await c.post(f"{B}/admin/providers", headers=H(admin), json={"sec": "smm", "action": "add", "name": "P1", "api_url": "https://p.example/api/v2", "api_key": "secretkey1234"})).json()
        assert ap["providers"]["smm"][-1]["key_hint"] == "…1234" and "api_key" not in ap["providers"]["smm"][-1]
        await c.post(f"{B}/admin/providers", headers=H(admin), json={"sec": "smm", "action": "delete", "index": len(ap["providers"]["smm"]) - 1})
        asl = await (await c.get(f"{B}/admin/sellers", headers=H(admin))).json()
        assert any(x["bot_id"] == seed for x in asl["bots"])
        await db.kv_set(0, "smm:catalog_map", {})
    finally:
        await c.close()
