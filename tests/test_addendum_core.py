import pytest
import time
from forge import db
from forge.modules import ledger
from forge.modules.markup import MarkupManager
from forge.modules.discounts import DiscountManager
from forge.modules.bulk_import import BulkImportManager


@pytest.mark.anyio
async def test_markup_hierarchy_and_floor():
    await db.init()
    uid = int(time.time() * 1000) % 900000000 + 11000

    # 1. Global markup rule
    await MarkupManager.set_margin_rule("global", "percent", 15.0, admin_id=1, note="test global")
    cost = await MarkupManager.calculate_platform_cost(10.0, owner_id=uid, tpl_key="smm")
    assert cost == 11.5  # 10 * 1.15

    # 2. Template level overrides global
    await MarkupManager.set_margin_rule("tpl:digital", "fixed", 3.0, admin_id=1, note="test tpl")
    cost_tpl = await MarkupManager.calculate_platform_cost(10.0, owner_id=uid, tpl_key="digital")
    assert cost_tpl == 13.0  # 10 + 3.0

    # 3. Product level overrides template
    await MarkupManager.set_margin_rule("prd:pubg", "percent", 5.0, admin_id=1, note="test prd")
    cost_prd = await MarkupManager.calculate_platform_cost(10.0, owner_id=uid, tpl_key="digital", product_id="pubg")
    assert cost_prd == 10.5  # 10 * 1.05

    # 4. Floor validation
    ok, floor, msg = await MarkupManager.validate_seller_price(
        seller_price_usd=9.0,
        provider_cost_usd=10.0,
        owner_id=uid,
        tpl_key="digital",
        product_id="pubg",
    )
    assert ok is False
    assert floor == 10.5


@pytest.mark.anyio
async def test_flash_sale_and_floor_protection():
    await db.init()
    bot_id = int(time.time() * 1000) % 900000000 + 22000

    # 1. Create a flash sale
    ok, sale_id, msg = await DiscountManager.create_flash_sale(
        bot_id=bot_id,
        title="تخفيضات العيد",
        scope="all",
        target_id="",
        discount_type="percent",
        discount_value=20.0,
        duration_hours=24.0,
    )
    assert ok is True

    # 2. Calculate discounted price without floor
    disc_price, amt, badge, rem = await DiscountManager.calculate_discounted_price(
        original_price_usd=20.0,
        bot_id=bot_id,
        owner_id=1,
    )
    assert disc_price == 16.0
    assert amt == 4.0
    assert "متبقي" in badge

    # 3. Calculate discounted price with floor protection
    # Provider cost is $15.0, platform markup is 10% ($16.5). Discount would be $14.0, but floor is $16.5
    disc_price_flr, amt_flr, _, _ = await DiscountManager.calculate_discounted_price(
        original_price_usd=20.0,
        bot_id=bot_id,
        owner_id=1,
        provider_cost_usd=15.0,
    )
    assert disc_price_flr >= 16.5


@pytest.mark.anyio
async def test_atomic_dual_refund_workflow():
    await db.init()
    uid = int(time.time() * 1000) % 900000000 + 33000
    buyer_id = uid + 1
    seller_id = uid + 2
    bot_id = uid + 10

    # 1. Setup bot owner
    async with db.Session() as s:
        bot = db.Bot(id=bot_id, owner_id=seller_id, username=f"test_{bot_id}", token="tok", template="digital")
        s.add(bot)
        await s.commit()

    # 2. Add ServiceOrder
    ord_id = f"DUAL-{uid}"
    async with db.Session() as s:
        order = db.ServiceOrder(
            order_id=ord_id,
            tpl_key="digital",
            bot_id=bot_id,
            user_id=buyer_id,
            service_id="netflix",
            service_name="Netflix 1M",
            target="test@netflix.com",
            price_user_usd=5.0,
            cost_platform_usd=3.0,
            cost_provider_usd=2.5,
            status="pending",
        )
        s.add(order)
        await s.commit()

    # 3. شراء حقيقي أولاً: الزبون يدفع 5$ والبائع تُخصم منه تكلفة المنصة 3$
    await ledger.credit_user(bot_id, buyer_id, 5.0, "deposit")
    await ledger.credit_seller(seller_id, 3.0, "deposit")
    ok_p, why, bal_after = await ledger.purchase(bot_id=bot_id, buyer_id=buyer_id, price_usd=5.0,
                                                 seller_id=seller_id, platform_cost_usd=3.0, order_id=ord_id)
    assert ok_p and why == "ok" and bal_after == 0.0
    assert await ledger.get_seller_balance_usd(seller_id) == 0.0
    # تكرار نفس الطلب لا يخصم مرتين
    ok_dup, why_dup, _ = await ledger.purchase(bot_id=bot_id, buyer_id=buyer_id, price_usd=5.0,
                                               seller_id=seller_id, platform_cost_usd=3.0, order_id=ord_id)
    assert ok_dup and why_dup == "duplicate"

    # 4. الاسترجاع المزدوج يعيد ما دُفع فعلاً بالضبط
    ok, msg, res = await ledger.atomic_dual_refund(ord_id, reason="غير متوفر")
    assert ok is True
    assert res["buyer_refund_usd"] == 5.0
    assert res["seller_refund_usd"] == 3.0
    assert await ledger.get_user_balance_usd(bot_id, buyer_id) == 5.0
    assert await ledger.get_seller_balance_usd(seller_id) == 3.0

    # 5. لا يتكرر الاسترجاع
    ok_retry, msg_retry, _ = await ledger.atomic_dual_refund(ord_id, reason="إعادة محاولة")
    assert ok_retry is False
    assert await ledger.get_user_balance_usd(bot_id, buyer_id) == 5.0


