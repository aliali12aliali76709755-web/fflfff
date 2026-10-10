"""اختبارات قالب نجوم تيليجرام واشتراكات بريميوم (Telegram Stars & Premium)"""
import asyncio
import time
import pytest
from forge import db
from forge.templates import tgstars
from forge.modules import currency, ledger, payments, promo
from forge.modules.providers import tgstars as tgstars_prov


@pytest.mark.anyio
async def test_tgstars_username_validation():
    # 1. يوزر عادي مع @
    ok1, u1 = tgstars_prov.clean_and_validate_username("@telegram_user")
    assert ok1 is True
    assert u1 == "@telegram_user"

    # 2. يوزر بدون @
    ok2, u2 = tgstars_prov.clean_and_validate_username("ahmed_dev")
    assert ok2 is True
    assert u2 == "@ahmed_dev"

    # 3. رابط t.me
    ok3, u3 = tgstars_prov.clean_and_validate_username("https://t.me/special_vip")
    assert ok3 is True
    assert u3 == "@special_vip"

    # 4. يوزر قصير جداً أو غير صالح
    ok4, _ = tgstars_prov.clean_and_validate_username("abc")
    assert ok4 is False

    # 5. يوزر يحتوي على رموز غير مسموحة
    ok5, _ = tgstars_prov.clean_and_validate_username("@bad-user$name")
    assert ok5 is False


@pytest.mark.anyio
async def test_tgstars_catalog_and_margin():
    await db.init()
    test_bot_id = int(time.time() * 1000) % 900000000 + 400000

    # 1. الكتالوج الافتراضي مع هامش 25%
    catalog = await tgstars_prov.TGStarsManager.get_services_catalog(test_bot_id)
    assert len(catalog) >= 10

    # 50 Stars cost is 0.85 -> with 25% = round(0.85 * 1.25, 2) = 1.06
    s50 = next(s for s in catalog if s["id"] == "stars_50")
    assert s50["price_usd"] > s50["base_cost_usd"]

    # 3 Months Premium cost is 11.50 -> with 25% = round(11.50 * 1.25, 2) = 14.38
    p3m = next(s for s in catalog if s["id"] == "prem_3m")
    assert p3m["price_usd"] > 11.50

    # 2. تخصيص سعر مباشر للباقة
    await db.kv_set(test_bot_id, "tgstars:services_override", {
        "stars_50": {"custom_price_usd": 1.50},
        "prem_3m": {"hide": True},
    })
    cat_over = await tgstars_prov.TGStarsManager.get_services_catalog(test_bot_id)
    s50_over = next(s for s in cat_over if s["id"] == "stars_50")
    assert s50_over["price_usd"] == 1.50
    assert not any(s["id"] == "prem_3m" for s in cat_over)


@pytest.mark.anyio
async def test_tgstars_failover_dispatch():
    await db.init()
    test_bot_id = int(time.time() * 1000) % 900000000 + 500000

    ok, order_id, prov_name, cost = await tgstars_prov.TGStarsManager.dispatch_order_with_failover(
        test_bot_id,
        "stars_100",
        "@target_recipient",
        1
    )
    assert ok is True
    assert "tgstars_mock_" in order_id
    assert prov_name == "DefaultTGStarsCatalog"
    assert cost > 0.0


@pytest.mark.anyio
async def test_tgstars_order_workflow():
    await db.init()
    test_bot_id = int(time.time() * 1000) % 900000000 + 600000
    test_user_id = test_bot_id + 1

    # 1. شحن رصيد للمستخدم
    await ledger.credit_user(test_bot_id, test_user_id, 30.0, "initial_tgstars_credit")
    bal = await ledger.get_user_balance_usd(test_bot_id, test_user_id)
    assert bal == 30.0

    # 2. خصم قيمة باقة بريميوم 6 أشهر ($19.75)
    ord_key = f"ord_tg_{int(time.time() * 1000)}"
    price = 19.75
    ok_debit, tx, new_bal = await ledger.debit_user(
        test_bot_id,
        test_user_id,
        price,
        kind="order_tgstars",
        ref_id=ord_key,
        description="Telegram Premium 6 Months"
    )
    assert ok_debit is True
    assert new_bal == round(30.0 - 19.75, 2)

    # 3. تسجيل الطلب في قاعدة البيانات
    async with db.Session() as s:
        s_order = db.ServiceOrder(
            order_id=ord_key,
            bot_id=test_bot_id,
            user_id=test_user_id,
            tpl_key="tgstars",
            service_id="prem_6m",
            service_name="اشتراك تيليجرام بريميوم (6 أشهر)",
            target="@vip_friend",
            quantity=1,
            cost_provider_usd=15.80,
            price_user_usd=price,
            currency="USD",
            price_user_currency=price,
            status="processing",
            provider_name="DefaultTGStarsCatalog",
            provider_order_id="mock_tg_999",
        )
        s.add(s_order)
        await s.commit()

    # 4. التأكد من حفظ الطلب
    async with db.Session() as s:
        fetched = (await s.execute(
            db.select(db.ServiceOrder).where(db.ServiceOrder.order_id == ord_key)
        )).scalars().first()
        assert fetched is not None
        assert fetched.target == "@vip_friend"
        assert fetched.status == "processing"
