"""محفظة البائع في الصانع + الشحن بالنجوم في المتاجر: لا رصيد قبل الدفع، شحن مرة واحدة لكل عملية، والتحويل اليدوي مع مراجعة الإدارة."""
import asyncio
import time

from harness import ADMIN, MAKER, MID, Check, boot, make_bot

B_DIG = 270000001


def paid_update(user: dict, payload: str, stars: int, charge: str) -> dict:
    return {"message": {"message_id": int(time.time() * 1000) % 10**9, "date": int(time.time()),
                        "chat": {"id": user["id"], "type": "private"}, "from": user,
                        "successful_payment": {"currency": "XTR", "total_amount": stars, "invoice_payload": payload,
                                               "telegram_payment_charge_id": charge, "provider_payment_charge_id": ""}}}


def precheckout(user: dict, payload: str, stars: int, qid: str) -> dict:
    return {"pre_checkout_query": {"id": qid, "from": user, "currency": "XTR", "total_amount": stars, "invoice_payload": payload}}


async def main():  # noqa: C901
    tg, mgr = await boot()
    from forge import wallet
    from forge.modules import ledger, payments
    ck = Check()
    ali, sara, boss = tg.user(500, "Ali", username="ali_k"), tg.user(600, "Sara"), tg.user(ADMIN, "Boss")
    for u in (boss, ali, sara):
        await tg.say(MAKER, u, "/start")

    print("— شاشة الرصيد —")
    ck.ok(tg.find(MID, "رصيدي"), "زر «رصيدي» في الرئيسية")
    t = await tg.click(MAKER, ali, "m:wal")
    ck.ok("رصيدي في الصانع" in t and "$0.00" in t and "سعر المنصة" in t, "شاشة الرصيد تشرح الخصم مع كل بيعة")

    print("— الشحن بالنجوم في الصانع —")
    t = await tg.click(MAKER, ali, "m:wals")
    ck.ok(tg.find(MID, "$10.00") and "الحد الأدنى" in t, "باقات النجوم تبدأ من الحد الأدنى")
    n0 = len(tg.calls)
    await tg.click(MAKER, ali, "m:walsb:10")
    inv = [c for c in tg.calls[n0:] if c["method"] == "sendInvoice"]
    ck.ok(bool(inv) and inv[0]["p"]["currency"] == "XTR", "فاتورة نجوم حقيقية تُرسل")
    ck.ok(await ledger.get_seller_balance_usd(500) == 0.0, "لا رصيد قبل الدفع")
    payload = inv[0]["p"]["payload"]
    stars = wallet.stars_for(10)
    n0 = len(tg.calls)
    tg.raw(MAKER, precheckout(ali, payload, stars, "pq1"))
    await tg.settle()
    ans = [c for c in tg.calls[n0:] if c["method"] == "answerPreCheckoutQuery"]
    ck.ok(bool(ans) and str(ans[0]["p"].get("ok")).lower() == "true", "فحص ما قبل الدفع يقبل فاتورة صحيحة")
    n0 = len(tg.calls)
    tg.raw(MAKER, precheckout(sara, payload, stars, "pq2"))
    await tg.settle()
    ans = [c for c in tg.calls[n0:] if c["method"] == "answerPreCheckoutQuery"]
    ck.ok(bool(ans) and str(ans[0]["p"].get("ok")).lower() == "false", "فاتورة مستخدم آخر تُرفض قبل الدفع")
    tg.raw(MAKER, paid_update(ali, payload, stars, "CHG-1"))
    await tg.settle()
    bal1 = await ledger.get_seller_balance_usd(500)
    ck.ok(bal1 >= 10.0, "الدفع المؤكد يشحن الرصيد")
    tg.raw(MAKER, paid_update(ali, payload, stars, "CHG-1"))
    await tg.settle()
    ck.ok(await ledger.get_seller_balance_usd(500) == bal1, "نفس عملية الدفع لا تُشحن مرتين")

    print("— التحويل اليدوي ومراجعة الإدارة —")
    t = await tg.click(MAKER, ali, "m:walm")
    ck.ok("لا توجد طرق تحويل" in t, "بلا طرق تحويل: رسالة واضحة")
    await tg.click(MAKER, ali, "m:walpm")
    ck.ok(await ledger.get_seller_balance_usd(500) == bal1, "غير المدير لا يدخل إعدادات الشحن")
    await tg.click(MAKER, boss, "m:walpa")
    t = await tg.say(MAKER, boss, "زين كاش | 07700000000 | حوّل ثم أرسل الإيصال")
    ck.ok("زين كاش" in t, "المدير يضيف طريقة تحويل")
    await tg.click(MAKER, ali, "m:walm")
    await tg.click(MAKER, ali, "m:walmp:0")
    t = await tg.say(MAKER, ali, "5")
    ck.ok("لا يقل عن 10" in t, "الحد الأدنى 10$ مفروض")
    await tg.say(MAKER, ali, "25")
    n0 = len(tg.calls)
    await tg.say(MAKER, ali, "TX-778899")
    ck.ok(any("قيد المراجعة" in str(c["p"].get("text", "")) and str(c["p"].get("chat_id")) == "500" for c in tg.calls[n0:]), "الإيصال يُستلم للمراجعة")
    to_admin = [c for c in tg.calls[n0:] if str(c["p"].get("chat_id")) == str(ADMIN) and "إيصال شحن بائع" in str(c["p"].get("text", ""))]
    ck.ok(bool(to_admin), "الإدارة تُبلَّغ بالإيصال مع أزرار القبول والرفض")
    rid = [b for row in to_admin[0]["p"]["reply_markup"]["inline_keyboard"] for b in row][0]["callback_data"].split(":")[2]
    await tg.click(MAKER, sara, f"m:walok:{rid}")
    ck.ok(await ledger.get_seller_balance_usd(500) == bal1, "غير المدير لا يقبل الإيصالات")
    await tg.click(MAKER, boss, f"m:walam:{rid}")
    await tg.say(MAKER, boss, "20")
    bal2 = await ledger.get_seller_balance_usd(500)
    ck.ok(abs(bal2 - (bal1 + 20)) < 0.001, "المدير يعتمد المبلغ الذي وصل فعلاً")
    await tg.click(MAKER, boss, f"m:walok:{rid}")
    ck.ok(await ledger.get_seller_balance_usd(500) == bal2, "الإيصال لا يُقبل مرتين")

    print("— الشحن بالنجوم داخل متجر البائع —")
    T = await make_bot(tg, ali, B_DIG, "digital")
    await tg.say(T, sara, "/start")
    n0 = len(tg.calls)
    await tg.click(T, sara, "t:stars_buy:500")
    inv = [c for c in tg.calls[n0:] if c["method"] == "sendInvoice" and c["bot"] == B_DIG]
    ck.ok(bool(inv), "زر النجوم في المتجر يرسل فاتورة")
    ck.ok(await ledger.get_user_balance_usd(B_DIG, 600) == 0.0, "لا رصيد للزبون قبل الدفع")
    pl = inv[0]["p"]["payload"]
    tg.raw(T, paid_update(sara, pl, 500, "CHG-S1"))
    await tg.settle()
    b = await ledger.get_user_balance_usd(B_DIG, 600)
    ck.ok(abs(b - 500 * payments.STAR_RATE_USD) < 0.001, "الدفع المؤكد يشحن رصيد الزبون")
    tg.raw(T, paid_update(sara, pl, 500, "CHG-S1"))
    await tg.settle()
    ck.ok(await ledger.get_user_balance_usd(B_DIG, 600) == b, "ولا يتكرر الشحن")
    tg.raw(T, paid_update(sara, pl, 9999, "CHG-S2"))
    await tg.settle()
    ck.ok(await ledger.get_user_balance_usd(B_DIG, 600) == b, "مبلغ لا يطابق الفاتورة لا يُشحن")

    print("— تنبيه انخفاض الرصيد —")
    await tg.say(MAKER, ali, "/start")
    await tg.click(MAKER, ali, "m:walal")
    await tg.say(MAKER, ali, "1000")
    n0 = len(tg.calls)
    ok, why, _ = await ledger.purchase(bot_id=B_DIG, buyer_id=600, price_usd=1.0, seller_id=500, platform_cost_usd=0.5, order_id="LB-1")
    await asyncio.sleep(0.3)
    await tg.settle()
    ck.ok(ok and any("رصيدك في الصانع منخفض" in str(c["p"].get("text", "")) for c in tg.calls[n0:]), "تنبيه للبائع حين ينخفض رصيده")

    ck.errors("المحفظة")
    ck.ok(not tg.problems, "كل الرسائل صالحة لتيليجرام" + "".join("\n      " + p for p in sorted(set(tg.problems))[:12]))
    await mgr.shutdown()
    await tg.stop()
    ck.done()


asyncio.run(main())
