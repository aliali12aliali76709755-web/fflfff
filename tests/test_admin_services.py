import pytest
import time
from forge import db
from forge.modules import ledger
from forge.admin import scr_services_stats


class DummyBot:
    id = 12345
    username = "BotMaker45bot"


class DummyM:
    def __init__(self, uid: int):
        self.uid = uid
        self.fid = 0
        self.bot = DummyBot()
        self.last_text = None
        self.last_kb = None
        self.state = {}

    def set_state(self, k, **data):
        self.state = {"k": k, **data}

    def clear_state(self):
        self.state = {}

    async def show(self, text, reply_markup=None):
        self.last_text = text
        self.last_kb = reply_markup


@pytest.mark.anyio
async def test_admin_services_stats_and_credit():
    await db.init()
    uid = int(time.time() * 1000) % 900000000 + 55500
    m = DummyM(uid=uid)

    # 1. Test scr_services_stats with no orders
    await scr_services_stats(m)
    assert m.last_text is not None
    assert "إحصائيات خدمات ومبيعات المنصة المركزية" in m.last_text

    # 2. Add an order and test again
    async with db.Session() as s:
        order = db.ServiceOrder(
            order_id=f"TEST-{uid}",
            tpl_key="smm",
            bot_id=1,
            user_id=uid + 1,
            service_id="101",
            service_name="Followers Test",
            target="https://instagram.com/test",
            quantity=1000,
            price_user_usd=5.0,
            cost_provider_usd=2.0,
            status="completed",
        )
        s.add(order)
        await s.commit()

    await scr_services_stats(m)
    assert f"TEST-{uid}" in m.last_text

    # 3. Test crediting seller
    ok, tx, bal = await ledger.credit_seller(
        uid,
        50.0,
        "admin_test",
        description="Admin test credit",
    )
    assert ok is True
    assert bal >= 50.0
