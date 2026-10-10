"""معرفة الآيدي: يعرض للمستخدم آيديه واسمه ويوزره ولغته.

رقم الهاتف لا يكشفه تيليجرام للبوت تلقائياً (حمايةً للخصوصية)، لذا يظهر زر
«إظهار رقمي» يشارك به المستخدم رقمه بنفسه. كما يعرض آيدي أي رسالة معاد توجيهها
إن لم يكن صاحبها مخفياً. لا يحتاج القالب أي إعداد.
"""
from __future__ import annotations

from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

from .. import ui
from ..ctx import Ctx
from ..ui import esc, kb
from . import Tpl
from ._util import bump


def _card(c: Ctx, phone: str | None = None) -> str:
    u = c.user
    uname = f"@{u.username}" if u and u.username else c.t("لا يوجد", "none")
    lines = [
        ui.head(c.t("🪪 معلومات حسابك", "🪪 Your account")),
        c.t(f"🆔 الآيدي: <code>{u.id}</code>", f"🆔 ID: <code>{u.id}</code>"),
        c.t(f"📛 الاسم: {esc(u.full_name)}", f"📛 Name: {esc(u.full_name)}"),
        c.t(f"🔖 اليوزر: {esc(uname)}", f"🔖 Username: {esc(uname)}"),
        c.t(f"🌐 اللغة: {esc(u.language_code or '—')}", f"🌐 Language: {esc(u.language_code or '—')}"),
    ]
    if phone:
        lines.append(c.t(f"📞 الهاتف: <code>{esc(phone)}</code>", f"📞 Phone: <code>{esc(phone)}</code>"))
    return "\n".join(lines)


class GetIdTpl(Tpl):
    emoji, ar, en = "🆔", "معرفة الآيدي", "Get my ID"
    d_ar, d_en = "اعرف آيديك واسمك ويوزرك", "Get your ID, name and username"
    guide_ar = (
        "عند الضغط على «بدء» يعرض البوت للمستخدم آيديه واسمه ويوزره ولغته. رقم الهاتف "
        "لا يكشفه تيليجرام تلقائياً، فيظهر زر «إظهار رقمي» ليشاركه المستخدم بنفسه. "
        "كما يعرض آيدي أي رسالة تُعاد توجيهها للبوت. لا يحتاج القالب أي إعداد."
    )
    guide_en = (
        "On Start the bot shows the user's ID, name, username and language. Telegram does "
        "not reveal phone numbers to bots, so a Share-my-number button lets the user share it. "
        "Forwarding a message also reveals its sender's ID."
    )

    async def home(self, c: Ctx) -> None:
        await c.edit(_card(c), kb([c.tail()]))
        # لوحة مفاتيح لمشاركة الرقم (اختياري من المستخدم)
        try:
            rkb = ReplyKeyboardMarkup(
                [[KeyboardButton(c.t("📞 إظهار رقمي", "📞 Share my number"), request_contact=True)]],
                resize_keyboard=True)
            await c.bot.send_message(
                c.chat.id,
                c.t("لإظهار رقمك اضغط الزر بالأسفل، أو أعد توجيه رسالة لمعرفة آيدي مصدرها.",
                    "Tap below to reveal your number, or forward a message to see its sender's ID."),
                reply_markup=rkb)
        except Exception:
            pass

    async def owner(self, c: Ctx):
        n = await c.kv("gid:count", 0)
        return c.t(f"🆔 استعلامات: {n}", f"🆔 Lookups: {n}"), []

    async def msg(self, c: Ctx) -> bool:
        m = c.msg

        # مشاركة جهة اتصال
        if m.contact is not None:
            phone = m.contact.phone_number if m.contact.user_id == c.uid else None
            await bump(c, "gid:count")
            extra = "" if phone else c.t("\n\n(الرقم المشارَك ليس رقمك أنت.)",
                                         "\n\n(The shared number isn't yours.)")
            await c.bot.send_message(
                c.chat.id, _card(c, phone) + extra,
                parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
            return True

        # رسالة معاد توجيهها
        origin = getattr(m, "forward_origin", None)
        if origin is not None:
            sender = getattr(origin, "sender_user", None) or getattr(origin, "sender_chat", None)
            if sender is None:
                await c.send(c.t("🔒 مصدر الرسالة مخفٍ لإعادة التوجيه، فلا يمكن معرفة آيديه.",
                                 "🔒 The sender hid forwarding, so their ID isn't available."),
                             kb([c.home_row()]))
                return True
            name = getattr(sender, "full_name", None) or getattr(sender, "title", "—")
            uname = f"@{sender.username}" if getattr(sender, "username", None) else c.t("لا يوجد", "none")
            await bump(c, "gid:count")
            await c.send(
                ui.head(c.t("📨 مصدر الرسالة", "📨 Message source")) +
                c.t(f"🆔 الآيدي: <code>{sender.id}</code>\n📛 الاسم: {esc(name)}\n🔖 اليوزر: {esc(uname)}",
                    f"🆔 ID: <code>{sender.id}</code>\n📛 Name: {esc(name)}\n🔖 Username: {esc(uname)}"),
                kb([c.home_row()]))
            return True

        # أي رسالة أخرى: أعد عرض البطاقة
        await bump(c, "gid:count")
        await c.send(_card(c), kb([c.home_row()]))
        return True


TPL = GetIdTpl()
