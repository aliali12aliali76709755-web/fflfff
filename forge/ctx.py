"""سياق موحّد تتعامل معه القوالب بدل Update/Context الخام."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from telegram import InlineKeyboardMarkup, Message, Update
from telegram.constants import ParseMode
from telegram.error import Forbidden, TelegramError
from telegram.ext import ContextTypes

from . import config, db, ui
from .i18n import norm, pick


async def _autodel(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id, mid = context.job.data
    try:
        await context.bot.delete_message(chat_id, mid)
    except TelegramError:
        pass


class Ctx:
    def __init__(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.u, self.x, self.bot = update, context, context.bot
        bd = context.bot_data
        self.bot_id: int = bd["bot_id"]
        self.owner_id: int = bd["owner_id"]
        self.core: dict = bd["core"]
        self.tpl = bd["tpl"]
        self.user = update.effective_user
        self.uid: int = self.user.id if self.user else 0
        self.chat = update.effective_chat
        self.msg: Message | None = update.effective_message
        self.q = update.callback_query
        forced = self.core.get("lang") or "auto"
        self.lang = norm(self.user.language_code if (forced == "auto" and self.user) else forced)
        if forced == "auto" and not self.user:
            self.lang = norm(None)

    # ── نص ──
    def t(self, ar: str, en: str) -> str:
        return pick(self.lang, ar, en)

    @property
    def is_owner(self) -> bool:
        return self.uid == self.owner_id or self.uid in self.core.get("admins", []) or self.is_super

    @property
    def is_super(self) -> bool:
        """مدير المنصة حين يفعّل «دخول غرفة التحكم» لهذا البوت من لوحة الإدارة."""
        bd = self.x.bot_data
        return bool(self.uid and self.uid == config.ADMIN_ID and not bd.get("factory_id") and (bd.get("adm") or {}).get("super"))

    @property
    def name(self) -> str:
        return ui.esc(self.user.full_name) if self.user else ""

    @property
    def brand(self) -> str:
        """عنوان الشاشة الرئيسية للعضو: رمز النوع مع اسم البوت نفسه، لا اسم القالب."""
        name = (self.core.get("idn") or {}).get("name") or self.bot.bot.first_name or self.tpl.name(self.lang)
        return f"{self.tpl.emoji} {ui.esc(name)}"

    @property
    def text(self) -> str:
        return (self.msg.text or self.msg.caption or "").strip() if self.msg else ""

    def link(self, param: str = "") -> str:
        base = f"https://t.me/{self.bot.username}"
        return f"{base}?start={param}" if param else base

    # ── حالة الإدخال ──
    @property
    def st(self) -> dict | None:
        return self.x.user_data.get("st")

    def set_state(self, k: str, **data) -> None:
        self.x.user_data["st"] = {"k": k, **data}

    def clear_state(self) -> None:
        self.x.user_data.pop("st", None)

    # ── إرسال ──
    @property
    def protect(self) -> bool:
        return bool(self.core.get("protect"))

    def track(self, m: Message | None) -> Message | None:
        ad = self.core.get("autodel") or {}
        if m is not None and ad.get("on") and self.x.job_queue is not None:
            self.x.job_queue.run_once(_autodel, int(ad.get("sec", 300)), data=(m.chat_id, m.message_id))
        return m

    async def send(self, text: str, kb: InlineKeyboardMarkup | None = None, chat_id: int | None = None, **kw):
        kw.setdefault("parse_mode", ParseMode.HTML)
        kw.setdefault("disable_web_page_preview", True)
        kw.setdefault("protect_content", self.protect)
        m = await self.bot.send_message(chat_id or self.chat.id, ui.tidy(text), reply_markup=kb, **kw)
        return self.track(m)

    async def edit(self, text: str, kb: InlineKeyboardMarkup | None = None, **kw):
        m = await ui.show(self.u, self.x, text, kb, **kw)
        if not self.q and isinstance(m, Message):
            self.track(m)
        return m

    async def answer(self, text: str | None = None, alert: bool = False) -> None:
        await ui.ack(self.u, text, alert)

    async def _media(self, method: str, file, kb=None, chat_id=None, **kw):
        kw.setdefault("protect_content", self.protect)
        if "caption" in kw:
            kw.setdefault("parse_mode", ParseMode.HTML)
            kw["caption"] = ui.tidy(kw["caption"])
        fn = getattr(self.bot, method)
        m = await fn(chat_id or self.chat.id, file, reply_markup=kb, **kw)
        return self.track(m)

    async def doc(self, file, **kw):
        return await self._media("send_document", file, **kw)

    async def photo(self, file, **kw):
        return await self._media("send_photo", file, **kw)

    async def video(self, file, **kw):
        return await self._media("send_video", file, **kw)

    async def audio(self, file, **kw):
        return await self._media("send_audio", file, **kw)

    async def voice(self, file, **kw):
        return await self._media("send_voice", file, **kw)

    async def sticker(self, file, **kw):
        return await self._media("send_sticker", file, **kw)

    async def copy_to(self, chat_id: int, from_chat: int, mid: int, kb=None):
        return await self.bot.copy_message(chat_id, from_chat, mid, reply_markup=kb, protect_content=self.protect)

    async def notify_owner(self, text: str, kb: InlineKeyboardMarkup | None = None) -> bool:
        try:
            await self.bot.send_message(self.owner_id, text, reply_markup=kb, parse_mode=ParseMode.HTML,
                                        disable_web_page_preview=True)
            return True
        except Forbidden:
            return False
        except TelegramError:
            return False

    # ── ملفات ──
    def tmp(self, suffix: str = "") -> Path:
        return config.TMP_DIR / f"{self.bot_id}_{uuid.uuid4().hex}{suffix}"

    async def download(self, file_id: str, suffix: str = "") -> Path:
        f = await self.bot.get_file(file_id)
        path = self.tmp(suffix)
        await f.download_to_drive(path)
        return path

    def file_of(self) -> tuple[str, str, int] | None:
        """(file_id, نوع, الحجم) لأول وسائط في الرسالة."""
        m = self.msg
        if m is None:
            return None
        if m.photo:
            return m.photo[-1].file_id, "photo", m.photo[-1].file_size or 0
        for kind in ("video", "document", "audio", "voice", "animation", "video_note", "sticker"):
            obj = getattr(m, kind, None)
            if obj:
                return obj.file_id, kind, getattr(obj, "file_size", 0) or 0
        return None

    # ── بيانات ──
    async def kv(self, key: str, default: Any = None) -> Any:
        return await db.kv_get(self.bot_id, key, default)

    async def kv_set(self, key: str, value: Any) -> None:
        await db.kv_set(self.bot_id, key, value)

    async def rec_add(self, kind: str, data: dict, status: str = "", user_id: int | None = None) -> int:
        return await db.rec_add(self.bot_id, kind, data, self.uid if user_id is None else user_id, status)

    async def rec_get(self, rid: int):
        return await db.rec_get(self.bot_id, rid)

    async def rec_list(self, kind: str, **kw):
        return await db.rec_list(self.bot_id, kind, **kw)

    async def rec_count(self, kind: str, **kw) -> int:
        return await db.rec_count(self.bot_id, kind, **kw)

    async def rec_update(self, rid: int, data: dict | None = None, status: str | None = None) -> None:
        await db.rec_update(self.bot_id, rid, data, status)

    async def rec_del(self, rid: int) -> None:
        await db.rec_del(self.bot_id, rid)

    async def save_core(self) -> None:
        await db.kv_set(self.bot_id, "core", self.core)

    # ── أزرار شائعة ──
    def site_on(self) -> bool:
        from . import web
        return web.public() and bool((self.core.get("site") or {}).get("on", True))

    def mini_app(self) -> bool:
        """هل يفتح موقع البوت داخل تيليجرام (تطبيق مصغّر)؟ يتطلب رابطاً عاماً https ومحادثة خاصة."""
        from . import web
        return self.site_on() and web.https() and self.chat is not None and self.chat.type == "private"

    def site_btn(self, ar: str = "🌐 افتح الموقع", en: str = "🌐 Open the website", app_ar: str = "", app_en: str = ""):
        """زر يفتح موقع البوت للعضو: داخل تيليجرام إن كان الرابط https (بتسمية app_*)، وإلا في المتصفح.

        يعيد None إن لم يكن للمنصة رابط عام أو أوقف المالك الموقع.
        """
        if not self.site_on():
            return None
        from . import web
        from .web import sign
        from telegram import InlineKeyboardButton, WebAppInfo
        private = self.chat is not None and self.chat.type == "private"
        url = web.site_url(self.bot.username, sign.user_token(self.bot_id, self.uid) if private else "")
        if self.mini_app():
            return InlineKeyboardButton(self.t(app_ar or ar, app_en or en), web_app=WebAppInfo(url), style="primary")
        return InlineKeyboardButton(self.t(ar, en), url=url)

    def tail(self):
        """آخر صف في الشاشة الرئيسية: مشاركة البوت للعضو، وغرفة التحكم للمالك."""
        from urllib.parse import quote
        row = []
        if self.core.get("share", False) and self.chat is not None and self.chat.type == "private":
            text = self.t("جرّب هذا البوت 👇", "Try this bot 👇")
            row.append(ui.B(self.t("📤 شارك البوت", "📤 Share the bot"), url=f"https://t.me/share/url?url={quote(self.link())}&text={quote(text)}"))
        if self.is_owner:
            row.append(ui.B(self.t("🎛 غرفة التحكم", "🎛 Control room"), "o:home"))
        return row

    def home_row(self):
        """صف الرجوع: للمستخدم «الرئيسية» وللمالك «لوحة المالك» أيضاً."""
        row = [ui.B(self.t("🏠 الرئيسية", "🏠 Home"), "t:home")]
        if self.is_owner:
            row.append(ui.B(self.t("🎛 غرفة التحكم", "🎛 Control room"), "o:home"))
        return row


class Lite:
    """سياق بيانات بلا تحديث تيليجرام: يستخدمه موقع الويب ليستدعي منطق القوالب نفسه."""

    is_owner = False
    q = None

    def __init__(self, bot_id: int, owner_id: int, *, uid: int = 0, lang: str = "ar", name: str = "", bot=None, core: dict | None = None):
        self.bot_id, self.owner_id, self.uid, self.lang, self.bot = bot_id, owner_id, uid, lang, bot
        self.name = ui.esc(name)
        self.core = core or {}

    def t(self, ar: str, en: str) -> str:
        return pick(self.lang, ar, en)

    async def kv(self, key: str, default: Any = None) -> Any:
        return await db.kv_get(self.bot_id, key, default)

    async def kv_set(self, key: str, value: Any) -> None:
        await db.kv_set(self.bot_id, key, value)

    async def rec_add(self, kind: str, data: dict, status: str = "", user_id: int | None = None) -> int:
        return await db.rec_add(self.bot_id, kind, data, self.uid if user_id is None else user_id, status)

    async def rec_get(self, rid: int):
        return await db.rec_get(self.bot_id, rid)

    async def rec_list(self, kind: str, **kw):
        return await db.rec_list(self.bot_id, kind, **kw)

    async def rec_count(self, kind: str, **kw) -> int:
        return await db.rec_count(self.bot_id, kind, **kw)

    async def rec_update(self, rid: int, data: dict | None = None, status: str | None = None) -> None:
        await db.rec_update(self.bot_id, rid, data, status)

    async def send(self, text: str, kb: InlineKeyboardMarkup | None = None, chat_id: int | None = None, **kw) -> bool:
        if self.bot is None or not (chat_id or self.uid):
            return False
        try:
            await self.bot.send_message(chat_id or self.uid, text, reply_markup=kb, parse_mode=ParseMode.HTML, disable_web_page_preview=True, **kw)
            return True
        except TelegramError:
            return False

    async def notify_owner(self, text: str, kb: InlineKeyboardMarkup | None = None) -> bool:
        return await self.send(text, kb, chat_id=self.owner_id)
