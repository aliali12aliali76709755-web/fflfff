"""القوالب المدمجة: «التفاعل + الأرقام» و«المتجر الشامل» — أقسام، محفظة مشتركة، لوحة مالك مجمّعة، وتسعير المتجر المصغّر."""
import asyncio

from harness import MAKER, Check, boot, make_bot

B_MEGA, B_DUO = 280000001, 280000002


async def main():  # noqa: C901
    tg, mgr = await boot()
    from forge import db
    from forge.modules import ledger
    from forge.web import miniapp_api
    ck = Check()
    ali, sara = tg.user(500, "Ali", username="ali_k"), tg.user(600, "Sara")
    for u in (ali, sara):
        await tg.say(MAKER, u, "/start")
    from forge import plat as platform
    (await platform.get(0))["promo"]["when"] = "idle"      # رسالة الترويج لا تلي رسالة البداية في هذا الاختبار

    print("— المتجر الشامل —")
    T = await make_bot(tg, ali, B_MEGA, "megastore")
    t = await tg.say(T, sara, "/start")
    labels = [b["text"] for b in tg.buttons(B_MEGA)]
    ck.ok(all(any(x in l for l in labels) for x in ("الألعاب", "التفاعل", "أرقام التفعيل", "نجوم")), "الرئيسية تعرض الأقسام الأربعة")
    ck.ok("رصيدك" in t, "الرصيد في الرئيسية")
    t = await tg.click(T, sara, "t:sec:smm")
    ck.ok(any("تصفّح الخدمات" in b["text"] for b in tg.buttons(B_MEGA)), "قسم التفاعل يفتح واجهته")
    t = await tg.click(T, sara, "t:cats")
    ck.ok(len(tg.buttons(B_MEGA)) > 2, "أزرار القسم تعمل داخل القسم المفتوح")
    await tg.click(T, sara, "t:sec:sms")
    t = await tg.click(T, sara, "t:countries")
    ck.ok(any("العراق" in b["text"] for b in tg.buttons(B_MEGA)), "قسم الأرقام يعرض الدول")
    await tg.click(T, sara, "t:home")
    ck.ok(any("نجوم" in b["text"] for b in tg.buttons(B_MEGA)), "زر الرجوع يعود لرئيسية المتجر الشامل")
    t = await tg.click(T, sara, "t:orders")
    ck.ok("طلباتي" in t, "طلباتي الموحّدة")

    print("— لوحة المالك المجمّعة —")
    t = await tg.say(T, ali, "/admin")
    ck.ok("رصيدك في الصانع" in t and "اليوم" in t, "غرفة التحكم تعرض أرقام اليوم ورصيد الصانع")
    owner_btns = tg.buttons(B_MEGA)
    ck.ok(sum(1 for b in owner_btns if b["text"].startswith("──")) == 4, "لوحة المالك تجمع لوحات الأقسام الأربعة")
    tagged = [b for b in owner_btns if str(b.get("callback_data", "")).startswith("t:@")]
    ck.ok(len(tagged) >= 4, "أزرار كل قسم موسومة بقسمها")
    sms_btn = next((b for b in tagged if b["callback_data"].startswith("t:@s:")), None)
    if sms_btn:
        await tg.click(T, ali, sms_btn["callback_data"])
        ck.ok(bool(tg.buttons(B_MEGA)), "زر قسم الأرقام في لوحة المالك يفتح شاشته")
    ck.ok(not any("مزودو" in b["text"] for b in owner_btns), "البائع لا يرى إعدادات المزودين (تديرها المنصة)")

    print("— المتجر المصغّر: كتالوج وتسعير من كل الأقسام —")
    async with db.Session() as s:
        bot = await s.get(db.Bot, B_MEGA)
    q_d = await miniapp_api._quote_item(bot, "pubg_60uc", 1)
    q_m = await miniapp_api._quote_item(bot, "ig_likes_hq", 1000)
    q_s = await miniapp_api._quote_item(bot, "iq_tg", 1)
    q_g = await miniapp_api._quote_item(bot, "stars_50", 1)
    ck.ok(q_d.ok and q_d.tpl == "digital" and q_m.ok and q_m.tpl == "smm" and q_s.ok and q_s.tpl == "sms" and q_g.ok and q_g.tpl == "tgstars",
          "تسعير منتجات الأقسام الأربعة")
    ck.ok(all(q.price_usd >= q.platform_cost_usd > 0 for q in (q_d, q_m, q_s, q_g)), "سعر البيع لا يقل عن سعر المنصة")
    ck.ok(not (await miniapp_api._quote_item(bot, "xx_fake", 1)).ok, "منتج غير موجود يُرفض")

    print("— التفاعل + الأرقام —")
    T2 = await make_bot(tg, ali, B_DUO, "smmsms")
    await tg.say(T2, sara, "/start")
    labels = [b["text"] for b in tg.buttons(B_DUO)]
    ck.ok(any("التفاعل" in l for l in labels) and any("أرقام" in l for l in labels) and not any("نجوم" in l for l in labels),
          "قسمان فقط: التفاعل والأرقام")
    async with db.Session() as s:
        bot2 = await s.get(db.Bot, B_DUO)
    ck.ok(not (await miniapp_api._quote_item(bot2, "pubg_60uc", 1)).ok and (await miniapp_api._quote_item(bot2, "iq_wa", 1)).ok,
          "منتجات القسمين فقط")

    print("— شراء حقيقي داخل القسم يخصم من الطرفين —")
    await ledger.credit_user(B_MEGA, 600, 50.0, "deposit")
    await ledger.credit_seller(500, 50.0, "deposit")
    await tg.click(T, sara, "t:sec:sms")
    b0, s0 = await ledger.get_user_balance_usd(B_MEGA, 600), await ledger.get_seller_balance_usd(500)
    await tg.click(T, sara, "t:do_rent:iq:tg")
    b1, s1 = await ledger.get_user_balance_usd(B_MEGA, 600), await ledger.get_seller_balance_usd(500)
    ck.ok(b1 < b0 and s1 < s0, "شراء رقم: خصم من الزبون ومن رصيد البائع في الصانع")

    ck.errors("القوالب المدمجة")
    ck.ok(not tg.problems, "كل الرسائل صالحة لتيليجرام" + "".join("\n      " + p for p in sorted(set(tg.problems))[:12]))
    await mgr.shutdown()
    await tg.stop()
    ck.done()


asyncio.run(main())
