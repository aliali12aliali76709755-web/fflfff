"""الاشتراكات + العروض المؤقتة + الوكلاء + استرجاع الزبائن + الأرباح + كشف الاحتيال."""
import asyncio
import datetime as dt
import time

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from forge import config, crypto, db
from forge.modules import insights, ledger, perks, subs
from forge.web import store_api

from test_store_v2 import init


@pytest.mark.anyio
async def test_growth_full():  # noqa: C901
    await db.init()
    seed = int(time.time() * 1000) % 500000 + 2100000
    tok = f"{seed}:AAH_growth_token_abcdefghijklmnop"
    seller, buyer, agent = seed + 1, seed + 2, seed + 3
    uname = f"grow_{seed}"
    async with db.Session() as s:
        s.add(db.Bot(id=seed, owner_id=seller, username=uname, name="متجر", token=crypto.enc(tok), template="megastore", status="active"))
        for u in (buyer, agent):
            s.add(db.BUser(bot_id=seed, user_id=u, name=f"U{u}", kind="private"))
        await s.commit()
    app = web.Application()
    store_api.setup_routes(app)
    c = TestClient(TestServer(app))
    await c.start_server()
    H = lambda uid: {"X-Telegram-Init-Data": init(tok, {"id": uid, "first_name": "U", "language_code": "ar"})}
    B = f"/api/v2/{uname}"
    try:
        await ledger.credit_user(seed, buyer, 50.0, "deposit")
        await ledger.credit_user(seed, agent, 50.0, "deposit")
        await ledger.credit_seller(seller, 30.0, "deposit")

        # ── الاشتراكات ──
        assert not (await subs.conf())["on"], "مطفأة افتراضياً في الاختبارات"
        await subs.set_conf(on=True, price=7.5, days=30, trial_days=3)
        assert await subs.needs(seller, "megastore") and not await subs.needs(seller, "quran"), "الأنواع التجارية فقط"
        assert not await subs.needs(config.ADMIN_ID or 8625825633, "megastore"), "المدير معفى"
        j = await (await c.post(f"{B}/order", headers=H(buyer), json={"product_id": "ig_likes_hq", "quantity": 1000, "target": "https://instagram.com/p/1"})).json()
        assert not j["ok"] and j["error"] == "service_unavailable", "متجر بلا اشتراك لا يبيع"
        assert await ledger.get_user_balance_usd(seed, buyer) == 50.0, "رصيد الزبون محفوظ"
        ok, _ = await subs.start_trial(seller)
        assert ok and await subs.active(seller)
        ok, _ = await subs.start_trial(seller)
        assert not ok, "التجربة مرة واحدة"
        bal0 = await ledger.get_seller_balance_usd(seller)
        r = await asyncio.gather(subs.buy(seller), subs.buy(seller))
        assert all(x[0] for x in r)
        st = await subs.state(seller)
        assert abs((await ledger.get_seller_balance_usd(seller)) - (bal0 - 15.0)) < 1e-6 and st["paid"] == 2
        assert st["until"] > time.time() + 60 * 86400, "شراءان متزامنان = فترتان مدفوعتان بلا ضياع"
        poor = seed + 9
        ok, msg = await subs.buy(poor)
        assert not ok and "لا يكفي" in msg
        # انتهاء + تجديد تلقائي من الرصيد
        st["until"] = time.time() - 10
        await db.kv_set(0, f"sub:{seller}", st)
        assert not await subs.store_open(seed, seller)
        subs._LAST_SWEEP = 0
        notes = []

        async def note(uid, txt):
            notes.append((uid, txt))
        out = await subs.sweep(note)
        assert out["renewed"] == 1 and await subs.active(seller) and notes and "جُدّد" in notes[0][1]
        # بلا رصيد ولا تجديد → إشعار توقف
        st = await subs.state(seller)
        st.update(until=time.time() - 10, auto=False, warned=0)
        await db.kv_set(0, f"sub:{seller}", st)
        subs._LAST_SWEEP = 0
        notes.clear()
        out = await subs.sweep(note)
        assert out["expired"] == 1 and "انتهى" in notes[0][1]
        await subs.grant(seller, 30)
        assert await subs.active(seller)
        j = await (await c.get(f"{B}/admin/subs", headers=H(config.ADMIN_ID))).json()
        assert j["ok"] and any(x["uid"] == seller and x["active"] for x in j["sellers"]) and j["conf"]["price"] == 7.5
        assert not (await (await c.get(f"{B}/admin/subs", headers=H(seller))).json()).get("ok"), "البائع لا يرى إعدادات الاشتراك"

        # ── العروض المؤقتة ──
        q0 = await (await c.post(f"{B}/quote", headers=H(buyer), json={"product_id": "ig_likes_hq", "quantity": 1000})).json()
        assert q0["perk_usd"] == 0
        j = await (await c.post(f"{B}/seller/marketing", headers=H(seller), json={"action": "sale_create", "title": "جمعة", "pct": 20, "hours": 2,
                                                                                 "scope": "sec", "target": "smm"})).json()
        assert j["ok"] and len(j["sales"]) == 1 and j["sales"][0]["ends"] > time.time() + 7000
        q1 = await (await c.post(f"{B}/quote", headers=H(buyer), json={"product_id": "ig_likes_hq", "quantity": 1000})).json()
        assert q1["total_usd"] < q0["total_usd"] and q1["total_usd"] >= q0["total_usd"] * 0.8 - 1e-6 and "جمعة" in q1["perk_label"], q1
        qd = await (await c.post(f"{B}/quote", headers=H(buyer), json={"product_id": "iq_tg", "quantity": 1})).json()
        assert qd["perk_usd"] == 0, "العرض على قسم التفاعل فقط"
        boot = await (await c.get(f"{B}/boot", headers=H(buyer))).json()
        assert boot["perks"]["sales"][0]["pct"] == 20 and boot["perks"]["agent"] == 0
        # الأرضية: خصم 90% لا ينزل تحت سعر المنصة
        await (await c.post(f"{B}/seller/marketing", headers=H(seller), json={"action": "sale_create", "title": "مجنون", "pct": 90, "hours": 1, "scope": "all"})).json()
        from forge.web import miniapp_api as v1
        async with db.Session() as s:
            bot = await s.get(db.Bot, seed)
        qq = await v1._quote_item(bot, "ig_likes_hq", 1000, uid=buyer)
        assert qq.price_usd >= qq.platform_cost_usd + 0.0099 and qq.perk_usd > 0, "البائع لا يخسر أبداً"
        b0, sb0 = await ledger.get_user_balance_usd(seed, buyer), await ledger.get_seller_balance_usd(seller)
        j = await (await c.post(f"{B}/order", headers=H(buyer), json={"product_id": "ig_likes_hq", "quantity": 1000, "target": "https://instagram.com/p/2"})).json()
        assert j["ok"], j
        paid = b0 - await ledger.get_user_balance_usd(seed, buyer)
        assert abs(paid - qq.price_usd) < 0.0001, "الزبون دفع سعر العرض المحسوب في السيرفر"
        assert abs((sb0 - await ledger.get_seller_balance_usd(seller)) - qq.platform_cost_usd) < 0.0001
        for sl in await perks.active_sales(seed):
            await (await c.post(f"{B}/seller/marketing", headers=H(seller), json={"action": "sale_end", "id": sl["id"]})).json()
        assert await perks.active_sales(seed) == []

        # ── الوكلاء ──
        j = await (await c.post(f"{B}/seller/customers", headers=H(seller), json={"uid": agent, "action": "agent", "pct": 15})).json()
        assert j["ok"] and j["agent_pct"] == 15
        j = await (await c.get(f"{B}/seller/customers", headers=H(seller))).json()
        assert next(x for x in j["customers"] if x["uid"] == agent)["agent_pct"] == 15
        qa = await (await c.post(f"{B}/quote", headers=H(agent), json={"product_id": "ig_likes_hq", "quantity": 1000})).json()
        qb = await (await c.post(f"{B}/quote", headers=H(buyer), json={"product_id": "ig_likes_hq", "quantity": 1000})).json()
        assert qa["total_usd"] < qb["total_usd"] and "الوكيل" in qa["perk_label"]
        j = await (await c.post(f"{B}/seller/customers", headers=H(buyer), json={"uid": buyer, "action": "agent", "pct": 50})).json()
        assert not j.get("ok"), "الزبون لا يجعل نفسه وكيلاً"
        assert await perks.agent_pct(seed, buyer) == 0
        # عرض 10% + وكيل 15% = الأعلى فقط (لا تُجمع)
        await perks.create_sale(seed, title="x", scope="all", target="", pct=10, hours=1)
        pct, label = await perks.best(seed, agent, "ig_likes_hq", "smm")
        assert pct == 15 and "الوكيل" in label
        for sl in await perks.active_sales(seed):
            await perks.end_sale(seed, sl["id"])

        # ── إعادة الطلب: الطلب يحمل رقم المنتج ──
        j = await (await c.get(f"{B}/orders", headers=H(buyer))).json()
        assert j["orders"][0]["product_id"] == "ig_likes_hq" and j["orders"][0]["target"]

        # ── الزبائن المتوقفون ──
        old = db.now() - dt.timedelta(days=20)
        async with db.Session() as s:
            s.add(db.ServiceOrder(order_id=f"old_{seed}", bot_id=seed, user_id=agent, tpl_key="smm", service_id="ig_likes_hq",
                                  service_name="x", target="t", quantity=1, price_user_usd=4.0, status="completed", created=old))
            await s.commit()
        ina = await perks.inactive_customers(seed, 14)
        assert [x["uid"] for x in ina] == [agent] and ina[0]["days"] >= 19

        class FakeBot:
            sent = []

            async def send_message(self, uid, text, **kw):
                self.sent.append((uid, text))
        fb = FakeBot()
        ok, msg = await perks.send_winback(seed, agent, fb)
        assert ok and fb.sent and "BACK" in fb.sent[0][1]
        from forge.modules import promo
        import re
        code = re.search(r"BACK[A-Z0-9]+", msg).group(0)
        assert code in await promo.get_bot_promos(seed)
        assert await perks.inactive_customers(seed, 14) == [], "لا يتكرر التنبيه عن نفس الزبون"
        st = await perks.day_stats(seed, db.now() - dt.timedelta(hours=1))
        assert st["orders"] >= 1 and st["sales"] > 0 and st["top"]
        j = await (await c.post(f"{B}/seller/marketing", headers=H(seller), json={"action": "reports", "daily": False, "wb_pct": 12})).json()
        assert j["ok"] and j["reports"]["daily"] is False and j["reports"]["wb_pct"] == 12

        # ── الأرباح وكشف الاحتيال ──
        p = await insights.profits(30)
        assert p["orders"] >= 1 and p["intake"] > 0 and p["subs"] >= 15.0 and p["total"] >= p["profit"]
        assert any(x["name"] == f"@{uname}" for x in p["by_store"]) and any(x["name"] == "smm" for x in p["by_section"])
        async with db.Session() as s:
            for i in range(4):
                s.add(db.ServiceOrder(order_id=f"rf_{seed}_{i}", bot_id=seed, user_id=buyer, tpl_key="smm", service_id="x", service_name="x",
                                      target="t", quantity=1, price_user_usd=1, status="refunded"))
            s.add(db.Report(factory_id=0, user_id=buyer, kind="complaint", text=f"@{uname} [{seed}] owner={seller}\nنصب"))
            await s.commit()
        r = await insights.risk(30)
        assert any(x["uid"] == buyer and x["refunds"] >= 4 for x in r["customers"])
        assert any(x["bot_id"] == seed and x["complaints"] == 1 for x in r["stores"])
        j = await (await c.get(f"{B}/admin/profits?days=7", headers=H(config.ADMIN_ID))).json()
        assert j["ok"] and j["days"] == 7
        j = await (await c.get(f"{B}/admin/risk", headers=H(config.ADMIN_ID))).json()
        assert j["ok"] and j["customers"]
        j = await (await c.get(f"{B}/admin/profits", headers=H(seller))).json()
        assert not j.get("ok"), "البائع لا يرى أرباح المنصة"
    finally:
        await subs.set_conf(on=False)
        await c.close()
