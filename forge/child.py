"""نواة البوت المصنوع: تتبّع المستخدمين، الاشتراك الإجباري، ولوحة المالك المشتركة بين كل القوالب."""
from __future__ import annotations

import asyncio
import csv
import datetime as dt
import io
import json
import logging
import re
import secrets
import time

from sqlalchemy import func, select, update as sa_update
from telegram import Update
from telegram.constants import ChatType, ParseMode
from telegram.error import Forbidden, RetryAfter, TelegramError
from telegram.ext import (Application, ApplicationHandlerStop, CallbackQueryHandler, ChatJoinRequestHandler, ChatMemberHandler,
                          CommandHandler, ContextTypes, InlineQueryHandler, MessageHandler, TypeHandler, filters)

from . import config, db, errors, ui
from . import plat as platform
from .ctx import Ctx
from .i18n import LANGS, LANG_NAMES, norm
from .ui import B, esc, kb, clean_url

log = logging.getLogger("forge.child")


def default_core() -> dict:
    return {
        "admins": [], "fs": [], "fs_msg": "", "fs_passed": 0, "links": {},
        "welcome": {"text": "", "buttons": [], "order": "before"},
        "quick": [], "shortcuts": [], "autodel": {"on": False, "sec": 300},
        "notify_join": False, "notify_block": False, "protect": False, "lang": "auto",
        "maint": {"on": False, "text": ""},
        "site": {"on": True, "color": "", "tagline": "", "menu": True},
        "idn": {"desc": "", "about": ""},
    }


async def load_core(bot_id: int) -> dict:
    core = default_core()
    saved = await db.kv_get(bot_id, "core")
    if isinstance(saved, dict):
        core.update(saved)
    return core


# ───────────────────────── تتبّع المستخدمين ─────────────────────────
async def touch(c: Ctx, *, start: bool = False, count: bool = True, source: str = "") -> tuple[bool, bool]:
    """يسجّل المستخدم ويحدّث نشاطه. يعيد (جديد؟، محظور؟)."""
    if not c.user:
        return False, False
    u = c.user
    is_new = False
    banned = False
    for attempt in range(3):
        try:
            async with db.Session() as s:
                row = await s.get(db.BUser, (c.bot_id, u.id))
                is_new = row is None
                if is_new:
                    row = db.BUser(bot_id=c.bot_id, user_id=u.id, source=source[:32])
                    s.add(row)
                row.name = (u.full_name or "")[:128]
                row.username = u.username or ""
                row.lang = (u.language_code or "")[:8]
                row.premium = bool(u.is_premium)
                row.last_seen = db.now()
                row.blocked = False
                if count:
                    row.msgs = (row.msgs or 0) + 1
                banned = bool(row.banned)
                await s.commit()
            break
        except Exception as e:
            if attempt == 2:
                log.warning("touch() error for bot %d user %d after 3 attempts: %s", c.bot_id, u.id, e)
                return False, False
            await asyncio.sleep(0.04 * (attempt + 1))

    inc = {}
    if is_new:
        inc["new"] = 1
    if start:
        inc["starts"] = 1
    if count:
        inc["msgs"] = 1
        inc[f"h{db.now().hour:02d}"] = 1
    if inc:
        await db.bump(c.bot_id, **inc)
    return is_new, banned


async def counts(bot_id: int) -> dict:
    U = db.BUser
    day0 = dt.datetime.combine(db.now().date(), dt.time())
    async with db.Session() as s:
        async def n(*cond):
            return int((await s.execute(select(func.count()).select_from(U).where(U.bot_id == bot_id, *cond))).scalar() or 0)
        return {
            "total": await n(), "private": await n(U.kind == "private"), "groups": await n(U.kind != "private"),
            "banned": await n(U.banned.is_(True)), "blocked": await n(U.blocked.is_(True)),
            "premium": await n(U.premium.is_(True)), "new": await n(U.joined >= day0),
            "active": await n(U.last_seen >= day0),
            "msgs": int((await s.execute(select(func.coalesce(func.sum(U.msgs), 0)).where(U.bot_id == bot_id))).scalar() or 0),
        }


# ───────────────────────── الاشتراك الإجباري ─────────────────────────
async def check_sub(c: Ctx) -> bool:
    fs = [x for x in c.core.get("fs", []) if x.get("on", True)]
    if not fs or c.is_owner:
        return True
    missing = []
    for x in fs:
        if x.get("type") == "chat":
            try:
                m = await c.bot.get_chat_member(x["chat_id"], c.uid)
                if m.status in ("left", "kicked"):
                    missing.append(x)
            except TelegramError:
                continue  # تعذّر التحقق: لا نحجب المستخدم
        elif not c.x.user_data.get("fs_ack"):
            missing.append(x)
    if not missing:
        if c.x.user_data.pop("fs_blocked", None):
            c.core["fs_passed"] = int(c.core.get("fs_passed", 0)) + 1
            await c.save_core()
        return True
    c.x.user_data["fs_blocked"] = True
    text = c.core.get("fs_msg") or c.t("🔐 للاستخدام، اشترك أولاً في القنوات التالية ثم اضغط «تحقّقت».",
                                       "🔐 Please join the following first, then tap “I joined”.")
    if missing:
        rows = []
        for x in missing:
            u = clean_url(x.get("url"))
            if u:
                rows.append([B(f"📢 {x.get('title') or 'Channel'}", url=u)])
        if rows:
            rows.append([B(c.t("✅ تحقّقت", "✅ I joined"), "sub:check", style="success")])
            await c.send(text, kb(rows))
            return False
    return True


# ───────────────────────── شاشات البداية ─────────────────────────
def parse_buttons(text: str) -> list[list[dict]]:
    """كل سطر صف. الأزرار في السطر تُفصل بـ && والصيغة: نص - رابط أو رابط - نص أو نص | رابط"""
    rows = []
    for line in text.splitlines():
        row = []
        for part in line.split("&&"):
            part = part.strip()
            if not part:
                continue
            sep = None
            for candidate in (" - ", " | ", " : ", "-", "|", ":"):
                if candidate in part:
                    sep = candidate
                    break
            if not sep:
                continue
            t, u = part.split(sep, 1)
            t, u = t.strip(), u.strip()
            u_clean = clean_url(u)
            t_clean = clean_url(t)
            if not u_clean and t_clean:
                t, u = u, t
                u_clean = t_clean
            if t and u_clean:
                row.append({"t": t[:60], "u": u_clean})
        if row:
            rows.append(row)
    return rows


def buttons_kb(rows: list[list[dict]]):
    valid_rows = []
    for r in (rows or []):
        row = []
        for b in r:
            t = b.get("t") or "زر"
            u = clean_url(b.get("u"))
            if u:
                row.append(B(t, url=u))
        if row:
            valid_rows.append(row)
    return kb(valid_rows) if valid_rows else None



async def user_home(c: Ctx) -> None:
    w = c.core.get("welcome") or {}
    text, order = w.get("text") or "", w.get("order", "before")

    async def welcome():
        if text:
            await c.send(text.replace("{name}", c.name), buttons_kb(w.get("buttons") or []))

    if order == "only" and text:
        return await welcome()
    if order == "before":
        await welcome()
    await c.tpl.home(c)
    if order == "after":
        await welcome()


async def week_series(bot_ids: list[int], key: str, days: int = 7) -> list[int]:
    """قيم عدّاد يومي لآخر N يوماً، الأقدم أولاً."""
    out = []
    for i in range(days - 1, -1, -1):
        d = (db.now() - dt.timedelta(days=i)).strftime("%Y-%m-%d")
        out.append((await db.daily(bot_ids, d)).get(key, 0))
    return out


GROUPS = {
    "aud": ("📣 الجمهور", "📣 Audience", [("stats", "📊 الأرقام", "📊 Numbers"), ("users", "👥 الأعضاء", "👥 Members"),
                                         ("bc", "📡 رسالة جماعية", "📡 Broadcast"), ("ban", "🚫 قائمة الحظر", "🚫 Ban list")]),
    "gate": ("🚪 الدخول والترحيب", "🚪 Entry & welcome", [("fs", "🔐 اشتراك إجباري", "🔐 Forced subscription"), ("wel", "👋 رسالة الترحيب", "👋 Welcome message"),
                                                         ("sl", "🔗 روابط التتبّع", "🔗 Tracking links")]),
    "auto": ("💬 الردود الآلية", "💬 Auto replies", [("qr", "💬 ردود بالكلمات", "💬 Keyword replies"), ("sc", "⚡ أوامر مختصرة", "⚡ Custom commands"),
                                                    ("ad", "⏱ تنظيف تلقائي", "⏱ Auto clean-up")]),
    "sys": ("🛠 النظام", "🛠 System", [("set", "⚙️ خيارات البوت", "⚙️ Bot options"), ("sys", "🗄 النسخ الاحتياطي", "🗄 Backups"),
                                      ("adm", "🛡 المشرفون", "🛡 Admins"), ("guide", "📖 شرح اللوحة", "📖 Panel guide")]),
}
SCREEN_GROUP = {a: g for g, (_, _, items) in GROUPS.items() for a, _, _ in items}
SCREEN_GROUP.update({"u": "aud", "usearch": "aud", "uban": "aud", "umsg": "aud", "uexp": "aud", "mt": "sys", "mttxt": "sys"})
PREFIX_GROUP = {"adm": "sys", "bc": "aud", "ban": "aud", "fs": "gate", "wel": "gate", "sl": "gate", "qr": "auto", "sc": "auto", "ad": "auto",
                "set": "sys", "tg": "sys", "sys": "sys", "adm": "sys"}


async def owner_home(c: Ctx) -> None:
    n = await counts(c.bot_id)
    info, rows = await c.tpl.owner(c)
    week = await week_series([c.bot_id], "new")
    t = c.t
    adm = c.x.bot_data.get("adm") or {}
    lk = current_lock(c.x.bot_data)
    banner = ""
    if lk is not None and lk["mode"] == "own":
        banner = t("🛠 <b>وضع الصيانة مفعّل</b> — الأعضاء يرون رسالة الصيانة فقط. أوقفه من «النظام» ← «خيارات البوت».\n\n",
                   "🛠 <b>Maintenance mode is on</b> — members only see the maintenance message. Turn it off in System → Bot options.\n\n")
    elif lk is not None:
        banner = lock_text(lk, c.lang) + "\n\n"
    text = (f"🎛 <b>{t('غرفة التحكم', 'Control room')}</b> — @{c.bot.username}" + (" ✅" if adm.get("verified") else "") + f"\n🧩 {c.tpl.title(c.lang)}\n{ui.LINE}\n" + banner
            + t(f"👥 <b>{ui.num(n['total'])}</b> عضو  ·  🆕 <b>+{n['new']}</b> اليوم  ·  💬 <b>{ui.num(n['msgs'])}</b> رسالة",
                f"👥 <b>{ui.num(n['total'])}</b> members  ·  🆕 <b>+{n['new']}</b> today  ·  💬 <b>{ui.num(n['msgs'])}</b> messages")
            + f"\n📈 <code>{ui.spark(week)}</code> " + t("أعضاء جدد — آخر 7 أيام", "new members — last 7 days")
            + ("\n\n" + info if info else ""))
    todo = await checklist(c)
    done = sum(1 for ok, _, _ in todo if ok)
    if todo and done < len(todo):
        text += "\n\n🚀 " + t("جاهزية بوتك", "Setup progress") + f": <code>{ui.bar(done, len(todo))}</code> {round(done * 100 / len(todo))}%"
    rows = list(rows) + [
        [B(t(f"🚀 أكمل التجهيز ({done}/{len(todo)})", f"🚀 Finish setup ({done}/{len(todo)})"), "o:todo", style="primary")] if todo and done < len(todo) else None,
        [B(t("🪪 هوية البوت", "🪪 Bot identity"), "o:idn")],
        [B(t("👁 جرّب كمستخدم", "👁 Try as a user"), "o:preview"), B(t("📖 شرح القالب", "📖 Template guide"), "o:tguide")],
        [B(t(GROUPS["aud"][0], GROUPS["aud"][1]), "o:g:aud"), B(t(GROUPS["gate"][0], GROUPS["gate"][1]), "o:g:gate")],
        [B(t(GROUPS["auto"][0], GROUPS["auto"][1]), "o:g:auto"), B(t(GROUPS["sys"][0], GROUPS["sys"][1]), "o:g:sys")],
    ]
    await c.edit(text, kb(rows))


