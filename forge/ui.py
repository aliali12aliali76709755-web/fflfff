"""أدوات الواجهة: الأزرار، الجداول النصية، وإرسال/تعديل الرسائل."""
from __future__ import annotations

import datetime as dt
import html
from typing import Iterable, Sequence

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

LINE = "─────────────────────"


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=False)


_VALID_SCHEMES = ("http://", "https://", "tg://")


def clean_url(u: str | None) -> str | None:
    """يتحقق من صحة الرابط لتيليجرام ويعيد الرابط بعد تنظيفه، أو None إن كان غير صالح."""
    if not u or not isinstance(u, str):
        return None
    u = u.strip()
    if u.startswith("@"):
        u = f"https://t.me/{u[1:]}"
    elif u.startswith("t.me/"):
        u = f"https://{u}"
    if not any(u.startswith(s) for s in _VALID_SCHEMES):
        return None
    try:
        from urllib.parse import urlparse
        parsed = urlparse(u)
        if u.startswith(("http://", "https://")):
            if not parsed.netloc or " " in parsed.netloc or not parsed.hostname:
                return None
        return u
    except Exception:
        return None


def B(text: str, data: str | None = None, *, url: str | None = None, style: str | None = None, **kw):
    """زر شفاف. style: primary | success | danger (ألوان الأزرار في Bot API الحديث)."""
    valid_u = clean_url(url) if url else None
    if valid_u:
        return InlineKeyboardButton(text, url=valid_u, style=style, **kw)
    if data is None and kw:
        return InlineKeyboardButton(text, style=style, **kw)
    return InlineKeyboardButton(text, callback_data=(data or "noop")[:64], style=style, **kw)



def kb(rows: Iterable[Sequence | None]) -> InlineKeyboardMarkup:
    out = []
    for row in rows:
        if not row:
            continue
        if isinstance(row, InlineKeyboardButton):
            row = [row]
        row = [b for b in row if b is not None]
        if row:
            out.append(list(row))
    return InlineKeyboardMarkup(out)


def grid(buttons: Sequence, cols: int = 2) -> list[list]:
    return [list(buttons[i:i + cols]) for i in range(0, len(buttons), cols)]


def head(title: str) -> str:
    return f"<b>{title}</b>\n{LINE}\n"


def rows(pairs: Iterable[tuple[str, object]]) -> str:
    return "\n".join(f"▫️ {esc(k)}: <b>{esc(v)}</b>" for k, v in pairs)


def pct(a: int, b: int) -> str:
    if not b:
        return "+0%" if not a else "+100%"
    v = round((a - b) * 100 / b)
    return f"{'+' if v >= 0 else ''}{v}%"


def tidy(text: str) -> str:
    """تنسيق موحّد: لا سطر فارغ بعد الفاصل، ولا أكثر من سطر فارغ واحد متتالٍ."""
    if not text:
        return text
    text = text.replace(f"{LINE}\n\n", f"{LINE}\n")
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text.strip("\n")


async def show(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str,
               markup: InlineKeyboardMarkup | None = None, *, new: bool = False, **kw):
    """يعدّل رسالة الزر المضغوط إن أمكن، وإلا يرسل رسالة جديدة."""
    text = tidy(text)
    q = update.callback_query
    kw.setdefault("parse_mode", ParseMode.HTML)
    kw.setdefault("disable_web_page_preview", True)
    if q and q.message and not new:
        try:
            return await q.edit_message_text(text, reply_markup=markup, **kw)
        except BadRequest as e:
            msg = str(e).lower()
            if "not modified" in msg:
                return None
            # رسالة وسائط أو قديمة: أرسل جديدة
    chat = update.effective_chat
    if chat is None:
        return None
    return await context.bot.send_message(chat.id, text, reply_markup=markup, **kw)


async def ack(update: Update, text: str | None = None, alert: bool = False) -> None:
    q = update.callback_query
    if q:
        try:
            await q.answer(text, show_alert=alert)
        except Exception:
            pass


_BARS = "▁▂▃▄▅▆▇█"


def spark(values: Sequence[float]) -> str:
    """رسم بياني نصي صغير، مثل ▁▂▅▇ — الأقدم يساراً."""
    vals = [max(0.0, float(v)) for v in values]
    top = max(vals, default=0)
    if top <= 0:
        return _BARS[0] * len(vals)
    return "".join(_BARS[min(7, int(v * 7 / top + 0.5))] for v in vals)


def bar(done: float, total: float, width: int = 10) -> str:
    """شريط تقدّم نصي."""
    k = 0 if total <= 0 else max(0, min(width, round(done * width / total)))
    return "▰" * k + "▱" * (width - k)


def num(n) -> str:
    return f"{int(n):,}"


def dur(seconds: float, lang: str = "ar") -> str:
    """مدة مقروءة: 3 أيام، 5 س 20 د..."""
    s = max(0, int(seconds))
    d, h, m = s // 86400, s % 86400 // 3600, s % 3600 // 60
    ar = lang == "ar"
    if d:
        return (f"{d} يوم" + (f" و{h} س" if h else "")) if ar else (f"{d}d" + (f" {h}h" if h else ""))
    if h:
        return (f"{h} س" + (f" {m} د" if m else "")) if ar else (f"{h}h" + (f" {m}m" if m else ""))
    if m:
        return f"{m} د" if ar else f"{m}m"
    return f"{s} ث" if ar else f"{s}s"


def when(ts, fmt: str = "%Y-%m-%d %H:%M") -> str:
    """وقت محلي حسب TZ_HOURS. يقبل epoch أو datetime بتوقيت UTC."""
    from . import config
    if not isinstance(ts, dt.datetime):
        ts = dt.datetime.utcfromtimestamp(float(ts))
    return (ts + dt.timedelta(hours=config.TZ_HOURS)).strftime(fmt)


def html_of(msg) -> str:
    """نص الرسالة بصيغة HTML آمنة (يشمل تعليق الوسائط)."""
    if msg is None:
        return ""
    return msg.text_html or msg.caption_html or ""
