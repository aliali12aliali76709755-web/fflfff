"""اختبارات الوحدات المشتركة: العملات، دفتر الأستاذ، المدفوعات، والخصومات والإحالة."""
import asyncio
import time
import pytest
from forge import db
from forge.modules import currency, ledger, payments, promo


@pytest.mark.anyio
async def test_currency_module():
    await db.init()
    # 1. فحص قائمة العملات
    assert "USD" in currency.CURRENCIES
    assert "IQD" in currency.CURRENCIES
    assert "POINTS" in currency.CURRENCIES

    # 2. تحويل العملات الافتراضية
    usd_val = 10.0
    iqd_val = await currency.usd_to_currency(usd_val, "IQD", bot_id=123)
    assert iqd_val >= 10000.0  # $10 = ~15,000 IQD

    back_usd = await currency.currency_to_usd(iqd_val, "IQD", bot_id=123)
    assert abs(back_usd - usd_val) < 0.1

    # 3. اختبار السعر اليدوي
    await currency.set_manual_rate(123, "IQD", 1600.0)
    iqd_manual = await currency.usd_to_currency(10.0, "IQD", bot_id=123)
    assert iqd_manual == 16000.0

    # 4. التنسيق
    await currency.set_bot_currency(123, "IQD")
    formatted = await currency.format_price_for_bot(123, 10.0)
    assert "د.ع" in formatted or "16,000" in formatted


@pytest.mark.anyio
async def test_ledger_module():
    await db.init()
    test_bot_id = int(time.time()) + 100
    test_user_id = int(time.time()) + 200

    # 1. الرصيد الأولي صفر
    bal0 = await ledger.get_user_balance_usd(test_bot_id, test_user_id)
    assert bal0 == 0.0

    # 2. إضافة رصيد
    ok, tx1, bal1 = await ledger.credit_user(test_bot_id, test_user_id, 25.0, "deposit_test")
    assert ok is True
    assert bal1 == 25.0

    # 3. فحص الـ Idempotency بنفس tx1
    ok_dup, tx_dup, bal_dup = await ledger.credit_user(test_bot_id, test_user_id, 25.0, "deposit_test", tx_id=tx1)
    assert ok_dup is True
    assert bal_dup == 25.0  # لم يتضاعف الرصيد

    # 4. خصم بمبلغ أكبر من الرصيد (فشل متوقع)
    ok_fail, reason, cur_bal = await ledger.debit_user(test_bot_id, test_user_id, 50.0, "order_test")
    assert ok_fail is False
    assert reason == "insufficient_balance"
    assert cur_bal == 25.0

    # 5. خصم سليم
    ok_deb, tx_deb, new_bal = await ledger.debit_user(test_bot_id, test_user_id, 10.0, "order_test")
    assert ok_deb is True
    assert new_bal == 15.0

    # 6. فحص سجل المعاملات
    txs = await ledger.get_user_transactions(test_bot_id, test_user_id)
    assert len(txs) >= 2


@pytest.mark.anyio
async def test_payments_module():
    await db.init()
    test_bot = 555444
    test_buyer = 333222

    # 1. حساب الرسوم
    net, fee, total = payments.calculate_fees(100.0, {"fee_type": "buyer", "fee_val": 5.0})
    assert net == 100.0
    assert fee == 5.0
    assert total == 105.0

    # 2. إنشاء إيصال دفع يدوي
    rcpt = await payments.create_receipt(
        bot_id=test_bot,
        user_id=test_buyer,
        user_name="Ahmed",
        username="ahmed_iq",
        method_name="Zain Cash",
        amount=15000.0,
        currency_code="IQD",
        amount_usd=10.0,
        proof_text="Ref: 987654321",
    )
    assert rcpt.status == "pending"

    # 3. موافقة البائع على الإيصال وشحن الرصيد تلقائياً
    ok, msg, new_bal = await payments.approve_receipt(rcpt.receipt_id)
    assert ok is True
    assert new_bal >= 10.0

    # 4. محاولة إعادة الموافقة على نفس الإيصال (فشل متوقع)
    ok_again, msg_again, _ = await payments.approve_receipt(rcpt.receipt_id)
    assert ok_again is False


@pytest.mark.anyio
async def test_promo_and_referral():
    await db.init()
    test_bot = 777666
    user_a = 111111
    user_b = 222222

    # 1. إنشاء كود خصم
    await promo.save_bot_promo(test_bot, "VIP20", discount_type="percent", value=20.0, min_order_usd=5.0)

    # 2. فحص الكود
    val_ok, discount, msg = await promo.validate_promo(test_bot, user_a, "VIP20", 10.0)
    assert val_ok is True
    assert discount == 2.0  # 20% of $10

    # 3. إحالة جديدة مع بونص تسجيل
    await promo.save_referral_config(test_bot, {"on": True, "mode": "both", "signup_bonus": 0.10})
    awarded = await promo.check_and_award_signup(test_bot, user_a, user_b)
    assert awarded is True

    # التأكد من رصيد المحيل بعد البونص
    ref_bal = await ledger.get_user_balance_usd(test_bot, user_a)
    assert ref_bal >= 0.10