async def checklist(c: Ctx) -> list:
    """خطوات تجهيز البوت: العامة ثم الخاصة بالقالب. كل خطوة (تمّت؟، الوصف، الزر الذي يفتحها)."""
    core = c.core
    items = list(await c.tpl.checklist(c))
    if not items:
        return []
    items.append((bool((core.get("welcome") or {}).get("text")), c.t("اكتب رسالة ترحيب خاصة ببوتك", "Write your own welcome message"), "o:wel"))
    items.append((bool((core.get("idn") or {}).get("custom")), c.t("راجع وصف البوت الظاهر قبل «بدء»", "Review the bot description shown before Start"), "o:idn"))
    return items


async def scr_todo(c: Ctx) -> None:
    t = c.t
    todo = await checklist(c)
    done = sum(1 for ok, _, _ in todo if ok)
    lines = "\n".join(("✅ " if ok else "⬜️ ") + esc(label) for ok, label, _ in todo)
    rows = [[B("▶️ " + label[:44], cb)] for ok, label, cb in todo if not ok]
    text = (ui.head(t("🚀 تجهيز البوت", "🚀 Bot setup")) + f"<code>{ui.bar(done, max(1, len(todo)))}</code> {done}/{len(todo)}\n\n{lines}\n\n" +
            (t("🎉 بوتك جاهز تماماً. انشر رابطه الآن.", "🎉 Your bot is fully set up. Share its link now.") if done == len(todo)
             else t("اضغط أي خطوة لم تكتمل لتفتحها مباشرة.", "Tap any unfinished step to open it.")))
    await c.edit(text, kb(rows + [[B(t("🎛 غرفة التحكم", "🎛 Control room"), "o:home")]]))


# ───────────────────────── موقع البوت وهويته ─────────────────────────
def site_conf(core: dict) -> dict:
    return {"on": True, "color": "", "tagline": "", "menu": True, **(core.get("site") or {})}


async def scr_site(c: Ctx) -> None:
    from . import web
    from .web.server import COLORS, PALETTE
    t, cfg = c.t, site_conf(c.core)
    url = web.site_url(c.bot.username)
    day = await db.daily([c.bot_id], db.today())
    week = sum(await week_series([c.bot_id], "web"))
    color = cfg["color"] or COLORS.get(c.tpl.key, "#2563eb")
    cname = next((n for h, n in PALETTE if h == color), t("لون القالب", "template colour"))
    kind = (t("موقع كامل خاص بهذا النوع: يتصفح منه الزوار ويتفاعلون، وما يفعلونه يصل إلى البوت.", "A full site for this type: visitors browse and act, and it all reaches the bot.") if c.tpl.site
            else t("صفحة تعريفية ببوتك مع زر يفتحه في تيليجرام.", "A landing page for your bot with a button that opens it in Telegram."))
    if not web.enabled():
        state = t("⚪ خادم الويب متوقف في هذه المنصة.", "⚪ The web server is off on this platform.")
    elif not web.public():
        state = t("🟡 الموقع جاهز، لكن المنصة تعمل الآن بلا رابط عام، وتيليجرام لا يفتح صفحة داخله إلا من رابط https. يفعّله مدير المنصة بضبط <code>PUBLIC_URL</code> أو تشغيل النفق التلقائي.",
                  "🟡 The site is ready, but the platform has no public URL yet, and Telegram only opens in-app pages from an https URL.")
    elif not cfg["on"]:
        state = t("⚪ الموقع متوقف: الرابط لا يفتح وأزراره مخفية.", "⚪ The site is off: the link is closed and its buttons are hidden.")
    else:
        state = (t("🟢 يعمل داخل تيليجرام: يفتحه العضو من زر القائمة بجانب خانة الكتابة، ومن الزر الأول في الشاشة الرئيسية، دون الخروج من البوت.",
                   "🟢 Live inside Telegram: members open it from the menu button next to the message box and from the first home button, without leaving the bot.")
                 if web.https() and c.tpl.site else
                 t("🟢 يعمل ويفتح داخل تيليجرام.", "🟢 Live and opens inside Telegram.") if web.https() else
                 t("🟢 الموقع يعمل ويفتح في المتصفح. ليفتح داخل تيليجرام يحتاج رابط المنصة أن يكون https.", "🟢 The site is live and opens in the browser. Opening inside Telegram needs an https platform URL."))
    text = (ui.head(t("🌐 موقع البوت", "🌐 Bot website")) + f"{kind}\n\n{state}\n\n🔗 <code>{esc(url)}</code>\n\n" + ui.rows([
        (t("زيارات اليوم", "Visits today"), day.get("web", 0)), (t("زيارات آخر 7 أيام", "Visits, last 7 days"), week),
        (t("اللون", "Colour"), cname), (t("زر القائمة بجانب خانة الكتابة", "Menu button next to the message box"), "🟢" if cfg["menu"] else "⚪")]) +
        (f"\n\n📝 {esc(cfg['tagline'])}" if cfg["tagline"] else ""))
    live = web.public() and cfg["on"]
    await c.edit(text, kb([
        [c.site_btn("↗ افتح الموقع", "↗ Open the site", "📱 افتحه داخل تيليجرام", "📱 Open it inside Telegram")] if live else None,
        [B(t("🔳 رمز QR للموقع", "🔳 Site QR code"), "o:siteqr"), B(t("🎨 اللون", "🎨 Colour"), "o:sitecol")] if live else [B(t("🎨 اللون", "🎨 Colour"), "o:sitecol")],
        [B(t("✏️ العبارة التعريفية", "✏️ Tagline"), "o:sitetag"), B((t("⚪ أخفِ زر القائمة", "⚪ Hide menu button") if cfg["menu"] else t("🟢 أظهر زر القائمة", "🟢 Show menu button")), "o:sitemenu")],
        [B(t("⚪ أوقف الموقع", "⚪ Turn the site off") if cfg["on"] else t("🟢 شغّل الموقع", "🟢 Turn the site on"), "o:siteon")],
        [B(t("🎛 غرفة التحكم", "🎛 Control room"), "o:home")]]))


def default_identity(tpl, lang: str) -> tuple[str, str]:
    """وصف ونبذة افتراضيان يظهران في صفحة البوت قبل أن يكتب المالك نصه."""
    if lang == "ar":
        return f"{tpl.pitch('ar')}\n\nاضغط «بدء» للدخول 👇"[:500], tpl.pitch("ar")[:120]
    return f"{tpl.pitch('en')}\n\nPress Start to begin 👇"[:500], tpl.pitch("en")[:120]


async def apply_identity(app: Application, *, first: bool = False) -> None:
    """يضبط وصف البوت ونبذته في تيليجرام. عند الإنشاء لا يستبدل نصاً كتبه المالك في BotFather."""
    core, tpl = app.bot_data["core"], app.bot_data["tpl"]
    idn = core.setdefault("idn", {"desc": "", "about": ""})
    try:
        if first:
            if idn.get("set"):
                return
            have = await app.bot.get_my_description()
            if getattr(have, "description", ""):
                idn["set"] = True
                await db.kv_set(app.bot_data["bot_id"], "core", core)
                return
        for code, lang in ((None, "ar"), ("en", "en")):
            desc, about = default_identity(tpl, lang)
            if lang == "ar":
                desc, about = idn.get("desc") or desc, idn.get("about") or about
            elif idn.get("desc") or idn.get("about"):
                continue      # نص المالك يظهر لكل اللغات
            await app.bot.set_my_description(desc, language_code=code)
            await app.bot.set_my_short_description(about, language_code=code)
        idn["set"] = True
        await db.kv_set(app.bot_data["bot_id"], "core", core)
    except Exception:  # noqa: BLE001  (يشمل إيقاف البوت أثناء التنفيذ)
        log.debug("identity not applied for %s", app.bot_data.get("bot_id"))


async def apply_menu_button(app: Application) -> None:
    """زر القائمة بجانب خانة الكتابة يعرض أوامر البوت دوماً."""
    from telegram import MenuButtonCommands
    try:
        await app.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        app.bot_data["menu_web"] = False
    except Exception:
        pass
    except Exception:  # noqa: BLE001
        log.debug("menu button not applied for %s", app.bot_data.get("bot_id"))


async def scr_idn(c: Ctx) -> None:
    t = c.t
    idn = c.core.get("idn") or {}
    d_desc, d_about = default_identity(c.tpl, "ar")
    text = (ui.head(t("🪪 هوية البوت", "🪪 Bot identity")) + t("هكذا يظهر بوتك للناس قبل أن يضغطوا «بدء»، وعند مشاركة رابطه.", "How your bot looks to people before they press Start and when its link is shared.") +
            f"\n\n<b>{t('الاسم', 'Name')}</b>\n{esc(idn.get('name') or c.bot.bot.first_name)}\n\n<b>{t('الوصف — يظهر في الشاشة الفارغة قبل «بدء»', 'Description — shown on the empty screen before Start')}</b>\n{esc(idn.get('desc') or d_desc)}"
            f"\n\n<b>{t('النبذة — تظهر في صفحة البوت وعند مشاركته', 'About — shown on the bot profile and when shared')}</b>\n{esc(idn.get('about') or d_about)}"
            + ("" if idn.get("custom") else "\n\n" + t("<i>النصوص الحالية افتراضية حسب نوع البوت. اكتب نصك الخاص ليتميز بوتك.</i>", "<i>These are defaults for the bot type. Write your own to stand out.</i>")))
    await c.edit(text[:4000], kb([
        [B(t("✏️ الاسم", "✏️ Name"), "o:idname"), B(t("📝 الوصف", "📝 Description"), "o:iddesc"), B(t("ℹ️ النبذة", "ℹ️ About"), "o:idabout")],
        [B(t("♻️ أعد النصوص الافتراضية", "♻️ Restore defaults"), "o:idreset")] if idn.get("custom") else None,
        [B(t("🎛 غرفة التحكم", "🎛 Control room"), "o:home")]]))


async def group_menu(c: Ctx, g: str) -> None:
    if g not in GROUPS:
        return await owner_home(c)
    ar, en, items = GROUPS[g]
    hints = {"aud": ("أرقام بوتك، أعضاؤه، ومراسلتهم دفعة واحدة.", "Your numbers, members and mass messaging."),
             "gate": ("ما يراه العضو عند دخوله، ومن أين جاء.", "What members see when they enter, and where they came from."),
             "auto": ("ردود يرسلها البوت تلقائياً دون تدخلك.", "Replies the bot sends on its own."),
             "sys": ("خيارات عامة، نسخ احتياطي، ومشرفون.", "General options, backups and admins.")}[g]
    btns = [B(c.t(a_ar, a_en), f"o:{act}") for act, a_ar, a_en in items]
    await c.edit(ui.head(c.t(ar, en)) + "\n" + c.t(*hints), kb(ui.grid(btns, 2) + [[B(c.t("🎛 غرفة التحكم", "🎛 Control room"), "o:home")]]))


