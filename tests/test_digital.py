"""اختبارات قالب شحن الألعاب والخدمات الرقمية والمخزون (Digital Services & Game Top-Up)"""
import asyncio
import time
import pytest
from forge import db
from forge.templates import digital
from forge.modules import currency, ledger, payments, promo
from forge.modules.providers import digital as digital_prov


@pytest.mark.anyio
async def test_digital_catalog_and_margin():
    await db.init()
    test_bot_id = int(time.time() * 1000) % 900000000 + 110000

    # 1. الكتالوج الافتراضي مع هامش 20%
    catalog = await digital_prov.DigitalManager.get_services_catalog(test_bot_id)
    assert len(catalog) >= 10

    # ببجي 660 UC التكلفة 9.20 -> مع 20% = round(9.20 * 1.20, 2) = 11.04
    pubg = next(s for s in catalog if s["id"] == "pubg_660uc")
    assert pubg["price_usd"] > 9.20

    # 2. تغيير الهامش إلى +30%
    await db.kv_set(test_bot_id, "digital:margin", {"type": "percent", "val": 30.0})
    cat30 = await digital_prov.DigitalManager.get_services_catalog(test_bot_id)
    pubg30 = next(s for s in cat30 if s["id"] == "pubg_660uc")
    assert pubg30["price_usd"] > pubg["price_usd"]


@pytest.mark.anyio
async def test_digital_voucher_stock():
    await db.init()
    test_bot_id = int(time.time() * 1000) % 900000000 + 120000
    svc_id = "itunes_10"

    # 1. المخزون الأولي صفر
    cnt0 = await digital_prov.DigitalManager.get_stock_count(test_bot_id, svc_id)
    assert cnt0 == 0

    # 2. إضافة أكواد إلى المخزون
    test_codes = ["AAPL-1111-2222", "AAPL-3333-4444", "AAPL-5555-6666"]
    cnt_after = await digital_prov.DigitalManager.add_vouchers_to_stock(test_bot_id, svc_id, test_codes)
    assert cnt_after == 3

    # 3. سحب كود من المخزون للتسليم الفوري
    code1 = await digital_prov.DigitalManager.get_voucher_from_stock(test_bot_id, svc_id)
    assert code1 == "AAPL-1111-2222"
    assert await digital_prov.DigitalManager.get_stock_count(test_bot_id, svc_id) == 2

    # 4. سحب الكود الثاني
    code2 = await digital_prov.DigitalManager.get_voucher_from_stock(test_bot_id, svc_id)
    assert code2 == "AAPL-3333-4444"
    assert await digital_prov.DigitalManager.get_stock_count(test_bot_id, svc_id) == 1


@pytest.mark.anyio
async def test_digital_queue_fulfillment_and_refund():
    await db.init()
    test_bot_id = int(time.time() * 1000) % 900000000 + 130000
    test_user_id = test_bot_id + 1

    # 1. شحن رصيد للمستخدم ($25)
    await ledger.credit_user(test_bot_id, test_user_id, 25.0, "initial_digital_credit")
    bal = await ledger.get_user_balance_usd(test_bot_id, test_user_id)
    assert bal == 25.0

    # 2. خصم قيمة طلب شحن ببجي ($11.00)
    price = 11.00
    ord_key = f"dig_test_{int(time.time() * 1000)}"
    ok_deb, tx, new_bal = await ledger.debit_user(
        test_bot_id,
        test_user_id,
        price,
        kind="order_digital",
        ref_id=ord_key,
        description="PUBG 660 UC"
    )
    assert ok_deb is True
    assert new_bal == 14.00

    # 3. تسجيل الطلب في طابور المعالجة (queued)
    async with db.Session() as s:
        s_order = db.ServiceOrder(
            order_id=ord_key,
            bot_id=test_bot_id,
            user_id=test_user_id,
            tpl_key="digital",
            service_id="pubg_660uc",
            service_name="ببجي موبايل 660 UC",
            target="5123456789",
            quantity=1,
            cost_provider_usd=9.20,
            cost_platform_usd=0.0,
            price_user_usd=price,
            currency="USD",
            price_user_currency=price,
            status="queued",
            provider_name="DigitalFulfillment",
            provider_order_id=ord_key,
            details={},
        )
        s.add(s_order)
        await s.commit()

    # 4. إكمال الطلب بواسطة المالك وتسليم ملاحظة الإنجاز
    ok_done, msg_done = await digital_prov.DigitalManager.complete_order(test_bot_id, ord_key, "تم الشحن بنجاح")
    assert ok_done is True

    async with db.Session() as s:
        fetched = (await s.execute(
            db.select(db.ServiceOrder).where(db.ServiceOrder.order_id == ord_key)
        )).scalars().first()
        assert fetched.status == "completed"
        assert fetched.details.get("fulfillment_note") == "تم الشحن بنجاح"

    # 5. تجربة سيناريو إلغاء واسترجاع طلب آخر
    ord_refund_key = f"dig_ref_{int(time.time() * 1000)}"
    await ledger.debit_user(test_bot_id, test_user_id, 5.0, "order_digital", ref_id=ord_refund_key)

    async with db.Session() as s:
        s_ref = db.ServiceOrder(
            order_id=ord_refund_key,
            bot_id=test_bot_id,
            user_id=test_user_id,
            tpl_key="digital",
            service_id="ff_520d",
            service_name="فري فاير 520 جوهرة",
            target="987654321",
            quantity=1,
            cost_provider_usd=4.50,
            price_user_usd=5.00,
            currency="USD",
            price_user_currency=5.00,
            status="queued",
            provider_name="DigitalFulfillment",
            provider_order_id=ord_refund_key,
            details={},
        )
        s.add(s_ref)
        await s.commit()

    # إلغاء واسترجاع
    ok_cancel, msg_cancel, bal_after_ref = await digital_prov.DigitalManager.cancel_and_refund(
        test_bot_id, ord_refund_key, reason="آيدي غير صالح"
    )
    assert ok_cancel is True
    assert bal_after_ref == 14.00  # عاد الرصيد كاملاً
