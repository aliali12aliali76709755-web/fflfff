"""مُجمّع مواقع التفاعل: سحب الخدمات، أرخص سعر، تحويل العملة، التبديل عند الفشل، متابعة الحالة والاسترجاع، والاستيراد."""
import json
import time

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from forge import crypto, db
from forge.modules import currency, ledger, smm_agg
from forge.modules.providers.smm import SMMManager
from forge.web import store_api

from test_store_v2 import init

PANELS = {
    # موقع A: الأرخص للمتابعين، لكنه يرفض الطلبات (رصيد غير كافٍ) → يجب التحويل للتالي
    "pa": {"cur": "USD", "fail_add": True, "services": [
        {"service": 11, "name": "Instagram Followers [Real] [Refill 30D]", "category": "Instagram", "rate": "0.90", "min": 10, "max": 50000, "type": "Default"},
        {"service": 12, "name": "Instagram Followers USA", "category": "Instagram", "rate": "0.10", "min": 10, "max": 50000, "type": "Default"},
        {"service": 13, "name": "Instagram Custom Comments", "category": "Instagram", "rate": "0.05", "min": 10, "max": 500, "type": "Custom Comments"},
        {"service": 14, "name": "TikTok Views | Instant", "category": "TikTok", "rate": "0.020", "min": 100, "max": 1000000, "type": "Default"},
    ]},
    # موقع B: أغلى بقليل (ضمن 125%) ويقبل
    "pb": {"cur": "USD", "services": [
        {"service": "201", "name": "Instagram Followers - Real HQ - R30", "category": "IG", "rate": "1.05", "min": 20, "max": 20000, "type": "Default"},
        {"service": "202", "name": "Telegram Post Views [Last 1]", "category": "Telegram", "rate": "0.010", "min": 50, "max": 100000, "type": "Default"},
        {"service": "203", "name": "TikTok Views [Fast]", "category": "TikTok", "rate": "0.024", "min": 100, "max": 1000000, "type": "Default"},
    ]},
    # موقع C: بالروبية الهندية (يُحوّل للدولار) وأغلى بكثير للمتابعين (>125% فلا يُستعمل بديلاً)
    "pc": {"cur": "INR", "services": [
        {"service": 7, "name": "Instagram Followers Real Refill", "category": "Instagram", "rate": "180", "min": 10, "max": 10000, "type": "Default"},
        {"service": 8, "name": "Telegram Channel Members", "category": "Telegram", "rate": "50", "min": 10, "max": 10000, "type": "Default"},
    ]},
}
STATUS = {}      # (panel, order) → {"status":..., "remains":...}
ORDERS = []


def fake_panel_app():
    async def h(req):
        name = req.match_info["p"]
        d = await req.post()
        p = PANELS[name]
        if d.get("key") != f"key_{name}_0123456789abcdef0123":
            return web.json_response({"error": "Invalid API key"})
        act = d.get("action")
        if act == "services":
            return web.json_response(p["services"])
        if act == "balance":
            return web.json_response({"balance": "12.5", "currency": p["cur"]})
        if act == "add":
            if p.get("fail_add"):
                return web.json_response({"error": "Not enough funds on balance"})
            oid = 9000 + len(ORDERS)
            ORDERS.append((name, d.get("service"), d.get("quantity"), oid))
            return web.json_response({"order": oid})
        if act == "status":
            ids = (d.get("orders") or d.get("order") or "").split(",")
            return web.json_response({i: STATUS.get((name, i), {"status": "In progress", "remains": "0"}) for i in ids})
        return web.json_response({"error": "bad action"})
    app = web.Application()
    app.router.add_post("/{p}/api/v2", h)
    return app