async def on_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    c = Ctx(update, context)
    if c.chat is None or c.chat.type != ChatType.PRIVATE:
        await c.tpl.group_msg(c)
        return
    param = context.args[0] if context.args else ""
    is_new, banned = await touch(c, start=True, source=param if param.startswith("sl_") else "")
    if banned:
        return
    if param.startswith("sl_"):
        links = c.core.setdefault("links", {})
        if param[3:] in links:
            links[param[3:]]["n"] = int(links[param[3:]].get("n", 0)) + 1
            await c.save_core()
            await db.bump(c.bot_id, links=1)
        param = ""
    if is_new and c.core.get("notify_join") and not c.is_owner:
        await c.notify_owner(c.t(f"🔔 مستخدم جديد: {c.name} (<code>{c.uid}</code>)",
                                 f"🔔 New user: {c.name} (<code>{c.uid}</code>)"))
    c.clear_state()
    if not await check_sub(c):
        context.user_data["pending_start"] = param
        return
    await _enter(c, param)
    if not c.is_owner:
        await send_promo(context, c.chat.id, c.user, "start")


def context_fid(c: Ctx) -> int:
    return int(c.x.bot_data.get("factory_id", 0) or 0)


# ───────────────────────── الإغلاق والصيانة ─────────────────────────
def maker_app(bot_data: dict):
    """تطبيق الصانع الذي أُنشئ هذا البوت عبره (الرئيسي أو صانع فرعي)."""
    mgr = bot_data.get("manager")
    fid = int(bot_data.get("factory_id") or 0)
    if mgr is None:
        return None
    return getattr(mgr, "maker", None) if fid == 0 else mgr.apps.get(fid)


def current_lock(bot_data: dict) -> dict | None:
    """إغلاق الإدارة إن وُجد، وإلا وضع الصيانة الذي فعّله المالك."""
    lk = platform.admin_lock(bot_data)
    if lk is not None:
        return lk
    mt = (bot_data.get("core") or {}).get("maint") or {}
    return {"mode": "own", "reason": mt.get("text") or ""} if mt.get("on") else None


def lock_text(lk: dict, lang: str, *, owner: bool = False) -> str:
    ar = lang == "ar"
    mode = lk["mode"]
    reason = (lk.get("reason") if ar else (lk.get("reason_en") or lk.get("reason"))) or ""
    if mode == "own":
        return reason or ("🛠 <b>البوت في صيانة</b>\nنعود قريباً، شكراً لصبرك." if ar else "🛠 <b>Under maintenance</b>\nWe'll be back soon, thanks for your patience.")
    if mode == "maint":
        s = ("🛠 <b>البوت في صيانة</b>\nأوقفته إدارة المنصة مؤقتاً للصيانة ويعود قريباً." if ar
             else "🛠 <b>Under maintenance</b>\nThe platform paused this bot for maintenance. It will be back soon.")
    elif mode == "temp" and lk.get("until"):
        left = ui.dur(max(60, lk["until"] - time.time()), lang)
        s = (f"⏳ <b>البوت مغلق مؤقتاً</b>\nأغلقته إدارة المنصة.\n🔓 يعود للعمل بعد: <b>{left}</b>" if ar
             else f"⏳ <b>Temporarily closed</b>\nClosed by the platform.\n🔓 Back in: <b>{left}</b>")
    else:
        s = "🚫 <b>هذا البوت مغلق</b>\nأغلقته إدارة المنصة." if ar else "🚫 <b>This bot is closed</b>\nClosed by the platform."
    if reason:
        s += ("\n📌 السبب: " if ar else "\n📌 Reason: ") + esc(reason)
    if owner and mode != "maint":
        s += ("\n\n👤 أنت مالك هذا البوت. لطلب المراجعة: افتح الصانع ← «بوتاتي» ← هذا البوت ← «طلب مراجعة»." if ar
              else "\n\n👤 You own this bot. To appeal: open the maker → “My bots” → this bot → “Request review”.")
    return s


