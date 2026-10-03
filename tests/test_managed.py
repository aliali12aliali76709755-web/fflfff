"""اختبار الإنشاء الفوري (Managed Bots) وتعيين المدير تلقائياً."""
import asyncio

from harness import MAKER, MID, Check, boot, tok


async def main():
    tg, mgr = await boot(caps={"can_manage_bots": True}, admin=0)
    ck = Check()
    ali, sara = tg.user(500, "Ali"), tg.user(600, "Sara")
    await tg.say(MAKER, ali, "/start")
    ck.ok(any("مدير المنصة" in c["p"]["text"] for c in tg.out(MID)), "أول مستخدم يصبح المدير")
    await tg.say(MAKER, sara, "/start")
    ck.ok(any("مستخدم جديد" in c["p"]["text"] and str(c["p"]["chat_id"]) == "500" for c in tg.out(MID)), "المدير يستقبل إشعار المستخدم الجديد")
    ck.ok("لوحة الإدارة" in await tg.say(MAKER, ali, "/admin"), "لوحة المدير تفتح له")
    n = len(tg.out(MID))
    await tg.say(MAKER, sara, "/admin")
    ck.ok(not any("لوحة الإدارة</b>" in c["p"]["text"] for c in tg.out(MID)[n:]), "غير المدير لا يفتح اللوحة")

    await tg.click(MAKER, sara, "m:tpl:xo")
    url = tg.find(MID, "إنشاء فوري")["url"]
    ck.ok(url.startswith(f"https://t.me/newbot/b{MID}_bot/") and "_bot?name=" in url, "زر الإنشاء الفوري برابط صحيح")
    new_id = 410000001
    tg.managed[new_id] = tok(new_id)
    tg.raw(MAKER, {"managed_bot": {"user": sara, "bot": {"id": new_id, "is_bot": True, "first_name": "XO", "username": f"b{new_id}_bot"}}})
    await tg.settle()
    ck.ok(mgr.running(new_id), "البوت المُدار أُنشئ وشُغّل تلقائياً")
    ck.ok(any("بوتك أصبح حياً" in c["p"]["text"] and str(c["p"].get("chat_id")) == "600" for c in tg.out(MID)), "المستخدم يستلم رسالة الجاهزية")
    ck.ok("(1)" in await tg.click(MAKER, sara, "m:bots"), "البوت في قائمة المستخدم")
    await tg.say(tok(new_id), sara, "/start")
    ck.ok("غرفة التحكم" in tg.text(new_id), "البوت المُدار يعمل بقالبه")
    ck.errors("الإنشاء الفوري")
    ck.ok(not tg.problems, "رسائل صالحة" + "".join("\n      " + p for p in tg.problems[:5]))
    await mgr.shutdown()
    await tg.stop()
    ck.done()


asyncio.run(main())
