"""الموافقة اليدوية: طلبات التفاعل والأرقام تبقى عند المدير حتى يوافق، وتظهر للزبون «قيد التنفيذ»."""
import asyncio
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from harness import ADMIN, MAKER, MID, Check, boot, make_bot

B_SMS, B_MEGA = 290000001, 290000002


def init(token, user):
    pairs = {"auth_date": str(int(time.time())), "query_id": "AAE", "user": json.dumps(user, separators=(",", ":"))}
    chk = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    sec = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(sec, chk.encode(), hashlib.sha256).hexdigest()
    return urlencode(pairs)


async def order_of(bot_id, uid, n=0):
    from sqlalchemy import select

    from forge import db
    async with db.Session() as s:
        rows = (await s.execute(select(db.ServiceOrder).where(db.ServiceOrder.bot_id == bot_id, db.ServiceOrder.user_id == uid)
                                .order_by(db.ServiceOrder.id.desc()))).scalars().all()
    return rows[n] if len(rows) > n else None


async def main():  # noqa: C901
    tg, mgr = await boot()
    from aiohttp import web
    from aiohttp.test_utils import TestClient, TestServer

    from forge import db
    from forge.modules import hold, ledger
    from forge.modules.providers.smm import SMMManager
    from forge.web import store_api
    ck = Check()
    adm = tg.user(ADMIN, "Admin")
    ali, sara = tg.user(500, "Ali", username="ali_k"), tg.user(600, "Sara")
    for u in (adm, ali, sara):
        await tg.say(MAKER, u, "/start")
    from forge import plat as platform
    (await platform.get(0))["promo"]["when"] = "idle"
    ck.ok(not await hold.enabled("smm"), "في بيئة الاختبار الموافقة اليدوية مطفأة افتراضياً (في الإنتاج مفعّلة)")
    await hold.set_enabled("smm", True)
    await hold.set_enabled("sms", True)
    ck.ok(await hold.enabled("smm") and await hold.enabled("sms"), "تفعيل الموافقة اليدوية للقسمين")

    print("— أرقام التفعيل من البوت —")
    T = await make_bot(tg, ali, B_SMS, "sms")
    await ledger.credit_user(B_SMS, 600, 20.0, "deposit")
    await ledger.credit_seller(500, 20.0, "deposit")
    b0, s0 = await ledger.get_user_balance_usd(B_SMS, 600), await ledger.get_seller_balance_usd(500)
    await tg.say(T, sara, "/start")
    tg.sent_before = len(tg.out(MID))
    t = await tg.click(T, sara, "t:do_rent:iq:tg")
    ck.ok("قيد التنفيذ" in t and "انتظار" not in t and "موقوف" not in t and "معلّق" not in t, "الزبون يرى «قيد التنفيذ» فقط")
    o = await order_of(B_SMS, 600)
    ck.ok(o and o.status == "processing" and o.provider_name == hold.HOLD and not o.provider_order_id, "الطلب محفوظ ولم يُرسل للموقع")
    b1, s1 = await ledger.get_user_balance_usd(B_SMS, 600), await ledger.get_seller_balance_usd(500)
    ck.ok(b1 < b0 and s1 < s0, "المبلغ مخصوم من الزبون والبائع (لا يُصرف مرتين)")
    await asyncio.sleep(0.3)
    await tg.settle()
    note = [m["p"] for m in tg.out(MID)[tg.sent_before:] if str(m["p"].get("chat_id")) == str(ADMIN)]
    ck.ok(note and "بانتظار موافقتك" in note[-1].get("text", ""), "إشعار للمدير في بوت الصانع")
    t = await tg.click(T, sara, f"t:check_sms:{o.order_id}")
    o2 = await order_of(B_SMS, 600)
    ck.ok(o2.status == "processing" and o2.provider_name == hold.HOLD, "فحص الكود قبل الموافقة لا يكسر شيئاً")
    # لوحة الموافقات في الصانع
    t = await tg.click(MAKER, adm, "m:hold:list")
    ck.ok("بانتظار موافقتك: 1" in t and "المطلوب شحنه" in t, "قائمة المعلّقات مع المبلغ المطلوب شحنه")
    n0 = len(tg.out(MID))
    await tg.click(MAKER, sara, "m:hold:list")
    ck.ok(not any("بانتظار موافقتك" in (m["p"].get("text") or "") for m in tg.out(MID)[n0:]), "غير المدير لا يرى المعلّقات")
    # موافقة مزدوجة متزامنة → تنفيذ واحد فقط
    r = await asyncio.gather(hold.approve(o.id, notify=mgr._order_note), hold.approve(o.id, notify=mgr._order_note))
    ck.ok(sum(1 for x in r if x[0]) == 1, "ضغطتان متزامنتان على «موافقة» = رقم واحد فقط")
    o3 = await order_of(B_SMS, 600)
    ck.ok(o3.status == "waiting_sms" and o3.target.startswith("+") and o3.provider_order_id and not hold.is_held(o3.provider_name),
          "بعد الموافقة: الرقم محجوز من الموقع")
    await tg.settle()
    msgs = [m["p"] for m in tg.out(B_SMS) if str(m["p"].get("chat_id")) == "600"]
    ck.ok(any(o3.target in (m.get("text") or "") for m in msgs), "الرقم يصل للزبون برسالة")
    btns = tg.buttons(B_SMS)
    ck.ok(any(b.get("callback_data") == f"t:check_sms:{o3.order_id}" for b in btns), "مع زر فحص الكود")
    ck.ok(await ledger.get_user_balance_usd(B_SMS, 600) == b1, "الموافقة لا تخصم مرة ثانية")
    ok, msg = await hold.reject(o.id)
    ck.ok(not ok, "لا يمكن رفض طلب نُفّذ")

    print("— إلغاء الزبون قبل الموافقة —")
    await tg.click(T, sara, "t:do_rent:eg:wa")
    o = await order_of(B_SMS, 600)
    bh = await ledger.get_user_balance_usd(B_SMS, 600)
    t = await tg.click(T, sara, f"t:cancel_refund:{o.order_id}")
    ck.ok("استرجاع" in t and await ledger.get_user_balance_usd(B_SMS, 600) > bh, "الزبون يلغي ويسترجع")
    ok, msg = await hold.approve(o.id)
    ck.ok(not ok and "ليس معلّقاً" in msg, "لا يمكن الموافقة على طلب ألغاه الزبون")
    # إلغاء أثناء الإرسال (القفل)
    await tg.click(T, sara, "t:do_rent:eg:tg")
    o = await order_of(B_SMS, 600)
    from forge.modules.providers.sms import SMSManager
    from sqlalchemy import update
    async with db.Session() as s:
        await s.execute(update(db.ServiceOrder).where(db.ServiceOrder.id == o.id).values(provider_name=hold.BUSY))
        await s.commit()
    ok, msg, _ = await SMSManager.cancel_number_and_refund(B_SMS, 600, o.order_id)
    ck.ok(not ok, "لا يمكن الإلغاء أثناء إرسال الطلب للموقع (لا مال ضائع)")
    async with db.Session() as s:
        await s.execute(update(db.ServiceOrder).where(db.ServiceOrder.id == o.id).values(provider_name=hold.HOLD))
        await s.commit()
    br = await ledger.get_user_balance_usd(B_SMS, 600)
    t = await tg.click(MAKER, adm, f"m:hold:no:{o.id}")
    o = await order_of(B_SMS, 600)
    ck.ok(o.status in ("canceled", "refunded") and await ledger.get_user_balance_usd(B_SMS, 600) > br, "رفض المدير = استرجاع كامل")
    ok, _ = await hold.reject(o.id)
    ck.ok(not ok, "الرفض لا يتكرر")

    print("— التفاعل من التطبيق المصغّر (المتجر الشامل) —")
    TM = await make_bot(tg, ali, B_MEGA, "megastore")
    async with db.Session() as s:
        bm = await s.get(db.Bot, B_MEGA)
    app = web.Application()
    store_api.setup_routes(app)
    c = TestClient(TestServer(app))
    await c.start_server()
    H = lambda uid: {"X-Telegram-Init-Data": init(TM, {"id": uid, "first_name": "U", "language_code": "ar"})}
    B = f"/api/v2/{bm.username}"
    await ledger.credit_user(B_MEGA, 600, 30.0, "deposit")
    try:
        before = await ledger.get_user_balance_usd(B_MEGA, 600)
        sel0 = await ledger.get_seller_balance_usd(500)
        j = await (await c.post(f"{B}/order", headers=H(600), json={"product_id": "ig_likes_hq", "quantity": 1000, "target": "https://instagram.com/p/x"})).json()
        ck.ok(j.get("ok") and j.get("status") == "processing", "طلب تفاعل: «قيد التنفيذ»")
        o = await order_of(B_MEGA, 600)
        ck.ok(o.provider_name == hold.HOLD, "لم يُرسل للموقع")
        j = await (await c.get(f"{B}/orders", headers=H(600))).json()
        ck.ok(all("__hold__" not in json.dumps(x) for x in j.get("orders", [])) and j["orders"][0]["status"] == "processing", "قائمة الزبون: قيد التنفيذ بلا أي أثر للتعليق")
        j = await (await c.get(f"{B}/seller/orders", headers=H(500))).json()
        ck.ok(j.get("ok") and "__hold__" not in json.dumps(j), "البائع لا يرى أن الطلب موقوف")
        j = await (await c.get(f"{B}/admin/hold", headers=H(ADMIN))).json()
        ck.ok(j.get("ok") and len(j["orders"]) == 1 and j["total"] > 0 and j["settings"]["smm"], "لوحة المدير: الطلب + المبلغ المطلوب شحنه")
        j2 = await (await c.get(f"{B}/admin/hold", headers=H(600))).json()
        ck.ok(not j2.get("ok"), "الزبون لا يصل للوحة الموافقات")
        # فشل الإرسال (رصيد الموقع لا يكفي) → يبقى معلّقاً
        orig = SMMManager.dispatch_order_with_failover

        async def fail(*a, **k):
            return False, "", "", 0.0
        SMMManager.dispatch_order_with_failover = fail
        j = await (await c.post(f"{B}/admin/hold", headers=H(ADMIN), json={"action": "approve", "id": o.id})).json()
        SMMManager.dispatch_order_with_failover = orig
        o = await order_of(B_MEGA, 600)
        ck.ok(j.get("done") is False and o.provider_name == hold.HOLD and o.status == "processing", "فشل الموقع: يبقى الطلب عندك لتعيد المحاولة")
        j = await (await c.post(f"{B}/admin/hold", headers=H(ADMIN), json={"action": "approve", "id": o.id})).json()
        o = await order_of(B_MEGA, 600)
        ck.ok(j.get("done") and o.provider_name and not hold.is_held(o.provider_name) and o.status == "processing", "الموافقة: أُرسل للموقع")
        ck.ok(await ledger.get_user_balance_usd(B_MEGA, 600) < before and await ledger.get_seller_balance_usd(500) < sel0, "الخصم مرة واحدة")
        # أرسل الكل
        for _ in range(3):
            await c.post(f"{B}/order", headers=H(600), json={"product_id": "tt_views_hq", "quantity": 1000, "target": "https://tiktok.com/@a/video/1"})
        j = await (await c.get(f"{B}/admin/hold", headers=H(ADMIN))).json()
        ck.ok(len(j["orders"]) == 3, "ثلاث طلبات معلّقة")
        j = await (await c.post(f"{B}/admin/hold", headers=H(ADMIN), json={"action": "approve_all"})).json()
        ck.ok(not j["orders"] and "3" in j.get("message", ""), "«أرسل الكل» يرسلها دفعة واحدة")
        # رقم من المتجر الشامل
        j = await (await c.post(f"{B}/order", headers=H(600), json={"product_id": "iq_tg", "quantity": 1})).json()
        ck.ok(j.get("ok") and j.get("status") == "processing" and not j.get("phone"), "رقم من التطبيق: قيد التنفيذ")
        o = await order_of(B_MEGA, 600)
        j = await (await c.post(f"{B}/sms/check", headers=H(600), json={"order_id": o.order_id})).json()
        ck.ok(j.get("ok") and j.get("status") == "processing", "فحص الكود قبل الموافقة آمن")
        tg_before = len(tg.out(B_MEGA))
        j = await (await c.post(f"{B}/admin/hold", headers=H(ADMIN), json={"action": "approve", "id": o.id})).json()
        ck.ok(j.get("done"), "موافقة الرقم")
        await tg.settle()
        new = tg.out(B_MEGA)[tg_before:]
        ck.ok(any("رقمك جاهز" in (m["p"].get("text") or "") for m in new), "الرقم يصل برسالة من بوت المتجر")
        ck.ok(any(b.get("callback_data", "").startswith("t:@s:check_sms:") for b in tg.buttons(B_MEGA)), "زر فحص الكود موجّه لقسم الأرقام")
        t = await tg.click(TM, sara, f"t:@s:check_sms:{o.order_id}")
        ck.ok(bool(t), "زر الفحص يعمل في المتجر الشامل")
        # إيقاف الموافقة اليدوية = إرسال فوري
        await c.post(f"{B}/admin/hold", headers=H(ADMIN), json={"action": "toggle", "sec": "smm", "on": False})
        j = await (await c.post(f"{B}/order", headers=H(600), json={"product_id": "ig_likes_hq", "quantity": 1000, "target": "https://instagram.com/p/y"})).json()
        o = await order_of(B_MEGA, 600)
        ck.ok(j.get("ok") and o.target.endswith("/p/y") and not hold.is_held(o.provider_name) and o.provider_order_id, "عند الإيقاف: يُرسل فوراً كالسابق")
    finally:
        await c.close()

    ck.errors("الموافقة اليدوية")
    ck.ok(not tg.problems, "كل الرسائل صالحة لتيليجرام" + "".join("\n      " + p for p in sorted(set(tg.problems))[:12]))
    await mgr.shutdown()
    await tg.stop()
    ck.done()


asyncio.run(main())
