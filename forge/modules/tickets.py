"""نظام تذاكر الدعم الفني الداخلي المتقدم داخل البوت.
- يدعم أقساماً متعددة (مبيعات، شكاوى، دعم فني...).
- يرسل التذكرة لحسابات المشرفين المحددة من البائع.
- يدعم الرد بالـ Reply المباشر أو بزر [رد على التذكرة].
- يرجع الرد للزبون داخل البوت نفسه مع حفظ السجل بالكامل.
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Any
from sqlalchemy import select, and_
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import TelegramError

from forge import db

log = logging.getLogger("forge.tickets")


class TicketManager:
    """إدارة دورة حياة تذاكر الدعم الفني."""

    @staticmethod
    def _kb(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(text=t, callback_data=d) for t, d in r]
            for r in rows
        ])

    @classmethod
    async def create_ticket(
        cls,
        *,
        bot_id: int,
        user_id: int,
        user_name: str,
        username: str,
        dept_key: str,
        dept_name: str,
        initial_text: str,
        photo_id: str = "",
    ) -> tuple[bool, str, db.SupportTicket | None]:
        """ينشئ تذكرة دعم فني جديدة ويحفظ الرسالة الأولى."""
        now = dt.datetime.utcnow()
        ticket_id = f"TCK-{int(now.timestamp()) % 1000000}-{user_id % 1000}"

        async with db.Session() as s:
            ticket = db.SupportTicket(
                ticket_id=ticket_id,
                bot_id=bot_id,
                user_id=user_id,
                user_name=user_name[:120],
                username=username[:60],
                dept_key=dept_key,
                dept_name=dept_name,
                status="open",
                created=now,
            )
            s.add(ticket)

            msg = db.TicketMessage(
                ticket_id=ticket_id,
                bot_id=bot_id,
                sender_type="user",
                sender_id=user_id,
                text=initial_text,
                photo_id=photo_id,
                created=now,
            )
            s.add(msg)
            await s.commit()

        log.info("Ticket created: %s by user %d in bot %d", ticket_id, user_id, bot_id)
        return True, ticket_id, ticket

    @classmethod
    async def dispatch_ticket_to_staff(
        cls,
        bot_api: Bot,
        ticket_id: str,
        staff_chat_id: int,
    ) -> bool:
        """يرسل بطاقة التذكرة لحساب المشرف مع أزرار التحكم والرد."""
        async with db.Session() as s:
            ticket = (await s.execute(
                select(db.SupportTicket).where(db.SupportTicket.ticket_id == ticket_id)
            )).scalars().first()
            if not ticket:
                return False

            first_msg = (await s.execute(
                select(db.TicketMessage)
                .where(db.TicketMessage.ticket_id == ticket_id)
                .order_by(db.TicketMessage.created.asc())
            )).scalars().first()

        text_content = first_msg.text if first_msg else ""
        user_ref = f"@{ticket.username}" if ticket.username else f"<code>{ticket.user_id}</code>"

        card_text = (
            f"🎫 <b>تذكرة دعم جديدة #{ticket.ticket_id}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>الزبون:</b> {ticket.user_name} ({user_ref})\n"
            f"🏢 <b>القسم:</b> {ticket.dept_name}\n"
            f"🕒 <b>الوقت:</b> {ticket.created.strftime('%H:%M %Y-%m-%d')}\n\n"
            f"💬 <b>نص المشكلة / الاستفسار:</b>\n"
            f"<blockquote>{text_content}</blockquote>\n\n"
            f"<i>💡 يمكنك الرد مباشرة كـ Reply على هذه الرسالة، أو اضغط الزر أدناه.</i>"
        )

        buttons = [
            [("✍️ رد على التذكرة", f"tck:r:{ticket.ticket_id}"), ("🔒 إغلاق التذكرة", f"tck:c:{ticket.ticket_id}")]
        ]
        reply_markup = cls._kb(buttons)

        try:
            if first_msg and first_msg.photo_id:
                sent = await bot_api.send_photo(
                    chat_id=staff_chat_id,
                    photo=first_msg.photo_id,
                    caption=card_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                )
            else:
                sent = await bot_api.send_message(
                    chat_id=staff_chat_id,
                    text=card_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                )

            # حفظ معرّف الرسالة لتسهيل ربط الـ Reply
            async with db.Session() as s:
                row = (await s.execute(
                    select(db.SupportTicket).where(db.SupportTicket.ticket_id == ticket_id)
                )).scalars().first()
                if row:
                    row.staff_id = staff_chat_id
                    row.staff_msg_id = sent.message_id
                    await s.commit()

            return True
        except TelegramError as e:
            log.warning("Failed to dispatch ticket %s to staff %d: %s", ticket_id, staff_chat_id, e)
            return False

    @classmethod
    async def reply_to_ticket(
        cls,
        bot_api: Bot,
        ticket_id: str,
        staff_id: int,
        reply_text: str,
        photo_id: str = "",
    ) -> tuple[bool, str]:
        """يرسل رد المشرف مباشرة إلى الزبون داخل البوت."""
        async with db.Session() as s:
            ticket = (await s.execute(
                select(db.SupportTicket).where(db.SupportTicket.ticket_id == ticket_id)
            )).scalars().first()
            if not ticket:
                return False, "التذكرة غير موجودة."

            if ticket.status == "closed":
                return False, "هذه التذكرة مغلقة حالياً."

            # حفظ رسالة الرد
            msg = db.TicketMessage(
                ticket_id=ticket_id,
                bot_id=ticket.bot_id,
                sender_type="staff",
                sender_id=staff_id,
                text=reply_text,
                photo_id=photo_id,
                created=dt.datetime.utcnow(),
            )
            s.add(msg)
            await s.commit()

        # إيصال الرسالة للزبون داخل البوت
        user_notification = (
            f"📩 <b>رد جديد على تذكرتك #{ticket.ticket_id}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🏢 <b>القسم:</b> {ticket.dept_name}\n\n"
            f"<blockquote>{reply_text}</blockquote>\n\n"
            f"<i>💡 يمكنك إرسال رد إضافي هنا لمتابعة المحادثة مع الدعم.</i>"
        )
        try:
            if photo_id:
                await bot_api.send_photo(
                    chat_id=ticket.user_id,
                    photo=photo_id,
                    caption=user_notification,
                    parse_mode=ParseMode.HTML,
                )
            else:
                await bot_api.send_message(
                    chat_id=ticket.user_id,
                    text=user_notification,
                    parse_mode=ParseMode.HTML,
                )
            return True, "تم إرسال ردك للزبون بنجاح!"
        except TelegramError as e:
            log.warning("Failed to send staff reply to user %d: %s", ticket.user_id, e)
            return False, f"تعذّر إيصال الرد للمستخدم: {e}"

    @classmethod
    async def close_ticket(
        cls,
        bot_api: Bot,
        ticket_id: str,
        closed_by_staff_id: int,
    ) -> tuple[bool, str]:
        """يغلق التذكرة ويخطر الزبون بانتهاء المشكلة."""
        now = dt.datetime.utcnow()
        async with db.Session() as s:
            ticket = (await s.execute(
                select(db.SupportTicket).where(db.SupportTicket.ticket_id == ticket_id)
            )).scalars().first()
            if not ticket:
                return False, "التذكرة غير موجودة."

            ticket.status = "closed"
            ticket.closed_at = now
            await s.commit()

        try:
            await bot_api.send_message(
                chat_id=ticket.user_id,
                text=f"✅ <b>تم إغلاق تذكرة الدعم #{ticket.ticket_id}</b>\n\nنشكر تواصلك معنا! إذا واجهتك أي مشكلة أخرى يمكنك فتح تذكرة جديدة في أي وقت.",
                parse_mode=ParseMode.HTML,
            )
        except TelegramError:
            pass

        return True, f"تم إغلاق التذكرة #{ticket_id} بنجاح."

    @staticmethod
    async def get_ticket_by_msg_id(staff_chat_id: int, msg_id: int) -> db.SupportTicket | None:
        """يعيد التذكرة المرتبطة برسالة تم الرد عليها."""
        async with db.Session() as s:
            return (await s.execute(
                select(db.SupportTicket).where(
                    and_(
                        db.SupportTicket.staff_id == staff_chat_id,
                        db.SupportTicket.staff_msg_id == msg_id,
                    )
                )
            )).scalars().first()
