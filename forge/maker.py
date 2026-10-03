"""بوت الصانع: ورشة لبناء البوتات من القوالب، لوحة لكل مستخدم، ولوحة إدارة للمنصة.

يعمل كصانع رئيسي (factory_id = 0) وكقالب «صانع بوتات» داخل بوت مصنوع (factory_id = رقم ذلك البوت).
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
import random
import re
import secrets
import string
import time
from urllib.parse import quote, urlparse

from sqlalchemy import delete, func, select
from telegram import Update
from telegram.constants import ChatType, ParseMode
from telegram.error import Forbidden, InvalidToken, RetryAfter, TelegramError
from telegram.ext import (Application, CallbackQueryHandler, ChatJoinRequestHandler, ChatMemberHandler,
                          CommandHandler, ContextTypes, ManagedBotUpdatedHandler, MessageHandler, filters)

from . import child, config, crypto, db, errors, templates, ui, web
from . import plat as platform
from .i18n import LANGS, LANG_NAMES, norm, pick
from .ui import B, esc, kb

log = logging.getLogger("forge.maker")
TOKEN_RE = re.compile(r"\b(\d{6,12}:[A-Za-z0-9_-]{30,})\b")
LEVELS = [(0, "🥉 مبتدئ", "🥉 Starter"), (100, "🥈 صاعد", "🥈 Rising"), (1000, "🥇 محترف", "🥇 Pro"), (10000, "💎 نخبة", "💎 Elite")]
_last_user_notify: float = 0.0
_SEEN_USERS: set[tuple[int, int]] = set()
_KNOWN_CHANNELS: set[int] = set()
_USER_BATCH_QUEUE: asyncio.Queue = asyncio.Queue()
_BATCH_WORKER_STARTED: bool = False


async def _user_batch_worker() -> None:
    """معالج دفعي خفيف لتسجيل المستخدمين في قاعدة البيانات بدون أي تأخير للبوت."""
    _fail_streak = 0
    while True:
        try:
            # انتظر أول عنصر
            item = await asyncio.wait_for(_USER_BATCH_QUEUE.get(), timeout=5.0)
            _USER_BATCH_QUEUE.task_done()
            batch = [item]
            # جمع المزيد فوراً بدون انتظار
            while len(batch) < 200:
                try:
                    batch.append(_USER_BATCH_QUEUE.get_nowait())
                    _USER_BATCH_QUEUE.task_done()
                except asyncio.QueueEmpty:
                    break
            # كتابة الدفعة في قاعدة البيانات
            async with db.Session() as s:
                for fid, uid, name, username, lang, ref in batch:
                    try:
                        row = await s.get(db.MUser, (fid, uid))
                        if row is None:
                            s.add(db.MUser(
                                factory_id=fid,
                                user_id=uid,
                                name=(name or "")[:128],
                                username=username or "",
                                lang=lang or "",
                                ref_by=ref,
                            ))
                        else:
                            row.name = (name or "")[:128]
                            row.username = username or ""
                    except Exception:
                        pass
                await s.commit()
            _fail_streak = 0
        except asyncio.TimeoutError:
            # لا توجد عناصر، تابع الانتظار
            _fail_streak = 0
            continue
        except asyncio.CancelledError:
            break
        except Exception as e:
            _fail_streak += 1
            wait = min(2 ** _fail_streak, 30)
            log.warning("user batch worker error (streak=%d, wait=%ds): %s", _fail_streak, wait, e)
            await asyncio.sleep(wait)



class M:
    """سياق الصانع لمستخدم واحد."""

    def __init__(self, update: Update | None, context, user=None):
        self.u, self.x, self.bot = update, context, context.bot
        self.fid: int = context.bot_data.get("maker_fid", 0)
        self.mgr = context.bot_data["manager"]
        self.user = user or (update.effective_user if update else None)
        self.uid = self.user.id if self.user else 0
        self.chat_id = (update.effective_chat.id if update and update.effective_chat else self.uid)
        self.msg = update.effective_message if update else None
        self.q = update.callback_query if update else None
        self.udata: dict = context.user_data if update is not None else context.application.user_data[self.uid]
        self.lang = self.udata.get("mlang") or norm(self.user.language_code if self.user else None)

    def t(self, ar: str, en: str) -> str:
        return pick(self.lang, ar, en)

    @property
    def st(self) -> dict | None:
        return self.udata.get("mst")

    def set_state(self, k: str, **d) -> None:
        self.udata["mst"] = {"k": k, **d}

    def clear_state(self) -> None:
        self.udata.pop("mst", None)

    async def show(self, text: str, markup=None, **kw):
        if self.u is None:
            return await self.send(text, markup)
        return await ui.show(self.u, self.x, text, markup, **kw)

    async def send(self, text: str, markup=None, **kw):
        kw.setdefault("parse_mode", ParseMode.HTML)
        kw.setdefault("disable_web_page_preview", True)
        return await self.bot.send_message(self.chat_id, text, reply_markup=markup, **kw)

    async def answer(self, text: str | None = None, alert: bool = False) -> None:
        if self.u is not None:
            await ui.ack(self.u, text, alert)

    @property
    def admin_id(self) -> int:
        """مدير هذا الصانع: مدير المنصة للصانع الرئيسي، أو مالك البوت للصانع الفرعي."""
        return config.ADMIN_ID if self.fid == 0 else self.x.bot_data.get("owner_id", 0)

    @property
    def is_admin(self) -> bool:
        return bool(self.uid) and self.uid == self.admin_id

    async def notify_admin(self, text: str, kind: str | None = None, markup=None) -> None:
        """إشعار مدير هذا الصانع. kind = user | bot يخضع لمفاتيح الإشعارات في إعدادات المنصة."""
        global _last_user_notify
        if not self.admin_id or self.admin_id == self.uid:
            return
        if kind and not (await platform.get(self.fid))["notify"].get(kind, True):
            return
        if kind == "user":
            now_t = time.time()
            if now_t - _last_user_notify < 3.0:
                return
            _last_user_notify = now_t
        try:
            await self.bot.send_message(self.admin_id, text, parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=markup)
        except TelegramError:
            pass

    def home_btn(self):
        return B(self.t("🏠 الرئيسية", "🏠 Home"), "m:home")

    def brand(self) -> str:
        if self.fid:
            return self.bot.bot.first_name
        return config.BRAND if self.lang == "ar" else config.BRAND_EN


# ───────────────────────── المستخدمون والبوابة ─────────────────────────
async def ensure_user(m: M, ref: int = 0) -> bool:
    global _BATCH_WORKER_STARTED
    if not _BATCH_WORKER_STARTED:
        _BATCH_WORKER_STARTED = True
        asyncio.create_task(_user_batch_worker())

    key = (m.fid, m.uid)
    if not ref and key in _SEEN_USERS:
        return False
    if len(_SEEN_USERS) > 200000:
        _SEEN_USERS.clear()
    _SEEN_USERS.add(key)

    # وضع المستخدم في الطابور الخلفي الفوري دون أي قفل لقاعدة البيانات
    name = (m.user.full_name or "")[:128] if m.user else ""
    username = m.user.username or "" if m.user else ""
    _USER_BATCH_QUEUE.put_nowait((m.fid, m.uid, name, username, m.lang, ref if ref != m.uid else 0))

    if m.fid == 0 and not config.ADMIN_ID:
        config.ADMIN_ID = m.uid
        async def _set_admin():
            try:
                await db.kv_set(0, "sys:admin", m.uid)
                await m.bot.send_message(m.uid, "👑 أنت أول من فتح البوت، فأصبحت <b>مدير المنصة</b>.\nسيظهر لك زر «لوحة الإدارة» في القائمة الرئيسية.", parse_mode=ParseMode.HTML)
            except Exception:
                pass
        asyncio.create_task(_set_admin())

    return True


async def gate(m: M) -> bool:
    """يعيد True إن سُمح للمستخدم بالمتابعة (غير محظور، لا صيانة، ومشترك في قنوات الصانع)."""
    if m.is_admin:
        return True
    # استخدام try/except لضمان عدم توقف البوت عند فشل DB أثناء الضغط العالي
    try:
        p = await platform.get(m.fid)
    except Exception:
        log.warning("gate: platform.get failed, allowing user through")
        return True
    if m.uid in p["banned"]:
        text = m.t("🚫 تم إيقاف حسابك في هذا الصانع.", "🚫 Your account is suspended here.")
        await m.answer(text, True) if m.q else await m.send(text)
        return False
    # فحص الحظر في الصانع الرئيسي (فقط إذا كنا في صانع فرعي)
    if m.fid:
        try:
            p0 = await platform.get(0)
            if m.uid in p0["banned"]:
                text = m.t("🚫 تم إيقاف حسابك في هذا الصانع.", "🚫 Your account is suspended here.")
                await m.answer(text, True) if m.q else await m.send(text)
                return False
        except Exception:
            pass
    if p["maintenance"]:
        text = m.t("🛠 الصانع في صيانة قصيرة ويعود بعد قليل. بوتاتك تعمل كالمعتاد.", "🛠 The maker is under brief maintenance. Your bots keep running.")
        await m.answer(text, True) if m.q else await m.send(text)
        return False
    missing = []
    for x in p["fs"]:
        try:
            cm = await m.bot.get_chat_member(x["chat_id"], m.uid)
            if cm.status in ("left", "kicked"):
                missing.append(x)
        except TelegramError:
            continue
    if missing:
        rows = [[B(f"📢 {x['title']}", url=x["url"])] for x in missing if x.get("url")]
        rows.append([B(m.t("✅ اشتركت، افتح الصانع", "✅ Joined, open the maker"), "m:home", style="success")])
        await m.answer()
        await m.send(m.t("🔐 للاستخدام المجاني، اشترك في قناتنا أولاً ثم اضغط الزر.", "🔐 To use the maker for free, join our channel first, then tap the button."), kb(rows))
        return False
    return True



async def my_bots(m: M) -> list[db.Bot]:
    try:
        async with db.Session() as s:
            return list((await s.execute(select(db.Bot).where(db.Bot.factory_id == m.fid, db.Bot.owner_id == m.uid)
                                         .order_by(db.Bot.created.desc()))).scalars().all())
    except Exception as e:
        log.warning("my_bots error: %s", e)
        return []


async def get_bot(m: M, bot_id: int, admin: bool = False) -> db.Bot | None:
    async with db.Session() as s:
        row = await s.get(db.Bot, bot_id)
    if row is None:
        return None
    if admin and m.is_admin and (row.factory_id == m.fid or m.fid == 0):
        return row      # مدير المنصة الرئيسية يصل إلى كل البوتات، ومدير الصانع الفرعي إلى بوتات صانعه
    if row.factory_id != m.fid or row.owner_id != m.uid:
        return None
    return row


async def users_by_bot(ids: list[int]) -> dict[int, int]:
    if not ids:
        return {}
    async with db.Session() as s:
        rows = (await s.execute(select(db.BUser.bot_id, func.count()).where(db.BUser.bot_id.in_(ids)).group_by(db.BUser.bot_id))).all()
    return {b: n for b, n in rows}


LOCK_ICON = {"closed": "🔒", "temp": "⏳", "maint": "🛠"}


def lock_of(b: db.Bot) -> dict | None:
    return platform.lock_of(platform.peek(b.id))


def closed(b: db.Bot) -> bool:
    """مغلق من الإدارة إغلاقاً كاملاً أو مؤقتاً (الصيانة لا تمنع المالك من العمل)."""
    lk = lock_of(b)
    return lk is not None and lk["mode"] != "maint"


def status_icon(b: db.Bot) -> str:
    lk = lock_of(b)
    if lk is not None:
        return LOCK_ICON.get(lk["mode"], "🔒")
    return {"active": "🟢", "disabled": "⏸"}.get(b.status, "⚠️")


def lock_label(m: M, lk: dict) -> str:
    T = m.t
    if lk["mode"] == "maint":
        return T("🛠 في صيانة (من الإدارة)", "🛠 Under maintenance (by the platform)")
    if lk["mode"] == "temp" and lk.get("until"):
        return T(f"⏳ مغلق مؤقتاً — يعود بعد {ui.dur(lk['until'] - time.time(), 'ar')}", f"⏳ Temporarily closed — back in {ui.dur(lk['until'] - time.time(), 'en')}")
    return T("🔒 مغلق من الإدارة", "🔒 Closed by the platform")


def status_text(m: M, b: db.Bot) -> str:
    lk = lock_of(b)
    if lk is not None:
        return lock_label(m, lk)
    if b.status == "active":
        if m.mgr.in_conflict(b.id):
            return m.t("🟠 يعمل، لكن التوكن مستخدم في مكان آخر", "🟠 Running, but the token is used elsewhere")
        return m.t("🟢 يعمل", "🟢 Running")
    if b.status == "disabled":
        return m.t("⏸ متوقف مؤقتاً", "⏸ Paused")
    return m.t("⚠️ يحتاج انتباهك", "⚠️ Needs attention") + (f" — {esc(b.error)}" if b.error else "")


def level(users: int, lang: str) -> tuple[str, str]:
    idx = max(i for i, (need, _, _) in enumerate(LEVELS) if users >= need)
    name = LEVELS[idx][1] if lang == "ar" else LEVELS[idx][2]
    if idx + 1 == len(LEVELS):
        return name, ui.bar(1, 1)
    nxt = LEVELS[idx + 1][0]
    return name, f"{ui.bar(users, nxt)} {ui.num(users)}/{ui.num(nxt)}"


async def _agg(bot_ids: list[int]) -> dict:
    U = db.BUser
    out = {"total": 0, "private": 0, "groups": 0, "banned": 0, "msgs": 0, "active": 0, "new": 0}
    if not bot_ids:
        return out
    day0 = dt.datetime.combine(db.now().date(), dt.time())
    async with db.Session() as s:
        async def n(*cond):
            return int((await s.execute(select(func.count()).select_from(U).where(U.bot_id.in_(bot_ids), *cond))).scalar() or 0)
        out.update(total=await n(), private=await n(U.kind == "private"), groups=await n(U.kind != "private"),
                   banned=await n(U.banned.is_(True)), active=await n(U.last_seen >= day0), new=await n(U.joined >= day0),
                   msgs=int((await s.execute(select(func.coalesce(func.sum(U.msgs), 0)).where(U.bot_id.in_(bot_ids)))).scalar() or 0))
    return out


# ───────────────────────── الرئيسية ─────────────────────────
async def home(m: M, *, new: bool = False) -> None:
    m.clear_state()
    T = m.t
    bots = await my_bots(m)
    head = f"⚡ <b>{esc(m.brand())}</b>\n{T('أهلاً', 'Hi')} {esc(m.user.first_name)} 👋\n{ui.LINE}\n"
    if bots:
        a = await _agg([b.id for b in bots])
        run = sum(1 for b in bots if b.status == "active")
        lv, prog = level(a["total"], m.lang)
        body = T(f"🗂 بوتاتك: <b>{len(bots)}</b>  (🟢 {run} تعمل)\n👥 جمهورك: <b>{ui.num(a['total'])}</b>  ·  🆕 +{a['new']} اليوم\n🏅 مستواك: {lv}\n<code>{prog}</code>",
                 f"🗂 Your bots: <b>{len(bots)}</b>  (🟢 {run} running)\n👥 Audience: <b>{ui.num(a['total'])}</b>  ·  🆕 +{a['new']} today\n🏅 Level: {lv}\n<code>{prog}</code>")
        attention = [b for b in bots if b.status == "error" or m.mgr.in_conflict(b.id) or lock_of(b) is not None]
        if attention:
            body += "\n\n" + T(f"⚠️ {len(attention)} من بوتاتك يحتاج انتباهك — افتح «بوتاتي».", f"⚠️ {len(attention)} of your bots need attention — open “My bots”.")
    else:
        n = len(await available(m))
        body = T("هنا تبني بوت تيليجرام يعمل فعلاً، دون أي برمجة:\n\n① اختر نوع البوت\n② اربطه بتوكن من @BotFather\n③ جهّزه من غرفة التحكم وانشر رابطه\n\n"
                 f"<b>{n}</b> نوعاً جاهزاً بانتظارك، وكلها مجانية.",
                 "Build a real, working Telegram bot without code:\n\n① Pick a bot type\n② Link it with a token from @BotFather\n③ Set it up in its control room and share it\n\n"
                 f"<b>{n}</b> ready-made types, all free.")
    links = []
    if config.UPDATES_URL and m.fid == 0:
        links.append(f'<a href="{config.UPDATES_URL}">{T("📣 جديد الصانع", "📣 What is new")}</a>')
    if config.PRIVACY_URL and m.fid == 0:
        links.append(f'<a href="{config.PRIVACY_URL}">{T("🔏 الخصوصية", "🔏 Privacy")}</a>')
    try:
        await m.show(head + body + tail, kb([
            [B(T("➕ ابنِ بوتاً جديداً", "➕ Build a new bot"), "m:new", style="success")],
            [B(T("🗂 بوتاتي", "🗂 My bots"), "m:bots"), B(T("📊 لوحتي", "📊 My dashboard"), "m:stats")],
            [B(T("🎁 ادعُ أصدقاءك", "🎁 Invite friends"), "m:ref"), B(T("⚙️ الإعدادات", "⚙️ Settings"), "m:set")],
            [B(T("🆘 مساعدة", "🆘 Help"), "m:more"), B(T("🖥 لوحتي على الويب", "🖥 My web dashboard"), "m:web") if bots and web.enabled() else None],
            [B(T("👑 لوحة الإدارة", "👑 Admin panel"), "m:adm:home", style="primary")] if m.is_admin else None,
        ]), new=new)
    except Exception as err:
        log.debug("home show error (flood/rate limit): %s", err)


# ───────────────────────── بناء بوت: اختيار النوع ─────────────────────────
async def available(m: M) -> list:
    off = set((await platform.get(m.fid))["off_tpls"])
    return [t for t in templates.load().values() if t.key not in off]


async def popular(m: M) -> list:
    tpls = {t.key: t for t in await available(m)}
    async with db.Session() as s:
        rows = (await s.execute(select(db.Bot.template, func.count()).where(db.Bot.factory_id == m.fid)
                                .group_by(db.Bot.template).order_by(func.count().desc()).limit(8))).all()
    keys = [k for k, _ in rows if k in tpls]
    keys += [k for k in templates.STARTERS if k in tpls and k not in keys]
    return [tpls[k] for k in keys[:8]]


def _tpl_btn(m: M, t):
    return B(t.title(m.lang) + (" 🌐" if t.site and web.enabled() else ""), f"m:tpl:{t.key}")


async def pick_type(m: M) -> None:
    m.clear_state()
    T = m.t
    tpls = await available(m)
    btns = []
    for k, e, ar, en in templates.CATEGORIES:
        n = sum(1 for t in tpls if k in t.cats)
        if n:
            btns.append(B(f"{e} {T(ar, en)} · {n}", f"m:cat:{k}"))
    await m.show(T("🧭 <b>الخطوة 1 من 3</b> — ماذا تريد أن يفعل بوتك؟\n\nاختر المجال لترى الأنواع المتاحة مع شرح كل نوع.",
                   "🧭 <b>Step 1 of 3</b> — what should your bot do?\n\nPick an area to see the available types with a short description."),
                 kb([[B(T("🔥 الأكثر استخداماً", "🔥 Most used"), "m:cat:hot")]] + ui.grid(btns, 2) +
                    [[B(T(f"📚 كل الأنواع ({len(tpls)})", f"📚 All types ({len(tpls)})"), "m:all:0"), B(T("🔍 بحث", "🔍 Search"), "m:tsearch")], [m.home_btn()]]))


async def cat(m: M, key: str) -> None:
    T = m.t
    if key == "hot":
        title, tpls = T("🔥 الأكثر استخداماً", "🔥 Most used"), await popular(m)
    else:
        info = next((x for x in templates.CATEGORIES if x[0] == key), None)
        if info is None:
            return await pick_type(m)
        title, tpls = f"{info[1]} {T(info[2], info[3])}", [t for t in await available(m) if key in t.cats]
    body = "\n\n".join(f"{t.emoji} <b>{esc(t.name(m.lang))}</b>" + (" 🌐" if t.site and web.enabled() else "") + f"\n{esc(t.desc(m.lang))}" for t in tpls)
    note = T("\n\n🌐 = يأتي معه موقع ويب مرتبط بالبوت.", "\n\n🌐 = comes with a website linked to the bot.") if web.enabled() and any(t.site for t in tpls) else ""
    await m.show(f"<b>{title}</b>\n{ui.LINE}\n{body}{note}\n\n" + T("اضغط النوع الذي يناسبك 👇", "Tap the type that fits you 👇"),
                 kb(ui.grid([_tpl_btn(m, t) for t in tpls], 2) + [[B(T("⬅️ المجالات", "⬅️ Areas"), "m:new"), m.home_btn()]]))


async def all_types(m: M, page: int) -> None:
    tpls = await available(m)
    per = 12
    pages = max(1, (len(tpls) + per - 1) // per)
    page = max(0, min(page, pages - 1))
    nav = [B("‹", f"m:all:{page - 1}") if page else None, B(f"{page + 1} / {pages}", "noop"), B("›", f"m:all:{page + 1}") if page < pages - 1 else None]
    await m.show(m.t(f"📚 <b>كل الأنواع</b> — {len(tpls)} نوعاً", f"📚 <b>All types</b> — {len(tpls)}"),
                 kb(ui.grid([_tpl_btn(m, t) for t in tpls[page * per:(page + 1) * per]], 2) + [nav, [B(m.t("⬅️ المجالات", "⬅️ Areas"), "m:new"), m.home_btn()]]))


def suggest_username() -> str:
    return "".join(random.choices(string.ascii_uppercase, k=3)) + str(random.randint(100, 999)) + "_bot"


async def tpl_card(m: M, key: str) -> None:
    tpls = {t.key: t for t in await available(m)}
    if key not in tpls:
        return await pick_type(m)
    t, T = tpls[key], m.t
    sug = suggest_username()
    m.set_state("token", tpl=key, sug=sug)
    feats = "\n".join(f"  ✓ {esc(f)}" for f in t.feats) if m.lang == "ar" and t.feats else ""
    if t.site and web.enabled():
        feats += ("\n" if feats else "") + T("  🌐 يأتي معه موقع ويب مرتبط بالبوت", "  🌐 Comes with a website linked to the bot")
    text = (f"{t.emoji} <b>{esc(t.name(m.lang))}</b>\n<i>{esc(t.desc(m.lang))}</i>\n" + (f"\n{feats}\n" if feats else "") + f"{ui.LINE}\n" +
            T("🔗 <b>الخطوة 2 من 3</b> — اربط بوتك\n\n1. افتح @BotFather وأرسل <code>/newbot</code>\n2. اختر اسماً، ثم معرّفاً ينتهي بـ <code>bot</code>\n"
              "3. انسخ التوكن الذي يعطيك إياه وألصقه هنا 👇\n\n<i>يمكنك أيضاً تحويل رسالة BotFather كما هي.</i>",
              "🔗 <b>Step 2 of 3</b> — link your bot\n\n1. Open @BotFather and send <code>/newbot</code>\n2. Choose a name, then a username ending in <code>bot</code>\n"
              "3. Copy the token it gives you and paste it here 👇\n\n<i>You can also forward BotFather's message as is.</i>"))
    rows = []
    if config.MANAGED_BOTS and getattr(m.bot.bot, "can_manage_bots", False):
        url = f"https://t.me/newbot/{m.bot.username}/{sug}?name={quote(t.name(m.lang))}"
        rows.append([B(T("⚡ إنشاء فوري بلا توكن", "⚡ Instant creation, no token"), url=url)])
        rows.append([B(T("🎲 اقترح معرّفاً آخر", "🎲 Suggest another username"), f"m:tpl:{key}")])
    back = f"m:cat:{t.cats[0]}" if t.cats else "m:new"
    rows += [[B(T("❓ أول مرة؟ شرح خطوة بخطوة", "❓ First time? Step-by-step help"), f"m:guide:{key}")],
             [B(T("⬅️ نوع آخر", "⬅️ Another type"), back), m.home_btn()]]
    await m.show(text, kb(rows))


async def tpl_guide(m: M, key: str) -> None:
    if key not in templates.load():
        return await pick_type(m)
    t = templates.get(key)
    sug = (m.st or {}).get("sug") or suggest_username()
    m.set_state("token", tpl=key, sug=sug)
    await m.show(m.t(
        f"🪜 <b>طريقة إنشاء بوت «{esc(t.name('ar'))}» لأول مرة</b>\n\n"
        "<b>١.</b> افتح @BotFather واضغط «بدء».\n\n"
        "<b>٢.</b> أرسل له هذه الرسائل بالترتيب، وانتظر ردّه بعد كل واحدة:\n"
        f"• الأمر: <code>/newbot</code>\n• اسم البوت (يظهر للناس): <code>{esc(t.name('ar'))}</code>\n• المعرّف (يجب أن ينتهي بـ bot): <code>{sug}</code>\n\n"
        "إن قال إن المعرّف محجوز، جرّب معرّفاً آخر.\n\n"
        "<b>٣.</b> سيرسل لك رسالة فيها سطر طويل يشبه:\n<code>123456789:AAH…</code>\nهذا هو <b>التوكن</b>. انسخه وألصقه هنا، أو حوّل الرسالة كلها.\n\n"
        "🔒 التوكن يُحفظ مشفّراً ولا يظهر لبقية المستخدمين، ورسالتك تُحذف من المحادثة فوراً.\n\n⏳ بانتظار التوكن…",
        f"🪜 <b>Creating your “{esc(t.name('en'))}” bot for the first time</b>\n\n"
        "<b>1.</b> Open @BotFather and press Start.\n\n<b>2.</b> Send these, one by one:\n"
        f"• Command: <code>/newbot</code>\n• Bot name: <code>{esc(t.name('en'))}</code>\n• Username (must end in bot): <code>{sug}</code>\n\n"
        "<b>3.</b> It replies with a long line like:\n<code>123456789:AAH…</code>\nThat is the <b>token</b>. Paste it here or forward the message.\n\n"
        "🔒 The token is stored encrypted and your message is deleted right away.\n\n⏳ Waiting for the token…"),
        kb([[B(m.t("⬅️ رجوع", "⬅️ Back"), f"m:tpl:{key}")]]))


async def create_bot(m: M, token: str, tpl_key: str) -> None:
    """الخطوة 3: التحقق من التوكن، حفظه مشفّراً، وتشغيل البوت فوراً."""
    T = m.t
    if token == config.MAKER_TOKEN:
        await m.send(T("⚠️ هذا توكن الصانع نفسه. أنشئ بوتاً جديداً من @BotFather.", "⚠️ That's the maker's own token."))
        return
    p = await platform.get(m.fid)
    limit = platform.max_bots(p, m.uid)
    if limit and not m.is_admin and len(await my_bots(m)) >= limit:
        await m.send(T(f"⚠️ وصلت للحد الأقصى ({limit}) من البوتات لكل مستخدم.", f"⚠️ You reached the limit of {limit} bots per user."))
        return
    if tpl_key in p["off_tpls"]:
        await m.send(T("⚠️ هذا النوع غير متاح حالياً.", "⚠️ This type is unavailable right now."))
        return
    wait = await m.send(T("⏳ أتحقق من التوكن وأشغّل بوتك…", "⏳ Checking the token and starting your bot…"))
    try:
        me, hook = await m.mgr.probe(token, webhook=True)
    except (InvalidToken, Forbidden):
        await wait.edit_text(T("❌ التوكن غير صحيح. انسخه كاملاً من @BotFather وأرسله مرة أخرى.", "❌ Invalid token. Copy it fully from @BotFather and send it again."))
        return
    except TelegramError as e:
        await wait.edit_text(T(f"⚠️ تعذّر الاتصال بتيليجرام: {esc(e)}", f"⚠️ Telegram error: {esc(e)}"))
        return
    if me.id in p["blocked_bots"] or me.id in (await platform.get(0))["blocked_bots"]:
        await wait.edit_text(T("⛔ هذا البوت محظور من المنصة ولا يمكن تسجيله.", "⛔ This bot is banned from the platform and cannot be registered."))
        return
    async with db.Session() as s:
        row = await s.get(db.Bot, me.id)
        if row is not None and (row.owner_id != m.uid or row.factory_id != m.fid):
            await wait.edit_text(T("⚠️ هذا البوت مسجّل هنا مسبقاً باسم مستخدم آخر.", "⚠️ This bot is already registered here by someone else."))
            return
        existed = row is not None
        if existed and (lk := platform.lock_of(platform.peek(me.id))) is not None and lk["mode"] != "maint":
            await wait.edit_text(T("🔒 هذا البوت مغلق من الإدارة، ولا يمكن تعديله حتى يُعاد فتحه.", "🔒 This bot is closed by the platform and cannot be changed until it reopens."))
            return
        if row is None:
            row = db.Bot(id=me.id, factory_id=m.fid, owner_id=m.uid, token=crypto.enc(token), template=tpl_key)
            s.add(row)
        else:
            row.token, row.template = crypto.enc(token), tpl_key
        row.username, row.name, row.status, row.error = me.username or "", me.full_name or "", "active", ""
        await s.commit()
    if existed:
        await m.mgr.stop_bot(me.id)
    ok, err = await m.mgr.start_bot(row)
    m.clear_state()
    t = templates.get(tpl_key)
    if ok and m.mgr.apps.get(me.id) is not None:
        m.x.application.create_task(child.apply_identity(m.mgr.apps[me.id], first=True))
    if not ok:
        await wait.edit_text(T(f"⚠️ حُفظ البوت لكن تعذّر تشغيله: {esc(err)}", f"⚠️ Saved but failed to start: {esc(err)}"),
                             reply_markup=kb([[B(T("🗂 بطاقة البوت", "🗂 Bot card"), f"m:b:{me.id}")]]))
        return
    note = ""
    if hook:
        host = urlparse(hook).netloc or hook[:40]
        note = T(f"\n\nℹ️ كان هذا البوت مربوطاً بخدمة أخرى (<code>{esc(host)}</code>) وفصلته عنها. إن أعادت تلك الخدمة ربطه فسيتعارض مع هنا؛ "
                 "للفصل النهائي أرسل /revoke إلى @BotFather ثم حدّث التوكن من بطاقة البوت.",
                 f"\n\nℹ️ This bot was linked to another service (<code>{esc(host)}</code>) and has been detached. If that service re-links it, they will conflict; "
                 "to cut it off for good send /revoke to @BotFather and update the token from the bot card.")
    await wait.edit_text(
        T(f"🎉 <b>الخطوة 3 من 3 — بوتك أصبح حياً!</b>\n\n🤖 @{me.username}\n🧩 {t.title('ar')}\n{ui.LINE}\n"
          "<b>ماذا بعد؟</b>\n① افتح <b>غرفة التحكم</b> داخل بوتك واتبع «🚀 أكمل التجهيز»\n② اضغط «جرّب كمستخدم» لترى ما يراه الناس\n"
          f"③ انشر رابطه: <code>t.me/{me.username}</code>" + (f"\n\n🌐 ولبوتك موقع ويب جاهز: <code>{web.site_url(me.username)}</code>" if t.site and web.public() else "") + note,
          f"🎉 <b>Step 3 of 3 — your bot is live!</b>\n\n🤖 @{me.username}\n🧩 {t.title('en')}\n{ui.LINE}\n"
          "<b>What next?</b>\n① Open the <b>control room</b> inside your bot and set it up\n② Tap “Try as a user” to see what people see\n"
          f"③ Share its link: <code>t.me/{me.username}</code>" + note),
        parse_mode=ParseMode.HTML, disable_web_page_preview=True,
        reply_markup=kb([[B(T("🎛 افتح غرفة التحكم", "🎛 Open control room"), url=f"https://t.me/{me.username}?start=panel")],
                         [B(T("🗂 بطاقة البوت", "🗂 Bot card"), f"m:b:{me.id}"), m.home_btn()]]))
    await m.notify_admin(f"🤖 بوت جديد: @{me.username}\n🧩 {t.title('ar')}\n👤 {esc(m.user.full_name)} (<code>{m.uid}</code>)", "bot",
                         kb([[B("🤖 بطاقة البوت", f"m:adm:bc:{me.id}")]]))


# ───────────────────────── بوتاتي ─────────────────────────
def _view(m: M) -> dict:
    return m.udata.setdefault("mb", {"f": "all", "tpl": "", "q": "", "page": 0, "sel": None})


async def bots_list(m: M) -> None:
    m.clear_state()
    T, v = m.t, _view(m)
    bots = await my_bots(m)
    cnt = {k: sum(1 for b in bots if b.status == k) for k in ("active", "disabled", "error")}
    shown = [b for b in bots if (v["f"] == "all" or b.status == v["f"]) and (not v["tpl"] or b.template == v["tpl"])
             and (not v["q"] or v["q"].lower() in f"{b.username} {b.name} {templates.get(b.template).ar} {templates.get(b.template).en}".lower())]
    users = await users_by_bot([b.id for b in shown])
    text = (f"🗂 <b>{T('بوتاتك', 'Your bots')}</b>  ({len(bots)})\n{ui.LINE}\n" +
            T(f"🟢 {cnt['active']} تعمل  ·  ⚠️ {cnt['error']} تحتاج انتباهك  ·  ⏸ {cnt['disabled']} متوقفة",
              f"🟢 {cnt['active']} running  ·  ⚠️ {cnt['error']} need attention  ·  ⏸ {cnt['disabled']} paused"))
    flt = []
    if v["tpl"]:
        flt.append(templates.get(v["tpl"]).name(m.lang))
    if v["q"]:
        flt.append(f"“{esc(v['q'])}”")
    if flt:
        text += "\n🔎 " + " · ".join(flt) + f" ({len(shown)})"
    if not bots:
        text += "\n\n" + T("لم تبنِ أي بوت بعد. ابدأ بأول بوت الآن!", "You haven't built a bot yet. Start with your first one!")
    sel = v["sel"]
    if sel is not None:
        text += T(f"\n☑ المحدد: {len(sel)} — اضغط البوتات لتحديدها", f"\n☑ Selected: {len(sel)} — tap bots to select")
    mark = lambda f: "• " if v["f"] == f else ""  # noqa: E731
    rows = []
    per = 7
    pages = max(1, (len(shown) + per - 1) // per)
    v["page"] = max(0, min(v["page"], pages - 1))
    for b in shown[v["page"] * per:(v["page"] + 1) * per]:
        icon = "🟠" if b.status == "active" and m.mgr.in_conflict(b.id) else status_icon(b)
        label = f"{icon} @{b.username} · {templates.get(b.template).name(m.lang)} · 👥 {users.get(b.id, 0)}"
        if sel is None:
            rows.append([B(label[:60], f"m:b:{b.id}")])
        else:
            rows.append([B((("☑ " if b.id in sel else "☐ ") + label)[:60], f"m:selt:{b.id}")])
    if pages > 1:
        rows.append([B("‹", f"m:bp:{v['page'] - 1}") if v["page"] > 0 else None, B(f"{v['page'] + 1} / {pages}", "noop"),
                     B("›", f"m:bp:{v['page'] + 1}") if v["page"] < pages - 1 else None])
    if sel is not None:
        rows.append([B(T("⏸ إيقاف المحدد", "⏸ Pause selected"), "m:selstop"), B(T("▶️ تشغيل المحدد", "▶️ Start selected"), "m:selrun")])
        rows.append([B(T("✕ إنهاء التحديد", "✕ Done selecting"), "m:selx")])
    elif len(bots) > 1:
        rows.append([B(mark("all") + T("الكل", "All"), "m:bf:all"), B(mark("active") + "🟢", "m:bf:active"),
                     B(mark("disabled") + "⏸", "m:bf:disabled"), B(mark("error") + "⚠️", "m:bf:error")])
        rows.append([B(T("🔍 بحث", "🔍 Search"), "m:bsearch"), B(T("🧩 حسب النوع", "🧩 By type"), "m:bytpl"), B(T("☑ تحديد متعدد", "☑ Multi-select"), "m:sel")])
    rows.append([B(T("➕ بوت جديد", "➕ New bot"), "m:new", style="success"), m.home_btn()])
    await m.show(text, kb(rows))


async def bots_bytpl(m: M) -> None:
    v = _view(m)
    used = sorted({b.template for b in await my_bots(m)})
    rows = [[B(("• " if not v["tpl"] else "") + m.t("كل الأنواع", "All types"), "m:bt:")]]
    rows += [[B(("• " if v["tpl"] == k else "") + templates.get(k).title(m.lang), f"m:bt:{k}")] for k in used]
    rows.append([B(m.t("⬅️ بوتاتي", "⬅️ My bots"), "m:bots")])
    await m.show(m.t("🧩 <b>عرض نوع واحد فقط</b>", "🧩 <b>Show one type only</b>"), kb(rows))


async def set_enabled(m: M, b: db.Bot, on: bool) -> None:
    if on:
        async with db.Session() as s:
            row = await s.get(db.Bot, b.id)
            row.status = "active"
            await s.commit()
        await m.mgr.start_bot(row)
    else:
        await m.mgr.stop_bot(b.id)
        async with db.Session() as s:
            row = await s.get(db.Bot, b.id)
            row.status, row.error = "disabled", ""
            await s.commit()


async def bot_card(m: M, bot_id: int) -> None:
    m.clear_state()
    m.udata.pop("adm_ctx", None)
    T = m.t
    b = await get_bot(m, bot_id)
    if b is None:
        await m.answer(T("البوت غير موجود.", "Bot not found."), True)
        return await bots_list(m)
    n = await child.counts(b.id)
    week = await child.week_series([b.id], "new")
    t = templates.get(b.template)
    adm = await platform.adm(b.id)
    lk = platform.lock_of(adm)
    text = (f"🤖 <b>{esc(b.name or b.username)}</b>  @{b.username}" + (" ✅" if adm.get("verified") else "") +
            f"\n🧩 {t.title(m.lang)}\n⚡ {status_text(m, b)}\n📅 {T('منذ', 'Since')} {ui.when(b.created, '%Y-%m-%d')}\n{ui.LINE}\n" +
            T(f"👥 الأعضاء: <b>{ui.num(n['total'])}</b>  (+{n['new']} اليوم)\n💬 الرسائل: <b>{ui.num(n['msgs'])}</b>\n📈 <code>{ui.spark(week)}</code> آخر 7 أيام",
              f"👥 Members: <b>{ui.num(n['total'])}</b>  (+{n['new']} today)\n💬 Messages: <b>{ui.num(n['msgs'])}</b>\n📈 <code>{ui.spark(week)}</code> last 7 days"))
    if m.mgr.in_conflict(b.id):
        text += "\n\n" + T("🟠 <b>التوكن مستخدم في مكان آخر</b> (منصة أو سيرفر آخر)، فتضيع بعض الرسائل. أرسل /revoke إلى @BotFather ثم اضغط «🔑 التوكن» هنا وأرسل الجديد.",
                           "🟠 <b>The token is in use elsewhere</b>, so some messages are lost. Send /revoke to @BotFather, then tap “🔑 Token” here and send the new one.")
    if adm.get("verified"):
        text += "\n\n" + T("✅ بوت موثّق من إدارة المنصة.", "✅ Verified by the platform.")
    if lk is not None:
        text += f"\n\n{ui.LINE}\n" + child.lock_text(lk, m.lang)
        if lk["mode"] != "maint":
            text += "\n\n" + T("ما دام البوت مغلقاً لا يمكن تغيير توكنه أو نوعه أو نقله أو حذفه. إن رأيت أن الإغلاق خطأ فاطلب المراجعة.",
                                 "While closed, the token, type, ownership and deletion are locked. If you think this is a mistake, request a review.")
            await m.show(text, kb([
                [B(T("📨 طلب مراجعة", "📨 Request review"), f"m:apl:{b.id}", style="primary")],
                [B(T("📈 الإحصائيات", "📈 Statistics"), f"m:bs:{b.id}"), B(T("↗ فتح البوت", "↗ Open bot"), url=f"https://t.me/{b.username}")],
                [B(T("⬅️ بوتاتي", "⬅️ My bots"), "m:bots"), m.home_btn()]]))
            return
    toggle = (B(T("⏸ إيقاف مؤقت", "⏸ Pause"), f"m:dis:{b.id}") if b.status == "active" else B(T("▶️ تشغيل", "▶️ Start"), f"m:en:{b.id}", style="success"))
    await m.show(text, kb([
        [B(T("🎛 غرفة التحكم", "🎛 Control room"), url=f"https://t.me/{b.username}?start=panel"), B(T("↗ فتح البوت", "↗ Open bot"), url=f"https://t.me/{b.username}")],
        [B(T("🌐 موقع البوت", "🌐 Bot website"), url=web.site_url(b.username))] if web.public() and b.status == "active" else None,
        [B(T("📈 الإحصائيات", "📈 Statistics"), f"m:bs:{b.id}"), B(T("🩺 فحص وإصلاح", "🩺 Check & repair"), f"m:chk:{b.id}")],
        [B(T("🔄 تغيير النوع", "🔄 Change type"), f"m:chg:{b.id}:0"), B(T("🔑 التوكن", "🔑 Token"), f"m:tok:{b.id}")],
        [B(T("🌐 الاسم باللغات", "🌐 Localized name"), f"m:names:{b.id}"), B(T("📤 نقل الملكية", "📤 Transfer"), f"m:tr:{b.id}")],
        [toggle, B(T("🗑 حذف", "🗑 Delete"), f"m:del:{b.id}", style="danger")],
        [B(T("⬅️ بوتاتي", "⬅️ My bots"), "m:bots"), m.home_btn()]]))


async def bot_stats(m: M, bot_id: int) -> None:
    b = await get_bot(m, bot_id, admin=True)
    if b is None:
        return await bots_list(m)
    text = f"📈 <b>{m.t('إحصائيات', 'Statistics')} @{b.username}</b>\n{ui.LINE}\n" + await child.stats_text(b.id, m.lang)
    back = f"m:adm:bc:{b.id}" if (m.is_admin and (m.udata.get("adm_ctx") == b.id or b.owner_id != m.uid)) else f"m:b:{b.id}"
    await m.show(text, kb([[B(m.t("🔄 تحديث", "🔄 Refresh"), f"m:bs:{b.id}")], [B(m.t("⬅️ رجوع", "⬅️ Back"), back)]]))


async def bot_check(m: M, bot_id: int) -> None:
    T = m.t
    b = await get_bot(m, bot_id)
    if b is None:
        return await bots_list(m)
    lines = []
    try:
        me = await m.mgr.probe(crypto.dec(b.token))
        lines.append(T("✅ التوكن صالح", "✅ Token is valid"))
        if b.status == "disabled":
            lines.append(T("⏸ البوت متوقف مؤقتاً بطلبك", "⏸ The bot is paused by you"))
        elif not m.mgr.running(b.id):
            ok, err = await m.mgr.restart_bot(b.id)
            lines.append(T("🔧 كان متوقفاً فأعدت تشغيله ✅", "🔧 It was down; restarted ✅") if ok else T(f"❌ تعذّر التشغيل: {esc(err)}", f"❌ Failed to start: {esc(err)}"))
        else:
            lines.append(T("✅ يعمل ويستقبل الرسائل", "✅ Running and receiving messages"))
        if m.mgr.in_conflict(b.id):
            lines.append(T("🟠 التوكن مستخدم في مكان آخر: أرسل /revoke إلى @BotFather ثم حدّث التوكن هنا", "🟠 Token used elsewhere: send /revoke to @BotFather, then update the token here"))
        if me.username and me.username != b.username:
            async with db.Session() as s:
                row = await s.get(db.Bot, b.id)
                row.username, row.name = me.username, me.full_name or ""
                await s.commit()
            lines.append(T(f"ℹ️ حُدّث المعرّف إلى @{me.username}", f"ℹ️ Username updated to @{me.username}"))
    except (InvalidToken, Forbidden):
        await m.mgr.stop_bot(b.id)
        async with db.Session() as s:
            row = await s.get(db.Bot, b.id)
            row.status, row.error = "error", "التوكن غير صالح أو تم إلغاؤه"
            await s.commit()
        lines.append(T("❌ التوكن لم يعد صالحاً. اضغط «🔑 التوكن» وأرسل التوكن الجديد من @BotFather.", "❌ The token is no longer valid. Tap “🔑 Token” and send the new one."))
    except TelegramError as e:
        lines.append(T(f"⚠️ تعذّر الاتصال بتيليجرام: {esc(e)}", f"⚠️ Telegram error: {esc(e)}"))
    b = await get_bot(m, bot_id)
    await m.show(f"🩺 <b>{T('فحص', 'Check')} @{b.username}</b>\n{ui.LINE}\n" + "\n".join(lines), kb([
        [B(T("🔁 أعد الفحص", "🔁 Re-check"), f"m:chk:{b.id}"), B(T("🔑 التوكن", "🔑 Token"), f"m:tok:{b.id}")],
        [B(T("⬅️ بطاقة البوت", "⬅️ Bot card"), f"m:b:{b.id}")]]))


async def change_tpl(m: M, bot_id: int, page: int) -> None:
    b = await get_bot(m, bot_id)
    if b is None:
        return await bots_list(m)
    tpls = await available(m)
    per = 10
    pages = max(1, (len(tpls) + per - 1) // per)
    page = max(0, min(page, pages - 1))
    btns = [B(("• " if t.key == b.template else "") + t.title(m.lang), f"m:chgto:{b.id}:{t.key}") for t in tpls[page * per:(page + 1) * per]]
    nav = [B("‹", f"m:chg:{b.id}:{page - 1}") if page > 0 else None, B(f"{page + 1} / {pages}", "noop"),
           B("›", f"m:chg:{b.id}:{page + 1}") if page < pages - 1 else None]
    await m.show(m.t(f"🔄 <b>تغيير نوع @{b.username}</b>\n\nأعضاء البوت وإحصائياته تبقى كما هي. محتوى النوع الحالي يُحفظ ويعود إن رجعت إليه.",
                     f"🔄 <b>Change the type of @{b.username}</b>\n\nMembers and statistics stay. The current type's content is kept and returns if you switch back."),
                 kb(ui.grid(btns, 2) + [nav, [B(m.t("⬅️ بطاقة البوت", "⬅️ Bot card"), f"m:b:{b.id}")]]))


async def names_menu(m: M, bot_id: int) -> None:
    b = await get_bot(m, bot_id)
    if b is None:
        return await bots_list(m)
    names = await db.kv_get(b.id, "sys:names", {})
    cur = "\n".join(f"• {LANG_NAMES.get(k, k)}: <b>{esc(v)}</b>" for k, v in names.items()) or m.t("لم تخصص أي اسم بعد.", "No localized names yet.")
    await m.show(m.t(f"🌐 <b>اسم @{b.username} حسب لغة العضو</b>\n\nمن يستخدم تيليجرام بالإنجليزية يرى اسماً، ومن يستخدمه بالعربية يرى اسماً آخر.\n\n{cur}",
                     f"🌐 <b>Name of @{b.username} per member language</b>\n\n{cur}"),
                 kb(ui.grid([B(name, f"m:name:{b.id}:{code}") for code, name in sorted(LANGS, key=lambda x: x[0] != "ar")], 2)
                    + [[B(m.t("⬅️ بطاقة البوت", "⬅️ Bot card"), f"m:b:{b.id}")]]))


async def wipe_bot(bot_id: int) -> None:
    async with db.Session() as s:
        for model in (db.BUser, db.KV, db.Rec, db.Daily):
            await s.execute(delete(model).where(model.bot_id == bot_id))
        await s.execute(delete(db.Transfer).where(db.Transfer.bot_id == bot_id))
        await s.execute(delete(db.Bot).where(db.Bot.id == bot_id))
        await s.commit()
    platform.adm_drop(bot_id)


async def send_web_link(m: M, kind: str) -> None:
    """رابط دخول موقّع إلى لوحة الويب، صالح 15 دقيقة."""
    from .web import dash
    T = m.t
    if not web.enabled():
        await m.answer(T("لوحة الويب غير مفعّلة في هذه المنصة.", "The web dashboard is not enabled here."), True)
        return
    link = dash.login_link(kind, m.uid, m.fid)
    title = T("🖥 <b>لوحة الإدارة على الويب</b>", "🖥 <b>Admin web dashboard</b>") if kind == "admin" else T("🖥 <b>لوحتك على الويب</b>", "🖥 <b>Your web dashboard</b>")
    what = (T("أرقام المنصة كلها برسوم بيانية: المستخدمون، البوتات، الأعضاء، الرسائل، وزيارات المواقع.", "All platform numbers with charts.") if kind == "admin"
            else T("أرقام كل بوتاتك برسوم بيانية لآخر 30 يوماً، وما ينتظرك من طلبات وحجوزات.", "Charts for all your bots over the last 30 days, plus pending orders and bookings."))
    await m.answer()
    if web.https():      # تفتح داخل تيليجرام
        from telegram import WebAppInfo
        await m.send(f"{title}\n{what}", kb([[B(T("📊 افتح اللوحة", "📊 Open the dashboard"), web_app=WebAppInfo(link), style="primary")]]))
    elif web.public():
        await m.send(f"{title}\n{what}\n\n" + T("الرابط خاص بك ويعمل 15 دقيقة. لا تشاركه.", "This link is personal and works for 15 minutes. Don't share it."),
                     kb([[B(T("↗ افتح اللوحة", "↗ Open the dashboard"), url=link)]]))
    else:
        await m.send(f"{title}\n{what}\n\n" + T("المنصة تعمل بلا رابط عام، فاللوحة تُفتح من الجهاز الذي يعمل عليه السيرفر فقط. انسخ الرابط وافتحه في متصفحه (يعمل 15 دقيقة):",
                                                   "The platform has no public URL, so open this on the machine running the server (valid 15 minutes):") + f"\n\n<code>{esc(link)}</code>")


# ───────────────────────── لوحتي ─────────────────────────
async def dashboard(m: M) -> None:
    T = m.t
    bots = await my_bots(m)
    ids = [b.id for b in bots]
    if not bots:
        await m.show(T("📊 <b>لوحتك</b>\n\nهنا تظهر أرقام كل بوتاتك مجتمعة: الأعضاء، الرسائل، النمو اليومي، وأفضل بوتاتك.\n\nابنِ أول بوت لتبدأ الأرقام بالظهور.",
                       "📊 <b>Your dashboard</b>\n\nNumbers for all your bots together appear here once you build your first bot."),
                     kb([[B(T("➕ ابنِ بوتاً جديداً", "➕ Build a new bot"), "m:new", style="success")], [m.home_btn()]]))
        return
    a = await _agg(ids)
    d0, d1 = db.today(), (db.now() - dt.timedelta(days=1)).strftime("%Y-%m-%d")
    t0, t1 = await db.daily(ids, d0), await db.daily(ids, d1)
    s_new, s_msg = await child.week_series(ids, "new"), await child.week_series(ids, "msgs")
    users = await users_by_bot(ids)
    top = sorted(bots, key=lambda b: -users.get(b.id, 0))
    lv, prog = level(a["total"], m.lang)
    medals = ["🥇", "🥈", "🥉"]
    by_tpl: dict[str, int] = {}
    for b in bots:
        by_tpl[b.template] = by_tpl.get(b.template, 0) + 1
    text = (
        f"📊 <b>{T('لوحتك', 'Your dashboard')}</b>\n{ui.LINE}\n" +
        T(f"🤖 البوتات: <b>{len(bots)}</b>\n👥 كل الأعضاء: <b>{ui.num(a['total'])}</b>  (خاص {ui.num(a['private'])} · مجموعات {a['groups']})\n💬 كل الرسائل: <b>{ui.num(a['msgs'])}</b>\n🏅 {lv}  <code>{prog}</code>",
          f"🤖 Bots: <b>{len(bots)}</b>\n👥 All members: <b>{ui.num(a['total'])}</b>  (private {ui.num(a['private'])} · groups {a['groups']})\n💬 All messages: <b>{ui.num(a['msgs'])}</b>\n🏅 {lv}  <code>{prog}</code>") +
        f"\n\n<b>{T('اليوم مقابل الأمس', 'Today vs yesterday')}</b>\n" + ui.rows([
            (T("أعضاء جدد", "New members"), f"{t0.get('new', 0)}  ({ui.pct(t0.get('new', 0), t1.get('new', 0))})"),
            (T("تفاعلوا اليوم", "Active today"), a["active"]),
            (T("رسائل", "Messages"), f"{t0.get('msgs', 0)}  ({ui.pct(t0.get('msgs', 0), t1.get('msgs', 0))})"),
            (T("مرات التشغيل", "Starts"), f"{t0.get('starts', 0)} / {t1.get('starts', 0)}")]) +
        f"\n\n<b>{T('آخر 7 أيام', 'Last 7 days')}</b>\n<code>{ui.spark(s_new)}</code> " + T(f"أعضاء جدد: {sum(s_new)}", f"new members: {sum(s_new)}") +
        f"\n<code>{ui.spark(s_msg)}</code> " + T(f"رسائل: {sum(s_msg)}", f"messages: {sum(s_msg)}") +
        f"\n\n<b>{T('أفضل بوتاتك', 'Your top bots')}</b>\n" + "\n".join(f"{medals[i]} @{b.username} — 👥 {ui.num(users.get(b.id, 0))}" for i, b in enumerate(top[:3])) +
        f"\n\n<b>{T('حسب النوع', 'By type')}</b>\n" + "\n".join(f"{templates.get(k).title(m.lang)} × {v}" for k, v in sorted(by_tpl.items(), key=lambda x: -x[1])))
    rows = [[B(f"📈 @{b.username}", f"m:bs:{b.id}")] for b in top[:5]]
    rows += [[B(T("📡 رسالة لكل جمهوري", "📡 Message all my members"), "m:gbc")], [B(T("🔄 تحديث", "🔄 Refresh"), "m:stats"), m.home_btn()]]
    await m.show(text, kb(rows))


async def run_global_broadcast(m: M, bots: list[db.Bot], html_text: str) -> None:
    ok = fail = 0
    for b in bots:
        app = m.mgr.apps.get(b.id)
        if app is None:
            continue
        for uid in await child.audience(b.id, "pv"):
            try:
                await app.bot.send_message(uid, html_text, parse_mode=ParseMode.HTML)
                ok += 1
            except TelegramError:
                fail += 1
            await asyncio.sleep(0.05)
    try:
        await m.bot.send_message(m.uid, m.t(f"✅ انتهى الإرسال.\n📬 وصلت: {ok}\n⚠️ لم تصل: {fail}", f"✅ Sending finished.\n📬 Delivered: {ok}\n⚠️ Failed: {fail}"))
    except TelegramError:
        pass


# ───────────────────────── الدعوات والمساعدة ─────────────────────────
async def referral(m: M) -> None:
    async with db.Session() as s:
        invited = list((await s.execute(select(db.MUser.user_id).where(db.MUser.factory_id == m.fid, db.MUser.ref_by == m.uid))).scalars().all())
        makers = active = 0
        if invited:
            makers = int((await s.execute(select(func.count(func.distinct(db.Bot.owner_id))).where(db.Bot.factory_id == m.fid, db.Bot.owner_id.in_(invited)))).scalar() or 0)
            active = int((await s.execute(select(func.count()).select_from(db.Bot).where(db.Bot.factory_id == m.fid, db.Bot.owner_id.in_(invited), db.Bot.status == "active"))).scalar() or 0)
    link = f"https://t.me/{m.bot.username}?start=ref_{m.uid}"
    share = f"https://t.me/share/url?url={quote(link)}&text={quote(m.t('ابنِ بوت تيليجرام خاصاً بك مجاناً وبدون برمجة 🤖', 'Build your own Telegram bot for free, no code 🤖'))}"
    await m.show(m.t(
        f"🎁 <b>ادعُ أصدقاءك</b>\n{ui.LINE}\nشارك رابطك، وكل من يدخل منه يُحسب في سجلك. أعضاء بوتاتك الجدد يرون أيضاً دعوة تحمل رابطك تلقائياً.\n\n"
        f"🔗 <code>{link}</code>\n\n👥 دخلوا عبرك: <b>{len(invited)}</b>\n🚀 بنوا بوتات: <b>{makers}</b>\n🤖 بوتاتهم العاملة: <b>{active}</b>",
        f"🎁 <b>Invite friends</b>\n{ui.LINE}\nShare your link; everyone who joins through it is counted for you.\n\n"
        f"🔗 <code>{link}</code>\n\n👥 Joined via you: <b>{len(invited)}</b>\n🚀 Built bots: <b>{makers}</b>\n🤖 Their running bots: <b>{active}</b>"),
        kb([[B(m.t("📤 شارك الرابط", "📤 Share link"), url=share)], [m.home_btn()]]))


GUIDE_AR = (
    "📖 <b>كيف يعمل الصانع؟</b>\n\n"
    "<b>١. تبني:</b> تختار نوع البوت وتربطه بتوكن من @BotFather، فيعمل خلال ثوانٍ.\n\n"
    "<b>٢. تجهّز:</b> تفتح بوتك وتضغط «بدء»، فتظهر لك <b>غرفة التحكم</b> (تظهر لك وحدك لأنك المالك). اتبع «🚀 أكمل التجهيز» خطوة خطوة، ومنها تضبط الترحيب والاشتراك الإجباري والرسائل الجماعية وهوية البوت.\n\n"
    "<b>٣. الموقع:</b> الأنواع التي تحمل علامة 🌐 (المتجر، المنيو، الحجز، القرآن، تعليم الإنجليزية، بوت الأزرار) لها موقع ويب جاهز: ما يطلبه الزائر في الموقع يصلك في البوت. تضبطه من «🌐 موقع البوت» في غرفة التحكم.\n\n"
    "<b>٤. تتابع:</b> من «🗂 بوتاتي» هنا تفتح بطاقة كل بوت: إحصائياته، فحصه، تغيير نوعه، توكنه، نقله أو حذفه. ومن «📊 لوحتي» ترى أرقام كل بوتاتك معاً، ومن «🖥 لوحتي على الويب» تراها برسوم بيانية.\n\n"
    "اكتب /admin داخل أي بوت من بوتاتك للعودة إلى غرفة التحكم."
)
GUIDE_EN = (
    "📖 <b>How does the maker work?</b>\n\n<b>1. Build:</b> pick a type and link a token from @BotFather.\n\n"
    "<b>2. Set up:</b> open your bot and press Start to see its <b>control room</b> (only you see it).\n\n"
    "<b>3. Track:</b> “My bots” has a card per bot; “My dashboard” shows all numbers together.\n\nSend /admin inside any of your bots to return to the control room."
)
FAQ_AR = (
    "❓ <b>أسئلة شائعة</b>\n\n"
    "<b>أين لوحة تحكم بوتي؟</b>\nداخل البوت نفسه: افتحه واضغط «بدء» أو اكتب /admin. أو من بطاقة البوت هنا اضغط «🎛 غرفة التحكم».\n\n"
    "<b>بوتي لا يرد أو يرد بشيء غريب؟</b>\nغالباً التوكن نفسه مستخدم في منصة أو سيرفر آخر. أرسل /revoke إلى @BotFather لتحصل على توكن جديد، ثم من بطاقة البوت اضغط «🔑 التوكن».\n\n"
    "<b>هل توكني آمن؟</b>\nيُحفظ مشفّراً ولا يظهر لأي مستخدم آخر، ورسالتك التي تحتويه تُحذف فوراً. إدارة المنصة هي الجهة التي تشغّل بوتك، ولذلك تستطيع الوصول إليه عند مراجعة مخالفة أو حل مشكلة. "
    "تستطيع سحب بوتك في أي وقت بإرسال /revoke إلى @BotFather.\n\n"
    "<b>لماذا أُغلق بوتي؟</b>\nالإدارة تغلق البوت الذي يخالف الشروط (احتيال، تصيّد، محتوى مخالف، إزعاج). يظهر لك السبب في بطاقة البوت، ومنها تضغط «📨 طلب مراجعة».\n\n"
    "<b>هل أستطيع تغيير نوع البوت لاحقاً؟</b>\nنعم من بطاقة البوت، والأعضاء يبقون كما هم.\n\n"
    "<b>هل الخدمة مجانية؟</b>\nنعم، بناء البوتات وتشغيلها مجاني."
)
FAQ_EN = (
    "❓ <b>FAQ</b>\n\n<b>Where is my bot's control panel?</b>\nInside the bot: open it and press Start or send /admin.\n\n"
    "<b>My bot doesn't answer?</b>\nThe token is probably used elsewhere. Send /revoke to @BotFather and update the token from the bot card.\n\n"
    "<b>Is my token safe?</b>\nIt is stored encrypted and never shown to other users. The platform team runs your bot, so it can access the token when reviewing a violation or fixing a problem. "
    "You can pull your bot out anytime with /revoke in @BotFather.\n\n<b>Is it free?</b>\nYes."
)
POLICY_AR = ("📜 <b>كيف نتعامل مع البلاغات والمخالفات</b>\n\nتُراجع البلاغات يدوياً. عند ثبوت مخالفة (تصيّد، احتيال، محتوى مخالف، إزعاج) قد تتخذ الإدارة واحداً من الآتي:\n"
             "• تحذير مالك البوت\n• إغلاق البوت مؤقتاً أو نهائياً مع ذكر السبب\n• إرسال إشعار لأعضاء البوت بأنه أُغلق\n• مراجعة محتوى البوت وإعداداته\n\n"
             "مالك البوت يستطيع طلب المراجعة من بطاقة بوته. لا نشارك بياناتك مع أي طرف آخر.")
POLICY_EN = ("📜 <b>How reports and violations are handled</b>\n\nReports are reviewed manually. When a violation is confirmed the platform may warn the owner, close the bot temporarily or permanently "
             "(with a reason), notify the bot's members, and review the bot's content and settings. Owners can request a review from the bot card. Your data is not shared.")


# ───────────────────────── الأزرار ─────────────────────────
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:  # noqa: C901
    m = M(update, context)
    if (m.q.data or "") == "noop":
        return await m.answer()
    a = (m.q.data or "").split(":")[1:]
    act = a[0] if a else "home"
    arg = a[1] if len(a) > 1 else ""
    T = m.t
    try:
        if not m.udata.get("mseen"):
            await ensure_user(m)
            m.udata["mseen"] = True
        if not await gate(m):
            return
        ident = arg.lstrip("-").isdigit()
        if act in ("tok", "chg", "chgto", "tr", "trok", "del", "delok", "names", "name") and ident:
            lk = platform.lock_of(platform.peek(int(arg)))
            if lk is not None and lk["mode"] != "maint" and await get_bot(m, int(arg)) is not None:
                await m.answer(T("🔒 البوت مغلق من الإدارة، وهذا الإجراء متوقف حتى يُعاد فتحه.", "🔒 The bot is closed by the platform; this action is locked until it reopens."), True)
                return await bot_card(m, int(arg))
        if act == "home":
            await home(m)
        elif act == "new":
            await pick_type(m)
        elif act == "cat":
            await cat(m, arg)
        elif act == "all":
            await all_types(m, int(arg) if ident else 0)
        elif act == "tsearch":
            m.set_state("tsearch")
            await m.show(T("🔍 اكتب كلمة تصف ما تريده (مثلاً: متجر، حجز، تحميل، ترجمة).\n\n/cancel للإلغاء",
                           "🔍 Type a word describing what you want (e.g. store, booking, download).\n\n/cancel to abort"),
                         kb([[B(T("❌ إلغاء", "❌ Cancel"), "m:new")]]))
        elif act == "tpl":
            await tpl_card(m, arg)
        elif act == "guide":
            await tpl_guide(m, arg)
        elif act == "bots":
            await bots_list(m)
        elif act == "bf":
            _view(m).update(f=arg if arg in ("all", "active", "disabled", "error") else "all", page=0, q="")
            await bots_list(m)
        elif act == "bp" and ident:
            _view(m)["page"] = int(arg)
            await bots_list(m)
        elif act == "bytpl":
            await bots_bytpl(m)
        elif act == "bt":
            _view(m).update(tpl=arg, page=0)
            await bots_list(m)
        elif act == "bsearch":
            m.set_state("bsearch")
            await m.show(T("🔍 أرسل جزءاً من معرّف البوت أو اسمه أو نوعه.\n\n/cancel للإلغاء", "🔍 Send part of the bot's username, name or type.\n\n/cancel to abort"),
                         kb([[B(T("❌ إلغاء", "❌ Cancel"), "m:bots")]]))
        elif act == "sel":
            _view(m)["sel"] = []
            await bots_list(m)
        elif act == "selx":
            _view(m)["sel"] = None
            await bots_list(m)
        elif act == "selt" and ident:
            sel = _view(m)["sel"]
            if sel is not None:
                sel.remove(int(arg)) if int(arg) in sel else sel.append(int(arg))
            await bots_list(m)
        elif act in ("selstop", "selrun"):
            sel = _view(m)["sel"] or []
            if not sel:
                await m.answer(T("حدّد بوتاً واحداً على الأقل.", "Select at least one bot."), True)
            else:
                for bid in sel:
                    b = await get_bot(m, bid)
                    if b is not None:
                        await set_enabled(m, b, act == "selrun")
                await m.answer(T("✅ تم.", "✅ Done."))
            await bots_list(m)
        elif act == "b" and ident:
            await bot_card(m, int(arg))
        elif act == "bs" and ident:
            await bot_stats(m, int(arg))
        elif act == "chk" and ident:
            await bot_check(m, int(arg))
        elif act == "tok" and ident:
            b = await get_bot(m, int(arg))
            if b is None:
                return await bots_list(m)
            m.set_state("newtoken", id=b.id)
            await m.show(T(f"🔑 <b>توكن @{b.username}</b>\n\nالتوكن الحالي محفوظ مشفّراً.\n\nلتغييره: أرسل /revoke إلى @BotFather واختر هذا البوت، ثم ألصق التوكن الجديد هنا.\n\n/cancel للإلغاء",
                           f"🔑 <b>Token of @{b.username}</b>\n\nThe current token is stored encrypted.\n\nTo change it: send /revoke to @BotFather, pick this bot, then paste the new token here.\n\n/cancel to abort"),
                         kb([[B(T("❌ إلغاء", "❌ Cancel"), f"m:b:{b.id}")]]))
        elif act == "chg" and ident:
            await change_tpl(m, int(arg), int(a[2]) if len(a) > 2 and a[2].isdigit() else 0)
        elif act == "chgto" and ident:
            b = await get_bot(m, int(arg))
            if b is None or len(a) < 3 or a[2] not in {t.key for t in await available(m)}:
                return await bots_list(m)
            async with db.Session() as s:
                row = await s.get(db.Bot, b.id)
                row.template = a[2]
                await s.commit()
            if b.status == "active":
                await m.mgr.restart_bot(b.id)
            await m.answer(T("✅ تم تغيير النوع.", "✅ Type changed."), True)
            await bot_card(m, b.id)
        elif act == "tr" and ident:
            b = await get_bot(m, int(arg))
            if b is None:
                return await bots_list(m)
            await m.show(T(f"📤 <b>نقل ملكية @{b.username}</b>\n\nستحصل على رابط تعطيه للمالك الجديد. عند فتحه:\n• يصبح هو المالك الكامل\n• تفقد أنت الوصول إلى غرفة التحكم\n• لا يمكن التراجع\n\nالرابط يعمل مرة واحدة خلال 24 ساعة.",
                           f"📤 <b>Transfer @{b.username}</b>\n\nYou get a link for the new owner. Once opened:\n• they become the full owner\n• you lose access to the control room\n• it cannot be undone\n\nThe link works once, within 24 hours."),
                         kb([[B(T("✅ أنشئ رابط النقل", "✅ Create transfer link"), f"m:trok:{b.id}", style="danger"), B(T("❌ إلغاء", "❌ Cancel"), f"m:b:{b.id}")]]))
        elif act == "trok" and ident:
            b = await get_bot(m, int(arg))
            if b is None:
                return await bots_list(m)
            code = secrets.token_urlsafe(18)
            async with db.Session() as s:
                await s.execute(delete(db.Transfer).where(db.Transfer.bot_id == b.id))
                s.add(db.Transfer(code=code, bot_id=b.id, from_id=m.uid, expires=db.now() + dt.timedelta(hours=24)))
                await s.commit()
            link = f"https://t.me/{m.bot.username}?start=tr_{code}"
            await m.show(T(f"📤 <b>رابط نقل @{b.username}</b>\n\nأرسله للمالك الجديد فقط:\n<code>{link}</code>\n\n⏳ يعمل مرة واحدة خلال 24 ساعة.",
                           f"📤 <b>Transfer link for @{b.username}</b>\n\nSend it to the new owner only:\n<code>{link}</code>\n\n⏳ Works once, within 24 hours."),
                         kb([[B(T("🚫 ألغِ الرابط", "🚫 Revoke link"), f"m:trx:{b.id}")], [B(T("⬅️ بطاقة البوت", "⬅️ Bot card"), f"m:b:{b.id}")]]))
        elif act == "trx" and ident:
            async with db.Session() as s:
                await s.execute(delete(db.Transfer).where(db.Transfer.bot_id == int(arg), db.Transfer.from_id == m.uid))
                await s.commit()
            await m.answer(T("أُلغي الرابط.", "Link revoked."), True)
            await bot_card(m, int(arg))
        elif act == "names" and ident:
            await names_menu(m, int(arg))
        elif act == "name" and ident and len(a) > 2:
            b = await get_bot(m, int(arg))
            if b is None:
                return await bots_list(m)
            m.set_state("botname", id=b.id, lang=a[2])
            await m.show(T(f"🌐 أرسل اسم البوت الذي يراه مستخدمو <b>{LANG_NAMES.get(a[2], a[2])}</b> (حتى 64 حرفاً).\n\n/cancel للإلغاء",
                           f"🌐 Send the bot name shown to <b>{LANG_NAMES.get(a[2], a[2])}</b> users (max 64 chars).\n\n/cancel to abort"),
                         kb([[B(T("❌ إلغاء", "❌ Cancel"), f"m:names:{b.id}")]]))
        elif act in ("dis", "en") and ident:
            b = await get_bot(m, int(arg))
            if b is not None:
                await set_enabled(m, b, act == "en")
            await bot_card(m, int(arg))
        elif act == "del" and ident:
            b = await get_bot(m, int(arg))
            if b is None:
                return await bots_list(m)
            await m.show(T(f"🗑 <b>حذف @{b.username}؟</b>\n\nيتوقف البوت وتُحذف إعداداته وأعضاؤه وبياناته نهائياً من هنا. البوت نفسه يبقى في حسابك لدى BotFather.",
                           f"🗑 <b>Delete @{b.username}?</b>\n\nThe bot stops and its settings, members and data are erased here for good. The bot itself stays in your BotFather account."),
                         kb([[B(T("🗑 نعم، احذف", "🗑 Yes, delete"), f"m:delok:{b.id}", style="danger"), B(T("❌ إلغاء", "❌ Cancel"), f"m:b:{b.id}")]]))
        elif act == "delok" and ident:
            b = await get_bot(m, int(arg))
            if b is not None:
                await m.mgr.stop_bot(b.id)
                await wipe_bot(b.id)
                await m.answer(T("تم الحذف.", "Deleted."), True)
            await bots_list(m)
        elif act == "stats":
            await dashboard(m)
        elif act == "set":
            m.clear_state()
            cur = m.udata.get("mlang") or m.lang
            await m.show(T(f"⚙️ <b>الإعدادات</b>\n\n🌐 لغة الواجهة: {LANG_NAMES.get(cur, cur)}", f"⚙️ <b>Settings</b>\n\n🌐 Interface language: {LANG_NAMES.get(cur, cur)}"),
                         kb([[B(T("🌐 تغيير اللغة", "🌐 Change language"), "m:lang")], [B(T("📡 رسالة لكل جمهوري", "📡 Message all my members"), "m:gbc")], [m.home_btn()]]))
        elif act == "gbc":
            bots = [b for b in await my_bots(m) if b.status == "active" and not closed(b)]
            aud = sum([len(await child.audience(b.id, "pv")) for b in bots])
            m.set_state("gbc")
            await m.show(T(f"📡 <b>رسالة لكل جمهورك</b>\n\nتصل لكل أعضاء بوتاتك العاملة دفعة واحدة، كلٌّ عبر بوته.\n\n🤖 البوتات: {len(bots)}\n👥 المستلمون: {ui.num(aud)}\n\n📝 أرسل النص الآن.\n/cancel للإلغاء",
                           f"📡 <b>Message all your members</b>\n\n🤖 Bots: {len(bots)}\n👥 Recipients: {ui.num(aud)}\n\n📝 Send the text now.\n/cancel to abort"),
                         kb([[B(T("❌ إلغاء", "❌ Cancel"), "m:home")]]))
        elif act == "gbcgo":
            text = m.udata.pop("gbc_text", None)
            if not text:
                return await home(m)
            bots = [b for b in await my_bots(m) if b.status == "active" and not closed(b)]
            context.application.create_task(run_global_broadcast(m, bots, text))
            await m.show(T("🚀 بدأ الإرسال. سيصلك تقرير عند الانتهاء.", "🚀 Sending started. You'll get a report."), kb([[m.home_btn()]]))
        elif act == "lang":
            cur = m.udata.get("mlang") or m.lang
            btns = [B(("• " if code == cur else "") + name, f"m:setlang:{code}") for code, name in LANGS]
            await m.show(T("🌐 <b>لغة الواجهة</b>\n\nالنصوص متوفرة بالعربية والإنجليزية؛ بقية اللغات تعرض الإنجليزية حالياً.", "🌐 <b>Interface language</b>\n\nTexts exist in Arabic and English; other languages show English for now."),
                         kb(ui.grid(btns, 2) + [[m.home_btn()]]))
        elif act == "setlang" and arg in LANG_NAMES:
            async with db.Session() as s:
                row = await s.get(db.MUser, (m.fid, m.uid))
                if row is not None:
                    row.lang = arg
                    await s.commit()
            m.udata["mlang"] = arg
            m.lang = arg
            await home(m)
        elif act == "more":
            m.clear_state()
            guide = B(T("📖 كيف يعمل الصانع؟", "📖 How it works"), url=config.GUIDE_URL) if config.GUIDE_URL and m.fid == 0 else B(T("📖 كيف يعمل الصانع؟", "📖 How it works"), "m:help")
            await m.show(T("🆘 <b>مساعدة</b>\n\nاختر ما تحتاجه:", "🆘 <b>Help</b>\n\nPick what you need:"),
                         kb([[guide], [B(T("❓ أسئلة شائعة", "❓ FAQ"), "m:faq")],
                             [B(T("🐞 بلّغ عن مشكلة", "🐞 Report a problem"), "m:bug"), B(T("🚨 بلّغ عن إساءة", "🚨 Report abuse"), "m:abuse")], [m.home_btn()]]))
        elif act == "help":
            await m.show(GUIDE_AR if m.lang == "ar" else GUIDE_EN, kb([[B(T("⬅️ مساعدة", "⬅️ Help"), "m:more")]]))
        elif act == "faq":
            await m.show(FAQ_AR if m.lang == "ar" else FAQ_EN, kb([[B(T("⬅️ مساعدة", "⬅️ Help"), "m:more")]]))
        elif act in ("bug", "abuse"):
            m.set_state("report", kind=act)
            text = (T("🐞 <b>بلّغ عن مشكلة</b>\n\nاكتب ما حدث في رسالة واحدة: ماذا ضغطت، وماذا توقعت، وماذا ظهر لك.\n\n<i>مثال: أضفت قناة للاشتراك الإجباري ولم تظهر في القائمة.</i>",
                      "🐞 <b>Report a problem</b>\n\nDescribe what happened in one message.")
                    if act == "bug" else
                    T("🚨 <b>بلّغ عن إساءة</b>\n\nأرسل معرّف البوت المخالف مع وصف قصير.\n\n<i>مثال: @badbot يطلب كود تسجيل الدخول إلى تيليجرام.</i>",
                      "🚨 <b>Report abuse</b>\n\nSend the offending bot's username with a short description."))
            await m.show(text, kb([[B(T("📜 كيف نتعامل مع البلاغات؟", "📜 How reports are handled"), "m:policy")], [B(T("❌ إلغاء", "❌ Cancel"), "m:more")]]))
        elif act == "policy":
            await m.answer()
            await m.send(POLICY_AR if m.lang == "ar" else POLICY_EN)
        elif act == "ref":
            await referral(m)
        elif act == "web":
            await send_web_link(m, "me")
        elif act == "apl" and ident:
            b = await get_bot(m, int(arg))
            if b is None:
                return await bots_list(m)
            adm = await platform.adm(b.id)
            if platform.lock_of(adm) is None:
                return await bot_card(m, b.id)
            if time.time() - adm.get("appeal_at", 0) < 6 * 3600:
                await m.answer(T("وصل طلبك السابق وهو قيد المراجعة. يمكنك إرسال طلب جديد بعد 6 ساعات.", "Your previous request is under review. You can send a new one in 6 hours."), True)
                return
            m.set_state("appeal", id=b.id)
            await m.show(T(f"📨 <b>طلب مراجعة إغلاق @{b.username}</b>\n\nاكتب في رسالة واحدة لماذا ترى أن الإغلاق يجب أن يُرفع، وما الذي أصلحته إن وُجد.\n\n/cancel للإلغاء",
                           f"📨 <b>Request a review for @{b.username}</b>\n\nExplain in one message why the bot should be reopened and what you fixed, if anything.\n\n/cancel to abort"),
                         kb([[B(T("❌ إلغاء", "❌ Cancel"), f"m:b:{b.id}")]]))
        elif act == "adm":
            if m.is_admin:
                await admin.admin_cb(m, a[1:])
            else:
                await m.answer(T("هذه اللوحة لمدير المنصة فقط.", "Admins only."), True)
        else:
            await home(m)
    finally:
        await m.answer()


# ───────────────────────── الرسائل ─────────────────────────
def _home_kb(m: M):
    T = m.t
    return kb([[B(T("➕ ابنِ بوتاً جديداً", "➕ Build a new bot"), "m:new", style="success")],
               [B(T("🗂 بوتاتي", "🗂 My bots"), "m:bots"), B(T("📊 لوحتي", "📊 My dashboard"), "m:stats")],
               [B(T("🆘 مساعدة", "🆘 Help"), "m:more"), m.home_btn()]])


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:  # noqa: C901
    m = M(update, context)
    if m.msg is None or m.user is None:
        return False
    await ensure_user(m)
    m.udata["mseen"] = True
    if not await gate(m):
        return True
    T, st = m.t, m.st
    text = (m.msg.text or m.msg.caption or "").strip()
    if text.lower() == "/cancel":
        m.clear_state()
        await home(m, new=True)
        return True
    tok = TOKEN_RE.search(text)
    if tok and (not st or st["k"] in ("token", "newtoken")):
        try:
            await m.msg.delete()  # لا نترك التوكن ظاهراً في المحادثة
        except TelegramError:
            pass
        if st and st["k"] == "newtoken":
            b = await get_bot(m, st["id"])
            if b is None:
                m.clear_state()
                return True
            if tok.group(1).split(":")[0] != str(b.id):
                await m.send(T("⚠️ هذا التوكن لبوت آخر. أرسل توكن نفس البوت.", "⚠️ That token belongs to another bot."))
                return True
            try:
                await m.mgr.probe(tok.group(1))
            except TelegramError:
                await m.send(T("❌ التوكن غير صحيح.", "❌ Invalid token."))
                return True
            async with db.Session() as s:
                row = await s.get(db.Bot, b.id)
                row.token, row.status, row.error = crypto.enc(tok.group(1)), "active", ""
                await s.commit()
            ok, _ = await m.mgr.restart_bot(b.id)
            m.clear_state()
            await m.send(T("✅ حُفظ التوكن الجديد والبوت يعمل.", "✅ New token saved and the bot is running.") if ok else
                         T("⚠️ حُفظ التوكن لكن تعذّر التشغيل.", "⚠️ Saved but failed to start."),
                         kb([[B(T("🗂 بطاقة البوت", "🗂 Bot card"), f"m:b:{b.id}")]]))
            return True
        if st and st["k"] == "token":
            await create_bot(m, tok.group(1), st["tpl"])
            return True
        await m.send(T("🔑 وصلني توكن، لكن اختر نوع البوت أولاً ثم أرسله من جديد.", "🔑 Got a token, but pick the bot type first, then send it again."),
                     kb([[B(T("🧭 اختيار النوع", "🧭 Choose type"), "m:new")]]))
        return True
    if not st:
        await m.send(T("🤔 لم أفهم. اختر من الأزرار:", "🤔 I didn't get that. Use the buttons:"), _home_kb(m))
        return True
    k = st["k"]
    if k.startswith("adm_"):
        if m.is_admin:
            await admin.admin_input(m, st, text)
        else:
            m.clear_state()
        return True
    if k == "appeal":
        m.clear_state()
        b = await get_bot(m, st["id"])
        if b is None:
            return True
        adm = await platform.adm(b.id)
        adm["appeal_at"] = time.time()
        await platform.adm_save(b.id)
        async with db.Session() as s:
            s.add(db.Report(factory_id=m.fid, user_id=m.uid, kind="appeal", text=f"@{b.username} [{b.id}]\n{text[:2500]}"))
            await s.commit()
        await m.notify_admin(f"📨 <b>طلب مراجعة</b> للبوت @{b.username}\n👤 {esc(m.user.full_name)} (<code>{m.uid}</code>)\n\n{esc(text[:2500])}",
                             markup=kb([[B("🤖 بطاقة البوت", f"m:adm:bc:{b.id}")]]))
        await m.send(T("✅ وصل طلبك إلى الإدارة. سيصلك الرد هنا.", "✅ Your request reached the platform team. You'll get the answer here."),
                     kb([[B(T("🗂 بطاقة البوت", "🗂 Bot card"), f"m:b:{b.id}")]]))
        return True
    if k in ("token", "newtoken"):
        await m.send(T("⏳ أنتظر التوكن. شكله هكذا:\n<code>123456789:AAH…</code>\n\n/cancel للإلغاء", "⏳ Waiting for the token. It looks like:\n<code>123456789:AAH…</code>\n\n/cancel to abort"))
    elif k == "tsearch":
        q = text.lower()
        found = [t for t in await available(m) if q and q in f"{t.ar} {t.en} {t.d_ar} {t.d_en} {' '.join(t.feats)}".lower()]
        m.clear_state()
        body = "\n\n".join(f"{t.emoji} <b>{esc(t.name(m.lang))}</b>\n{esc(t.desc(m.lang))}" for t in found[:8])
        await m.send(T(f"🔍 نتائج «{esc(text)}»: {len(found)}\n\n", f"🔍 Results for “{esc(text)}”: {len(found)}\n\n") + body,
                     kb(ui.grid([_tpl_btn(m, t) for t in found[:16]], 2) + [[B(T("⬅️ المجالات", "⬅️ Areas"), "m:new")]]))
    elif k == "bsearch":
        _view(m).update(q=text[:40], page=0)
        await bots_list(m)
    elif k == "botname":
        b = await get_bot(m, st["id"])
        app = m.mgr.apps.get(st["id"])
        m.clear_state()
        if b is None or app is None:
            await m.send(T("⚠️ البوت غير مشغّل حالياً.", "⚠️ The bot is not running."))
            return True
        try:
            await app.bot.set_my_name(text[:64], language_code=st["lang"])
        except TelegramError as e:
            await m.send(T(f"⚠️ تعذّر التغيير: {esc(e)}", f"⚠️ Failed: {esc(e)}"))
            return True
        names = await db.kv_get(b.id, "sys:names", {})
        names[st["lang"]] = text[:64]
        await db.kv_set(b.id, "sys:names", names)
        await m.send(T("✅ حُفظ الاسم.", "✅ Name saved."), kb([[B(T("⬅️ رجوع", "⬅️ Back"), f"m:names:{b.id}")]]))
    elif k == "gbc":
        m.clear_state()
        m.udata["gbc_text"] = ui.html_of(m.msg) or esc(text)
        await m.send(T("☝️ هل تؤكد إرسال هذا النص لكل أعضاء بوتاتك؟", "☝️ Send this text to all members of your bots?"),
                     kb([[B(T("✅ إرسال", "✅ Send"), "m:gbcgo", style="success"), B(T("❌ إلغاء", "❌ Cancel"), "m:home", style="danger")]]))
    elif k == "report":
        m.clear_state()
        async with db.Session() as s:
            s.add(db.Report(factory_id=m.fid, user_id=m.uid, kind=st["kind"], text=text[:3000]))
            await s.commit()
        icon = "🐞" if st["kind"] == "bug" else "🚨"
        await m.notify_admin(f"{icon} <b>بلاغ جديد</b>\n👤 {esc(m.user.full_name)} (<code>{m.uid}</code>)\n\n{esc(text[:3000])}")
        await m.send(T("✅ وصل بلاغك، شكراً لك.", "✅ Your report was received, thank you."), kb([[m.home_btn()]]))
    else:
        m.clear_state()
        await home(m, new=True)
    return True


async def on_start(update: Update, context: ContextTypes.DEFAULT_TYPE, param: str | None = None) -> None:
    try:
        m = M(update, context)
        log.info("▶ /start uid=%s chat=%s", m.uid, update.effective_chat.type if update.effective_chat else "?")
        if update.effective_chat is None or update.effective_chat.type != ChatType.PRIVATE or m.user is None:
            return
        if param is None:
            param = context.args[0] if context.args else ""
        ref = int(param[4:]) if param.startswith("ref_") and param[4:].isdigit() else 0
        await ensure_user(m, ref)
        m.udata["mseen"] = True
        if not await gate(m):
            log.info("▶ /start uid=%s blocked by gate", m.uid)
            return
        log.info("▶ /start uid=%s gate passed, showing home", m.uid)

        if param.startswith(("adm_", "bot_")) and param[4:].isascii() and param[4:].isdecimal():
            if param.startswith("adm_") and m.is_admin:
                return await admin.admin_bot(m, int(param[4:]))
            if await get_bot(m, int(param[4:])) is not None:
                return await bot_card(m, int(param[4:]))
        if param.startswith("tr_"):
            try:
                async with db.Session() as s:
                    tr = await s.get(db.Transfer, param[3:])
                    if tr is None or tr.used or tr.expires < db.now():
                        await m.send(m.t("⚠️ رابط النقل غير صالح أو انتهت صلاحيته.", "⚠️ Transfer link is invalid or expired."))
                    else:
                        row = await s.get(db.Bot, tr.bot_id)
                        lk = platform.lock_of(await platform.adm(tr.bot_id))
                        if row is None or row.owner_id != tr.from_id or (lk is not None and lk["mode"] != "maint"):
                            await m.send(m.t("⚠️ رابط النقل غير صالح.", "⚠️ Transfer link is invalid."))
                        else:
                            old = row.owner_id
                            row.owner_id, tr.used = m.uid, True
                            await s.commit()
                            m.mgr.set_owner(row.id, m.uid)
                            await m.send(m.t(f"✅ أصبحت مالك البوت @{row.username}.", f"✅ You now own @{row.username}."),
                                         kb([[B(m.t("🗂 بطاقة البوت", "🗂 Bot card"), f"m:b:{row.id}")]]))
                            try:
                                await m.bot.send_message(old, f"📤 انتقلت ملكية @{row.username} إلى {esc(m.user.full_name)}.", parse_mode=ParseMode.HTML)
                            except TelegramError:
                                pass
            except Exception as e:
                log.warning("on_start tr_ error: %s", e)
        await home(m, new=True)
    except Exception as e:
        log.error("on_start unhandled error for user %s: %s", getattr(update.effective_user, 'id', '?') if update else '?', e)




async def on_managed_bot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """إنشاء فوري: تيليجرام يبلغنا أن المستخدم أنشأ بوتاً مُداراً من هذا الصانع."""
    mb = update.managed_bot
    if mb is None:
        return
    m = M(None, context, user=mb.user)
    if not m.is_admin and (m.uid in (await platform.get(m.fid))["banned"] or m.uid in (await platform.get(0))["banned"]):
        return
    st = m.st or {}
    tpl_key = st.get("tpl") if st.get("k") == "token" else None
    try:
        token = await context.bot.get_managed_bot_token(mb.bot.id)
    except TelegramError:
        log.exception("get_managed_bot_token failed")
        return
    async with db.Session() as s:
        existing = await s.get(db.Bot, mb.bot.id)
        if existing is not None:  # تحديث توكن بوت موجود
            existing.token, existing.username = crypto.enc(token), mb.bot.username or existing.username
            await s.commit()
    if existing is not None:
        if existing.status == "active":
            await m.mgr.restart_bot(mb.bot.id)
        return
    if not tpl_key:
        try:
            await m.send(m.t("🤖 أُنشئ بوتك. اختر نوعه ثم أرسل التوكن لإكمال التفعيل.", "🤖 Your bot was created. Pick its type, then send the token to finish."),
                         kb([[B(m.t("🧭 اختيار النوع", "🧭 Choose type"), "m:new")]]))
        except TelegramError:
            pass
        return
    await create_bot(m, token, tpl_key)


async def _cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    m = M(update, context)
    if m.is_admin:
        await admin.admin_home(m)


async def _msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await on_message(update, context)


async def _start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await on_start(update, context)


async def _error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    await errors.handle(update, context, "maker")


async def apply_menu(app: Application) -> None:
    """زر القائمة بجانب خانة الكتابة في بوت الصانع يعرض الأوامر دوماً."""
    from telegram import MenuButtonCommands
    try:
        await app.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        await db.kv_set(0, "sys:menu_web", False)
    except Exception:  # noqa: BLE001
        log.debug("maker menu button not applied")


async def set_commands(app: Application) -> None:
    from telegram import BotCommand, BotCommandScopeChat
    await apply_menu(app)
    try:
        await app.bot.set_my_commands([BotCommand("start", "القائمة الرئيسية")])
        if config.ADMIN_ID:
            await app.bot.set_my_commands([BotCommand("start", "القائمة الرئيسية"), BotCommand("admin", "لوحة الإدارة")], scope=BotCommandScopeChat(config.ADMIN_ID))
    except TelegramError:
        pass


async def on_chat_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """قبول فوري وتلقائي لأي طلب انضمام لقناة أو مجموعة مع دعم الضغط العالي والفيضان."""
    jr = update.chat_join_request
    if not jr:
        return
    chat_id = jr.chat.id
    user_id = jr.from_user.id
    name = jr.from_user.full_name or ""
    title = jr.chat.title or "القناة"

    # 1. قبول الطلب مع إعادة المحاولة التلقائية في حال طلب تيليجرام مهلة (Flood / RetryAfter)
    approved = False
    for _ in range(3):
        try:
            await context.bot.approve_chat_join_request(chat_id, user_id)
            approved = True
            log.info("Auto-approved join request for user %s (%s) in chat %s (%s)", user_id, name, chat_id, title)
            break
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after + 0.1)
        except TelegramError as e:
            # تم قبوله مسبقاً أو ملغي
            log.debug("Join request exception for %s: %s", user_id, e)
            approved = True
            break
        except Exception as e:
            log.warning("Failed to approve join request for %s in %s: %s", user_id, chat_id, e)
            break

    # 2. تسجيل القناة في الذاكرة والقاعدة دون إبطاء البوت
    if chat_id not in _KNOWN_CHANNELS:
        _KNOWN_CHANNELS.add(chat_id)
        async def _save_chan():
            try:
                channels = await db.kv_get(0, "sys:channels", []) or []
                if chat_id not in [c.get("id") for c in channels]:
                    channels.append({"id": chat_id, "title": title, "type": jr.chat.type})
                    await db.kv_set(0, "sys:channels", channels)
            except Exception:
                pass
        asyncio.create_task(_save_chan())

    # 3. إرسال رسالة ترحيب في الخلفية بشكل غير متزامن تماماً لعدم استهلاك وقت المعالجة
    if approved:
        async def _send_welcome():
            try:
                await context.bot.send_message(
                    user_id,
                    f"🎉 أهلاً <b>{esc(name)}</b>!\nتم قبول طلب انضمامك إلى <b>{esc(title)}</b> بنجاح ✅",
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass
        asyncio.create_task(_send_welcome())


async def on_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """تسجيل أي قناة أو مجموعة يُضاف إليها البوت كمشرف."""
    m = update.my_chat_member
    if not m:
        return
    chat = m.chat
    status = m.new_chat_member.status if m.new_chat_member else ""
    log.info("Maker bot status in %s (%s): %s", chat.id, chat.title, status)
    if status in ("administrator", "creator"):
        try:
            channels = await db.kv_get(0, "sys:channels", []) or []
            if chat.id not in [c.get("id") for c in channels]:
                channels.append({"id": chat.id, "title": chat.title or "", "type": chat.type})
                await db.kv_set(0, "sys:channels", channels)
            if config.ADMIN_ID:
                await context.bot.send_message(
                    config.ADMIN_ID,
                    f"📢 تمت إضافة البوت مشرفاً في: <b>{esc(chat.title)}</b> (<code>{chat.id}</code>)\nسيتم قبول جميع طلبات الانضمام تلقائياً فور إرسالها ✅",
                    parse_mode=ParseMode.HTML,
                )
        except Exception:
            pass


async def _cmd_approve_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """أمر لقبول جميع الطلبات المعلقة دفعة واحدة."""
    m = M(update, context)
    if not m.is_admin:
        return
    args = context.args or []
    target_chat = args[0] if args else None
    channels = await db.kv_get(0, "sys:channels", []) or []
    target_chats = [target_chat] if target_chat else [c.get("id") for c in channels]
    if not target_chats:
        await m.send("⚠️ أرسل الأمر متبوعاً بمعرف القناة أو الآيدي:\n<code>/approve @channel_username</code>\nأو أضف البوت مشرفاً في القناة أولاً لتسجيلها تلقائياً.")
        return
    wait_msg = await m.send("⏳ جاري فحص وقبول جميع طلبات الانضمام المعلقة...")
    async with db.Session() as s:
        u_rows = (await s.execute(select(db.MUser.user_id))).scalars().all()
    approved = 0
    for cid in target_chats:
        for uid in u_rows:
            try:
                await context.bot.approve_chat_join_request(cid, uid)
                approved += 1
                await asyncio.sleep(0.04)
            except Exception:
                pass
    await wait_msg.edit_text(f"✅ تم الانتهاء! تم قبول {approved} طلب انضمام.")


def register(app: Application) -> None:
    """يسجّل معالجات الصانع الرئيسي."""
    app.add_handler(CommandHandler("start", _start, filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("admin", _cmd_admin, filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("approve", _cmd_approve_all, filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("accept", _cmd_approve_all, filters.ChatType.PRIVATE))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(ManagedBotUpdatedHandler(on_managed_bot))
    app.add_handler(ChatJoinRequestHandler(on_chat_join_request))
    app.add_handler(ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.StatusUpdate.ALL & ~filters.UpdateType.EDITED, _msg))
    app.add_error_handler(_error)


from . import admin  # noqa: E402  (في آخر الملف لتفادي الاستيراد الدائري)