async def on_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يسبق كل المعالجات: إن كان البوت مغلقاً أو في صيانة يرد بالإشعار ويوقف المعالجة."""
    bd = context.bot_data
    lk = current_lock(bd)
    if lk is None or update.my_chat_member is not None or update.chat_member is not None:
        return
    user, chat = update.effective_user, update.effective_chat
    uid = user.id if user else 0
    core = bd.get("core") or {}
    staff = bool(uid) and (uid == bd["owner_id"] or uid in core.get("admins", []))
    sup = bool(uid) and uid == config.ADMIN_ID and not bd.get("factory_id") and (bd.get("adm") or {}).get("super")
    if sup or (staff and lk["mode"] in ("maint", "own")):
        return
    try:      # مهما حدث هنا، البوت المغلق لا يكمل المعالجة
        forced = core.get("lang") or "auto"
        lang = norm(user.language_code if (forced == "auto" and user) else (None if forced == "auto" else forced))
        text = lock_text(lk, lang, owner=uid == bd["owner_id"])
        if update.inline_query is not None:
            await update.inline_query.answer([], cache_time=5)
        elif update.callback_query is not None:
            await update.callback_query.answer(re.sub(r"<[^>]+>", "", text)[:190], show_alert=True)
        elif update.message is not None and chat is not None and chat.type == ChatType.PRIVATE:
            ud = context.user_data if context.user_data is not None else {}
            sig = (lk["mode"], lk.get("at"), lk.get("reason"))
            last = ud.get("lock_seen") or (None, 0)
            if last[0] != sig or time.time() - last[1] > 8:      # لا نكرر الإشعار نفسه مع كل رسالة
                ud["lock_seen"] = (sig, time.time())
                mk = maker_app(bd)
                markup = None
                if uid == bd["owner_id"] and mk is not None and lk["mode"] in ("closed", "temp"):
                    markup = kb([[B("🗂 افتح الصانع" if lang == "ar" else "🗂 Open the maker", url=f"https://t.me/{mk.bot.username}")]])
                await context.bot.send_message(chat.id, text, parse_mode=ParseMode.HTML, reply_markup=markup)
    except TelegramError:
        pass
    except Exception:  # noqa: BLE001
        log.exception("lock notice failed")
    raise ApplicationHandlerStop


# ───────────────────────── رسالة الترويج ─────────────────────────
PROMO_AR = "🤖 عجبك البوت؟ اصنع بوتك الخاص مجاناً!\n{maker}"
PROMO_EN = "🤖 Like this bot? Build your own for free!\n{maker}"


async def promo_cfg(bot_data: dict) -> dict | None:
    if bot_data["tpl"].key == "maker" or maker_app(bot_data) is None:
        return None
    p = await platform.get(int(bot_data.get("factory_id") or 0))
    return platform.promo_for(p, bot_data.get("adm"))


def promo_render(cfg: dict, lang: str, *, maker: str, bot: str, name: str, owner_id: int):
    text = cfg.get("text") or (PROMO_AR if lang == "ar" else PROMO_EN)
    text = text.replace("{maker}", f"@{maker}").replace("{bot}", f"@{bot}").replace("{name}", esc(name))
    markup = None
    if cfg.get("btn", True):
        markup = kb([[B("🤖 اصنع بوتك مجاناً" if lang == "ar" else "🤖 Build yours for free", url=f"https://t.me/{maker}?start=ref_{owner_id}")]])
    return text, markup


async def send_promo(context, chat_id: int, user, trigger: str) -> bool:
    """يرسل رسالة الترويج إن كانت مفعّلة لهذا البوت ولم يرها العضو مؤخراً."""
    bd = context.bot_data
    cfg = await promo_cfg(bd)
    if cfg is None or cfg.get("when", "both") not in (trigger, "both") or current_lock(bd) is not None:
        return False
    ud = context.user_data if context.user_data is not None else {}
    if time.time() - ud.get("promo_at", 0) < int(cfg.get("every", 86400)):
        return False
    forced = (bd.get("core") or {}).get("lang") or "auto"
    lang = norm(getattr(user, "language_code", None) if forced == "auto" else forced)
    mk = maker_app(bd)
    text, markup = promo_render(cfg, lang, maker=mk.bot.username, bot=context.bot.username,
                                name=getattr(user, "first_name", "") or "", owner_id=bd["owner_id"])
    try:
        await context.bot.send_message(chat_id, text, parse_mode=ParseMode.HTML, reply_markup=markup,
                                       disable_notification=True, disable_web_page_preview=True)
    except TelegramError:
        return False
    ud["promo_at"] = time.time()
    await db.bump(bd["bot_id"], promo=1)
    return True


async def _promo_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_promo(context, context.job.chat_id, context.job.data, "idle")


async def on_after(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """بعد كل تفاعل من عضو: نؤجل رسالة الترويج إلى أن يتوقف عن استخدام البوت."""
    user, chat = update.effective_user, update.effective_chat
    if user is None or chat is None or chat.type != ChatType.PRIVATE or context.job_queue is None:
        return
    if update.message is None and update.callback_query is None:
        return
    bd = context.bot_data
    if user.id == bd["owner_id"] or user.id in (bd.get("core") or {}).get("admins", []):
        return
    cfg = await promo_cfg(bd)
    name = f"promo:{user.id}"
    for job in context.job_queue.get_jobs_by_name(name):
        job.schedule_removal()
    if cfg is None or cfg.get("when", "both") not in ("idle", "both"):
        return
    if time.time() - (context.user_data or {}).get("promo_at", 0) < int(cfg.get("every", 86400)):
        return
    context.job_queue.run_once(_promo_job, max(1, int(cfg.get("idle", 120))), name=name, chat_id=chat.id, user_id=user.id, data=user)


# ───────────────────────── الإبلاغ عن البوت ─────────────────────────
async def on_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    c = Ctx(update, context)
    if c.chat is None or c.chat.type != ChatType.PRIVATE:
        return
    if time.time() - context.user_data.get("rep_at", 0) < 600:
        await c.send(c.t("✅ وصل بلاغك السابق. يمكنك إرسال بلاغ آخر بعد قليل.", "✅ Your previous report was received. You can send another one shortly."))
        return
    c.set_state("rep_abuse")
    await c.send(c.t("🚨 <b>الإبلاغ عن هذا البوت</b>\n\nاكتب سبب البلاغ في رسالة واحدة. يصل البلاغ إلى إدارة المنصة مباشرة، لا إلى مالك البوت.\n\n/cancel للإلغاء",
                     "🚨 <b>Report this bot</b>\n\nDescribe the problem in one message. It goes straight to the platform team, not to the bot owner.\n\n/cancel to abort"))


async def _save_report(c: Ctx) -> None:
    c.clear_state()
    text = c.text[:2000]
    if not text:
        await c.send(c.t("أرسل البلاغ نصاً.", "Please send the report as text."))
        return
    # البلاغ يذهب دائماً إلى مدير المنصة الرئيسية، حتى لو أُنشئ البوت عبر صانع فرعي
    async with db.Session() as s:
        s.add(db.Report(factory_id=0, user_id=c.uid, kind="abuse", text=f"@{c.bot.username} [{c.bot_id}]\n{text}"))
        await s.commit()
    c.x.user_data["rep_at"] = time.time()
    await c.send(c.t("✅ وصل بلاغك إلى إدارة المنصة، شكراً لك.", "✅ Your report reached the platform team, thank you."))
    mk = getattr(c.x.bot_data.get("manager"), "maker", None)
    if mk is None or not config.ADMIN_ID:
        return
    try:
        await mk.bot.send_message(config.ADMIN_ID, f"🚨 <b>بلاغ على بوت</b> @{c.bot.username}\n👤 {c.name} (<code>{c.uid}</code>)\n\n{esc(text)}",
                                  parse_mode=ParseMode.HTML, reply_markup=kb([[B("🤖 بطاقة البوت", f"m:adm:bc:{c.bot_id}")]]))
    except TelegramError:
        pass


async def _enter(c: Ctx, param: str) -> None:
    if param == "panel":
        param = ""
    if param and await c.tpl.start_param(c, param):
        return
    if c.is_owner:
        await owner_home(c)
        if c.uid == c.owner_id and not c.x.bot_data.get("cmds_ok"):
            c.x.bot_data["cmds_ok"] = True      # الآن يمكن تعيين قائمة أوامر خاصة بالمالك
            c.x.application.create_task(set_commands(c.x.application))
    else:
        await user_home(c)


async def on_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    c = Ctx(update, context)
    if c.is_owner and c.chat.type == ChatType.PRIVATE:
        c.clear_state()
        await owner_home(c)


async def on_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    c = Ctx(update, context)
    c.clear_state()
    context.user_data.pop("mst", None)
    await c.send(c.t("✅ تم الإلغاء.", "✅ Cancelled."), kb([c.home_row()]))


# ───────────────────────── الرسائل ─────────────────────────
async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    c = Ctx(update, context)
    if c.chat is None or c.msg is None:
        return
    if c.chat.type != ChatType.PRIVATE:
        await c.tpl.group_msg(c)
        return
    _, banned = await touch(c)
    if banned:
        return
    st = c.st
    if st and st["k"] == "rep_abuse":
        await _save_report(c)
        return
    if st and st["k"].startswith("o_"):
        if c.is_owner:
            await owner_input(c, st)
            return
        c.clear_state()
        st = None
    text = c.text
    if text.startswith("/"):
        cmd = text.split()[0][1:].split("@")[0].lower()
        for s in c.core.get("shortcuts", []):
            if s["cmd"] == cmd:
                await c.send(s["v"])
                return
    if not await check_sub(c):
        return
    if not st and text:
        low = text.lower()
        for qr in c.core.get("quick", []):
            if qr["k"].lower() == low:
                await c.send(qr["v"])
                return
    if c.tpl.key in SLOW and (c.msg.effective_attachment or text):      # مؤشر «يكتب…» أثناء المعالجة
        context.application.create_task(_typing(context.bot, c.chat.id))
    if await c.tpl.msg(c):
        return
    await c.send(c.t("🤔 لم أفهم طلبك. اختر من الأزرار.", "🤔 I didn't get that. Please use the buttons."),
                 kb([c.home_row()]))


SLOW = {"downloader", "compress", "convert", "mediaedit", "sticker", "img2pdf", "pdftools", "voice", "ocr", "translate", "shortener", "wallets", "shazam"}


async def _typing(bot, chat_id: int) -> None:
    try:
        await bot.send_chat_action(chat_id, "typing")
    except Exception:  # noqa: BLE001
        pass


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    c = Ctx(update, context)
    data = c.q.data or ""
    try:
        if data == "noop":
            return
        if c.chat is not None and c.chat.type == ChatType.PRIVATE:
            _, banned = await touch(c, count=False)
            if banned:
                return
        if data.startswith("o:"):
            if not c.is_owner:
                await c.answer(c.t("هذه اللوحة للمالك فقط.", "Owner only."), True)
                return
            await owner_cb(c, data.split(":")[1:])
        elif data == "sub:check":
            context.user_data["fs_ack"] = True
            if await check_sub(c):
                try:
                    await c.q.message.delete()
                except TelegramError:
                    pass
                await _enter(c, context.user_data.pop("pending_start", ""))
            else:
                await c.answer(c.t("لم يكتمل الاشتراك بعد.", "You haven't joined yet."), True)
        elif data.startswith("t:"):
            a = data.split(":")[1:]
            if a[0] == "home":
                c.clear_state()
                await c.tpl.home(c)
            else:
                await c.tpl.cb(c, a)
        else:
            await c.tpl.cb(c, data.split(":"))
    finally:
        await c.answer()


async def on_inline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    c = Ctx(update, context)
    await c.tpl.inline(c)


async def on_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    c = Ctx(update, context)
    await c.tpl.join_request(c)


async def on_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    c = Ctx(update, context)
    cm = update.my_chat_member
    if cm is None or c.chat is None:
        return
    status = cm.new_chat_member.status
    gone = status in ("kicked", "left")
    if c.chat.type == ChatType.PRIVATE:
        for attempt in range(3):
            try:
                async with db.Session() as s:
                    await s.execute(sa_update(db.BUser).where(db.BUser.bot_id == c.bot_id, db.BUser.user_id == c.chat.id)
                                    .values(blocked=gone))
                    await s.commit()
                break
            except Exception as e:
                if attempt == 2:
                    log.warning("private chat block update error: %s", e)
                    break
                await asyncio.sleep(0.04 * (attempt + 1))
        if gone:
            await db.bump(c.bot_id, left=1)
            if c.core.get("notify_block"):
                await c.notify_owner(c.t(f"🚫 {c.name} حظر البوت.", f"🚫 {c.name} blocked the bot."))
        return
    kind = "channel" if c.chat.type == ChatType.CHANNEL else "group"
    for attempt in range(3):
        try:
            async with db.Session() as s:
                row = await s.get(db.BUser, (c.bot_id, c.chat.id))
                if row is None:
                    if gone:
                        return
                    s.add(db.BUser(bot_id=c.bot_id, user_id=c.chat.id, name=(c.chat.title or "")[:128],
                                   username=c.chat.username or "", kind=kind))
                    await db.bump(c.bot_id, groups=1)
                else:
                    row.blocked = gone
                    row.name = (c.chat.title or "")[:128]
                await s.commit()
            break
        except Exception as e:
            if attempt == 2:
                log.warning("chat member update error for bot %d chat %d: %s", c.bot_id, c.chat.id, e)
                break
            await asyncio.sleep(0.04 * (attempt + 1))


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    await errors.handle(update, context, f"bot @{context.bot.username} ({context.bot_data.get('tpl').key})")


# ───────────────────────── لوحة المالك ─────────────────────────
def _back(c: Ctx, to: str = "o:cfg"):
    if to == "o:cfg":
        to = c.x.user_data.get("oback", "o:home")
    return [B(c.t("⬅️ رجوع", "⬅️ Back"), to)]


def _cancel(c: Ctx, to: str = "o:cfg"):
    if to == "o:cfg":
        to = c.x.user_data.get("oback", "o:home")
    return kb([[B(c.t("❌ إلغاء", "❌ Cancel"), to)]])


async def stats_text(bot_id: int, lang: str) -> str:
    """نص إحصائيات بوت واحد — يُستخدم داخل البوت وفي الصانع."""
    t = lambda ar, en: ar if lang == "ar" else en  # noqa: E731
    n = await counts(bot_id)
    days = [(db.now() - dt.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    week: dict[str, int] = {}
    for d in days:
        for k, v in (await db.daily([bot_id], d)).items():
            week[k] = week.get(k, 0) + v
    hours = {k: v for k, v in week.items() if k.startswith("h")}
    peak = f"{(int(max(hours, key=hours.get)[1:]) + config.TZ_HOURS) % 24:02d}:00" if hours else "—"
    async with db.Session() as s:
        langs = (await s.execute(select(db.BUser.lang, func.count()).where(
            db.BUser.bot_id == bot_id, db.BUser.kind == "private").group_by(db.BUser.lang)
            .order_by(func.count().desc()).limit(6))).all()
    known = sum(v for k, v in langs if k)
    lang_rows = [(LANG_NAMES.get(k[:2], k), f"{v} ({round(v * 100 / known)}%)") for k, v in langs if k]
    pm = n["premium"]
    s_new, s_msg = await week_series([bot_id], "new"), await week_series([bot_id], "msgs")
    return (
        ui.rows([
            (t("كل الأعضاء", "All members"), ui.num(n["total"])),
            (t("محادثات خاصة", "Private chats"), ui.num(n["private"])),
            (t("مجموعات وقنوات", "Groups & channels"), n["groups"]),
            (t("انضموا اليوم", "Joined today"), n["new"]),
            (t("تفاعلوا اليوم", "Active today"), n["active"]),
            (t("كل الرسائل", "All messages"), ui.num(n["msgs"])),
            (t("⭐ بريميوم", "⭐ Premium"), f"{pm} ({round(pm * 100 / n['private']) if n['private'] else 0}%)"),
            (t("ما زالوا معك (لم يحظروا البوت)", "Still reachable (not blocked)"), n["total"] - n["blocked"]),
        ]) + "\n\n<b>" + t("📈 آخر 7 أيام", "📈 Last 7 days") + "</b>\n"
        + f"<code>{ui.spark(s_new)}</code> " + t(f"أعضاء جدد: {sum(s_new)}", f"new members: {sum(s_new)}") + "\n"
        + f"<code>{ui.spark(s_msg)}</code> " + t(f"رسائل: {sum(s_msg)}", f"messages: {sum(s_msg)}") + "\n"
        + ui.rows([(t("▶️ مرات التشغيل", "▶️ Starts"), week.get("starts", 0)), (t("🔗 عبر روابط التتبّع", "🔗 Via tracking links"), week.get("links", 0)),
                   (t("💔 حظروا البوت", "💔 Blocked the bot"), week.get("left", 0)), (t("🌐 زيارات الموقع", "🌐 Website visits"), week.get("web", 0)),
                   (t("🕒 ساعة الذروة", "🕒 Peak hour"), peak)])
        + "\n\n<b>" + t("🌍 لغات الأعضاء", "🌍 Member languages") + "</b>\n" + (ui.rows(lang_rows) or "—"))


async def scr_stats(c: Ctx) -> None:
    text = ui.head(c.t("📊 أرقام بوتك", "📊 Your bot's numbers")) + await stats_text(c.bot_id, c.lang)
    await c.edit(text, kb([[B(c.t("🔄 تحديث", "🔄 Refresh"), "o:stats")], _back(c)]))


async def scr_users(c: Ctx) -> None:
    t, n = c.t, await counts(c.bot_id)
    async with db.Session() as s:
        top = (await s.execute(select(db.BUser).where(db.BUser.bot_id == c.bot_id, db.BUser.kind == "private")
                               .order_by(db.BUser.msgs.desc()).limit(10))).scalars().all()
    text = (ui.head(t("👥 أعضاء البوت", "👥 Bot members")) + ui.rows([
        (t("الإجمالي", "Total"), n["total"]), (t("المحادثات الخاصة", "Private chats"), n["private"]),
        (t("جدد اليوم", "New today"), n["new"]), (t("المحظورون", "Banned"), n["banned"])]) +
        "\n\n<b>" + t("الأكثر تفاعلاً", "Most active") + "</b>\n" +
        ("\n".join(f"{i}. {esc(u.name or u.user_id)} — {u.msgs}" for i, u in enumerate(top, 1)) or "—"))
    rows = [[B(f"👤 {u.name or u.user_id}"[:40], f"o:u:{u.user_id}")] for u in top[:5]]
    rows += [[B(t("🔍 بحث عن عضو", "🔍 Find a member"), "o:usearch"), B(t("📥 تصدير الأعضاء", "📥 Export members"), "o:uexp")], _back(c)]
    await c.edit(text, kb(rows))


async def scr_member(c: Ctx, uid: int) -> None:
    t = c.t
    async with db.Session() as s:
        u = await s.get(db.BUser, (c.bot_id, uid))
    if u is None:
        await c.edit(t("لا يوجد عضو بهذا الرقم في بوتك.", "No member with that ID in your bot."), kb([_back(c, "o:users")]))
        return
    state = t("🚫 محظور", "🚫 Banned") if u.banned else (t("💔 حظر البوت", "💔 Blocked the bot") if u.blocked else t("✅ نشط", "✅ Active"))
    text = (f"👤 <b>{esc(u.name or uid)}</b>" + (f"  @{u.username}" if u.username else "") + f"\n<code>{uid}</code>\n{ui.LINE}\n" + ui.rows([
        (t("انضم", "Joined"), ui.when(u.joined)), (t("آخر نشاط", "Last seen"), ui.when(u.last_seen)), (t("رسائله", "Messages"), u.msgs),
        (t("اللغة", "Language"), LANG_NAMES.get((u.lang or "")[:2], u.lang or "—")), (t("بريميوم", "Premium"), "⭐" if u.premium else "—"),
        (t("المصدر", "Source"), u.source or "—"), (t("الحالة", "Status"), state)]))
    await c.edit(text, kb([
        [B(t("✓ رفع الحظر", "✓ Unban") if u.banned else t("🚫 حظر", "🚫 Ban"), f"o:uban:{uid}"), B(t("✉️ مراسلته", "✉️ Message"), f"o:umsg:{uid}")],
        _back(c, "o:users")]))


async def scr_admins(c: Ctx) -> None:
    t = c.t
    adm = c.core.get("admins", [])
    text = ui.head(t("🛡 المشرفون", "🛡 Admins")) + "\n" + t(
        "المشرف يستطيع دخول لوحة التحكم كاملة.", "Admins can access the whole control panel.") + "\n\n" + (
        "\n".join(f"• <code>{a}</code>" for a in adm) or t("لا يوجد مشرفون.", "No admins."))
    rows = [[B(f"🗑 {a}", f"o:admdel:{a}")] for a in adm]
    rows += [[B(t("➕ إضافة مشرف", "➕ Add admin"), "o:admadd")], _back(c)]
    await c.edit(text, kb(rows))


AUD = {"pv": ("👥 المستخدمون في الخاص", "👥 Private users"), "all": ("🌐 الكل (+ قنوات/مجموعات)", "🌐 All (+ channels/groups)"),
       "a7": ("🟢 النشطون (7 أيام)", "🟢 Active (7 days)"), "a30": ("📅 النشطون (30 يوم)", "📅 Active (30 days)")}


def _aud_cond(aud: str):
    U = db.BUser
    cond = [U.banned.is_(False), U.blocked.is_(False)]
    if aud != "all":
        cond.append(U.kind == "private")
    if aud in ("a7", "a30"):
        cond.append(U.last_seen >= db.now() - dt.timedelta(days=7 if aud == "a7" else 30))
    return cond


async def audience(bot_id: int, aud: str) -> list[int]:
    async with db.Session() as s:
        return list((await s.execute(select(db.BUser.user_id).where(db.BUser.bot_id == bot_id, *_aud_cond(aud)))).scalars().all())


async def scr_bc(c: Ctx) -> None:
    rows = []
    for k, (ar, en) in AUD.items():
        rows.append([B(f"{c.t(ar, en)}  ·  {len(await audience(c.bot_id, k))}", f"o:bca:{k}")])
    rows.append(_back(c))
    await c.edit(ui.head(c.t("📡 رسالة جماعية", "📡 Broadcast")) + "\n" + c.t("لمن تريد إرسال الرسالة؟", "Who should receive it?"), kb(rows))


async def run_broadcast(bot, bot_id: int, targets: list[int], from_chat: int, mid: int, report_to: int, lang: str) -> None:
    ok = fail = 0
    for uid in targets:
        try:
            await bot.copy_message(uid, from_chat, mid)
            ok += 1
        except RetryAfter as e:
            await asyncio.sleep(float(getattr(e, "retry_after", 3)) + 1)
            try:
                await bot.copy_message(uid, from_chat, mid)
                ok += 1
            except TelegramError:
                fail += 1
        except Forbidden:
            fail += 1
            async with db.Session() as s:
                await s.execute(sa_update(db.BUser).where(db.BUser.bot_id == bot_id, db.BUser.user_id == uid).values(blocked=True))
                await s.commit()
        except TelegramError:
            fail += 1
        await asyncio.sleep(0.05)
    msg = (f"✅ انتهت الإذاعة.\n📬 وصلت: {ok}\n⚠️ فشلت: {fail}" if lang == "ar"
           else f"✅ Broadcast finished.\n📬 Delivered: {ok}\n⚠️ Failed: {fail}")
    try:
        await bot.send_message(report_to, msg)
    except TelegramError:
        pass


async def scr_fs(c: Ctx) -> None:
    t, fs = c.t, c.core.get("fs", [])
    on = sum(1 for x in fs if x.get("on", True))
    text = (ui.head(t("🔐 الاشتراك الإجباري", "🔐 Forced subscription")) + "\n" +
            t(f"📦 المصادر: {len(fs)}  •  🟢 مفعّلة: {on}\n👥 اشتركوا عبر البوت: {c.core.get('fs_passed', 0)}\n\n"
              "يدعم قناة، قروب، رابط دعوة، أو بوت آخر.",
              f"📦 Sources: {len(fs)}  •  🟢 Enabled: {on}\n👥 Joined via the bot: {c.core.get('fs_passed', 0)}\n\n"
              "Supports channels, groups, invite links or other bots."))
    if not fs:
        text += "\n\n" + t("💡 ابدأ بإضافة قناة/قروب أو رابط/بوت من الأزرار أعلاه.", "💡 Start by adding a channel/group or a link/bot.")
    rows = [[B(t("➕ قناة/قروب", "➕ Channel/group"), "o:fsadd"), B(t("🔗 رابط/بوت", "🔗 Link/bot"), "o:fslink")]]
    for i, x in enumerate(fs):
        rows.append([B(("🟢 " if x.get("on", True) else "🔴 ") + (x.get("title") or "?")[:28], f"o:fstog:{i}"),
                     B("🗑", f"o:fsdel:{i}")])
    rows += [[B(t("✏️ رسالة الاشتراك", "✏️ Subscription message"), "o:fsmsg")],
             [B(t("🔄 تحديث", "🔄 Refresh"), "o:fs"), *_back(c)]]
    await c.edit(text, kb(rows))


async def scr_sl(c: Ctx) -> None:
    t, links = c.t, c.core.get("links", {})
    text = ui.head(t("🔗 روابط التتبّع", "🔗 Tracking links")) + "\n" + t(
        "لكل حملة إعلانية رابط خاص، فتعرف كم عضواً جاء من كل مصدر.",
        "Create special links for the bot; each one counts who came through it.") + "\n\n"
    text += "\n".join(f"• <b>{esc(v['name'])}</b> — {v.get('n', 0)}\n<code>{c.link('sl_' + k)}</code>" for k, v in links.items()) \
        or t("لم تنشئ أي رابط بعد.", "No start links yet.")
    rows = [[B(f"🗑 {v['name']}"[:40], f"o:sldel:{k}")] for k, v in links.items()]
    rows += [[B(t("➕ رابط جديد", "➕ New link"), "o:sladd")], [B(t("🔄 تحديث", "🔄 Refresh"), "o:sl")], _back(c)]
    await c.edit(text, kb(rows))


async def scr_ban(c: Ctx) -> None:
    t = c.t
    async with db.Session() as s:
        banned = (await s.execute(select(db.BUser).where(db.BUser.bot_id == c.bot_id, db.BUser.banned.is_(True)).limit(30))).scalars().all()
    text = ui.head(t("🚫 قائمة الحظر", "🚫 Ban list")) + "\n" + t(f"📦 المحظورون: {len(banned)}", f"📦 Banned: {len(banned)}") + "\n\n"
    text += "\n".join(f"• {esc(u.name)} <code>{u.user_id}</code>" for u in banned) or t("لا يوجد محظورون.", "Nobody is banned.")
    await c.edit(text, kb([[B(t("➕ حظر مستخدم", "➕ Ban user"), "o:banadd"), B(t("✓ إلغاء حظر", "✓ Unban"), "o:bandel")], _back(c)]))


ORDERS = {"before": ("قبل رسالة البداية", "before the start screen"), "after": ("بعد رسالة البداية", "after the start screen"),
          "only": ("بدل رسالة البداية", "instead of the start screen")}


async def scr_wel(c: Ctx) -> None:
    t, w = c.t, c.core.get("welcome") or {}
    nb = sum(len(r) for r in w.get("buttons") or [])
    cur = esc(w["text"][:300]) if w.get("text") else t("الافتراضي (نص القالب)", "Default (template text)")
    ar, en = ORDERS[w.get("order", "before")]
    text = (ui.head(t("👋 رسالة الترحيب", "👋 Welcome message")) + "\n" +
            t("هذه الرسالة تظهر للمستخدمين عند ضغط /start في البوت. يمكنك كتابة {name} ليُستبدل باسم المستخدم.",
              "Shown to users on /start. Use {name} for the user's name.") +
            f"\n\n{t('النص الحالي', 'Current text')}: {cur}\n\n🔗 {t('أزرار البداية', 'Start buttons')}: {nb}")
    await c.edit(text, kb([
        [B(t("✏️ تعيين رسالة ترحيب البداية", "✏️ Set welcome message"), "o:welset")],
        [B(t("🔗 تعيين أزرار البداية", "🔗 Set start buttons"), "o:welbtn")],
        [B(f"🔁 {t('الترحيب', 'Welcome')}: {t(ar, en)}", "o:welord")],
        [B(t("🗑 حذف الترحيب", "🗑 Remove welcome"), "o:weldel")] if w.get("text") else None,
        _back(c)]))


async def scr_list(c: Ctx, key: str, title: tuple, hint: tuple, add: tuple, pfx: str) -> None:
    t, items = c.t, c.core.get(key, [])
    text = ui.head(t(*title)) + "\n" + t(f"📦 العدد: {len(items)}", f"📦 Count: {len(items)}") + "\n\n" + t(*hint)
    rows = [[B(f"🗑 {('/' + x['cmd']) if key == 'shortcuts' else x['k']}"[:40], f"o:{pfx}del:{i}")] for i, x in enumerate(items)]
    rows += [[B(t(*add), f"o:{pfx}add")], _back(c)]
    await c.edit(text, kb(rows))


async def scr_ad(c: Ctx) -> None:
    t, ad = c.t, c.core.get("autodel") or {}
    sec = int(ad.get("sec", 300))
    on = ad.get("on")
    text = (ui.head(t("⏱ تنظيف تلقائي", "⏱ Auto clean-up")) + "\n" +
            t(f"الحالة: {'🟢 مفعّل' if on else '🔴 معطّل'}\nالمدة: {sec // 60} دقيقة ({sec} ثانية)\n\n"
              "عند التفعيل، رسائل البوت تُحذف تلقائياً بعد المدة المحددة.\n\n⚠️ يحفظ مساحة الشات للمستخدم — مفيد للبوتات اليومية.",
              f"Status: {'🟢 On' if on else '🔴 Off'}\nDelay: {sec // 60} min ({sec}s)\n\n"
              "When enabled, the bot's messages are deleted after the delay."))
    await c.edit(text, kb([
        [B(t("🔴 تعطيل", "🔴 Disable") if on else t("🟢 تفعيل", "🟢 Enable"), "o:adtog")],
        [B(t("⏱ 1 دقيقة", "⏱ 1 min"), "o:adset:60"), B(t("⏱ 5 دقائق", "⏱ 5 min"), "o:adset:300")],
        [B(t("⏱ 30 دقيقة", "⏱ 30 min"), "o:adset:1800"), B(t("⏱ ساعة", "⏱ 1 hour"), "o:adset:3600")],
        _back(c)]))


async def scr_set(c: Ctx) -> None:
    t, core = c.t, c.core
    onoff = lambda v: t("🟢 مفعّل", "🟢 On") if v else t("🔴 معطّل", "🔴 Off")  # noqa: E731
    lang = core.get("lang") or "auto"
    lang_s = t("🌍 تلقائية (حسب لغة كل مستخدم)", "🌍 Automatic (per user)") if lang == "auto" else LANG_NAMES.get(lang, lang)
    n = await counts(c.bot_id)
    text = (ui.head(t("⚙️ خيارات البوت", "⚙️ Bot options")) + "\n" +
            f"🔔 {t('إشعارات الدخول', 'Join notifications')}: {onoff(core.get('notify_join'))}\n"
            f"🚫 {t('إشعارات حظر البوت', 'Bot-blocked notifications')}: {onoff(core.get('notify_block'))}\n"
            f"🔒 {t('قفل المحتوى', 'Content protection')}: {onoff(core.get('protect'))}\n"
            f"🌐 {t('لغة البوت', 'Bot language')}: {lang_s}\n"
            f"📊 {t('إجمالي من حظروا البوت', 'Users who blocked the bot')}: {n['blocked']}\n"
            f"🚪 {t('روابط البداية', 'Start links')}: {len(core.get('links', {}))}\n"
            f"🛠 {t('وضع الصيانة', 'Maintenance mode')}: {onoff((core.get('maint') or {}).get('on'))}\n"
            f"📤 {t('زر «شارك البوت» في الرئيسية', 'Share button on the home screen')}: {onoff(core.get('share', True))}\n\n" +
            t("قفل المحتوى يمنع تحويل/حفظ الرسائل والوسائط الجديدة التي يرسلها البوت.",
              "Content protection prevents forwarding/saving new messages sent by the bot.") + "\n" +
            t("وضع الصيانة يوقف البوت عن الأعضاء مؤقتاً ويعرض لهم رسالتك، وأنت تتابع العمل في غرفة التحكم.",
              "Maintenance mode pauses the bot for members and shows them your message while you keep working here."))
    tog = lambda v, ar, en: (t("🔴 تعطيل ", "🔴 Disable ") if v else t("🟢 تفعيل ", "🟢 Enable ")) + t(ar, en)  # noqa: E731
    await c.edit(text, kb([
        [B(tog(core.get("notify_join"), "إشعار الدخول", "join notifications"), "o:tg:notify_join")],
        [B(tog(core.get("notify_block"), "إشعار حظر البوت", "block notifications"), "o:tg:notify_block")],
        [B(tog(core.get("protect"), "قفل المحتوى", "content protection"), "o:tg:protect")],
        [B(tog((core.get("maint") or {}).get("on"), "وضع الصيانة", "maintenance mode"), "o:mt"), B(t("✏️ رسالة الصيانة", "✏️ Maintenance text"), "o:mttxt")],
        [B(tog(core.get("share", True), "زر مشاركة البوت", "share button"), "o:tg:share")],
        [B(t("🌐 لغة البوت", "🌐 Bot language"), "o:setl")], _back(c)]))


async def scr_sys(c: Ctx) -> None:
    t, core = c.t, c.core
    snaps = await c.kv("sys:snaps", [])
    text = (ui.head(t("🗄 النسخ الاحتياطي", "🗄 Backups")) + "\n" +
            t("النسخة = لقطة كاملة لبنية بوتك وإعداداته (بدون المستخدمين).",
              "A backup is a full snapshot of your bot's structure and settings (without users).") + "\n\n" +
            f"🔐 {t('الاشتراك الإجباري', 'Forced subscription')}: {len(core.get('fs', []))}\n"
            f"💬 {t('الردود التلقائية', 'Quick replies')}: {len(core.get('quick', []))}\n"
            f"⌨️ {t('الأوامر المخصّصة', 'Custom commands')}: {len(core.get('shortcuts', []))}\n\n"
            f"🗂 {t('النسخ المحفوظة', 'Saved backups')}: {len(snaps)}")
    await c.edit(text, kb([
        [B(t("💾 احفظ نسخة الآن", "💾 Save backup now"), "o:syssave")],
        [B(t("🗂 نسخي المحفوظة", "🗂 My backups"), "o:syslist")],
        [B(t("📤 تصدير ملف", "📤 Export file"), "o:sysexp"), B(t("📥 استيراد ملف", "📥 Import file"), "o:sysimp")],
        _back(c)]))


async def _snapshot(c: Ctx) -> dict:
    data = await db.kv_all(c.bot_id)
    return {k: v for k, v in data.items() if not k.startswith("sys:")}


async def _restore(c: Ctx, data: dict) -> None:
    await db.kv_replace_all(c.bot_id, data)
    fresh = await load_core(c.bot_id)
    c.core.clear()
    c.core.update(fresh)


GUIDE_AR = (
    "📖 <b>دليل غرفة التحكم</b>\n\n"
    "• <b>الأرقام والأعضاء</b>: أرقام بوتك وأكثر الأعضاء تفاعلاً، مع بحث عن أي عضو برقمه أو معرّفه لحظره أو مراسلته، وتصدير كل الأعضاء في ملف.\n"
    "• <b>إذاعة</b>: اختر الجمهور ثم أرسل أي رسالة (نص، صورة، فيديو...) لتُنسخ للجميع.\n"
    "• <b>اشتراك إجباري</b>: أضف قناة/قروب (البوت يجب أن يكون مشرفاً فيها) أو رابطاً لا يُتحقق منه.\n"
    "• <b>روابط البداية</b>: روابط تتبّع تعرف منها مصدر المستخدمين.\n"
    "• <b>الحظر</b>: احظر مستخدماً برقمه (ID).\n"
    "• <b>رسالة الترحيب</b>: نص وأزرار تظهر عند /start.\n"
    "• <b>ردود سريعة</b>: كلمة مفتاحية ← رد تلقائي.\n"
    "• <b>اختصارات</b>: أمر مثل /price ← رد محفوظ.\n"
    "• <b>حذف تلقائي</b>: حذف رسائل البوت بعد مدة.\n"
    "• <b>وضع الصيانة</b> (في خيارات البوت): يوقف البوت عن الأعضاء مؤقتاً برسالة تكتبها، وأنت تتابع العمل هنا.\n"
    "• <b>النظام والنسخ</b>: حفظ واسترجاع وتصدير بنية البوت.\n\n"
    "اكتب /admin في أي وقت للعودة إلى اللوحة."
)
GUIDE_EN = (
    "📖 <b>Control room guide</b>\n\n"
    "• <b>Statistics/Users</b>: numbers, most active users, admins.\n"
    "• <b>Broadcast</b>: pick an audience then send any message to copy to everyone.\n"
    "• <b>Forced subscription</b>: add a channel/group (bot must be admin) or an unverified link.\n"
    "• <b>Start links</b>: tracking links.\n• <b>Bans</b>: ban by user ID.\n"
    "• <b>Welcome</b>: text and buttons on /start.\n• <b>Quick replies</b>: keyword → auto reply.\n"
    "• <b>Shortcuts</b>: a command like /price → saved reply.\n• <b>Auto delete</b>: remove bot messages after a delay.\n"
    "• <b>System & backups</b>: save, restore and export the bot structure.\n\nSend /admin anytime to return."
)


async def owner_cb(c: Ctx, a: list[str]) -> None:  # noqa: C901
    t, core, act = c.t, c.core, a[0]
    arg = a[1] if len(a) > 1 else ""
    c.clear_state()
    grp = SCREEN_GROUP.get(act) or next((g for pfx, g in PREFIX_GROUP.items() if act.startswith(pfx)), None)
    if grp:
        c.x.user_data["oback"] = f"o:g:{grp}"

    async def ask(state: str, text: str, back: str, **data):
        c.set_state(state, **data)
        await c.edit(text + t("\n\n/cancel للإلغاء", "\n\n/cancel to abort"), _cancel(c, back))

    if act == "home":
        await owner_home(c)
    elif act == "preview":
        await c.tpl.home(c)
    elif act == "tguide":
        g = c.tpl.guide_ar if c.lang == "ar" else (c.tpl.guide_en or c.tpl.guide_ar)
        await c.edit(ui.head(f"ℹ️ {c.tpl.name(c.lang)}") + "\n" + (g or esc(c.tpl.desc(c.lang))), kb([_back(c, "o:home")]))
    elif act == "g":
        await group_menu(c, arg)
    elif act == "cfg":
        await group_menu(c, (c.x.user_data.get("oback") or "o:g:aud").rsplit(":", 1)[-1])
    elif act == "stats":
        await scr_stats(c)
    elif act == "users":
        await scr_users(c)
    elif act == "todo":
        await scr_todo(c)
    elif act == "site":
        await scr_site(c)
    elif act in ("siteon", "sitemenu"):
        cfg = core.setdefault("site", {})
        key = "on" if act == "siteon" else "menu"
        cfg[key] = not site_conf(core)[key]
        await c.save_core()
        await apply_menu_button(c.x.application)
        await scr_site(c)
    elif act == "sitecol":
        from .web.server import PALETTE
        cur = site_conf(core)["color"]
        rows = ui.grid([B(("✓ " if h == cur else "") + name, f"o:sitec:{i}") for i, (h, name) in enumerate(PALETTE)], 3)
        await c.edit(ui.head(t("🎨 لون الموقع", "🎨 Site colour")) + t("اللون يظهر في الأزرار والعناوين داخل موقعك.", "The colour is used for buttons and highlights on your site."),
                     kb(rows + [[B(("✓ " if not cur else "") + t("لون القالب الافتراضي", "Template default"), "o:sitec:x")], _back(c, "o:site")]))
    elif act == "sitec":
        from .web.server import PALETTE
        core.setdefault("site", {})["color"] = PALETTE[int(arg)][0] if arg.isdigit() and int(arg) < len(PALETTE) else ""
        await c.save_core()
        await scr_site(c)
    elif act == "sitetag":
        await ask("o_sitetag", t("✏️ أرسل العبارة التعريفية التي تظهر تحت اسم البوت في الموقع (سطر أو سطران).\nأرسل <code>0</code> لحذفها.",
                                 "✏️ Send the tagline shown under the bot's name on the site (one or two lines).\nSend <code>0</code> to remove it."), "o:site")
    elif act == "siteqr":
        import qrcode

        from . import web
        url = web.site_url(c.bot.username)
        buf = io.BytesIO()
        qrcode.make(url).save(buf, format="PNG")
        buf.seek(0)
        await c.photo(buf, caption=t(f"🔳 <b>رمز QR لموقع بوتك</b>\nمن يمسحه يفتح الموقع مباشرة.\n\n{esc(url)}", f"🔳 <b>QR code for your bot's site</b>\n\n{esc(url)}"), filename="site_qr.png")
    elif act == "idn":
        await scr_idn(c)
    elif act in ("idname", "iddesc", "idabout"):
        prompt = {"idname": t("✏️ أرسل اسم البوت الجديد (حتى 64 حرفاً).", "✏️ Send the new bot name (up to 64 characters)."),
                  "iddesc": t("📝 أرسل وصف البوت (حتى 500 حرف). يظهر في الشاشة الفارغة قبل أن يضغط الزائر «بدء».", "📝 Send the bot description (up to 500 characters)."),
                  "idabout": t("ℹ️ أرسل النبذة (حتى 120 حرفاً). تظهر في صفحة البوت وعند مشاركة رابطه.", "ℹ️ Send the about text (up to 120 characters).")}[act]
        await ask("o_" + act, prompt, "o:idn")
    elif act == "idreset":
        core["idn"] = {"desc": "", "about": "", "set": True}
        await c.save_core()
        await apply_identity(c.x.application)
        await c.answer(t("✅ عادت النصوص الافتراضية.", "✅ Defaults restored."), True)
        await scr_idn(c)
    elif act == "u" and arg.isdigit():
        await scr_member(c, int(arg))
    elif act == "usearch":
        await ask("o_usearch", t("🔍 أرسل رقم (ID) العضو أو معرّفه (@username).", "🔍 Send the member's ID or @username."), "o:users")
    elif act == "uban" and arg.isdigit():
        async with db.Session() as s:
            row = await s.get(db.BUser, (c.bot_id, int(arg)))
            if row is not None:
                row.banned = not row.banned
                await s.commit()
        await scr_member(c, int(arg))
    elif act == "umsg" and arg.isdigit():
        await ask("o_umsg", t("✉️ أرسل الرسالة التي تريد إيصالها لهذا العضو (نص أو وسائط).", "✉️ Send the message for this member (text or media)."), f"o:u:{arg}", uid=int(arg))
    elif act == "uexp":
        async with db.Session() as s:
            rows = (await s.execute(select(db.BUser).where(db.BUser.bot_id == c.bot_id).order_by(db.BUser.joined))).scalars().all()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["id", "name", "username", "type", "language", "joined", "last_seen", "messages", "premium", "blocked_bot", "banned", "source"])
        for u in rows:
            w.writerow([u.user_id, u.name, u.username, u.kind, u.lang, ui.when(u.joined), ui.when(u.last_seen), u.msgs, int(u.premium), int(u.blocked), int(u.banned), u.source])
        await c.bot.send_document(c.chat.id, io.BytesIO(("\ufeff" + buf.getvalue()).encode("utf-8")), filename=f"members_{c.bot.username}.csv",
                                  caption=t(f"📥 أعضاء بوتك: {len(rows)}", f"📥 Your bot's members: {len(rows)}"))
    elif act == "mt":
        mt = core.setdefault("maint", {"on": False, "text": ""})
        mt["on"] = not mt.get("on")
        await c.save_core()
        await c.answer(t("🛠 الصيانة مفعّلة: الأعضاء يرون رسالة الصيانة.", "🛠 Maintenance on.") if mt["on"] else t("✅ عاد البوت للعمل.", "✅ The bot is live again."), True)
        await scr_set(c)
    elif act == "mttxt":
        cur = (core.get("maint") or {}).get("text")
        await ask("o_mttxt", t("✏️ أرسل الرسالة التي يراها الأعضاء أثناء الصيانة (يدعم التنسيق).\nأرسل <code>0</code> للعودة إلى الرسالة الافتراضية.",
                               "✏️ Send the message members see during maintenance.\nSend <code>0</code> to restore the default.") +
                  ("\n\n" + t("الحالية:", "Current:") + "\n" + cur if cur else ""), "o:set")
    elif act == "adm":
        await scr_admins(c)
    elif act == "admadd":
        await ask("o_adm", t("🛡 أرسل رقم (ID) المستخدم الذي تريد ترقيته مشرفاً.", "🛡 Send the user ID to promote."), "o:adm")
    elif act == "admdel":
        core["admins"] = [x for x in core.get("admins", []) if str(x) != arg]
        await c.save_core()
        await scr_admins(c)
    elif act == "bc":
        await scr_bc(c)
    elif act == "bca":
        n = len(await audience(c.bot_id, arg))
        await ask("o_bc", ui.head(t("📡 رسالة جماعية", "📡 Broadcast")) + "\n" +
                  t(f"👥 الجمهور: {n}\n\n📝 أرسل الآن الرسالة التي تريد إذاعتها (نص أو وسائط).",
                    f"👥 Audience: {n}\n\n📝 Now send the message to broadcast (text or media)."), "o:bc", aud=arg)
    elif act == "bcgo":
        job = c.x.user_data.pop("bc", None)
        if not job:
            await c.answer(t("انتهت صلاحية الطلب.", "Request expired."), True)
            return await scr_bc(c)
        targets = await audience(c.bot_id, job["aud"])
        c.x.application.create_task(run_broadcast(c.bot, c.bot_id, targets, job["chat"], job["mid"], c.uid, c.lang))
        await c.edit(t(f"🚀 بدأت الإذاعة إلى {len(targets)} محادثة. سيصلك تقرير عند الانتهاء.",
                       f"🚀 Broadcasting to {len(targets)} chats. You'll get a report when done."), kb([_back(c)]))
    elif act == "fs":
        await scr_fs(c)
    elif act == "fsadd":
        await ask("o_fs_chat", t("➕ <b>إضافة قناة/قروب</b>\n\n1. أضف هذا البوت مشرفاً في القناة أو القروب.\n"
                                "2. أرسل هنا المعرّف مثل <code>@mychannel</code> أو حوّل أي منشور من القناة.",
                                "➕ <b>Add channel/group</b>\n\n1. Make this bot an admin there.\n"
                                "2. Send its @username here or forward any post from it."), "o:fs")
    elif act == "fslink":
        await ask("o_fs_link", t("🔗 أرسل العنوان والرابط بهذه الصيغة:\n<code>اسم القناة | https://t.me/+xxxx</code>\n\n"
                                "هذا النوع يُعرض كزر فقط ولا يمكن التحقق من الاشتراك فيه.",
                                "🔗 Send title and link as:\n<code>Channel name | https://t.me/+xxxx</code>\n\n"
                                "Shown as a button only; membership can't be verified."), "o:fs")
    elif act == "fsmsg":
        await ask("o_fs_msg", t("✏️ أرسل نص رسالة الاشتراك الإجباري.", "✏️ Send the forced-subscription message text."), "o:fs")
    elif act in ("fstog", "fsdel"):
        fs = core.get("fs", [])
        if arg.isdigit() and int(arg) < len(fs):
            if act == "fsdel":
                fs.pop(int(arg))
            else:
                fs[int(arg)]["on"] = not fs[int(arg)].get("on", True)
            await c.save_core()
        await scr_fs(c)
    elif act == "sl":
        await scr_sl(c)
    elif act == "sladd":
        await ask("o_sl", t("➕ أرسل اسماً للرابط (مثلاً: إعلان فيسبوك).", "➕ Send a name for the link (e.g. Facebook ad)."), "o:sl")
    elif act == "sldel":
        core.get("links", {}).pop(arg, None)
        await c.save_core()
        await scr_sl(c)
    elif act == "ban":
        await scr_ban(c)
    elif act in ("banadd", "bandel"):
        await ask("o_ban" if act == "banadd" else "o_unban",
                  t("أرسل رقم (ID) المستخدم.", "Send the user ID."), "o:ban")
    elif act == "wel":
        await scr_wel(c)
    elif act == "welset":
        await ask("o_wel", t("✏️ أرسل نص رسالة الترحيب (يدعم التنسيق).", "✏️ Send the welcome text (formatting supported)."), "o:wel")
    elif act == "welbtn":
        await ask("o_welbtn", t("🔗 أرسل الأزرار، كل سطر صف:\n<code>نص الزر - https://example.com</code>\n"
                               "ولوضع زرين في صف واحد افصل بينهما بـ <code>&amp;&amp;</code>\n\nأرسل <code>0</code> لحذف الأزرار.",
                               "🔗 Send buttons, one row per line:\n<code>Button text - https://example.com</code>\n"
                               "Use <code>&amp;&amp;</code> between two buttons in one row.\n\nSend <code>0</code> to clear."), "o:wel")
    elif act == "welord":
        w = core.setdefault("welcome", {})
        order = list(ORDERS)
        w["order"] = order[(order.index(w.get("order", "before")) + 1) % len(order)]
        await c.save_core()
        await scr_wel(c)
    elif act == "weldel":
        core["welcome"] = {"text": "", "buttons": [], "order": "before"}
        await c.save_core()
        await scr_wel(c)
    elif act == "qr":
        await scr_list(c, "quick", ("💬 ردود بالكلمات", "💬 Keyword replies"),
                       ("إذا كتب العضو الكلمة تماماً كما حفظتها، يرد البوت بالنص الذي اخترته.", "When a user sends the keyword, the bot replies automatically."),
                       ("➕ رد جديد", "➕ New reply"), "qr")
    elif act == "qradd":
        await ask("o_qr_k", t("💬 أرسل الكلمة المفتاحية.", "💬 Send the keyword."), "o:qr")
    elif act == "qrdel":
        if arg.isdigit() and int(arg) < len(core.get("quick", [])):
            core["quick"].pop(int(arg))
            await c.save_core()
        await owner_cb(c, ["qr"])
    elif act == "sc":
        await scr_list(c, "shortcuts", ("⚡ أوامر مختصرة", "⚡ Custom commands"),
                       ("أضف أوامر خاصة ببوتك مثل /price أو /contact، وكل أمر يرد بنص تحفظه.", "Short commands (like /price) that return a saved reply."),
                       ("➕ أمر جديد", "➕ New command"), "sc")
    elif act == "scadd":
        await ask("o_sc_k", t("⚡ أرسل اسم الأمر بدون مسافات (مثل: price).", "⚡ Send the command name without spaces (e.g. price)."), "o:sc")
    elif act == "scdel":
        if arg.isdigit() and int(arg) < len(core.get("shortcuts", [])):
            core["shortcuts"].pop(int(arg))
            await c.save_core()
        await owner_cb(c, ["sc"])
    elif act == "ad":
        await scr_ad(c)
    elif act in ("adtog", "adset"):
        ad = core.setdefault("autodel", {"on": False, "sec": 300})
        if act == "adtog":
            ad["on"] = not ad.get("on")
        else:
            ad["sec"] = int(arg)
        await c.save_core()
        await scr_ad(c)
    elif act == "guide":
        await c.edit(GUIDE_AR if c.lang == "ar" else GUIDE_EN, kb([_back(c)]))
    elif act == "set":
        await scr_set(c)
    elif act == "tg" and arg in ("notify_join", "notify_block", "protect", "share"):
        core[arg] = not core.get(arg, arg == "share")
        await c.save_core()
        await scr_set(c)
    elif act == "setl":
        btns = [B(("✓ " if core.get("lang") == code else "") + name, f"o:setlang:{code}") for code, name in LANGS]
        rows = [[B(("✓ " if (core.get("lang") or "auto") == "auto" else "") + t("🌍 تلقائية", "🌍 Automatic"), "o:setlang:auto")]]
        await c.edit(ui.head(t("🌐 لغة البوت", "🌐 Bot language")) + "\n" +
                     t("النصوص متوفرة بالعربية والإنجليزية؛ بقية اللغات تعرض الإنجليزية.",
                       "Texts exist in Arabic and English; other languages show English."),
                     kb(rows + ui.grid(btns, 2) + [_back(c, "o:set")]))
    elif act == "setlang":
        core["lang"] = arg
        await c.save_core()
        await scr_set(c)
    elif act == "sys":
        await scr_sys(c)
    elif act == "syssave":
        snaps = await c.kv("sys:snaps", [])
        snaps.append({"id": secrets.token_hex(3), "at": db.now().strftime("%Y-%m-%d %H:%M"), "data": await _snapshot(c)})
        await c.kv_set("sys:snaps", snaps[-10:])
        await c.answer(t("✅ تم حفظ النسخة.", "✅ Backup saved."), True)
        await scr_sys(c)
    elif act == "syslist":
        snaps = await c.kv("sys:snaps", [])
        rows = [[B(f"♻️ {s['at']}", f"o:sysres:{s['id']}"), B("🗑", f"o:sysdel:{s['id']}")] for s in reversed(snaps)]
        await c.edit(ui.head(t("🗂 نسخي المحفوظة", "🗂 My backups")) + "\n" +
                     (t("اضغط ♻️ للاسترجاع (يستبدل البنية الحالية).", "Tap ♻️ to restore (replaces the current structure).")
                      if snaps else t("لا توجد نسخ محفوظة.", "No backups saved.")), kb(rows + [_back(c, "o:sys")]))
    elif act in ("sysres", "sysdel"):
        snaps = await c.kv("sys:snaps", [])
        snap = next((s for s in snaps if s["id"] == arg), None)
        if snap and act == "sysres":
            await _restore(c, snap["data"])
            await c.answer(t("✅ تم الاسترجاع.", "✅ Restored."), True)
        elif snap:
            await c.kv_set("sys:snaps", [s for s in snaps if s["id"] != arg])
        await owner_cb(c, ["syslist"] if act == "sysdel" else ["sys"])
    elif act == "sysexp":
        payload = {"format": "botforge-backup", "v": 1, "template": c.tpl.key, "data": await _snapshot(c)}
        buf = io.BytesIO(json.dumps(payload, ensure_ascii=False, indent=1).encode())
        await c.bot.send_document(c.chat.id, buf, filename=f"backup_{c.bot.username}.json",
                                  caption=t("📤 نسخة بنية البوت.", "📤 Bot structure backup."))
    elif act == "sysimp":
        await ask("o_imp", t("📥 أرسل ملف النسخة (.json) الذي صدّرته من قبل.", "📥 Send the backup (.json) file you exported."), "o:sys")
    else:
        await owner_home(c)


async def owner_input(c: Ctx, st: dict) -> None:  # noqa: C901
    t, core, k, text = c.t, c.core, st["k"], c.text

    async def done(scr: list[str], note: str | None = None):
        c.clear_state()
        await c.save_core()
        if note:
            await c.send(note)
        await owner_cb(c, scr)

    if text.lower() == "/cancel":
        c.clear_state()
        return await owner_home(c)
    if k == "o_bc":
        c.clear_state()
        c.x.user_data["bc"] = {"aud": st["aud"], "chat": c.chat.id, "mid": c.msg.message_id}
        n = len(await audience(c.bot_id, st["aud"]))
        await c.bot.copy_message(c.chat.id, c.chat.id, c.msg.message_id)
        await c.send(t(f"☝️ هذه معاينة الإذاعة.\n👥 ستُرسل إلى: {n}\n\nهل تؤكد الإرسال؟",
                       f"☝️ This is the broadcast preview.\n👥 Recipients: {n}\n\nConfirm sending?"),
                     kb([[B(t("✅ إرسال", "✅ Send"), "o:bcgo", style="success"), B(t("❌ إلغاء", "❌ Cancel"), "o:bc", style="danger")]]))
    elif k == "o_sitetag":
        core.setdefault("site", {})["tagline"] = "" if text == "0" else text[:160]
        await done(["site"], t("✅ حُفظت العبارة.", "✅ Tagline saved."))
    elif k in ("o_idname", "o_iddesc", "o_idabout"):
        limit = {"o_idname": 64, "o_iddesc": 500, "o_idabout": 120}[k]
        if not text or len(text) > limit:
            return await c.send(t(f"⚠️ أرسل نصاً لا يتجاوز {limit} حرفاً.", f"⚠️ Send text up to {limit} characters."))
        try:
            if k == "o_idname":
                await c.bot.set_my_name(text)
                core.setdefault("idn", {"desc": "", "about": ""})["name"] = text
                await c.save_core()
            else:
                idn = core.setdefault("idn", {"desc": "", "about": ""})
                idn["desc" if k == "o_iddesc" else "about"] = text
                idn["custom"] = True
                await c.save_core()
                await apply_identity(c.x.application)
        except TelegramError as err:
            return await c.send(t(f"⚠️ رفض تيليجرام التغيير: {esc(err)}", f"⚠️ Telegram rejected the change: {esc(err)}"))
        await done(["idn"], t("✅ تم التحديث. قد يستغرق ظهوره دقائق في تيليجرام.", "✅ Updated. It may take a few minutes to show in Telegram."))
    elif k == "o_usearch":
        c.clear_state()
        uid = int(text) if text.lstrip("-").isdigit() else None
        if uid is None:
            async with db.Session() as s:
                row = (await s.execute(select(db.BUser).where(db.BUser.bot_id == c.bot_id, func.lower(db.BUser.username) == text.lstrip("@").lower()))).scalars().first()
            uid = row.user_id if row else 0
        await scr_member(c, uid)
    elif k == "o_umsg":
        c.clear_state()
        try:
            await c.bot.copy_message(st["uid"], c.chat.id, c.msg.message_id)
            await c.send(t("✅ وصلت رسالتك للعضو.", "✅ Delivered."), kb([_back(c, f"o:u:{st['uid']}")]))
        except TelegramError:
            await c.send(t("⚠️ تعذّر الإرسال: العضو حظر البوت أو لم يبدأه.", "⚠️ Couldn't deliver: the member blocked the bot or never started it."), kb([_back(c, f"o:u:{st['uid']}")]))
    elif k == "o_mttxt":
        html = "" if text == "0" else ui.html_of(c.msg)
        if len(html) > 1500:
            return await c.send(t("⚠️ الرسالة طويلة. اختصرها وأرسلها من جديد.", "⚠️ Too long. Shorten it and send again."))
        core.setdefault("maint", {"on": False, "text": ""})["text"] = html
        await done(["set"], t("✅ حُفظت رسالة الصيانة.", "✅ Maintenance text saved."))
    elif k == "o_adm":
        if not text.lstrip("-").isdigit():
            return await c.send(t("أرسل رقماً صحيحاً.", "Send a numeric ID."))
        if int(text) not in core.setdefault("admins", []):
            core["admins"].append(int(text))
        await done(["adm"], t("✅ تمت الإضافة.", "✅ Added."))
    elif k == "o_fs_chat":
        origin = getattr(c.msg, "forward_origin", None)
        ref = None
        if origin is not None and getattr(origin, "chat", None) is not None:
            ref = origin.chat.id
        elif text:
            ref = text if text.startswith("@") or text.lstrip("-").isdigit() else "@" + text.rsplit("/", 1)[-1]
            if isinstance(ref, str) and ref.lstrip("-").isdigit():
                ref = int(ref)
        if ref is None:
            return await c.send(t("أرسل @المعرف أو حوّل منشوراً من القناة.", "Send the @username or forward a post."))
        try:
            chat = await c.bot.get_chat(ref)
            me = await c.bot.get_chat_member(chat.id, c.bot.id)
            if me.status not in ("administrator", "creator"):
                raise TelegramError("not admin")
        except TelegramError:
            return await c.send(t("⚠️ لم أستطع الوصول. تأكد أن البوت مشرف في القناة/القروب ثم أعد المحاولة.",
                                  "⚠️ Couldn't access it. Make sure the bot is an admin there and try again."))
        url = f"https://t.me/{chat.username}" if chat.username else (chat.invite_link or "")
        if not url:
            try:
                url = (await c.bot.create_chat_invite_link(chat.id)).invite_link
            except TelegramError:
                url = ""
        core.setdefault("fs", []).append({"type": "chat", "chat_id": chat.id, "title": chat.title or str(ref), "url": url, "on": True})
        await done(["fs"], t("✅ تمت الإضافة.", "✅ Added."))
    elif k == "o_fs_link":
        sep = "|" if "|" in text else (" - " if " - " in text else ("-" if "-" in text else None))
        if not sep:
            return await c.send(t("الصيغة: <code>الاسم | الرابط</code> أو <code>الاسم - الرابط</code>", "Format: <code>Title | link</code>"))
        title, url = [x.strip() for x in text.split(sep, 1)]
        u_clean = clean_url(url)
        t_clean = clean_url(title)
        if not u_clean and t_clean:
            title, url = url, title
            u_clean = t_clean
        if not u_clean:
            return await c.send(t("⚠️ الرابط غير صالح. يجب أن يبدأ بـ https:// أو @المعرف.", "⚠️ Invalid link. Must start with https:// or @username."))
        core.setdefault("fs", []).append({"type": "link", "title": title[:60] or "Link", "url": u_clean, "on": True})
        await done(["fs"], t("✅ تمت الإضافة.", "✅ Added."))
    elif k == "o_fs_msg":
        core["fs_msg"] = c.msg.text_html or ""
        await done(["fs"], t("✅ تم الحفظ.", "✅ Saved."))
    elif k == "o_sl":
        core.setdefault("links", {})[secrets.token_hex(4)] = {"name": text[:40] or "link", "n": 0}
        await done(["sl"])
    elif k in ("o_ban", "o_unban"):
        if not text.isdigit():
            return await c.send(t("أرسل رقماً صحيحاً.", "Send a numeric ID."))
        async with db.Session() as s:
            row = await s.get(db.BUser, (c.bot_id, int(text)))
            if row is None:
                row = db.BUser(bot_id=c.bot_id, user_id=int(text))
                s.add(row)
            row.banned = k == "o_ban"
            await s.commit()
        await done(["ban"], t("✅ تم.", "✅ Done."))
    elif k == "o_wel":
        core.setdefault("welcome", {})["text"] = c.msg.text_html or ""
        await done(["wel"], t("✅ تم حفظ الترحيب.", "✅ Welcome saved."))
    elif k == "o_welbtn":
        if text.strip() == "0":
            core.setdefault("welcome", {})["buttons"] = []
            await done(["wel"], t("✅ تم حذف الأزرار.", "✅ Buttons removed."))
        else:
            parsed = parse_buttons(text)
            if not parsed:
                return await c.send(t("⚠️ لم يتم العثور على أي زر برابط صالح.\nالصيغة: <code>نص الزر - https://example.com</code>\nأو أرسل <code>0</code> لإلغاء الأزرار.",
                                      "⚠️ No valid buttons with URLs found.\nFormat: <code>Button text - https://example.com</code>\nOr send <code>0</code> to clear."))
            core.setdefault("welcome", {})["buttons"] = parsed
            await done(["wel"], t(f"✅ تم حفظ {sum(len(r) for r in parsed)} زر بنجاح.", f"✅ Saved {sum(len(r) for r in parsed)} buttons."))
    elif k == "o_qr_k":
        c.set_state("o_qr_v", key=text[:60])
        await c.send(t("✍️ الآن أرسل نص الرد.", "✍️ Now send the reply text."))
    elif k == "o_qr_v":
        core.setdefault("quick", []).append({"k": st["key"], "v": ui.html_of(c.msg) or esc(text)})
        await done(["qr"], t("✅ تم الحفظ.", "✅ Saved."))
    elif k == "o_sc_k":
        cmd = text.lstrip("/").split()[0].lower() if text else ""
        if not cmd.replace("_", "").isalnum() or cmd in ("start", "admin", "panel", "cancel", "report"):
            return await c.send(t("اسم غير صالح. استخدم حروفاً إنجليزية وأرقاماً فقط.", "Invalid name. Use latin letters and digits only."))
        c.set_state("o_sc_v", cmd=cmd[:32])
        await c.send(t("✍️ الآن أرسل نص الرد.", "✍️ Now send the reply text."))
    elif k == "o_sc_v":
        core.setdefault("shortcuts", []).append({"cmd": st["cmd"], "v": ui.html_of(c.msg) or esc(text)})
        await done(["sc"], t("✅ تم الحفظ.", "✅ Saved."))
    elif k == "o_imp":
        d = c.msg.document
        if d is None:
            return await c.send(t("أرسل ملف .json.", "Send a .json file."))
        try:
            path = await c.download(d.file_id, ".json")
            payload = json.loads(path.read_text(encoding="utf-8"))
            path.unlink(missing_ok=True)
            assert payload.get("format") == "botforge-backup" and isinstance(payload.get("data"), dict)
        except Exception:
            return await c.send(t("⚠️ ملف غير صالح.", "⚠️ Invalid file."))
        await _restore(c, payload["data"])
        c.clear_state()
        await c.send(t("✅ تم الاستيراد.", "✅ Imported."))
        await owner_cb(c, ["sys"])
    else:
        c.clear_state()
        await owner_home(c)


def register(app: Application, bot_row: db.Bot, tpl, core: dict) -> None:
    app.bot_data.update(bot_id=bot_row.id, owner_id=bot_row.owner_id, factory_id=bot_row.factory_id, core=core, tpl=tpl)
    app.bot_data.setdefault("adm", {})
    app.add_handler(TypeHandler(Update, on_gate), group=-1)     # الإغلاق والصيانة قبل أي شيء
    app.add_handler(TypeHandler(Update, on_after), group=1)     # رسالة الترويج بعد انتهاء الاستخدام
    app.add_handler(CommandHandler("start", on_start))
    app.add_handler(CommandHandler("report", on_report))
    app.add_handler(CommandHandler(["admin", "panel"], on_admin))
    app.add_handler(CommandHandler("cancel", on_cancel))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(InlineQueryHandler(on_inline))
    app.add_handler(ChatJoinRequestHandler(on_join_request))
    app.add_handler(ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.ALL & ~filters.StatusUpdate.ALL & ~filters.UpdateType.EDITED, on_message))
    app.add_error_handler(on_error)
    tpl.setup(app)


async def set_commands(app: Application) -> None:
    """قائمة الأوامر: /start للجميع، و/admin يظهر للمالك فقط."""
    from telegram import BotCommand, BotCommandScopeChat
    try:
        await app.bot.set_my_commands([BotCommand("start", "القائمة الرئيسية"), BotCommand("report", "الإبلاغ عن إساءة")])
        await app.bot.set_my_commands([BotCommand("start", "القائمة الرئيسية"), BotCommand("admin", "غرفة التحكم")],
                                      scope=BotCommandScopeChat(app.bot_data["owner_id"]))
    except Exception:  # noqa: BLE001
        pass  # المالك لم يفتح البوت بعد، أو أُوقف البوت أثناء التنفيذ
    await apply_menu_button(app)
