"""تسجيل الأخطاء غير المتوقعة: ملف، ذاكرة قصيرة، وإشعار مدير المنصة في تيليجرام."""
from __future__ import annotations

import collections
import datetime as dt
import logging
import re
import time
import traceback

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden, NetworkError, TelegramError, TimedOut

from . import config
from .ui import esc

log = logging.getLogger("forge.errors")
RECENT: collections.deque = collections.deque(maxlen=30)
_last_sent: dict[str, float] = {}
QUIET = (Forbidden, TimedOut, NetworkError)


_TOKEN = re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}")


def _redact(text: str) -> str:
    """رسائل الأخطاء قد تحمل رابط Bot API وفيه التوكن؛ لا نحفظه ولا نعرضه."""
    return _TOKEN.sub("<token>", text)


def _ignorable(err: BaseException) -> bool:
    if isinstance(err, BadRequest):
        msg = str(err).lower()
        return any(x in msg for x in ("not modified", "query is too old", "message to edit not found", "message can't be deleted",
                                      "message to delete not found", "chat not found"))
    return isinstance(err, QUIET)


async def handle(update: object, context, where: str) -> None:
    """معالج أخطاء مشترك للصانع والبوتات المصنوعة."""
    err = context.error
    if err is None or _ignorable(err):
        return
    log.error("%s: %s", where, err, exc_info=err)
    short = _redact(f"{type(err).__name__}: {err}")[:300]
    tb = _redact("".join(traceback.format_exception(type(err), err, err.__traceback__)))[-1500:]
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    RECENT.appendleft({"at": stamp, "where": where, "err": short})
    try:
        with open(config.DATA_DIR / "errors.log", "a", encoding="utf-8") as fh:
            fh.write(f"[{stamp}] {where}\n{tb}\n")
    except OSError:
        pass
    # رسالة مهذبة للمستخدم بدل الصمت
    if isinstance(update, Update) and update.effective_chat is not None and update.effective_chat.type == "private":
        try:
            if update.callback_query:
                await update.callback_query.answer("⚠️ حدث خطأ غير متوقع. حاول مرة أخرى.", show_alert=True)
            else:
                await context.bot.send_message(update.effective_chat.id, "⚠️ حدث خطأ غير متوقع. حاول مرة أخرى أو أرسل /start")
        except TelegramError:
            pass
    # إشعار المدير عبر بوت الصانع، مع منع التكرار
    key = f"{where}|{type(err).__name__}|{str(err)[:60]}"
    now = time.time()
    if not config.ADMIN_ID or now - _last_sent.get(key, 0) < 600:
        return
    _last_sent[key] = now
    mgr = context.bot_data.get("manager")
    maker = getattr(mgr, "maker", None)
    if maker is None:
        return
    try:
        await maker.bot.send_message(config.ADMIN_ID, f"🧯 <b>خطأ تقني</b>\n📍 {esc(where)}\n<code>{esc(short)}</code>", parse_mode=ParseMode.HTML)
    except TelegramError:
        pass
