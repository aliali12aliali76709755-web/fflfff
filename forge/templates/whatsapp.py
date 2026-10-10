"""رابط واتساب: يحوّل رقماً مع رمز الدولة إلى رابط wa.me يفتح محادثة مباشرة.

لا يحتاج حفظ الرقم في جهات الاتصال، ويمكن إرفاق رسالة جاهزة تُكتب عند الفتح.
لا يحتاج القالب أي إعداد.
"""
from __future__ import annotations

import re
from urllib.parse import quote

from .. import ui
from ..ctx import Ctx
from ..ui import B, esc, kb
from . import Tpl
from ._util import bump


def clean_number(raw: str) -> str | None:
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("00"):
        digits = digits[2:]
    return digits if 8 <= len(digits) <= 15 else None


class WhatsAppTpl(Tpl):
    emoji, ar, en = "📱", "رابط واتساب", "WhatsApp link"
    d_ar, d_en = "حوّل رقماً إلى رابط محادثة واتساب", "Turn a number into a WhatsApp chat link"
    guide_ar = (
        "المستخدم يرسل رقم هاتف مع رمز الدولة، فيعطيه البوت رابط واتساب يفتح محادثة "
        "مباشرة دون حفظ الرقم. لإضافة رسالة جاهزة، يكتب الرقم ثم سطراً جديداً ثم الرسالة. "
        "لا يحتاج القالب أي إعداد."
    )
    guide_en = (
        "Users send a phone number with its country code and get a wa.me link that opens "
        "a chat without saving the number. A second line is used as a prefilled message."
    )

    async def home(self, c: Ctx) -> None:
        await c.edit(
            ui.head(c.brand) + "\n" + c.t(
                "📱 أرسل رقم الهاتف مع رمز الدولة، وسأعطيك رابطاً يفتح محادثة واتساب مباشرة "
                "دون حفظ الرقم.\n\nمثال: <code>963999123456</code>\n\n"
                "لإضافة رسالة جاهزة، أرسل الرقم ثم سطراً جديداً ثم الرسالة.",
                "📱 Send a phone number with its country code and I'll give you a link that "
                "opens a WhatsApp chat without saving it.\n\nExample: <code>963999123456</code>\n\n"
                "To add a prefilled message, send the number then the message on a new line."),
            kb([c.tail()]))

    async def owner(self, c: Ctx):
        n = await c.kv("wa:count", 0)
        return c.t(f"📱 روابط أُنشئت: {n}", f"📱 Links created: {n}"), []

    async def msg(self, c: Ctx) -> bool:
        text = (c.text or "").strip()
        if not text:
            return False
        parts = text.split("\n", 1)
        number = clean_number(parts[0])
        message = parts[1].strip() if len(parts) > 1 else ""
        if not number:
            await c.send(c.t("❌ لم أفهم الرقم. أرسل رقماً مع رمز الدولة، مثل <code>963999123456</code>.",
                             "❌ I couldn't read the number. Send it with a country code, e.g. <code>963999123456</code>."))
            return True
        url = f"https://wa.me/{number}"
        if message:
            url += f"?text={quote(message)}"
        await bump(c, "wa:count")
        await c.send(
            c.t(f"✅ رابط واتساب للرقم <code>+{number}</code>:\n{esc(url)}",
                f"✅ WhatsApp link for <code>+{number}</code>:\n{esc(url)}"),
            kb([[B(c.t("💬 فتح المحادثة", "💬 Open chat"), url=url)], c.home_row()]))
        return True


TPL = WhatsAppTpl()
