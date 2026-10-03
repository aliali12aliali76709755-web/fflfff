"""ترقية من نسخة قديمة: بوت مسجّل بنوع حُذف (المساعد الذكي) يجب ألا يكسر الصانع."""
import asyncio

from harness import MAKER, MID, Check, boot, tok

OLD = 430000001


async def main():
    tg, mgr = await boot()
    from forge import crypto, db
    ck = Check()
    ali, sara = tg.user(500, "Ali"), tg.user(600, "Sara")
    await tg.say(MAKER, ali, "/start")
    async with db.Session() as s:
        s.add(db.Bot(id=OLD, factory_id=0, owner_id=500, username=f"b{OLD}_bot", name="Old AI", token=crypto.enc(tok(OLD)), template="assistant", status="active"))
        await s.commit()
    await mgr.shutdown()
    await mgr.start_all()
    ck.ok(mgr.running(OLD), "البوت القديم يُقلع رغم حذف نوعه")
    ck.ok("(1)" in await tg.click(MAKER, ali, "m:bots") and tg.find(MID, "لم يعد متاحاً"), "قائمة البوتات تعمل وتوضح الحالة")
    ck.ok("لم يعد متاحاً" in await tg.click(MAKER, ali, f"m:b:{OLD}"), "بطاقة البوت تعمل")
    ck.ok("لوحتك" in await tg.click(MAKER, ali, "m:stats"), "لوحتي تعمل")
    ck.ok("تغيير النوع" in await tg.say(tok(OLD), ali, "/start"), "المالك يُرشَد إلى تغيير النوع")
    await tg.say(tok(OLD), sara, "/start")
    ck.ok(any("قيد التحديث" in c["p"]["text"] for c in tg.out(OLD)[-2:]), "العضو يرى رسالة مهذبة")
    await tg.click(MAKER, ali, f"m:chgto:{OLD}:contact")
    ck.ok("بوت التواصل" in await tg.say(tok(OLD), ali, "/start"), "تغيير النوع يعيد البوت للعمل")
    ck.errors("الترقية")
    ck.ok(not tg.problems, "رسائل صالحة" + "".join("\n      " + p for p in tg.problems[:5]))
    await mgr.shutdown()
    await tg.stop()
    ck.done()


asyncio.run(main())
