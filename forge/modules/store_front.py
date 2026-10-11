"""الوحدة المشتركة لميزات واجهة المتجر المتقدمة (Store Front Engine):
- الدعم الفني وتذاكر الدعم الداخلي المتقدمة (أقسام، فتح تذكرة، رد المشرف).
- الأسئلة الشائعة التفاعلية (FAQ).
- المتجر الويب الخارجي (Web Store Link).
- التحقق وشرط «قرأت وأوافق» الإجباري قبل الشراء.
- تخصيص أزرار وشكل القائمة الرئيسية ورسالة الترحيب.
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Any
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from .. import db, ui
from ..ctx import Ctx
from ..ui import B, esc, kb
from .tickets import TicketManager

log = logging.getLogger("forge.store_front")

DEFAULT_FAQS = [
    {"q": "كيف يتم تسليم الطلب؟", "a": "الطلبات التلقائية (أرقام، متابعين، نجوم) تُسلّم فورياً عبر النظام، والطلبات اليدوية كالألعاب والاشتراكات تُسلّم خلال دقائق إلى ساعتين كحد أقصى."},
    {"q": "ماذا لو لم يصل كود التفعيل أو الطلب؟", "a": "يتوفر زر استرجاع فوري يعيد كامل المبلغ إلى محفظتك في البوت دون أي خصومات."},
    {"q": "كيف يمكنني شحن رصيدي؟", "a": "اضغط على «💳 شحن المحفظة» واختر نجوم تيليجرام للدفع الفوري، أو الدفع اليدوي عبر المحافظ المتاحة مع إرفاق إشعار التحويل."},
    {"q": "كيف أتواصل مع الدعم الفني؟", "a": "يمكنك الضغط على «📞 الدعم الفني» ثم «🎫 فتح تذكرة جديدة» وكتابة استفسارك ليرد عليك المشرف داخل البوت مباشرة."},
]

DEFAULT_SUPPORT_DEPTS = [
    {"key": "tech", "name": "🛠 الدعم الفني والمساعدة", "staff": ""},
    {"key": "sales", "name": "💼 الاستفسارات والمبيعات", "staff": ""},
    {"key": "complaints", "name": "⚠️ الشكاوى والاقتراحات", "staff": ""},
]


class StoreFront:
    """محرك ميزات واجهة المتجر والدعم الفني والأسئلة الشائعة."""

    # ───────────────────────────── الدعم الفني ─────────────────────────────

    @classmethod
    async def show_support_menu(cls, c: Ctx) -> None:
        """يعرض أقسام الدعم الفني وخيارات التواصل / التذاكر."""
        t = c.t
        bot_id = c.bot_id
        depts = await c.kv("store:support_depts", DEFAULT_SUPPORT_DEPTS)
        ext_link = await c.kv("store:support_ext_link", "")
        ext_user = await c.kv("store:support_ext_user", "")

        text = (
            ui.head(t("📞 مركز الدعم الفني والمساعدة", "📞 Support Center")) +
            t(
                "مرحباً بك! فريق الدعم جاهز لمساعدتك وحل أي استفسار أو مشكلة تواجهك.\n\n"
                "اختر القسم المناسب لفتح تذكرة مباشرة مع المشرفين:",
                "Welcome to Support Center! Select a department to open a ticket:"
            )
        )

        rows = []
        for d in depts:
            rows.append([B(f"{d['name']}", f"sf:tck_dept:{d['key']}")])

        ext_row = []
        if ext_link:
            ext_row.append(B(t("💬 قناة / قروب الدعم", "💬 Support Channel"), url=ext_link))
        if ext_user:
            clean_u = ext_user.lstrip("@")
            ext_row.append(B(t("👤 تحدث مع المشرف", "👤 Chat with Staff"), url=f"https://t.me/{clean_u}"))
        if ext_row:
            rows.append(ext_row)

        rows.append([B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")])
        await c.edit(text, kb(rows))

    @classmethod
    async def prompt_open_ticket(cls, c: Ctx, dept_key: str) -> None:
        """يطلب من الزبون كتابة مشكلته وإرسال نص أو صورة."""
        t = c.t
        depts = await c.kv("store:support_depts", DEFAULT_SUPPORT_DEPTS)
        dept = next((d for d in depts if d["key"] == dept_key), {"name": "الدعم الفني", "key": dept_key})

        c.set_state("sf_ticket_input", dept_key=dept_key, dept_name=dept["name"])
        await c.edit(
            ui.head(f"🎫 فتح تذكرة جديدة — {dept['name']}") +
            t(
                "أرسل رسالتك أو مشكلتك الآن (يمكنك إرسال نص أو صورة مع توضيح):\n\n"
                "<i>سيتم إيصال رسالتك فوراً لمشرف القسم وسيرد عليك داخل البوت.</i>\n\n"
                "/cancel للإلغاء",
                "Send your issue or message now (text or photo):\n\n/cancel to abort"
            ),
            kb([[B(t("❌ إلغاء", "❌ Cancel"), "sf:support")]])
        )

    @classmethod
    async def handle_ticket_submission(cls, c: Ctx, st: dict[str, Any]) -> bool:
        """يعالج استلام تذكرة جديدة ويرسلها للمشرف المخصص."""
        dept_key = st.get("dept_key", "tech")
        dept_name = st.get("dept_name", "الدعم الفني")
        text_content = c.text or (c.msg.caption if c.msg else "") or "صورة مرفقة"
        photo_id = c.msg.photo[-1].file_id if (c.msg and c.msg.photo) else ""

        ok, tck_id, ticket = await TicketManager.create_ticket(
            bot_id=c.bot_id,
            user_id=c.uid,
            user_name=c.name,
            username=c.user.username or "",
            dept_key=dept_key,
            dept_name=dept_name,
            initial_text=text_content,
            photo_id=photo_id,
        )
        c.clear_state()

        if not ok:
            await c.send("⚠️ حدث خطأ أثناء إنشاء التذكرة، يرجى المحاولة لاحقاً.")
            return True

        # البحث عن المشرف المخصص للقسم أو مالك البوت
        depts = await c.kv("store:support_depts", DEFAULT_SUPPORT_DEPTS)
        target_staff = None
        for d in depts:
            if d["key"] == dept_key and d.get("staff"):
                val = str(d["staff"]).strip()
                if val.lstrip("-").isdigit():
                    target_staff = int(val)
                break

        bot_row = await c.bot_row()
        staff_id = target_staff or (bot_row.owner_id if bot_row else 0)

        if staff_id:
            await TicketManager.dispatch_ticket_to_staff(c.bot, tck_id, staff_id)

        await c.send(
            c.t(
                f"✅ <b>تم فتح تذكرتك بنجاح!</b>\n\n"
                f"🎫 <b>رقم التذكرة:</b> <code>#{tck_id}</code>\n"
                f"🏢 <b>القسم:</b> {dept_name}\n\n"
                f"وصلت رسالتك إلى فريق الدعم وسيصلك ردهم هنا داخل البوت قريباً.",
                f"✅ <b>Ticket #{tck_id} opened!</b> Staff will reply soon."
            ),
            kb([[B(c.t("📞 مركز الدعم", "📞 Support"), "sf:support"),
                 B(c.t("⬅️ الرئيسية", "⬅️ Home"), "t:home")]])
        )
        return True

    # ───────────────────────────── الأسئلة الشائعة (FAQ) ─────────────────────────────

    @classmethod
    async def show_faq_list(cls, c: Ctx) -> None:
        """يعرض قائمة الأسئلة الشائعة كأزرار قابلة للضغط."""
        t = c.t
        faqs = await c.kv("store:faqs", DEFAULT_FAQS)

        text = (
            ui.head(t("❓ الأسئلة الشائعة والأجوبة", "❓ FAQ")) +
            t("اضغط على أي سؤال لقراءة إجابته بالتفصيل:", "Tap any question to view its answer:")
        )

        rows = []
        for idx, item in enumerate(faqs):
            rows.append([B(f"🔹 {item['q']}", f"sf:faq_view:{idx}")])
        rows.append([B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")])

        await c.edit(text, kb(rows))

    @classmethod
    async def show_faq_item(cls, c: Ctx, idx: int) -> None:
        """يعرض جواب السؤال المحدد مع زر رجوع."""
        t = c.t
        faqs = await c.kv("store:faqs", DEFAULT_FAQS)
        if idx < 0 or idx >= len(faqs):
            await cls.show_faq_list(c)
            return

        item = faqs[idx]
        text = (
            ui.head(f"❓ {item['q']}") +
            f"\n<blockquote>{esc(item['a'])}</blockquote>\n"
        )
        rows = [
            [B(t("⬅️ كل الأسئلة الشائعة", "⬅️ All Questions"), "sf:faq")],
            [B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")],
        ]
        await c.edit(text, kb(rows))

    # ───────────────────────────── شاشة المتجر الويب ─────────────────────────────

    @classmethod
    async def get_webstore_url(cls, c: Ctx) -> str:
        """يعيد رابط المتجر الخارجي إن وجد."""
        return await c.kv("store:webstore_url", "") or ""

    # ───────────────────────────── شرط «قرأت وأوافق» ─────────────────────────────

    @classmethod
    async def show_terms_agreement(
        cls,
        c: Ctx,
        *,
        title: str,
        price_disp: str,
        terms_text: str,
        confirm_callback: str,
        cancel_callback: str,
    ) -> None:
        """يعرض شروط وتنبيهات المنتج مع زر إجباري «قرأت وأوافق» لفتح زر الشراء."""
        t = c.t
        terms_body = terms_text or (
            "1. تأكد من صحة بيانات الحساب والآيدي المدخلة، لا يتحمل المتجر مسؤولية البيانات الخاطئة.\n"
            "2. تأكد من تفعيل استقبال الرسائل أو الصداقة إن كانت الخدمة تتطلب ذلك.\n"
            "3. بمجرد تأكيد الطلب، سيتم خصم الرصيد تلقائياً والبدء في التنفيذ."
        )

        text = (
            ui.head(t("⚠️ شروط وتنبيهات الخدمة", "⚠️ Terms & Conditions")) +
            f"📌 <b>الخدمة:</b> {esc(title)}\n"
            f"💵 <b>السعر:</b> <code>{price_disp}</code>\n\n"
            f"📋 <b>الشروط الإلزامية:</b>\n"
            f"<blockquote>{esc(terms_body)}</blockquote>\n\n"
            f"<i>💡 يجب الموافقة على الشروط للمتابعة إلى الدفع والتنفيذ:</i>"
        )

        rows = [
            [B(t("✅ قرأت وأوافق على الشروط", "✅ I Agree to Terms"), confirm_callback, style="success")],
            [B(t("❌ إلغاء", "❌ Cancel"), cancel_callback, style="danger")],
        ]
        await c.edit(text, kb(rows))
