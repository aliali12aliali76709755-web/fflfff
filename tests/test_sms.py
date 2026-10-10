"""اختبارات قالب أرقام التفعيل واسترجاع الرصيد (SMS Virtual Numbers)"""
import asyncio
import time
import pytest
from forge import db
from forge.templates import sms
from forge.modules import currency, ledger, payments, promo
from forge.modules.providers import sms as sms_prov


@pytest.mark.anyio
async def test_sms_price_calculation():
    await db.init()
    test_bot_id = int(time.time() * 1000) % 900000000 + 700000

    # 1. حساب سعر رقم تلغرام لدولة العراق مع هامش 35%
    price_iq_tg = await sms_prov.SMSManager.calculate_number_price(test_bot_id, "iq", "tg")
    assert price_iq_tg > 0.40  # base is 0.40 * 1.2 = 0.48 -> +35% = ~0.65
    assert round(price_iq_tg, 2) == 0.65

    # 2. تغيير هامش الربح إلى +50%
    await db.kv_set(test_bot_id, "sms:margin", {"type": "percent", "val": 50.0})
    price_50 = await sms_prov.SMSManager.calculate_number_price(test_bot_id, "iq", "tg")
    assert price_50 > price_iq_tg


@pytest.mark.anyio
async def test_sms_rent_and_check_code():
    await db.init()
    test_bot_id = int(time.time() * 1000) % 900000000 + 800000

    # 1. استئجار رقم
    ok, act_id, phone, prov_name, cost = await sms_prov.SMSManager.rent_number_with_failover(
        test_bot_id, "iq", "wa"
    )
    assert ok is True
    assert phone.startswith("+96477")
    assert prov_name == "DefaultSMSMock"
    assert cost > 0.0

    # 2. فحص كود التفعيل
    res = await sms_prov.SMSManager.check_sms_code(test_bot_id, act_id, prov_name)
    assert res["status"] == "received"
    assert len(res["code"]) == 6


@pytest.mark.anyio
async def test_sms_cancel_and_atomic_refund():
    await db.init()
    test_bot_id = int(time.time() * 1000) % 900000000 + 900000
    test_user_id = test_bot_id + 1

    # 1. شحن رصيد للمستخدم
    await ledger.credit_user(test_bot_id, test_user_id, 10.0, "initial_sms_deposit")
    bal = await ledger.get_user_balance_usd(test_bot_id, test_user_id)
    assert bal == 10.0

    # 2. خصم سعر الرقم ($1.20)
    price = 1.20
    ord_key = f"sms_{int(time.time() * 1000)}"
    ok_deb, tx_deb, bal_after_deb = await ledger.debit_user(
        test_bot_id,
        test_user_id,
        price,
        kind="order_sms",
        ref_id=ord_key,
        description="Rent number test"
    )
    assert ok_deb is True
    assert bal_after_deb == 8.80

    # 3. تسجيل الطلب في قاعدة البيانات بحالة waiting_sms
    async with db.Session() as s:
        s_order = db.ServiceOrder(
            order_id=ord_key,
            bot_id=test_bot_id,
            user_id=test_user_id,
            tpl_key="sms",
            service_id="iq_tg",
            service_name="🇮🇶 تلغرام",
            target="+964771234567",
            quantity=1,
            cost_provider_usd=0.48,
            cost_platform_usd=0.0,
            price_user_usd=price,
            currency="USD",
            price_user_currency=price,
            status="waiting_sms",
            provider_name="DefaultSMSMock",
            provider_order_id="act_test_123",
            details={},
        )
        s.add(s_order)
        await s.commit()

    # 4. إلغاء الرقم واسترجاع الرصيد كاملاً
    ok_ref, msg, new_bal = await sms_prov.SMSManager.cancel_number_and_refund(
        test_bot_id, test_user_id, ord_key, reason="لم يصل الكود"
    )
    assert ok_ref is True
    assert new_bal == 10.0  # عاد الرصيد كاملاً!

    # 5. التحقق من حالة الطلب في قاعدة البيانات أنها canceled
    async with db.Session() as s:
        fetched = (await s.execute(
            db.select(db.ServiceOrder).where(db.ServiceOrder.order_id == ord_key)
        )).scalars().first()
        assert fetched.status == "canceled"
        assert "refund_tx" in fetched.details

    # 6. محاولة إلغاء نفس الطلب مرة أخرى (يجب أن ترفض لمنع التكرار)
    ok_again, _, _ = await sms_prov.SMSManager.cancel_number_and_refund(
        test_bot_id, test_user_id, ord_key
    )
    assert ok_again is False