@pytest.mark.anyio
async def test_smm_aggregator_full():  # noqa: C901
    await db.init()
    panel = TestServer(fake_panel_app())
    await panel.start_server()
    base = f"http://127.0.0.1:{panel.port}"
    old_rates = dict(currency._RATES_CACHE), currency._LAST_RATES_FETCH
    currency._RATES_CACHE.update({"INR": 90.0, "USD": 1.0})
    currency._LAST_RATES_FETCH = time.time()
    try:
        # ── الاستيراد من نص حر (مثل رسالة المدير) ──
        txt = "peakerr.com | 66030e995303a8cac240aeec5cf44649\nhttps://www.smmkings.com\n07d96fe4cc42fc8d277630474dd359b9\n# تعليق\nكلام بلا مفتاح"
        got = smm_agg.parse_providers_text(txt)
        assert [g["api_url"] for g in got] == ["https://peakerr.com/api/v2", "https://smmkings.com/api/v2"]
        assert got[1]["api_key"] == "07d96fe4cc42fc8d277630474dd359b9"
        # ملف seed_providers.txt المرفق بالمشروع يحتوي المواقع الـ 19
        from forge import config
        seeded = smm_agg.parse_providers_text(smm_agg.split_seed((config.ROOT / "seed_providers.txt").read_text(encoding="utf-8"))[0])
        assert len(seeded) == 19 and all(p["api_url"].endswith("/api/v2") for p in seeded)

        # ── ربط المواقع المحاكية ──
        await db.kv_set(0, "smm:providers", [{"name": n, "api_url": f"{base}/{n}/api/v2", "api_key": f"key_{n}_0123456789abcdef0123", "on": True}
                                             for n in PANELS] + [{"name": "dead", "api_url": "http://127.0.0.1:1/api/v2", "api_key": "x" * 32, "on": True}])
        smm_agg.reset_memory()
        r = await smm_agg.refresh()
        assert r["ok"] and r["items"] >= 4, r
        st = smm_agg.status()
        assert st["provs"]["pc"]["cur"] == "INR" and st["provs"]["pc"]["ok"] and not st["provs"]["dead"]["ok"]
        items = smm_agg.items_now()
        names = [i["name_ar"] for i in items]
        assert not any("USA" in i["gk"] for i in items)
        ig = next(i for i in items if i["platform"] == "instagram" and i["category"] == "followers")
        # الأرخص: موقع A بـ 0.90، ثم B بـ 1.05، ثم C (180 روبية = 2$)
        assert ig["rate_per_1k"] == 0.9 and [o["p"] for o in ig["offers"]] == ["pa", "pb", "pc"] and ig["n"] == 3
        assert abs(ig["offers"][2]["rate"] - 2.0) < 0.001, "تحويل الروبية للدولار"
        assert "متابعين انستغرام" in ig["name_ar"] and "ضمان" in ig["name_ar"]
        tt = next(i for i in items if i["platform"] == "tiktok" and i["category"] == "views")
        assert tt["rate_per_1k"] == 0.02 and tt["n"] == 2
        tgm = next(i for i in items if i["platform"] == "telegram" and i["category"] == "followers")
        assert "أعضاء تلغرام" in tgm["name_ar"] and abs(tgm["rate_per_1k"] - 50 / 90) < 0.001
        assert len(set(names)) == len(names)
        # المعرّف ثابت بين التحديثات (لا تضيع الطلبات والتخصيصات)
        ig_id = ig["id"]
        await smm_agg.refresh()
        assert smm_agg.get_item(ig_id) is not None
        # البديل الأغلى من 125% لا يُستخدم
        assert [o["p"] for o in smm_agg.offers_for(ig_id, 1000)] == ["pa", "pb"]

        # ── متجر حقيقي: الكتالوج والطلب عبر التطبيق المصغّر ──
        seed = int(time.time() * 1000) % 600000 + 1200000
        tok = f"{seed}:AAH_agg_test_token_abcdefghijklmnop"
        seller, buyer = seed + 1, seed + 2
        uname = f"aggshop_{seed}"
        async with db.Session() as s:
            s.add(db.Bot(id=seed, owner_id=seller, username=uname, name="متجر", token=crypto.enc(tok), template="smm", status="active"))
            await s.commit()
        store_api._CAT_CACHE.clear()
        cat = await SMMManager.get_services_catalog(seed)
        svc = next(x for x in cat if x["id"] == ig_id)
        assert "offers" not in svc and svc["price_per_1k_usd"] > svc["base_cost_per_1k"] == 0.9
        app = web.Application()
        store_api.setup_routes(app)
        c = TestClient(TestServer(app))
        await c.start_server()
        H = {"X-Telegram-Init-Data": init(tok, {"id": buyer, "first_name": "B", "language_code": "ar"})}
        B = f"/api/v2/{uname}"
        try:
            j = await (await c.get(f"{B}/catalog?lang=ar", headers=H)).json()
            pids = {p["id"] for p in j["products"]}
            assert ig_id in pids and "ig_followers_fast" not in pids, "الكتالوج من المواقع الحقيقية بدل التجريبي"
            assert all(x["id"].startswith("smm:") for x in j["categories"] if x["sec"] == "smm")
            await ledger.credit_user(seed, buyer, 20.0, "deposit")
            await ledger.credit_seller(seller, 20.0, "deposit")
            j = await (await c.post(f"{B}/order", headers=H, json={"product_id": ig_id, "quantity": 1000,
                                                                   "target": "https://instagram.com/someone"})).json()
            assert j["ok"], j
            assert ORDERS and ORDERS[-1][0] == "pb" and ORDERS[-1][1] == "201", "فشل الأرخص → تحويل تلقائي للتالي"
            async with db.Session() as s:
                from sqlalchemy import select
                o = (await s.execute(select(db.ServiceOrder).where(db.ServiceOrder.bot_id == seed))).scalars().first()
            assert o.provider_name == "pb" and o.status == "processing" and abs(float(o.cost_provider_usd) - 1.05) < 1e-6
            b_after = await ledger.get_user_balance_usd(seed, buyer)
            s_after = await ledger.get_seller_balance_usd(seller)

            # ── متابعة الحالة: جزئي → استرجاع النسبة الناقصة للطرفين ──
            STATUS[("pb", o.provider_order_id)] = {"status": "Partial", "remains": "250"}
            notes = []

            async def note(order, kind):
                notes.append(kind)
            stt = await smm_agg.track_orders(note)
            assert stt["partial"] == 1 and notes == ["partial"]
            b2, s2 = await ledger.get_user_balance_usd(seed, buyer), await ledger.get_seller_balance_usd(seller)
            assert abs((b2 - b_after) - (20 - b_after) * 0.25) < 0.01 and s2 > s_after
            stt = await smm_agg.track_orders(note)
            assert stt["partial"] == 0, "لا يتكرر الاسترجاع"

            # طلب ثانٍ يُلغى من الموقع → استرجاع كامل
            j = await (await c.post(f"{B}/order", headers=H, json={"product_id": tt["id"], "quantity": 1000,
                                                                   "target": "https://tiktok.com/@x/video/1"})).json()
            assert j["ok"], j
            assert ORDERS[-1][0] == "pb" and ORDERS[-1][1] == "203"
            b3 = await ledger.get_user_balance_usd(seed, buyer)
            STATUS[("pb", str(ORDERS[-1][3]))] = {"status": "Canceled", "remains": "1000"}
            stt = await smm_agg.track_orders(note)
            assert stt["refund"] == 1 and await ledger.get_user_balance_usd(seed, buyer) > b3
            assert abs(await ledger.get_user_balance_usd(seed, buyer) - b2) < 0.01

            # ── لوحة المدير ──
            import forge.config as cfg
            adm = cfg.ADMIN_ID
            HA = {"X-Telegram-Init-Data": init(tok, {"id": adm, "first_name": "A", "language_code": "ar"})}
            j = await (await c.get(f"{B}/admin/smm_sync", headers=HA)).json()
            assert j["ok"] and j["status"]["items"] >= 4 and j["items"][0]["rate"] > 0, j
            j = await (await c.post(f"{B}/admin/smm_sync", headers=HA, json={"action": "import", "text": "newpanel.io | " + "ab" * 16})).json()
            assert j["ok"] and j["added"] == 1
            j = await (await c.get(f"{B}/admin/smm_sync", headers=H)).json()
            assert not j.get("ok"), "الزبون لا يصل لإعدادات المزودين"
        finally:
            await c.close()
    finally:
        await db.kv_set(0, "smm:providers", [])
        await db.kv_set(0, smm_agg.KEY, {"ts": 0, "items": [], "provs": {}})
        smm_agg.reset_memory()
        await smm_agg.load()
        store_api._CAT_CACHE.clear()
        currency._RATES_CACHE.clear()
        currency._RATES_CACHE.update(old_rates[0])
        currency._LAST_RATES_FETCH = old_rates[1]
        await panel.close()
    assert json.dumps(smm_agg.status())
