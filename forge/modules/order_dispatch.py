"""محرك توجيه وإدارة الطلبات اليدوية (الألعاب، الاشتراكات، التطبيقات).
- إرسال بطاقة الطلب التفاعلية إلى قناة/قروب الإدارة وإلى المالك.
- أزرار التحكم الفوري: تسليم، رفض مع سبب، استرجاع مزدوج، قيد التنفيذ، تجميد.
- إيصال نتائج التنفيذ للزبون عبر بوت البائع نفسه.
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Any
from sqlalchemy import select
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import TelegramError

from .. import config, crypto, db
from . import ledger

log = logging.getLogger("forge.order_dispatch")


class OrderDispatcher:
    """إدارة وتوزيع طلبات الخدمات اليدوية على الإدارة وقنوات الإشعار."""

    @staticmethod
    def order_buttons(order_id: str) -> InlineKeyboardMarkup:
        """أزرار التحكم التفاعلية على بطاقة الطلب في قناة/قروب الإدارة."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📦 تسليم الطلب", callback_data=f"m:adm:ord_dlv:{order_id}"),
                InlineKeyboardButton("❌ رفض الطلب", callback_data=f"m:adm:ord_rej:{order_id}"),
            ],
            [
                InlineKeyboardButton("🔄 استرجاع مزدوج", callback_data=f"m:adm:ord_rfnd:{order_id}"),
                InlineKeyboardButton("⏳ قيد التنفيذ", callback_data=f"m:adm:ord_prog:{order_id}"),
            ],
            [
                InlineKeyboardButton("❄️ تجميد الطلب", callback_data=f"m:adm:ord_frz:{order_id}"),
            ],
        ])

    @classmethod
    async def dispatch_new_order(
        cls,
        bot_api: Bot,
        order: db.ServiceOrder,
        *,
        bot_username: str = "",
        seller_name: str = "",
        buyer_name: str = "",
        buyer_username: str = "",
    ) -> None:
        # 1. القناة المخصصة للبوت (التي حددها البائع باليوزر أو الآيدي)
        bot_chan_cfg = await db.kv_get(order.bot_id, "store:order_channel", {}) or {}
        bot_chan_id = bot_chan_cfg.get("id")

        # 2. القناة العامة للنظام
        chan_cfg = await db.kv_get(0, "sys:order_channel", {}) or {}
        chan_id = chan_cfg.get("id")

        async with db.Session() as s:
            bot_row = await s.get(db.Bot, order.bot_id)
        owner_id = bot_row.owner_id if bot_row else 0

        buyer_ref = f"@{buyer_username}" if buyer_username else f"<code>{order.user_id}</code>"
        seller_ref = f"@{bot_username}" if bot_username else f"بائع #{order.bot_id}"

        card = (
            f"🚨 <b>طلب يدوي جديد #{order.order_id}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 <b>البوت:</b> {seller_ref} (المالك: {seller_name or '—'})\n"
            f"👤 <b>المشتري:</b> {buyer_name or 'زبون'} ({buyer_ref})\n"
            f"🎮 <b>الخدمة:</b> <b>{order.service_name}</b>\n"
            f"🎯 <b>المطلوب/البيانات:</b> <code>{order.target}</code>\n"
            f"💵 <b>سعر الشراء:</b> <code>${order.price_user_usd:.2f}</code>\n"
            f"🕒 <b>الوقت:</b> {order.created.strftime('%H:%M %Y-%m-%d')}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>اختر إجراءً لتنفيذ الطلب:</i>"
        )
        kb = cls.order_buttons(order.order_id)

        sent_targets = set()

        # إرسال لقناة البوت الخاصة إذا تم ضبطها
        if bot_chan_id:
            try:
                await bot_api.send_message(
                    chat_id=bot_chan_id,
                    text=card,
                    parse_mode=ParseMode.HTML,
                    reply_markup=kb,
                )
                sent_targets.add(bot_chan_id)
            except Exception as e:
                log.warning("Failed to post order %s to bot channel %s: %s", order.order_id, bot_chan_id, e)

        # إرسال للقناة العامة للنظام
        if chan_id and chan_id not in sent_targets:
            try:
                await bot_api.send_message(
                    chat_id=chan_id,
                    text=card,
                    parse_mode=ParseMode.HTML,
                    reply_markup=kb,
                )
                sent_targets.add(chan_id)
            except Exception as e:
                log.warning("Failed to post order %s to channel %s: %s", order.order_id, chan_id, e)

        # إرسال لحساب مالك البوت المباشر
        if owner_id and owner_id not in sent_targets:
            try:
                await bot_api.send_message(
                    chat_id=owner_id,
                    text=card,
                    parse_mode=ParseMode.HTML,
                    reply_markup=kb,
                )
                sent_targets.add(owner_id)
            except Exception:
                pass

        # إرسال للإدارة العامة للنظام
        if config.ADMIN_ID and config.ADMIN_ID not in sent_targets:
            try:
                await bot_api.send_message(
                    chat_id=config.ADMIN_ID,
                    text=card,
                    parse_mode=ParseMode.HTML,
                    reply_markup=kb,
                )
            except Exception:
                pass

    @classmethod
    async def deliver_order(
        cls,
        mgr: Any,
        order_id: str,
        delivery_content: str,
        *,
        photo_id: str = "",
    ) -> tuple[bool, str]:
        """يسلم الطلب ويرسل بيانات التفعيل/الأكواد للمشتري عبر بوت البائع."""
        async with db.Session() as s:
            order = (await s.execute(
                select(db.ServiceOrder).where(db.ServiceOrder.order_id == order_id)
            )).scalars().first()
            if not order:
                return False, "الطلب غير موجود."

            if order.status in ("completed", "refunded"):
                return False, f"لا يمكن تسليم طلب حالته '{order.status}'."

            bot_row = await s.get(db.Bot, order.bot_id)
            order.status = "completed"
            await s.commit()

        # إرسال الرسالة للزبون من بوت البائع
        client_msg = (
            f"🎉 <b>تم تسليم طلبك بنجاح!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"▫️ <b>رقم الطلب:</b> <code>#{order.order_id}</code>\n"
            f"🎮 <b>الخدمة:</b> {order.service_name}\n\n"
            f"📦 <b>بيانات التسليم:</b>\n"
            f"<blockquote>{delivery_content}</blockquote>\n\n"
            f"شكراً لتعاملك معنا ونتمنى لك تجربة ممتعة! ⭐"
        )
        await cls._notify_buyer(mgr, bot_row, order.user_id, client_msg, photo_id)
        return True, f"✅ تم تسليم الطلب #{order_id} بنجاح وإشعار الزبون!"

    @classmethod
    async def reject_order(
        cls,
        mgr: Any,
        order_id: str,
        reason: str,
    ) -> tuple[bool, str]:
        """يرفض الطلب مع إشعار المشتري بالسبب."""
        async with db.Session() as s:
            order = (await s.execute(
                select(db.ServiceOrder).where(db.ServiceOrder.order_id == order_id)
            )).scalars().first()
            if not order:
                return False, "الطلب غير موجود."

            bot_row = await s.get(db.Bot, order.bot_id)
            order.status = "rejected"
            order.refund_reason = reason
            await s.commit()

        client_msg = (
            f"❌ <b>تم تعذّر تنفيذ طلبك #{order.order_id}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎮 <b>الخدمة:</b> {order.service_name}\n"
            f"⚠️ <b>سبب الرفض:</b> {reason}\n\n"
            f"<i>💡 تم إرجاع المبلغ كاملاً إلى رصيدك داخل البوت.</i>"
        )
        await cls._notify_buyer(mgr, bot_row, order.user_id, client_msg)
        return True, f"تم رفض الطلب #{order_id} وإبلاغ الزبون."

    @classmethod
    async def update_status_in_progress(
        cls,
        mgr: Any,
        order_id: str,
    ) -> tuple[bool, str]:
        """يحول حالة الطلب إلى 'قيد التنفيذ' ويخطر الزبون."""
        async with db.Session() as s:
            order = (await s.execute(
                select(db.ServiceOrder).where(db.ServiceOrder.order_id == order_id)
            )).scalars().first()
            if not order:
                return False, "الطلب غير موجود."

            bot_row = await s.get(db.Bot, order.bot_id)
            order.status = "in_progress"
            await s.commit()

        client_msg = (
            f"⏳ <b>طلبك #{order.order_id} قيد التنفيذ الآن!</b>\n\n"
            f"🎮 <b>الخدمة:</b> {order.service_name}\n"
            f"يقوم الفريق الآن بمعالجة طلبك وسيصلك إشعار فوري عند اكتماله."
        )
        await cls._notify_buyer(mgr, bot_row, order.user_id, client_msg)
        return True, f"تم تحويل الطلب #{order_id} إلى قيد التنفيذ وإشعار الزبون."

    @classmethod
    async def freeze_order(
        cls,
        mgr: Any,
        order_id: str,
    ) -> tuple[bool, str]:
        """يجمد الطلب مؤقتاً للتحقق."""
        async with db.Session() as s:
            order = (await s.execute(
                select(db.ServiceOrder).where(db.ServiceOrder.order_id == order_id)
            )).scalars().first()
            if not order:
                return False, "الطلب غير موجود."

            bot_row = await s.get(db.Bot, order.bot_id)
            order.status = "frozen"
            await s.commit()

        client_msg = (
            f"❄️ <b>تنبيه بخصوص طلبك #{order.order_id}</b>\n\n"
            f"تم إيقاف الطلب مؤقتاً لمراجعة البيانات. للتواصل السريع يرجى فتح تذكرة عبر زر الدعم الفني."
        )
        await cls._notify_buyer(mgr, bot_row, order.user_id, client_msg)
        return True, f"تم تجميد الطلب #{order_id} مؤقتاً."

    @classmethod
    async def _notify_buyer(
        cls,
        mgr: Any,
        bot_row: db.Bot | None,
        buyer_id: int,
        text: str,
        photo_id: str = "",
    ) -> None:
        """يرسل رسالة للمشتري عبر كائن البوت الخاص به."""
        if not bot_row or not mgr:
            return
        app = mgr.apps.get(bot_row.id)
        bot_api = app.bot if app else None

        if bot_api:
            try:
                if photo_id:
                    await bot_api.send_photo(chat_id=buyer_id, photo=photo_id, caption=text, parse_mode=ParseMode.HTML)
                else:
                    await bot_api.send_message(chat_id=buyer_id, text=text, parse_mode=ParseMode.HTML)
            except TelegramError as e:
                log.warning("Could not notify buyer %d: %s", buyer_id, e)