@pytest.mark.anyio
async def test_refund_never_pays_unpaid_order():
    """طلب لم يُدفع (أو دُفع جزئياً) لا يولّد رصيداً من العدم لأي طرف."""
    await db.init()
    uid = int(time.time() * 1000) % 900000000 + 55000
    bot_id, buyer_id, seller_id = uid + 10, uid + 1, uid + 2
    async with db.Session() as s:
        s.add(db.Bot(id=bot_id, owner_id=seller_id, username=f"t_{bot_id}", token="tok", template="digital"))
        s.add(db.ServiceOrder(order_id=f"FREE-{uid}", tpl_key="digital", bot_id=bot_id, user_id=buyer_id,
                              service_id="x", service_name="x", target="x", price_user_usd=9.0,
                              cost_platform_usd=7.0, cost_provider_usd=6.0, status="pending"))
        await s.commit()
    ok, _, res = await ledger.atomic_dual_refund(f"FREE-{uid}")
    assert ok and res["buyer_refund_usd"] == 0.0 and res["seller_refund_usd"] == 0.0
    assert await ledger.get_user_balance_usd(bot_id, buyer_id) == 0.0
    assert await ledger.get_seller_balance_usd(seller_id) == 0.0


@pytest.mark.anyio
async def test_purchase_is_all_or_nothing():
    """إن لم يكفِ رصيد البائع لا يُخصم شيء من الزبون، وإن لم يكفِ رصيد الزبون لا يُخصم شيء من البائع."""
    await db.init()
    uid = int(time.time() * 1000) % 900000000 + 66000
    bot_id, buyer_id, seller_id = uid + 10, uid + 1, uid + 2
    await ledger.credit_user(bot_id, buyer_id, 10.0, "deposit")
    await ledger.credit_seller(seller_id, 1.0, "deposit")
    ok, why, bal = await ledger.purchase(bot_id=bot_id, buyer_id=buyer_id, price_usd=8.0,
                                         seller_id=seller_id, platform_cost_usd=5.0, order_id=f"A-{uid}")
    assert not ok and why == "seller_insufficient" and bal == 10.0
    assert await ledger.get_seller_balance_usd(seller_id) == 1.0

    await ledger.credit_seller(seller_id, 10.0, "deposit")
    ok, why, bal = await ledger.purchase(bot_id=bot_id, buyer_id=buyer_id, price_usd=50.0,
                                         seller_id=seller_id, platform_cost_usd=5.0, order_id=f"B-{uid}")
    assert not ok and why == "insufficient_balance" and bal == 10.0
    assert await ledger.get_seller_balance_usd(seller_id) == 11.0


@pytest.mark.anyio
async def test_concurrent_debits_never_overspend():
    """عشرون خصماً متزامناً على رصيد يكفي خمسة فقط: ينجح خمسة بالضبط ولا يصبح الرصيد سالباً."""
    import asyncio
    await db.init()
    uid = int(time.time() * 1000) % 900000000 + 77000
    await ledger.credit_user(uid, uid, 5.0, "deposit")
    res = await asyncio.gather(*[ledger.debit_user(uid, uid, 1.0, "order") for _ in range(20)])
    assert sum(1 for ok, _, _ in res if ok) == 5
    assert await ledger.get_user_balance_usd(uid, uid) == 0.0


