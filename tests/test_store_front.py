"""اختبارات محرك واجهة المتجر والدعم الفني وتذاكر الدعم والأسئلة الشائعة وقناة الطلبات."""
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock
import pytest

from forge import db
from forge.modules.store_front import StoreFront, DEFAULT_FAQS, DEFAULT_SUPPORT_DEPTS
from forge.modules.tickets import TicketManager
from forge.modules.order_dispatch import OrderDispatcher
from forge.modules.bulk_import import BulkImportManager


@pytest.mark.anyio
async def test_store_front_ticket_lifecycle():
    await db.init()
    test_bot_id = int(time.time() * 1000) % 900000000 + 310000
    user_id = 123456789
    staff_id = 987654321

    # 1. إنشاء تذكرة دعم فني جديدة
    ok, tck_id, ticket = await TicketManager.create_ticket(
        bot_id=test_bot_id,
        user_id=user_id,
        user_name="Ali Customer",
        username="ali_cust",
        dept_key="tech",
        dept_name="الدعم الفني والمساعدة",
        initial_text="لدي مشكلة في استلام كود التفعيل",
    )
    assert ok is True
    assert tck_id.startswith("TCK-")
    assert ticket.status == "open"

    # 2. إرسال بطاقة التذكرة للمشرف
    unique_mid = int(time.time() * 1000) % 9000000 + 100000
    mock_bot = MagicMock()
    mock_sent_msg = MagicMock()
    mock_sent_msg.message_id = unique_mid
    mock_bot.send_message = AsyncMock(return_value=mock_sent_msg)
    mock_bot.send_photo = AsyncMock(return_value=mock_sent_msg)

    dispatched = await TicketManager.dispatch_ticket_to_staff(mock_bot, tck_id, staff_id)
    assert dispatched is True
    assert mock_bot.send_message.called

    # التحقق من حفظ staff_msg_id في قاعدة البيانات
    found_ticket = await TicketManager.get_ticket_by_msg_id(staff_id, unique_mid)
    assert found_ticket is not None
    assert found_ticket.ticket_id == tck_id

    # 3. رد المشرف على التذكرة
    ok_reply, reply_msg = await TicketManager.reply_to_ticket(
        mock_bot,
        tck_id,
        staff_id,
        "تم فحص طلبك، يرجى إعادة المحاولة الآن وسيصلك الكود فوراً.",
    )
    assert ok_reply is True
    assert "بنجاح" in reply_msg

    # 4. رد الزبون الإضافي على التذكرة (append_user_message)
    ok_user_reply, user_reply_msg = await TicketManager.append_user_message(
        mock_bot,
        tck_id,
        user_id,
        "Ali Customer",
        "ali_cust",
        "شكراً جزيلاً! وصل الكود بنجاح.",
    )
    assert ok_user_reply is True
    assert "بنجاح" in user_reply_msg

    # 5. إغلاق التذكرة
    ok_close, close_msg = await TicketManager.close_ticket(mock_bot, tck_id, staff_id)
    assert ok_close is True
    assert "تم إغلاق" in close_msg

    # محاولة الرد بعد الإغلاق ترجع خطأ
    ok_closed_reply, _ = await TicketManager.reply_to_ticket(mock_bot, tck_id, staff_id, "رد جديد")
    assert ok_closed_reply is False


@pytest.mark.anyio
async def test_order_dispatcher_with_bot_channel():
    import uuid
    await db.init()
    test_bot_id = int(time.time() * 1000) % 900000000 + 320000
    bot_channel_id = -1001999888777
    rand_ord_id = f"TEST_ORD_{uuid.uuid4().hex[:8]}"

    # تعيين قناة خاصة للبوت
    await db.kv_set(test_bot_id, "store:order_channel", {"id": bot_channel_id, "title": "قناة طلباتي", "username": "@MyOrders"})

    # إنشاء طلب
    async with db.Session() as s:
        order = db.ServiceOrder(
            order_id=rand_ord_id,
            bot_id=test_bot_id,
            user_id=11223344,
            tpl_key="digital",
            service_id="pubg_60uc",
            service_name="60 شدة ببجي",
            target="55667788",
            quantity=1,
            cost_provider_usd=0.7,
            cost_platform_usd=0.0,
            price_user_usd=0.99,
            currency="USD",
            price_user_currency=0.99,
            status="queued",
            provider_name="DigitalFulfillment",
            provider_order_id=f"PROV_{rand_ord_id}",
            details={},
        )
        s.add(order)
        await s.commit()

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    await OrderDispatcher.dispatch_new_order(
        mock_bot,
        order,
        bot_username="my_shop_bot",
        seller_name="متجر المحترف",
        buyer_name="Ahmed",
        buyer_username="ahmed_99",
    )

    # التحقق من إرسال الرسالة إلى قناة البوت الخاصة
    sent_chat_ids = [call.kwargs.get("chat_id") for call in mock_bot.send_message.call_args_list]
    assert bot_channel_id in sent_chat_ids


@pytest.mark.anyio
async def test_bulk_import_excel_csv_text():
    # 1. تحليل نصي سريع
    quick_txt = "60 شدة | 0.99\n325 شدة | 4.80\n660 شدة | 9.50"
    items = BulkImportManager.parse_quick_text(quick_txt)
    assert len(items) == 3
    assert items[0]["option_name"] == "60 شدة"
    assert items[0]["price_usd"] == 0.99

    # 2. إنشاء قالب Excel
    excel_bytes = BulkImportManager.generate_sample_excel()
    assert len(excel_bytes) > 100

    # 3. قراءة ملف Excel المتولد
    rows, errors = BulkImportManager.parse_excel_or_csv(excel_bytes, "sample.xlsx")
    assert len(rows) >= 3
    assert len(errors) == 0
    assert rows[0]["product_name"] != ""
