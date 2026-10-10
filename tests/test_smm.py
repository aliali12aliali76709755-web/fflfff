"""اختبارات قالب زيادة التفاعل (SMM Template & Providers)"""
import asyncio
import time
import pytest
from forge import db
from forge.templates import smm
from forge.modules import currency, ledger, payments, promo
from forge.modules.providers import smm as smm_prov


@pytest.mark.anyio
async def test_smm_url_validation():
    # 1. روابط انستغرام
    assert smm_prov.validate_target_url("instagram", "https://instagram.com/myuser") is True
    assert smm_prov.validate_target_url("instagram", "https://tiktok.com/@myuser") is False

    # 2. روابط تيك توك
    assert smm_prov.validate_target_url("tiktok", "https://tiktok.com/@user/video/1234") is True
    assert smm_prov.validate_target_url("tiktok", "https://facebook.com/post") is False

    # 3. روابط تلغرام
    assert smm_prov.validate_target_url("telegram", "https://t.me/channel_test") is True
    assert smm_prov.validate_target_url("telegram", "@channel_test") is True
    assert smm_prov.validate_target_url("telegram", "https://youtube.com/watch?v=123") is False

    # 4. روابط يوتيوب
    assert smm_prov.validate_target_url("youtube", "https://youtube.com/watch?v=12345") is True
    assert smm_prov.validate_target_url("youtube", "https://youtu.be/12345") is True


@pytest.mark.anyio
async def test_smm_catalog_and_margin():
    await db.init()
    test_bot_id = 999111

    # 1. فحص الكتالوج الافتراضي مع هامش 30%
    catalog = await smm_prov.SMMManager.get_services_catalog(test_bot_id)
    assert len(catalog) > 5

    ig_followers = next((s for s in catalog if s["id"] == "ig_followers_fast"), None)
    assert ig_followers is not None
    # Base cost is 0.85, with +30% margin = round(0.85 * 1.30, 4) = 1.105
    assert ig_followers["price_per_1k_usd"] > ig_followers["base_cost_per_1k"]

    # 2. تغيير هامش الربح إلى +50%
    await db.kv_set(test_bot_id, "smm:margin", {"type": "percent", "val": 50.0})
    cat50 = await smm_prov.SMMManager.get_services_catalog(test_bot_id)
    ig50 = next(s for s in cat50 if s["id"] == "ig_followers_fast")
    assert round(ig50["price_per_1k_usd"], 2) == round(0.85 * 1.5, 2)

    # 3. تخصيص سعر مباشر للخدمة وإخفاء خدمة أخرى
    await db.kv_set(test_bot_id, "smm:services_override", {
        "ig_followers_fast": {"custom_price_usd": 2.50},
        "ig_likes_hq": {"hide": True},
    })
    cat_over = await smm_prov.SMMManager.get_services_catalog(test_bot_id)
    ig_cust = next(s for s in cat_over if s["id"] == "ig_followers_fast")
    assert ig_cust["price_per_1k_usd"] == 2.50
    assert not any(s["id"] == "ig_likes_hq" for s in cat_over)


@pytest.mark.anyio
async def test_smm_failover_dispatch():
    await db.init()
    test_bot_id = 999222

    # اختبار الإرسال عبر المزود الافتراضي (Mock Adapter)
    ok, order_id, prov_name, cost = await smm_prov.SMMManager.dispatch_order_with_failover(
        test_bot_id,
        "ig_followers_fast",
        "https://instagram.com/test_user",
        1000
    )
    assert ok is True
    assert "mock_" in order_id
    assert prov_name == "DefaultCatalog"
    assert cost > 0.0


@pytest.mark.anyio
async def test_smm_order_workflow_and_ledger():
    await db.init()
    test_bot_id = 999333
    test_user_id = 888444

    # 1. شحن رصيد للمستخدم
    await ledger.credit_user(test_bot_id, test_user_id, 20.0, "initial_test_deposit")
    bal = await ledger.get_user_balance_usd(test_bot_id, test_user_id)
    assert bal == 20.0

    # 2. إنشاء كود خصم 10%
    await promo.save_bot_promo(test_bot_id, "SAVE10", discount_type="percent", value=10.0)

    # 3. محاكاة طلب بقيمة 5$
    order_amount = 5.0
    val_ok, discount, msg = await promo.validate_promo(test_bot_id, test_user_id, "SAVE10", order_amount)
    assert val_ok is True
    assert discount == 0.50
    final_price = order_amount - discount  # $4.50

    # 4. خصم الرصيد
    ord_key = f"ord_test_{int(time.time())}"
    ok_debit, tx, new_bal = await ledger.debit_user(
        test_bot_id,
        test_user_id,
        final_price,
        kind="order_smm",
        ref_id=ord_key,
        description="Test SMM Order"
    )
    assert ok_debit is True
    assert new_bal == 15.50

    # 5. حفظ الطلب في قاعدة البيانات
    async with db.Session() as s:
        s_order = db.ServiceOrder(
            order_id=ord_key,
            bot_id=test_bot_id,
            user_id=test_user_id,
            tpl_key="smm",
            service_id="ig_followers_fast",
            service_name="متابعين انستغرام حقيقيين",
            target="https://instagram.com/test_account",
            quantity=1000,
            cost_provider_usd=0.85,
            price_user_usd=final_price,
            currency="USD",
            price_user_currency=final_price,
            status="processing",
            provider_name="DefaultCatalog",
            provider_order_id="mock_123",
        )
        s.add(s_order)
        await s.commit()

    # 6. التحقق من وجود الطلب
    async with db.Session() as s:
        fetched = (await s.execute(
            db.select(db.ServiceOrder).where(db.ServiceOrder.order_id == ord_key)
        )).scalars().first()
        assert fetched is not None
        assert fetched.user_id == test_user_id
        assert fetched.price_user_usd == 4.50
        assert fetched.status == "processing"
