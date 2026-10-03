"""بعد إعادة تشغيل السيرفر تعود كل البوتات للعمل من قاعدة البيانات مع بياناتها."""
import asyncio

from harness import MAKER, Check, boot, make_bot, tok


async def main():
    tg, mgr = await boot()
    ck = Check()
    ali, sara = tg.user(500, "Ali"), tg.user(600, "Sara")
    await tg.say(MAKER, ali, "/start")
    T1 = await make_bot(tg, ali, 420000001, "qrmenu")
    T2 = await make_bot(tg, ali, 420000002, "decor")
    await tg.click(T1, ali, "t:ia:qrmenu")
    await tg.say(T1, ali, "شاورما | 3$ | دجاج")
    await tg.click(MAKER, ali, "m:dis:420000002")
    await mgr.shutdown()
    ck.ok(not mgr.apps, "توقف كل شيء")
    await mgr.start_all()
    ck.ok(mgr.running(420000001), "البوت النشط عاد للعمل")
    ck.ok(not mgr.running(420000002), "البوت المعطّل بقي معطّلاً")
    await tg.say(T1, sara, "/start")
    await tg.click(T1, sara, "t:menu")
    ck.ok(tg.find(420000001, "شاورما"), "بيانات القالب محفوظة بعد إعادة التشغيل")
    ck.ok("(2)" in await tg.click(MAKER, ali, "m:bots"), "قائمة البوتات محفوظة")
    ck.errors("إعادة التشغيل")
    await mgr.shutdown()
    await tg.stop()
    ck.done()


asyncio.run(main())
