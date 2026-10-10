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

    # 3. Perform dual refund
    ok, msg, res = await ledger.atomic_dual_refund(ord_id, reason="غير متوفر")
    assert ok is True
    assert res["buyer_refund_usd"] == 5.0
    assert res["seller_refund_usd"] == 3.0

    # 4. Check balances
    bal_buyer = await ledger.get_user_balance_usd(bot_id, buyer_id)
    bal_seller = await ledger.get_seller_balance_usd(seller_id)
    assert bal_buyer >= 5.0
    assert bal_seller >= 3.0

    # 5. Check Idempotency - cannot refund again
    ok_retry, msg_retry, _ = await ledger.atomic_dual_refund(ord_id, reason="إعادة محاولة")
    assert ok_retry is False


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