@pytest.mark.anyio
async def test_first_deposit_bonus():
    await db.init()
    seller_id = int(time.time() * 1000) % 900000000 + 44000

    # Enable bonus in config
    await db.kv_set(0, "sys:bonus_config", {
        "enabled": True,
        "type": "percent",
        "value": 20.0,
        "min_deposit": 10.0,
        "max_bonus": 50.0,
        "expires_at": None,
    })

    # Below min deposit
    ok1, amt1, _ = await ledger.apply_first_deposit_bonus(seller_id, 5.0)
    assert ok1 is False

    # Valid first deposit of $100 -> 20% capped at $50
    ok2, amt2, _ = await ledger.apply_first_deposit_bonus(seller_id, 100.0)
    assert ok2 is True
    assert amt2 == 20.0

    # Cannot get bonus again
    ok3, amt3, _ = await ledger.apply_first_deposit_bonus(seller_id, 100.0)
    assert ok3 is False


def test_bulk_import_quick_text_and_excel():
    # 1. Quick text parsing
    text = """
    60 UC | 0.99
    325 UC | 4.80
    ألعاب | فري فاير | 100 جوهرة | 1.20 | 0.80
    """
    items = BulkImportManager.parse_quick_text(text)
    assert len(items) == 3
    assert items[0]["option_name"] == "60 UC"
    assert items[0]["price_usd"] == 0.99
    assert items[2]["category"] == "ألعاب"

    # 2. Sample Excel generation and parsing
    excel_bytes = BulkImportManager.generate_sample_excel()
    assert len(excel_bytes) > 100
    rows, errs = BulkImportManager.parse_excel_or_csv(excel_bytes, "template.xlsx")
    assert len(rows) >= 5
    assert len(errs) == 0


@pytest.mark.anyio
async def test_price_floor_and_catalog_mapping():
    """البائع لا يبيع أبداً بأقل من سعر المنصة، والمدير يربط المنتجات بأرقام خدمات المزود وتكلفتها الحقيقية."""
    from forge.modules import catalog
    from forge.modules.markup import MarkupManager
    from forge.modules.providers.smm import SMMManager
    from forge.modules.providers.sms import SMSManager
    await db.init()
    uid = int(time.time() * 1000) % 900000000 + 88000
    bot_id, owner = uid + 10, uid + 2
    async with db.Session() as s:
        s.add(db.Bot(id=bot_id, owner_id=owner, username=f"fl_{bot_id}", token="tok", template="smm"))
        await s.commit()
    await MarkupManager.set_margin_rule("tpl:smm", "percent", 50.0, admin_id=1)
    await MarkupManager.set_margin_rule("tpl:sms", "percent", 50.0, admin_id=1)
    await db.kv_set(bot_id, "smm:margin", {"type": "percent", "val": 0.0})        # البائع بلا ربح
    await db.kv_set(bot_id, "sms:margin", {"type": "percent", "val": 0.0})
    await db.kv_set(bot_id, "smm:services_override", {"ig_likes_hq": {"custom_price_usd": 0.01}})  # سعر أقل من التكلفة
    cat = {x["id"]: x for x in await SMMManager.get_services_catalog(bot_id)}
    for x in cat.values():
        assert x["price_per_1k_usd"] >= round(x["base_cost_per_1k"] * 1.5, 4) - 0.0001
    # ربط بالمزود وتكلفة حقيقية وإخفاء
    upd, errs = catalog.parse_lines("ig_likes_hq | 4455 | 0.30\nig_followers_fast | off\nbad line without pipe")
    assert len(upd) == 2 and len(errs) == 1
    for iid, e in upd:
        await catalog.set_entry("smm", iid, **e)
    cat = {x["id"]: x for x in await SMMManager.get_services_catalog(bot_id)}
    assert "ig_followers_fast" not in cat
    assert cat["ig_likes_hq"]["base_cost_per_1k"] == 0.30 and cat["ig_likes_hq"]["price_per_1k_usd"] >= 0.45
    assert catalog.provider_service(await catalog.get_map("smm"), "ig_likes_hq") == "4455"
    # الأرقام: سعر مخصص منخفض لا يكسر الأرضية
    await db.kv_set(bot_id, "sms:overrides", {"iq_tg": {"price_usd": 0.01}})
    base = await SMSManager.platform_base("iq", "tg")
    assert await SMSManager.calculate_number_price(bot_id, "iq", "tg") >= round(base * 1.5, 2)
    await db.kv_set(0, "sys:markup_rules", {})
    await db.kv_set(0, "smm:catalog_map", {})
