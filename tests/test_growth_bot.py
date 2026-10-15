"""داخل البوتات: اشتراك البائع في الصانع، التقرير اليومي وزر خصم الاسترجاع، وإذاعة المدير من أي بوت."""
import asyncio
import datetime as dt
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from harness import ADMIN, MAKER, MID, Check, boot, make_bot, tok

B_SHOP, B_QURAN = 295000001, 295000002


def init(token, user):
    pairs = {"auth_date": str(int(time.time())), "query_id": "AAE", "user": json.dumps(user, separators=(",", ":"))}
    chk = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    sec = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(sec, chk.encode(), hashlib.sha256).hexdigest()
    return urlencode(pairs)


async def main():  # noqa: C901
    tg, mgr = await boot()
    from aiohttp import web
    from aiohttp.test_utils import TestClient, TestServer

    from forge import db
    from forge.modules import insights, ledger, perks, subs
    from forge.web import store_api
    ck = Check()
    adm = tg.user(ADMIN, "Admin")
    ali, sara, omar = tg.user(500, "Ali", username="ali_k"), tg.user(600, "Sara", username="sara_x"), tg.user(700, "Omar")
    for u in (adm, ali, sara, omar):
        await tg.say(MAKER, u, "/start")
    from forge import plat as platform
    (await platform.get(0))["promo"]["when"] = "idle"

    print("— اشتراك البائع في الصانع —")
    await subs.set_conf(on=True, price=5.0, days=30, trial_days=2)
    t = await tg.click(MAKER, ali, "m:home")
    ck.ok(any("اشتراكي" in b["text"] for b in tg.buttons(MID)), "زر «💎 اشتراكي» في رئيسية الصانع")
    t = await tg.click(MAKER, ali, "m:tpl:megastore")
    ck.ok("يحتاج اشتراكاً" in t and any("جرّب مجاناً 2" in b["text"] for b in tg.buttons(MID)), "النوع التجاري يطلب اشتراكاً مع تجربة مجانية")
    t = await tg.click(MAKER, ali, "m:tpl:quran")
    ck.ok("يحتاج اشتراكاً" not in t, "الأنواع غير التجارية بلا اشتراك")
    t = await tg.click(MAKER, ali, "m:sub:buy:megastore")
    ck.ok("لا يكفي" in t, "الشراء بلا رصيد يُرفض بوضوح")
    t = await tg.click(MAKER, ali, "m:sub:trial:megastore")
    ck.ok("الخطوة 2 من 3" in t, "بعد التجربة يكمل إنشاء البوت مباشرة")
    T = await make_bot(tg, ali, B_SHOP, "megastore")
    async with db.Session() as s:
        ck.ok((await s.get(db.Bot, B_SHOP)) is not None, "أُنشئ المتجر خلال التجربة")
    t = await tg.click(MAKER, ali, "m:sub")
    ck.ok("فعّال حتى" in t and not any("جرّب مجاناً" in b["text"] for b in tg.buttons(MID)), "حالة الاشتراك + التجربة لا تتكرر")
    await ledger.credit_seller(500, 12.0, "deposit")
    t = await tg.click(MAKER, ali, "m:sub:buy")
    ck.ok("فعّال حتى" in t and abs(await ledger.get_seller_balance_usd(500) - 7.0) < 1e-6, "التجديد من الرصيد")
    # بائع ثانٍ بلا اشتراك لا ينشئ متجراً حتى لو أرسل توكناً مباشرة
    t = await tg.click(MAKER, omar, "m:tpl:smm")
    ck.ok("يحتاج اشتراكاً" in t, "بائع آخر بلا اشتراك: يُطلب منه الاشتراك")
    await tg.click(MAKER, omar, "m:tpl:quran")
    await tg.say(MAKER, omar, tok(B_QURAN))
    await asyncio.sleep(0.3)
    async with db.Session() as s:
        ck.ok((await s.get(db.Bot, B_QURAN)) is not None, "ونفس البائع ينشئ بوتاً غير تجاري بحرية")
    t = await tg.click(MAKER, adm, "m:tpl:megastore")
    ck.ok("يحتاج اشتراكاً" not in t, "المدير معفى")

    print("— التقرير اليومي وزر خصم الاسترجاع —")
    await ledger.credit_user(B_SHOP, 600, 20.0, "deposit")
    await tg.say(T, sara, "/start")
    old = db.now() - dt.timedelta(days=30)
    async with db.Session() as s:
        s.add(db.ServiceOrder(order_id="rep_old_1", bot_id=B_SHOP, user_id=600, tpl_key="smm", service_id="ig_likes_hq", service_name="إعجابات",
                              target="t", quantity=1000, price_user_usd=3.0, cost_platform_usd=1.0, status="completed", created=old))
        s.add(db.ServiceOrder(order_id="rep_new_1", bot_id=B_SHOP, user_id=700, tpl_key="smm", service_id="ig_likes_hq", service_name="إعجابات انستغرام",
                              target="t", quantity=1000, price_user_usd=2.0, cost_platform_usd=1.2, status="completed"))
        await s.commit()
    from forge import config
    tz0 = config.TZ_HOURS
    config.TZ_HOURS = 21 - db.now().hour + (24 if db.now().hour > 21 else 0)
    n0 = len(tg.out(B_SHOP))
    sent = await perks.daily_reports(mgr)
    config.TZ_HOURS = tz0
    await tg.settle()
    rep = [m["p"] for m in tg.out(B_SHOP)[n0:] if str(m["p"].get("chat_id")) == "500"]
    ck.ok(sent == 1 and rep and "تقرير اليوم" in rep[-1]["text"] and "$0.80" in rep[-1]["text"], "التقرير اليومي يصل للبائع (مبيعات وربح وأكثر منتج)")
    ck.ok("زبائن توقفوا" in rep[-1]["text"] and "@sara_x" in rep[-1]["text"], "يذكر الزبون المتوقف")
    wb = next((b for b in tg.buttons(B_SHOP) if b.get("callback_data", "").startswith("o:wb:")), None)
    ck.ok(wb is not None, "زر «أرسل خصم» تحت التقرير")
    ck.ok(await perks.daily_reports(mgr) == 0, "التقرير مرة واحدة باليوم")
    if wb:
        n1 = len(tg.out(B_SHOP))
        await tg.click(T, ali, wb["callback_data"])
        await tg.settle()
        to_sara = [m["p"] for m in tg.out(B_SHOP)[n1:] if str(m["p"].get("chat_id")) == "600"]
        ck.ok(to_sara and "BACK" in to_sara[-1]["text"], "الزبون استلم كود خصم شخصي")
        n2 = len(tg.out(B_SHOP))
        await tg.click(T, sara, wb["callback_data"])
        await tg.settle()
        ck.ok(not [m for m in tg.out(B_SHOP)[n2:] if str(m["p"].get("chat_id")) == "600" and "BACK" in (m["p"].get("text") or "")],
              "الزبون لا يستطيع ضغط زر البائع")

    print("— إذاعة المدير من أي بوت —")
    async with db.Session() as s:
        bot = await s.get(db.Bot, B_SHOP)
        for u in (600, 700, 701):
            if await s.get(db.BUser, (B_SHOP, u)) is None:
                s.add(db.BUser(bot_id=B_SHOP, user_id=u, name=f"u{u}", kind="private"))
        await s.commit()
    app = web.Application()
    store_api.setup_routes(app)
    c = TestClient(TestServer(app))
    await c.start_server()
    H = lambda uid: {"X-Telegram-Init-Data": init(T, {"id": uid, "first_name": "U", "language_code": "ar"})}
    B = f"/api/v2/{bot.username}"
    try:
        j = await (await c.post(f"{B}/admin/broadcast", headers=H(ADMIN), json={"preview": 1, "bot": "@" + bot.username.upper()})).json()
        ck.ok(j.get("ok") and j["bot"]["users"] >= 3, "معاينة: البوت وعدد المستلمين (المعرّف بأي حالة أحرف)" + ("" if j.get("ok") else str(j)))
        j = await (await c.post(f"{B}/admin/broadcast", headers=H(ADMIN), json={"preview": 1, "bot": "@no_such_bot_x"})).json()
        ck.ok(not j.get("ok"), "بوت غير موجود يُرفض")
        n3 = len(tg.out(B_SHOP))
        j = await (await c.post(f"{B}/admin/broadcast", headers=H(ADMIN), json={"bot": bot.username, "text": "<b>عرض الجمعة</b> 🔥",
                                                                                "btn_text": "افتح المتجر", "btn_url": "https://t.me/x"})).json()
        ck.ok(j.get("ok") and j.get("job"), "بدأت الإذاعة")
        j2 = await (await c.post(f"{B}/admin/broadcast", headers=H(ADMIN), json={"bot": bot.username, "text": "ثانية"})).json()
        for _ in range(60):
            if all(x["state"] == "done" for x in insights.jobs()):
                break
            await asyncio.sleep(0.1)
        await tg.settle()
        got = [m["p"] for m in tg.out(B_SHOP)[n3:] if "عرض الجمعة" in (m["p"].get("text") or "")]
        ck.ok(len(got) >= 3 and got[0].get("reply_markup"), "وصلت الرسالة لكل المستخدمين مع الزر")
        job = insights.jobs()[0]
        ck.ok(job["state"] == "done" and job["sent"] >= 3, "تقرير الإذاعة: عدد الواصلين")
        j = await (await c.post(f"{B}/admin/broadcast", headers=H(500), json={"bot": bot.username, "text": "x"})).json()
        ck.ok(not j.get("ok"), "البائع لا يستطيع الإذاعة من بوتات غيره")
    finally:
        await c.close()

    print("— انتهاء الاشتراك يوقف البيع —")
    st = await subs.state(500)
    st.update(until=time.time() - 5, auto=False)
    await db.kv_set(0, "sub:500", st)
    await tg.click(T, sara, "t:sec:sms")
    b0 = await ledger.get_user_balance_usd(B_SHOP, 600)
    t = await tg.click(T, sara, "t:do_rent:iq:tg")
    ck.ok(await ledger.get_user_balance_usd(B_SHOP, 600) == b0, "متجر منتهي الاشتراك لا يخصم من الزبون")
    ck.ok("اشتراك" not in (tg.text(B_SHOP) or ""), "الزبون لا يرى سبب التوقف (فقط «غير متوفر مؤقتاً»)")
    await subs.set_conf(on=False)

    ck.errors("النمو")
    ck.ok(not tg.problems, "كل الرسائل صالحة لتيليجرام" + "".join("\n      " + p for p in sorted(set(tg.problems))[:12]))
    await mgr.shutdown()
    await tg.stop()
    ck.done()


asyncio.run(main())
