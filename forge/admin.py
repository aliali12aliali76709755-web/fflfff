"""لوحة إدارة المنصة: المستخدمون، البوتات، الإغلاق والصيانة، المراسلة، الترويج، والسجل.

تعمل لمدير المنصة في الصانع الرئيسي، ولمالك أي «صانع فرعي» على بوتات صانعه فقط.
عرض التوكن ودخول غرف التحكم مقصوران على مدير المنصة الرئيسية.
"""
from __future__ import annotations

import asyncio
import contextlib
import csv
import datetime as dt
import io
import re
import time

from sqlalchemy import func, select, update as sa_update
from telegram.constants import ParseMode
from telegram.error import Forbidden, RetryAfter, TelegramError

from . import child, config, crypto, db, errors, templates, ui
from . import maker as mk
from . import plat as platform
from .modules import currency, ledger
from .i18n import norm
from .ui import B, esc, kb

REASONS = [("مخالفة الشروط والأحكام", "Violation of the terms and conditions"), ("محتوى مخالف", "Prohibited content"),
           ("احتيال أو تصيّد", "Fraud or phishing"), ("رسائل مزعجة (سبام)", "Spam"), ("انتحال صفة جهة أخرى", "Impersonation")]
DURATIONS = [(3600, "ساعة"), (6 * 3600, "6 ساعات"), (86400, "يوم"), (3 * 86400, "3 أيام"), (7 * 86400, "أسبوع"), (30 * 86400, "شهر")]
MODE_NAME = {"closed": "🔒 إغلاق", "temp": "⏳ إغلاق مؤقت", "maint": "🛠 وضع الصيانة"}
FILTERS = [("all", "الكل"), ("run", "🟢 تعمل"), ("lock", "🔒 مغلقة"), ("off", "⏸ متوقفة"), ("err", "⚠️ أخطاء"), ("top", "🏆 الأكبر")]
ACTS = {"lock": "🔒 إغلاق", "unlock": "🔓 فتح", "auto_unlock": "🔓 فتح تلقائي", "token": "🔑 عرض التوكن", "bmsg": "📢 رسالة لأعضاء بوت",
        "warn": "⚠️ تحذير مالك", "del": "🗑 حذف بوت", "ban": "⛔ حظر بوت نهائياً", "unban": "♻️ رفع حظر بوت", "transfer": "📤 نقل ملكية",
        "super": "🎛 دخول غرفة تحكم", "verify": "✅ توثيق", "restart": "🔁 إعادة تشغيل", "uban": "🚫 حظر مستخدم", "uunban": "✅ رفع حظر مستخدم",
        "bcast": "📣 إذاعة عامة", "promo": "📢 إعداد الترويج", "stop": "⏸ إيقاف تقني", "start": "▶️ تشغيل"}
WHEN = {"start": "مع رسالة البداية", "idle": "بعد انتهاء الاستخدام", "both": "مع البداية وبعد انتهاء الاستخدام"}
IDLES = [30, 60, 120, 300, 900]
EVERY = [(0, "كل مرة"), (3600, "مرة كل ساعة"), (6 * 3600, "مرة كل 6 ساعات"), (86400, "مرة كل يوم"), (7 * 86400, "مرة كل أسبوع")]
BM_PRESETS = [
    ("🚫 أُغلق بسبب مخالفة الشروط", "📣 <b>إشعار من إدارة المنصة</b>\n\nتم إغلاق هذا البوت (@{u}) بسبب مخالفة الشروط والأحكام.",
     "📣 <b>Notice from the platform</b>\n\nThis bot (@{u}) has been closed for violating the terms and conditions."),
    ("🛠 صيانة مؤقتة", "📣 <b>إشعار من إدارة المنصة</b>\n\nهذا البوت (@{u}) متوقف مؤقتاً للصيانة وسيعود قريباً.",
     "📣 <b>Notice from the platform</b>\n\nThis bot (@{u}) is paused for maintenance and will be back soon."),
    ("✅ عاد البوت للعمل", "📣 <b>إشعار من إدارة المنصة</b>\n\nعاد البوت (@{u}) للعمل. أرسل /start للمتابعة.",
     "📣 <b>Notice from the platform</b>\n\nThis bot (@{u}) is back. Send /start to continue."),
]
BACK = [B("⬅️ لوحة الإدارة", "m:adm:home")]


def _plain(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html)


async def log_act(m: mk.M, act: str, b: db.Bot | None = None, info: str = "") -> None:
    await platform.audit(m.fid, m.uid, act, f"@{b.username}" if b is not None else "", info)


def _maker_bot(m: mk.M, b: db.Bot):
    """بوت الصانع الذي يعرفه مالك هذا البوت (الرئيسي أو الصانع الفرعي الذي أنشأه عبره)."""
    if b.factory_id == m.fid:
        return m.bot
    app = m.mgr.maker if b.factory_id == 0 else m.mgr.apps.get(b.factory_id)
    return app.bot if app is not None else m.bot


def _fit(head: str, items: list[str], sep: str = "\n", empty: str = "", limit: int = 3800) -> str:
    """يجمع العناصر كاملةً دون تجاوز حد رسالة تيليجرام (لا يقص وسماً من منتصفه)."""
    out = []
    size = len(head)
    for it in items:
        if size + len(it) + len(sep) > limit:
            break
        out.append(it)
        size += len(it) + len(sep)
    return head + (sep.join(out) if out else empty)


async def tell_owner(m: mk.M, b: db.Bot, text: str, markup=None) -> bool:
    try:
        await _maker_bot(m, b).send_message(b.owner_id, text, parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=markup)
        return True
    except TelegramError:
        return False


def _card_btn(m: mk.M, b: db.Bot):
    return kb([[B(m.t("🗂 بطاقة البوت", "🗂 Bot card"), f"m:b:{b.id}")]])


async def _factory_bots(fid: int, *cond) -> list[db.Bot]:
    async with db.Session() as s:
        return list((await s.execute(select(db.Bot).where(db.Bot.factory_id == fid, *cond).order_by(db.Bot.created.desc()))).scalars().all())


def _locked_ids() -> list[int]:
    return [bid for bid, a in platform._adm.items() if platform.lock_of(a) is not None]


# ───────────────────────── الإرسال عبر بوت مصنوع ─────────────────────────
@contextlib.asynccontextmanager
async def _bot_for(m: mk.M, b: db.Bot):
    """كائن Bot للإرسال باسم بوت مصنوع، حتى لو كان متوقفاً."""
    app = m.mgr.apps.get(b.id)
    if app is not None:
        yield app.bot
        return
    tmp = m.mgr.build(crypto.dec(b.token))
    await tmp.bot.initialize()
    try:
        yield tmp.bot
    finally:
        try:
            await tmp.bot.shutdown()
        except Exception:  # noqa: BLE001
            pass


async def _members(bot_id: int) -> list[tuple[int, str]]:
    U = db.BUser
    async with db.Session() as s:
        return [(u, l or "") for u, l in (await s.execute(select(U.user_id, U.lang).where(
            U.bot_id == bot_id, U.kind == "private", U.banned.is_(False), U.blocked.is_(False)))).all()]


async def notify_members(m: mk.M, b: db.Bot, make_text, *, report: bool = True) -> tuple[int, int]:
    """يرسل نصاً لكل أعضاء بوت عبر البوت نفسه. make_text(lang) يعيد النص بلغة العضو."""
    rows = await _members(b.id)
    ok = fail = 0
    try:
        async with _bot_for(m, b) as bot:
            for uid, lang in rows:
                text = make_text(norm(lang))
                try:
                    try:
                        await bot.send_message(uid, text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
                    except RetryAfter as e:
                        await asyncio.sleep(float(getattr(e, "retry_after", 3)) + 1)
                        await bot.send_message(uid, text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
                    ok += 1
                except Forbidden:
                    fail += 1
                    async with db.Session() as s:
                        await s.execute(sa_update(db.BUser).where(db.BUser.bot_id == b.id, db.BUser.user_id == uid).values(blocked=True))
                        await s.commit()
                except TelegramError:
                    fail += 1
                await asyncio.sleep(0.05)
    except TelegramError:
        fail = len(rows) - ok
    if report:
        try:
            await m.bot.send_message(m.uid, f"✅ انتهى الإرسال لأعضاء @{b.username}.\n📬 وصلت: {ok}\n⚠️ لم تصل: {fail}",
                                     reply_markup=kb([[B("🤖 بطاقة البوت", f"m:adm:bc:{b.id}")]]))
        except TelegramError:
            pass
    return ok, fail


# ───────────────────────── الإغلاق والفتح ─────────────────────────
async def _ensure_running(m: mk.M, b: db.Bot) -> bool:
    """البوت المغلق يبقى مشغّلاً ليعرض إشعار الإغلاق لمن يفتحه."""
    if m.mgr.running(b.id):
        return True
    if b.status == "error":
        return False
    async with db.Session() as s:
        row = await s.get(db.Bot, b.id)
        row.status = "active"
        await s.commit()
    ok, _ = await m.mgr.start_bot(row)
    return ok


async def apply_lock(m: mk.M, b: db.Bot, job: dict, notify: bool) -> None:
    adm = await platform.adm(b.id)
    mode = job["mode"] if not (job["mode"] == "temp" and not job.get("sec")) else "closed"
    lk = {"mode": mode, "reason": job.get("reason") or "", "reason_en": job.get("reason_en") or job.get("reason") or "",
          "until": (time.time() + max(60, int(job["sec"]))) if mode == "temp" else None, "at": time.time(), "by": m.uid,
          "paused": b.status == "disabled"}      # كان المالك قد أوقفه: نعيده متوقفاً عند الفتح
    adm["lock"] = lk
    await platform.adm_save(b.id)
    await _ensure_running(m, b)
    info = MODE_NAME[lk["mode"]] + (f" {ui.dur(job['sec'])}" if lk["until"] else "") + (f" — {lk['reason']}" if lk["reason"] else "")
    await log_act(m, "lock", b, info)
    await tell_owner(m, b, f"📣 <b>إشعار من إدارة المنصة</b> بخصوص بوتك @{b.username}\n\n" + child.lock_text(lk, "ar") +
                     ("" if lk["mode"] == "maint" else "\n\nإن رأيت أن هذا خطأ، افتح بطاقة البوت واضغط «📨 طلب مراجعة»."), _card_btn(m, b))
    if notify:
        m.x.application.create_task(notify_members(m, b, lambda lang: "📣 " + child.lock_text(lk, lang)))


async def apply_unlock(m: mk.M, b: db.Bot, notify: bool) -> None:
    adm = await platform.adm(b.id)
    was = adm.get("lock") or {}
    adm["lock"] = None
    await platform.adm_save(b.id)
    if was.get("paused"):
        await mk.set_enabled(m, b, False)
    await log_act(m, "unlock", b)
    await tell_owner(m, b, f"🔓 أعادت إدارة المنصة فتح بوتك @{b.username}، وهو يعمل الآن كالمعتاد.", _card_btn(m, b))
    if notify:
        ar, en = BM_PRESETS[2][1], BM_PRESETS[2][2]
        m.x.application.create_task(notify_members(m, b, lambda lang: (ar if lang == "ar" else en).replace("{u}", b.username)))


async def expire_locks(mgr) -> None:
    """ينهي الإغلاقات المؤقتة التي حان وقتها ويبلغ المالك."""
    for bid in platform.expired():
        adm = await platform.adm(bid)
        was = adm.get("lock") or {}
        if not was.get("until") or was["until"] > time.time():      # أُعيد إغلاقه أثناء الدورة
            continue
        adm["lock"] = None
        await platform.adm_save(bid)
        if was.get("paused"):
            await mgr.stop_bot(bid)
            await mgr._set_status(bid, "disabled")
        async with db.Session() as s:
            row = await s.get(db.Bot, bid)
        if row is None:
            continue
        await platform.audit(row.factory_id, 0, "auto_unlock", f"@{row.username}")
        sender = mgr.maker if row.factory_id == 0 else mgr.apps.get(row.factory_id)
        if sender is None:
            continue
        try:
            await sender.bot.send_message(row.owner_id, f"🔓 انتهت مدة الإغلاق المؤقت لبوتك @{row.username}، وعاد للعمل.")
        except TelegramError:
            pass


async def daily_report(mgr) -> None:
    """ملخص الأمس يصل مدير المنصة مرة كل يوم بعد التاسعة صباحاً بالتوقيت المحلي."""
    if not config.ADMIN_ID or mgr.maker is None:
        return
    local = db.now() + dt.timedelta(hours=config.TZ_HOURS)
    today = local.strftime("%Y-%m-%d")
    last = await db.kv_get(0, "sys:lastreport")
    if last is None:
        await db.kv_set(0, "sys:lastreport", today)
        return
    if last == today or local.hour < 9:
        return
    await db.kv_set(0, "sys:lastreport", today)
    if not (await platform.get(0))["notify"].get("daily", True):
        return
    d0 = dt.datetime.combine(db.now().date(), dt.time())
    d1 = d0 - dt.timedelta(days=1)
    async with db.Session() as s:
        async def cnt(model, *cond):
            return int((await s.execute(select(func.count()).select_from(model).where(*cond))).scalar() or 0)
        users, new_users = await cnt(db.MUser, db.MUser.factory_id == 0), await cnt(db.MUser, db.MUser.factory_id == 0, db.MUser.created >= d1, db.MUser.created < d0)
        new_bots = await cnt(db.Bot, db.Bot.factory_id == 0, db.Bot.created >= d1, db.Bot.created < d0)
        errs = await cnt(db.Bot, db.Bot.factory_id == 0, db.Bot.status == "error")
        ids = list((await s.execute(select(db.Bot.id).where(db.Bot.factory_id == 0))).scalars().all())
        reports = await cnt(db.Report, db.Report.factory_id == 0, db.Report.created >= d1, db.Report.created < d0)
    day = await db.daily(ids, d1.strftime("%Y-%m-%d"))
    locked = sum(1 for i in ids if platform.lock_of(platform.peek(i)) is not None)
    text = (f"📬 <b>تقرير الأمس</b> — {d1:%Y-%m-%d}\n{ui.LINE}\n" + ui.rows([
        ("مستخدمون جدد للصانع", f"+{new_users}  (الإجمالي {ui.num(users)})"), ("بوتات جديدة", f"+{new_bots}  (الإجمالي {ui.num(len(ids))})"),
        ("أعضاء جدد في كل البوتات", f"+{day.get('new', 0)}"), ("رسائل في كل البوتات", ui.num(day.get("msgs", 0))),
        ("رسائل ترويج أُرسلت", day.get("promo", 0)), ("بلاغات جديدة", reports), ("بوتات مغلقة الآن", locked), ("بوتات تحتاج انتباه", errs)]))
    try:
        await mgr.maker.bot.send_message(config.ADMIN_ID, text, parse_mode=ParseMode.HTML,
                                         reply_markup=kb([[B("👑 لوحة الإدارة", "m:adm:home")]]))
    except TelegramError:
        pass


# ───────────────────────── الرئيسية ─────────────────────────
async def admin_home(m: mk.M) -> None:
    m.clear_state()
    fid = m.fid
    day0 = dt.datetime.combine(db.now().date(), dt.time())
    async with db.Session() as s:
        async def cnt(model, *cond):
            return int((await s.execute(select(func.count()).select_from(model).where(*cond))).scalar() or 0)
        users, users_today = await cnt(db.MUser, db.MUser.factory_id == fid), await cnt(db.MUser, db.MUser.factory_id == fid, db.MUser.created >= day0)
        bots, bots_today = await cnt(db.Bot, db.Bot.factory_id == fid), await cnt(db.Bot, db.Bot.factory_id == fid, db.Bot.created >= day0)
        active, errs = await cnt(db.Bot, db.Bot.factory_id == fid, db.Bot.status == "active"), await cnt(db.Bot, db.Bot.factory_id == fid, db.Bot.status == "error")
        ids = list((await s.execute(select(db.Bot.id).where(db.Bot.factory_id == fid))).scalars().all())
        reports = await cnt(db.Report, db.Report.factory_id == fid)
        series = []
        for i in range(6, -1, -1):
            a, b = day0 - dt.timedelta(days=i), day0 - dt.timedelta(days=i - 1)
            series.append(await cnt(db.MUser, db.MUser.factory_id == fid, db.MUser.created >= a, db.MUser.created < b))
    agg = await mk._agg(ids)
    running = sum(1 for i in ids if m.mgr.running(i))
    locked = sum(1 for i in ids if platform.lock_of(platform.peek(i)) is not None)
    p = await platform.get(fid)
    flags = []
    if p["maintenance"]:
        flags.append("🛠 وضع صيانة الصانع مفعّل")
    if p["fs"]:
        flags.append(f"🔐 اشتراك إجباري: {len(p['fs'])}")
    if p["off_tpls"]:
        flags.append(f"🧩 أنواع معطّلة: {len(p['off_tpls'])}")
    text = (f"👑 <b>لوحة الإدارة</b> — {esc(m.brand())}\n{ui.LINE}\n" + ui.rows([
        ("مستخدمو الصانع", f"{ui.num(users)}  (+{users_today} اليوم)"), ("البوتات", f"{ui.num(bots)}  (+{bots_today} اليوم)"),
        ("تعمل الآن", f"{running} من {active} نشطة"), ("مغلقة من الإدارة", locked), ("تحتاج انتباه", errs),
        ("أعضاء كل البوتات", ui.num(agg["total"])), ("رسائل كل البوتات", ui.num(agg["msgs"])),
        ("أعضاء جدد اليوم", agg["new"]), ("البلاغات", reports)]) +
        f"\n\n📈 <code>{ui.spark(series)}</code> مستخدمون جدد للصانع — 7 أيام ({sum(series)})" + ("\n\n" + "\n".join(flags) if flags else ""))
    await m.show(text, kb([
        [B("👥 المستخدمون", "m:adm:u"), B("🤖 البوتات", "m:adm:b:0:all")],
        [B("🏆 الأفضل", "m:adm:top"), B(f"🔒 المغلقة ({locked})", "m:adm:b:0:lock")],
        [B("📢 رسالة الترويج", "m:adm:pm"), B("📣 الإذاعة", "m:adm:bcm")],
        [B("🧩 الأنواع", "m:adm:t"), B("🔐 اشتراك الصانع", "m:adm:fs")],
        [B("⚙️ إعدادات المنصة", "m:adm:s"), B("📜 سجل الإدارة", "m:adm:log")],
        [B(f"🐞 البلاغات ({reports})", "m:adm:rep"), B(f"🧯 الأخطاء ({len(errors.RECENT)})", "m:adm:err") if fid == 0 else None],
        [B("📊 مبيعات وخدمات المنصة", "m:adm:svc_stats"), B("📥 تصدير قائمة البوتات", "m:adm:exp")],
        [B("🖥 لوحة الويب", "m:adm:web"), B("🌐 حالة الويب", "m:adm:wb")] if fid == 0 else None,
        [B("🔄 تحديث", "m:adm:home"), m.home_btn()]]))


# ───────────────────────── المستخدم ─────────────────────────
async def admin_user(m: mk.M, uid: int) -> None:
    async with db.Session() as s:
        u = await s.get(db.MUser, (m.fid, uid))
        refs = int((await s.execute(select(func.count()).select_from(db.MUser).where(db.MUser.factory_id == m.fid, db.MUser.ref_by == uid))).scalar() or 0)
    bots = await _factory_bots(m.fid, db.Bot.owner_id == uid)
    if u is None:
        await m.show("لا يوجد مستخدم بهذا الرقم.", kb([[B("⬅️ المستخدمون", "m:adm:u")]]))
        return
    p = await platform.get(m.fid)
    banned = uid in p["banned"]
    agg = await mk._agg([b.id for b in bots])
    lim = platform.max_bots(p, uid)
    seller_bal = await ledger.get_seller_balance_display(uid)
    text = (f"👤 <b>{esc(u.name)}</b>" + (f"  @{u.username}" if u.username else "") + f"\n🆔 <code>{uid}</code>\n{ui.LINE}\n" + ui.rows([
        ("انضم", ui.when(u.created, "%Y-%m-%d")), ("اللغة", u.lang or "تلقائية"), ("بوتاته", len(bots)), ("جمهور بوتاته", ui.num(agg["total"])),
        ("دعا", refs), ("حد بوتاته", (lim or "بلا حد") if not own_lim else f"{lim or 'بلا حد'} (خاص به)"),
        ("رصيد البائع في الصانع", seller_bal),
        ("الحالة", "🚫 محظور من الصانع" if banned else "✅ نشط")]))
    rows = [[B(f"{mk.status_icon(b)} @{b.username}", f"m:adm:bc:{b.id}")] for b in bots[:10]]
    rows += [[B("💵 شحن رصيد البائع ($)", f"m:adm:crd_s:{uid}"), B("✉️ مراسلته", f"m:adm:uxm:{uid}")],
             [B("🔢 حد بوتاته", f"m:adm:uxl:{uid}")] if not bots else [B("🔢 حد بوتاته", f"m:adm:uxl:{uid}"), B("🔒 إغلاق كل بوتاته", f"m:adm:uxc:{uid}")],
             [B("🔓 فتح كل بوتاته", f"m:adm:uxo:{uid}")] if bots else None,
             [B("✅ رفع الحظر" if banned else "🚫 حظر من الصانع", f"m:adm:ub:{uid}", style=None if banned else "danger")],
             [B("⬅️ المستخدمون", "m:adm:u")]]
    await m.show(text, kb(rows))


# ───────────────────────── بطاقة البوت ─────────────────────────
def _promo_label(p: dict, adm: dict) -> str:
    own = adm.get("promo")
    if own is True:
        return "🟢 مفعّلة لهذا البوت دائماً"
    if own is False:
        return "🔴 معطّلة لهذا البوت"
    return "يتبع الوضع العام (" + ("🟢 تظهر" if p["promo"]["on"] else "⚪ لا تظهر") + ")"


def _lock_block(lk: dict) -> str:
    out = f"{MODE_NAME[lk['mode']]}"
    if lk.get("reason"):
        out += f"\n📌 السبب: {esc(lk['reason'])}"
    out += f"\n🕒 منذ: {ui.when(lk['at'])}"
    if lk.get("until"):
        out += f"\n🔓 يُفتح تلقائياً: {ui.when(lk['until'])} (بعد {ui.dur(lk['until'] - time.time())})"
    return out


async def admin_bot(m: mk.M, bot_id: int) -> None:
    b = await mk.get_bot(m, bot_id, admin=True)
    if b is None:
        await m.show("البوت غير موجود.", kb([[B("⬅️ البوتات", "m:adm:b:0")]]))
        return
    m.udata["adm_ctx"] = b.id
    n = await child.counts(b.id)
    week = await child.week_series([b.id], "new")
    adm = await platform.adm(b.id)
    lk = platform.lock_of(adm)
    p = await platform.get(b.factory_id)
    async with db.Session() as s:
        owner = await s.get(db.MUser, (b.factory_id, b.owner_id))
        owned = int((await s.execute(select(func.count()).select_from(db.Bot).where(db.Bot.factory_id == b.factory_id, db.Bot.owner_id == b.owner_id))).scalar() or 0)
        parent = await s.get(db.Bot, b.factory_id) if b.factory_id else None
    age = ui.dur((db.now() - b.created).total_seconds())
    text = (f"🤖 <b>{esc(b.name or b.username)}</b>  @{b.username}" + (" ✅" if adm.get("verified") else "") + f"\n🆔 <code>{b.id}</code>\n{ui.LINE}\n" + ui.rows([
        ("النوع", templates.get(b.template).title("ar")), ("الحالة", _plain(mk.status_text(m, b))),
        ("تاريخ الإنشاء", f"{ui.when(b.created)} (منذ {age})"),
        ("إجمالي المستخدمين", f"{ui.num(n['total'])}  (+{n['new']} اليوم)"), ("نشطون اليوم", n["active"]),
        ("الرسائل", ui.num(n["msgs"])), ("حظروا البوت", n["blocked"])]) +
        f"\n📈 <code>{ui.spark(week)}</code> أعضاء جدد — 7 أيام\n\n👤 <b>صانع البوت</b>\n" +
        f"▫️ الاسم: <b>{esc(owner.name if owner else '؟')}</b>\n▫️ اليوزر: " + (f"@{owner.username}" if owner and owner.username else "بلا يوزر") +
        f"\n▫️ الآيدي: <code>{b.owner_id}</code>\n▫️ عدد بوتاته: <b>{owned}</b>")
    if b.factory_id:
        text += "\n\n🏭 أُنشئ عبر صانع فرعي: " + (f"@{parent.username}" if parent is not None else f"<code>{b.factory_id}</code> (محذوف)")
    if lk is not None:
        text += "\n\n" + _lock_block(lk)
    text += f"\n\n📢 رسالة الترويج: {_promo_label(p, adm)}" + (" · بنص خاص" if adm.get("promo_text") else "")
    if adm.get("warns"):
        text += f"\n⚠️ تحذيرات سابقة للمالك: {len(adm['warns'])} (آخرها {ui.when(adm['warns'][-1]['at'], '%m-%d')})"
    if adm.get("super"):
        text += "\n🎛 دخولك إلى غرفة تحكم هذا البوت مفعّل: افتح البوت وأرسل /admin."
    if adm.get("note"):
        text += f"\n\n📝 <b>ملاحظتك:</b> {esc(adm['note'])}"
    main = m.fid == 0
    own_user = [B("👤 المالك", f"m:adm:uc:{b.owner_id}")] if b.factory_id == m.fid else []
    toggle = B("⏸ إيقاف تقني", f"m:adm:bt:{b.id}") if b.status == "active" else B("▶️ تشغيل", f"m:adm:bt:{b.id}")
    await m.show(text, kb([
        [B("↗ فتح البوت", url=f"https://t.me/{b.username}"), B("📈 الإحصائيات", f"m:bs:{b.id}")],
        [B("🔑 بيانات البوت والتوكن", f"m:adm:tk:{b.id}", style="primary")] if main else None,
        [B("🔓 إعادة فتح البوت", f"m:adm:ul:{b.id}", style="success")] if lk is not None else
        [B("🔒 إغلاق", f"m:adm:lk:{b.id}:c", style="danger"), B("⏳ مؤقت", f"m:adm:lk:{b.id}:t"), B("🛠 صيانة", f"m:adm:lk:{b.id}:m")],
        [B("📢 رسالة لأعضائه", f"m:adm:bm:{b.id}"), B("⚠️ تحذير المالك", f"m:adm:wn:{b.id}")],
        [B("📢 الترويج: " + {True: "🟢", False: "🔴", None: "تلقائي"}[adm.get("promo")], f"m:adm:pr:{b.id}"), B("✏️ نص ترويج خاص", f"m:adm:prt:{b.id}")],
        [B("☑️ إلغاء التوثيق" if adm.get("verified") else "✅ توثيق", f"m:adm:vf:{b.id}"), B("📝 ملاحظة", f"m:adm:nt:{b.id}")],
        [B("🎛 غرفة التحكم: " + ("🟢 دخولك مفعّل" if adm.get("super") else "⚪ فعّل دخولك"), f"m:adm:sp:{b.id}")] if main else None,
        own_user + ([B("📤 نقل الملكية", f"m:adm:to:{b.id}")] if main else []),
        [B("🔁 إعادة تشغيل", f"m:adm:rs:{b.id}"), toggle],
        [B("🗑 حذف", f"m:adm:bd:{b.id}", style="danger"), B("⛔ حظر نهائي", f"m:adm:bx:{b.id}", style="danger")],
        [B("⬅️ البوتات", "m:adm:b:0")]]))


async def _sheet(m: mk.M, b: db.Bot) -> str:
    """بطاقة البيانات الكاملة مع التوكن."""
    n = await child.counts(b.id)
    async with db.Session() as s:
        owner = await s.get(db.MUser, (b.factory_id, b.owner_id))
    return (f"🗂 <b>بيانات البوت</b>\n{ui.LINE}\n"
            f"🤖 اسم البوت: <b>{esc(b.name or '—')}</b>\n🔗 يوزر البوت: @{b.username}\n🆔 رقم البوت: <code>{b.id}</code>\n"
            f"🧩 النوع: {templates.get(b.template).title('ar')}\n📅 تاريخ الإنشاء: <b>{ui.when(b.created)}</b>\n"
            f"👥 إجمالي المستخدمين: <b>{ui.num(n['total'])}</b>\n{ui.LINE}\n"
            f"👤 صانع البوت: <b>{esc(owner.name if owner else '؟')}</b>\n🔗 يوزره: " + (f"@{owner.username}" if owner and owner.username else "بلا يوزر") +
            f"\n🆔 آيديه: <code>{b.owner_id}</code>\n{ui.LINE}\n🔑 التوكن:\n<code>{esc(crypto.dec(b.token))}</code>\n\n"
            "⏱ تُحذف هذه الرسالة تلقائياً بعد دقيقتين. من يملك التوكن يتحكم بالبوت كاملاً، فلا تشاركه.")


async def _del_msg(context) -> None:
    chat_id, mid = context.job.data
    try:
        await context.bot.delete_message(chat_id, mid)
    except TelegramError:
        pass


async def _bots_page(m: mk.M, page: int, flt: str) -> None:
    fid, per = m.fid, 8
    Bt = db.Bot
    locked = _locked_ids()
    cond = [Bt.factory_id != 0] if (flt == "sub" and fid == 0) else [Bt.factory_id == fid]
    if flt == "run":
        cond.append(Bt.status == "active")
        if locked:
            cond.append(Bt.id.notin_(locked))
    elif flt == "off":
        cond.append(Bt.status == "disabled")
    elif flt == "err":
        cond.append(Bt.status == "error")
    elif flt == "lock":
        cond.append(Bt.id.in_(locked or [0]))
    async with db.Session() as s:
        total = int((await s.execute(select(func.count()).select_from(Bt).where(*cond))).scalar() or 0)
        if flt == "top":
            n_users = func.count(db.BUser.user_id)
            q = select(Bt).outerjoin(db.BUser, db.BUser.bot_id == Bt.id).where(*cond).group_by(Bt.id).order_by(n_users.desc(), Bt.created.desc())
        else:
            q = select(Bt).where(*cond).order_by(Bt.created.desc())
        bots = (await s.execute(q.limit(per).offset(page * per))).scalars().all()
    users = await mk.users_by_bot([b.id for b in bots])
    pages = max(1, (total + per - 1) // per)
    rows = [[B(f"{mk.status_icon(b)} @{b.username} · {templates.get(b.template).ar} · 👥 {users.get(b.id, 0)}"[:60], f"m:adm:bc:{b.id}")] for b in bots]
    rows.append([B("‹", f"m:adm:b:{page - 1}:{flt}") if page else None, B(f"{page + 1} / {pages}", "noop"), B("›", f"m:adm:b:{page + 1}:{flt}") if page < pages - 1 else None])
    flts = FILTERS + ([("sub", "🏭 عبر صانع فرعي")] if fid == 0 else [])
    rows += ui.grid([B(("• " if k == flt else "") + name, f"m:adm:b:0:{k}") for k, name in flts], 3)
    title = dict(flts).get(flt, "الكل")
    await m.show(f"🤖 <b>البوتات</b> — {title} ({ui.num(total)})\n" + ("مرتبة بعدد الأعضاء." if flt == "top" else "الأحدث أولاً.") +
                 "\n\nاضغط أي بوت لفتح بطاقته: بياناته، صانعه، توكنه، وإجراءات الإغلاق والمراسلة.",
                 kb(rows + [[B("🔍 بحث: يوزر البوت أو رقمه أو آيدي صانعه", "m:adm:bs")], BACK]))


def _lock_job(m: mk.M, bot_id: int) -> dict | None:
    job = m.udata.get("adm_lk")
    return job if job and job.get("b") == bot_id else None


async def _reasons(m: mk.M, b: db.Bot) -> None:
    job = _lock_job(m, b.id)
    head = MODE_NAME[job["mode"]] + (f" لمدة {ui.dur(job['sec'])}" if job.get("sec") else "")
    rows = [[B(ar, f"m:adm:lkr:{b.id}:{i}")] for i, (ar, _) in enumerate(REASONS)]
    rows += [[B("✍️ سبب آخر (اكتبه)", f"m:adm:lkr:{b.id}:x"), B("بدون ذكر سبب", f"m:adm:lkr:{b.id}:n")], [B("❌ إلغاء", f"m:adm:bc:{b.id}")]]
    await m.show(f"{head} — @{b.username}\n\nاختر السبب. يظهر السبب لمالك البوت ولكل من يفتح البوت.", kb(rows))


async def _lock_confirm(m: mk.M, b: db.Bot) -> None:
    job = _lock_job(m, b.id)
    n = len(await _members(b.id))
    what = {"closed": "يتوقف البوت عن الجميع (المالك والأعضاء) حتى تعيد فتحه.",
            "temp": f"يتوقف البوت عن الجميع لمدة {ui.dur(job.get('sec') or 0)} ثم يعود تلقائياً.",
            "maint": "يتوقف البوت عن الأعضاء فقط، والمالك يبقى قادراً على دخول غرفة التحكم."}[job["mode"]]
    text = (f"{MODE_NAME[job['mode']]} — @{b.username}\n{ui.LINE}\n{what}\n" + (f"📌 السبب: {esc(job['reason'])}\n" if job.get("reason") else "") +
            "\nكل من يفتح البوت بعدها يرى إشعاراً بذلك، ويصل المالكَ إشعار عبر الصانع.\n\n"
            f"هل تريد أيضاً إرسال الإشعار الآن إلى كل أعضاء البوت (<b>{ui.num(n)}</b>)؟")
    await m.show(text, kb([[B(f"✅ نفّذ وأبلغ الأعضاء ({ui.num(n)})", f"m:adm:lkgo:{b.id}:1", style="danger")],
                           [B("✅ نفّذ دون إبلاغ", f"m:adm:lkgo:{b.id}:0")], [B("❌ إلغاء", f"m:adm:bc:{b.id}")]]))


async def _promo_menu(m: mk.M) -> None:
    p = await platform.get(m.fid)
    cfg = p["promo"]
    ids = [b.id for b in await _factory_bots(m.fid)]
    on = sum(1 for i in ids if platform.peek(i).get("promo") is True)
    off = sum(1 for i in ids if platform.peek(i).get("promo") is False)
    sent = (await db.daily(ids, db.today())).get("promo", 0)
    cur = cfg.get("text") or child.PROMO_AR
    every = dict(EVERY).get(int(cfg["every"]), ui.dur(cfg["every"]))
    text = ("📢 <b>رسالة الترويج في البوتات المصنوعة</b>\n\nرسالة قصيرة تصل لأعضاء البوتات المبنية هنا وتدعوهم لصنع بوتهم عندك. "
            "تحدد أنت نصها، ومتى تصل، وفي أي البوتات.\n\n" + ui.rows([
                ("الوضع العام", "🟢 تظهر في كل البوتات" if cfg["on"] else "⚪ لا تظهر إلا في البوتات التي تفعّلها لها"),
                ("متى تُرسل", WHEN[cfg["when"]]), ("يُعدّ العضو منتهياً بعد", ui.dur(cfg["idle"]) + " بلا تفاعل"),
                ("التكرار لكل عضو", every), ("زر «اصنع بوتك»", "🟢 يظهر" if cfg["btn"] else "⚪ مخفي"),
                ("بوتات مستثناة", f"{on} مفعّلة دائماً · {off} معطّلة"), ("أُرسلت اليوم", sent)]) +
            "\n\n<b>النص الحالي</b>" + ("" if cfg.get("text") else " (الافتراضي)") + f":\n{ui.LINE}\n{cur}")
    await m.show(text, kb([
        [B("⚪ أوقف الوضع العام" if cfg["on"] else "🟢 فعّل الوضع العام", "m:adm:pmt")],
        [B("🕒 متى: " + {"start": "البداية", "idle": "بعد الاستخدام", "both": "الاثنان"}[cfg["when"]], "m:adm:pmw"),
         B(f"⏱ المهلة: {ui.dur(cfg['idle'])}", "m:adm:pmi")],
        [B(f"🔁 {every}", "m:adm:pme"), B("🔘 الزر: " + ("يظهر" if cfg["btn"] else "مخفي"), "m:adm:pmb")],
        [B("✏️ تعديل النص", "m:adm:pmx"), B("👁 معاينة", "m:adm:pmv")],
        [B("📋 اختيار البوتات", "m:adm:pml")], BACK]))


def _report_bot(text: str) -> int | None:
    mt = re.match(r"@\w+ \[(\d+)\]", text or "")
    return int(mt.group(1)) if mt else None


async def scr_services_stats(m: mk.M) -> None:
    async with db.Session() as s:
        async def tpl_stat(key: str):
            cnt = (await s.execute(select(func.count(db.ServiceOrder.id)).where(db.ServiceOrder.tpl_key == key))).scalar() or 0
            vol = (await s.execute(select(func.sum(db.ServiceOrder.price_user_usd)).where(db.ServiceOrder.tpl_key == key))).scalar() or 0.0
            return cnt, float(vol)

        smm_cnt, smm_vol = await tpl_stat("smm")
        tg_cnt, tg_vol = await tpl_stat("tgstars")
        sms_cnt, sms_vol = await tpl_stat("sms")
        dig_cnt, dig_vol = await tpl_stat("digital")

        total_orders = smm_cnt + tg_cnt + sms_cnt + dig_cnt
        total_vol = smm_vol + tg_vol + sms_vol + dig_vol

        recent_orders = (await s.execute(
            select(db.ServiceOrder).order_by(db.ServiceOrder.created.desc()).limit(6)
        )).scalars().all()

    lines = []
    for o in recent_orders:
        lines.append(f"▫️ <b>#{o.order_id}</b> ({o.tpl_key}) | {esc(o.service_name[:18])} | <code>${o.price_user_usd:.2f}</code> | <b>{o.status}</b>")

    text = (
        f"📊 <b>إحصائيات خدمات ومبيعات المنصة المركزية</b>\n{ui.LINE}\n" +
        ui.rows([
            ("إجمالي الطلبات المنفذة", f"{total_orders:,} طلب"),
            ("إجمالي حجم المبيعات", f"${total_vol:,.2f}"),
            ("🚀 زيادة التفاعل (SMM)", f"{smm_cnt} طلب (${smm_vol:,.2f})"),
            ("⭐ نجوم وتلغرام بريميوم", f"{tg_cnt} طلب (${tg_vol:,.2f})"),
            ("📱 أرقام التفعيل (SMS)", f"{sms_cnt} طلب (${sms_vol:,.2f})"),
            ("🎮 ألعاب وخدمات رقمية", f"{dig_cnt} طلب (${dig_vol:,.2f})"),
        ]) +
        ("\n\n<b>آخر الطلبات في المنصة:</b>\n" + "\n".join(lines) if lines else "\n\n<i>لا توجد طلبات منفذة بعد.</i>")
    )
    rows = [
        [B("🚀 طلبات التفاعل", "m:adm:ord_tpl:smm"), B("⭐ طلبات النجوم", "m:adm:ord_tpl:tgstars")],
        [B("📱 طلبات الأرقام", "m:adm:ord_tpl:sms"), B("🎮 طلبات الألعاب", "m:adm:ord_tpl:digital")],
        [B("⬅️ لوحة الإدارة", "m:adm:home")],
    ]
    await m.show(text, kb(rows))


# ───────────────────────── الأزرار ─────────────────────────
async def admin_cb(m: mk.M, a: list[str]) -> None:  # noqa: C901
    act = a[0] if a else "home"
    arg = a[1] if len(a) > 1 else ""
    arg2 = a[2] if len(a) > 2 else ""
    fid = m.fid
    p = await platform.get(fid)
    cancel = kb([[B("❌ إلغاء", "m:adm:home")]])
    m.clear_state()
    b = None
    if act in ("bc", "tk", "lk", "lkd", "lkr", "lkgo", "ul", "ulgo", "bm", "bmp", "bmc", "bmgo", "wn", "pr", "prt", "vf", "sp", "nt", "to", "togo",
               "rs", "bt", "bd", "bdk", "bx", "bxk"):
        b = await mk.get_bot(m, int(arg), admin=True) if arg.isdigit() else None
        if b is None:
            await m.show("البوت غير موجود.", kb([[B("⬅️ البوتات", "m:adm:b:0")]]))
            return
    back_bot = kb([[B("❌ إلغاء", f"m:adm:bc:{b.id}")]]) if b is not None else None

    if act == "home":
        await admin_home(m)

    elif act == "svc_stats":
        await scr_services_stats(m)

    elif act == "ord_tpl":
        tpl_key = arg
        async with db.Session() as s:
            orders = (await s.execute(
                select(db.ServiceOrder).where(db.ServiceOrder.tpl_key == tpl_key).order_by(db.ServiceOrder.created.desc()).limit(15)
            )).scalars().all()
        lines = []
        for o in orders:
            lines.append(f"▫️ <b>#{o.order_id}</b> | <code>${o.price_user_usd:.2f}</code> | <b>{o.status}</b>\n   {esc(o.service_name[:24])} (مستخدم: <code>{o.user_id}</code>)")
        text = f"📋 <b>طلبات القالب ({tpl_key})</b>\n{ui.LINE}\n\n" + ("\n".join(lines) if lines else "<i>لا توجد طلبات بعد.</i>")
        await m.show(text, kb([[B("⬅️ مبيعات المنصة", "m:adm:svc_stats")], [B("⬅️ لوحة الإدارة", "m:adm:home")]]))

    # ── المستخدمون ──
    elif act == "u":
        async with db.Session() as s:
            total = int((await s.execute(select(func.count()).select_from(db.MUser).where(db.MUser.factory_id == fid))).scalar() or 0)
            last = (await s.execute(select(db.MUser).where(db.MUser.factory_id == fid).order_by(db.MUser.created.desc()).limit(8))).scalars().all()
        rows = [[B(f"{u.name or u.user_id} · {u.created:%m-%d}"[:50], f"m:adm:uc:{u.user_id}")] for u in last]
        await m.show(f"👥 <b>مستخدمو الصانع</b> ({ui.num(total)})\n🚫 محظورون: {len(p['banned'])}\n\nآخر المنضمين:",
                     kb(rows + [[B("🔍 بحث برقم ID أو @يوزر", "m:adm:us")], BACK]))
    elif act == "us":
        m.set_state("adm_us")
        await m.show("🔍 أرسل رقم (ID) المستخدم أو معرّفه (@username).", cancel)
    elif act == "uc" and arg.isdigit():
        await admin_user(m, int(arg))
    elif act == "crd_s" and arg.isdigit():
        target_uid = int(arg)
        m.set_state("adm_crd_s", uid=target_uid)
        await m.show(
            f"💵 <b>شحن محفظة البائع</b> (<code>{target_uid}</code>)\n\n"
            "أدخل المبلغ بالدولار الأمريكي (USD) لشحنه في رصيد البائع في المنصة:\n"
            "مثال: <code>25</code> أو <code>50.5</code>\n\n/cancel للإلغاء",
            kb([[B("❌ إلغاء", f"m:adm:uc:{target_uid}")]])
        )
    elif act == "ub" and arg.isdigit():
        uid = int(arg)
        if uid == m.uid:
            await m.answer("لا يمكنك حظر نفسك.", True)
        elif uid in p["banned"]:
            p["banned"].remove(uid)
            await platform.audit(fid, m.uid, "uunban", info=str(uid))
        else:
            p["banned"].append(uid)
            await platform.audit(fid, m.uid, "uban", info=str(uid))
        await platform.save(fid)
        await admin_user(m, uid)
    elif act == "uxm" and arg.isdigit():
        m.set_state("adm_um", uid=int(arg))
        await m.show("✉️ أرسل الرسالة التي تريد إيصالها لهذا المستخدم (نص أو وسائط). تصله من بوت الصانع بعنوان «رسالة من إدارة المنصة».\n\n/cancel للإلغاء",
                     kb([[B("❌ إلغاء", f"m:adm:uc:{arg}")]]))
    elif act == "uxl" and arg.isdigit():
        m.set_state("adm_ulim", uid=int(arg))
        await m.show("🔢 أرسل الحد الأقصى لعدد بوتات هذا المستخدم.\n<code>0</code> = بلا حد · <code>-</code> = العودة إلى الحد العام.", kb([[B("❌ إلغاء", f"m:adm:uc:{arg}")]]))
    elif act == "uxc" and arg.isdigit():
        n = len(await _factory_bots(fid, db.Bot.owner_id == int(arg)))
        await m.show(f"🔒 <b>إغلاق كل بوتات هذا المستخدم ({n})؟</b>\n\nتُغلق بسبب «{REASONS[0][0]}» ويصله إشعار بكل بوت. أعضاء البوتات يرون إشعار الإغلاق عند فتحها.",
                     kb([[B("🔒 نعم، أغلقها", f"m:adm:uxck:{arg}", style="danger"), B("❌ إلغاء", f"m:adm:uc:{arg}")]]))
    elif act in ("uxck", "uxo") and arg.isdigit():
        k = 0
        for x in await _factory_bots(fid, db.Bot.owner_id == int(arg)):
            locked = platform.lock_of(await platform.adm(x.id)) is not None
            if act == "uxck" and not locked:
                await apply_lock(m, x, {"mode": "closed", "reason": REASONS[0][0], "reason_en": REASONS[0][1]}, False)
                k += 1
            elif act == "uxo" and locked:
                await apply_unlock(m, x, False)
                k += 1
        await m.answer(f"تم: {k} بوت.", True)
        await admin_user(m, int(arg))

    # ── البوتات ──
    elif act == "b":
        flt = arg2 if arg2 in dict(FILTERS) or (arg2 == "sub" and fid == 0) else m.udata.get("adm_flt", "all")
        m.udata["adm_flt"] = flt
        await _bots_page(m, int(arg) if arg.isdigit() else 0, flt)
    elif act == "bs":
        m.set_state("adm_bs")
        await m.show("🔍 أرسل واحداً من:\n• يوزر البوت (أو جزءاً منه)\n• رقم البوت\n• آيدي صانع البوت", cancel)
    elif act == "bc":
        await admin_bot(m, b.id)
    elif act == "tk":
        if fid != 0:
            await m.answer("عرض التوكن متاح لمدير المنصة الرئيسية فقط.", True)
            return
        msg = await m.send(await _sheet(m, b), kb([[B("🗑 احذف هذه الرسالة الآن", "m:adm:tkx")]]))
        if m.x.job_queue is not None:
            m.x.job_queue.run_once(_del_msg, 120, data=(msg.chat_id, msg.message_id))
        await log_act(m, "token", b)
        await m.answer("أُرسلت البيانات في رسالة تُحذف بعد دقيقتين.")
    elif act == "tkx":
        try:
            await m.q.message.delete()
        except TelegramError:
            pass
    elif act == "lk":
        mode = {"c": "closed", "t": "temp", "m": "maint"}.get(arg2)
        if mode is None:
            return await admin_bot(m, b.id)
        m.udata["adm_lk"] = {"b": b.id, "mode": mode}
        if mode == "temp":
            rows = ui.grid([B(name, f"m:adm:lkd:{b.id}:{sec}") for sec, name in DURATIONS], 3)
            await m.show(f"⏳ <b>إغلاق مؤقت</b> — @{b.username}\n\nكم مدة الإغلاق؟ يعود البوت للعمل تلقائياً عند انتهائها ويصل المالكَ إشعار.",
                         kb(rows + [[B("✍️ مدة أخرى (بالساعات)", f"m:adm:lkd:{b.id}:x")], [B("❌ إلغاء", f"m:adm:bc:{b.id}")]]))
        elif mode == "maint":
            await _lock_confirm(m, b)
        else:
            await _reasons(m, b)
    elif act == "lkd":
        if _lock_job(m, b.id) is None:
            return await admin_bot(m, b.id)
        if arg2 == "x":
            m.set_state("adm_lkd", b=b.id)
            await m.show("✍️ أرسل مدة الإغلاق بالساعات (مثلاً 12).", back_bot)
        elif arg2.isdigit():
            m.udata["adm_lk"]["sec"] = int(arg2)
            await _reasons(m, b)
    elif act == "lkr":
        job = _lock_job(m, b.id)
        if job is None:
            return await admin_bot(m, b.id)
        if arg2 == "x":
            m.set_state("adm_lkr", b=b.id)
            await m.show("✍️ اكتب سبب الإغلاق كما سيظهر للمالك والأعضاء.", back_bot)
            return
        if job["mode"] == "temp" and not job.get("sec"):
            return await admin_cb(m, ["lk", str(b.id), "t"])
        if arg2.isdigit() and int(arg2) < len(REASONS):
            job["reason"], job["reason_en"] = REASONS[int(arg2)]
        await _lock_confirm(m, b)
    elif act == "lkgo":
        job = _lock_job(m, b.id)
        if job is None or (job["mode"] == "temp" and not job.get("sec")):
            return await admin_bot(m, b.id)
        m.udata.pop("adm_lk", None)
        await apply_lock(m, b, job, arg2 == "1")
        await m.answer("تم التنفيذ." + (" الإشعار يُرسل للأعضاء الآن وسيصلك تقرير." if arg2 == "1" else ""), True)
        await admin_bot(m, b.id)
    elif act == "ul":
        n = len(await _members(b.id))
        await m.show(f"🔓 <b>إعادة فتح @{b.username}</b>\n\nيعود البوت للعمل فوراً ويصل المالكَ إشعار. هل تبلغ الأعضاء أيضاً ({ui.num(n)})؟",
                     kb([[B("🔓 افتح دون إبلاغ", f"m:adm:ulgo:{b.id}:0", style="success")], [B(f"🔓 افتح وأبلغ الأعضاء ({ui.num(n)})", f"m:adm:ulgo:{b.id}:1")],
                         [B("❌ إلغاء", f"m:adm:bc:{b.id}")]]))
    elif act == "ulgo":
        await apply_unlock(m, b, arg2 == "1")
        await m.answer("أُعيد فتح البوت.", True)
        await admin_bot(m, b.id)

    # ── رسالة لأعضاء بوت ──
    elif act == "bm":
        n = len(await _members(b.id))
        rows = [[B(title, f"m:adm:bmp:{b.id}:{i}")] for i, (title, _, _) in enumerate(BM_PRESETS)]
        await m.show(f"📢 <b>رسالة لأعضاء @{b.username}</b>\n\nتصل لكل أعضاء هذا البوت (<b>{ui.num(n)}</b>) عبر البوت نفسه. اختر إشعاراً جاهزاً أو اكتب رسالتك.\n\n"
                     "<i>الإشعارات الجاهزة تصل بالعربية أو الإنجليزية حسب لغة كل عضو.</i>",
                     kb(rows + [[B("✍️ رسالة مخصصة", f"m:adm:bmc:{b.id}")], [B("⬅️ بطاقة البوت", f"m:adm:bc:{b.id}")]]))
    elif act == "bmp" and arg2.isdigit() and int(arg2) < len(BM_PRESETS):
        m.udata["adm_bm"] = {"b": b.id, "preset": int(arg2)}
        n = len(await _members(b.id))
        await m.show("👁 <b>معاينة</b>\n\n" + BM_PRESETS[int(arg2)][1].replace("{u}", b.username) + f"\n\n{ui.LINE}\nتُرسل إلى <b>{ui.num(n)}</b> عضو. تأكيد؟",
                     kb([[B("✅ إرسال", f"m:adm:bmgo:{b.id}", style="success"), B("❌ إلغاء", f"m:adm:bm:{b.id}", style="danger")]]))
    elif act == "bmc":
        m.set_state("adm_bm", b=b.id)
        await m.show(f"✍️ أرسل نص الرسالة التي تريد إيصالها لأعضاء @{b.username} (يدعم التنسيق: غامق، روابط…).\n\n/cancel للإلغاء", back_bot)
    elif act == "bmgo":
        job = m.udata.pop("adm_bm", None)
        if not job or job.get("b") != b.id:
            return await admin_bot(m, b.id)
        if "preset" in job:
            _, ar, en = BM_PRESETS[job["preset"]]
            make = lambda lang: (ar if lang == "ar" else en).replace("{u}", b.username)  # noqa: E731
            info = BM_PRESETS[job["preset"]][0]
        else:
            make = lambda lang: job["html"]  # noqa: E731
            info = _plain(job["html"])[:120]
        m.x.application.create_task(notify_members(m, b, make))
        await log_act(m, "bmsg", b, info)
        await m.show("🚀 بدأ الإرسال. سيصلك تقرير عند الانتهاء.", kb([[B("⬅️ بطاقة البوت", f"m:adm:bc:{b.id}")]]))
    elif act == "wn":
        m.set_state("adm_wn", b=b.id)
        await m.show(f"⚠️ <b>تحذير مالك @{b.username}</b>\n\nاكتب نص التحذير. يصل المالكَ من بوت الصانع ويُحفظ في سجل البوت.\n\n/cancel للإلغاء", back_bot)

    # ── خصائص البوت ──
    elif act == "pr":
        adm = await platform.adm(b.id)
        adm["promo"] = {None: True, True: False, False: None}[adm.get("promo")]
        await platform.adm_save(b.id)
        await admin_bot(m, b.id)
    elif act == "prt":
        adm = await platform.adm(b.id)
        m.set_state("adm_prt", b=b.id)
        await m.show(f"✏️ <b>نص ترويج خاص بـ @{b.username}</b>\n\nأرسل النص الذي يظهر في هذا البوت بدل النص العام.\n"
                     "الرموز: <code>{maker}</code> يوزر الصانع · <code>{bot}</code> يوزر هذا البوت · <code>{name}</code> اسم العضو\n"
                     "أرسل <code>0</code> للعودة إلى النص العام." + (f"\n\nالحالي:\n{ui.LINE}\n{adm['promo_text']}" if adm.get("promo_text") else ""), back_bot)
    elif act in ("vf", "sp"):
        if act == "sp" and fid != 0:
            return await admin_bot(m, b.id)
        adm = await platform.adm(b.id)
        key = "verified" if act == "vf" else "super"
        adm[key] = not adm.get(key)
        await platform.adm_save(b.id)
        await log_act(m, "verify" if act == "vf" else "super", b, "تفعيل" if adm[key] else "إلغاء")
        if act == "vf" and adm[key]:
            await tell_owner(m, b, f"✅ وثّقت إدارة المنصة بوتك @{b.username}. تظهر علامة التوثيق في بطاقته وغرفة تحكمه.")
        await admin_bot(m, b.id)
    elif act == "nt":
        m.set_state("adm_nt", b=b.id)
        await m.show("📝 أرسل ملاحظتك عن هذا البوت. تراها أنت فقط في بطاقته.\nأرسل <code>0</code> لحذف الملاحظة.", back_bot)
    elif act in ("to", "togo") and fid != 0:
        await m.answer("نقل الملكية متاح لمدير المنصة الرئيسية فقط.", True)
    elif act == "to":
        m.set_state("adm_to", b=b.id)
        await m.show(f"📤 <b>نقل ملكية @{b.username}</b>\n\nأرسل آيدي المالك الجديد. يجب أن يكون قد فتح الصانع من قبل.", back_bot)
    elif act == "togo" and arg2.isdigit():
        new = int(arg2)
        old = b.owner_id
        async with db.Session() as s:
            if await s.get(db.MUser, (b.factory_id, new)) is None or new == old:
                return await admin_bot(m, b.id)
            row = await s.get(db.Bot, b.id)
            row.owner_id = new
            await s.commit()
        m.mgr.set_owner(b.id, new)
        await log_act(m, "transfer", b, f"{old} ← {new}")
        for uid, txt in ((new, f"📥 نقلت إدارة المنصة إليك ملكية البوت @{b.username}. تجده في «بوتاتي»."),
                         (old, f"📤 نقلت إدارة المنصة ملكية البوت @{b.username} إلى مستخدم آخر.")):
            try:
                await _maker_bot(m, b).send_message(uid, txt)
            except TelegramError:
                pass
        await m.answer("تم نقل الملكية.", True)
        await admin_bot(m, b.id)
    elif act == "rs":
        ok, err = await m.mgr.restart_bot(b.id)
        await log_act(m, "restart", b)
        await m.answer("✅ أُعيد تشغيل البوت." if ok else f"⚠️ تعذّر التشغيل: {err}", True)
        await admin_bot(m, b.id)
    elif act == "bt":
        await mk.set_enabled(m, b, b.status != "active")
        await log_act(m, "stop" if b.status == "active" else "start", b)
        await admin_bot(m, b.id)
    elif act == "bd":
        await m.show(f"🗑 <b>حذف @{b.username} نهائياً؟</b>\n\nيتوقف البوت وتُحذف بياناته وأعضاؤه من المنصة. لا يمكن التراجع.\n"
                     "<i>يستطيع صاحبه تسجيله من جديد. لمنع ذلك استخدم «⛔ حظر نهائي».</i>",
                     kb([[B("🗑 نعم، احذف", f"m:adm:bdk:{b.id}", style="danger"), B("❌ إلغاء", f"m:adm:bc:{b.id}")]]))
    elif act == "bx":
        await m.show(f"⛔ <b>حظر @{b.username} نهائياً؟</b>\n\nيُحذف البوت وبياناته من المنصة، ويُمنع تسجيله هنا مرة أخرى حتى بتوكن جديد. يصل المالكَ إشعار.\n"
                     "ترفع الحظر لاحقاً من «إعدادات المنصة» ← «البوتات المحظورة».",
                     kb([[B("⛔ نعم، احظره", f"m:adm:bxk:{b.id}", style="danger"), B("❌ إلغاء", f"m:adm:bc:{b.id}")]]))
    elif act in ("bdk", "bxk"):
        await m.mgr.stop_bot(b.id)
        await mk.wipe_bot(b.id)
        if act == "bxk":
            if b.id not in p["blocked_bots"]:
                p["blocked_bots"].append(b.id)
                await platform.save(fid)
            await tell_owner(m, b, f"⛔ حذفت إدارة المنصة بوتك @{b.username} وحظرت تسجيله بسبب مخالفة الشروط والأحكام.")
        await log_act(m, "ban" if act == "bxk" else "del", b, f"owner {b.owner_id}")
        await m.answer("تم.", True)
        await _bots_page(m, 0, m.udata.get("adm_flt", "all"))

    # ── الأفضل / التصدير / السجل ──
    elif act == "top":
        bots = await _factory_bots(fid)
        users = await mk.users_by_bot([x.id for x in bots])
        top = sorted(bots, key=lambda x: -users.get(x.id, 0))[:10]
        per_owner: dict[int, list] = {}
        for x in bots:
            per_owner.setdefault(x.owner_id, []).append(x)
        makers = sorted(per_owner.items(), key=lambda kv: -sum(users.get(x.id, 0) for x in kv[1]))[:5]
        async with db.Session() as s:
            names = {u.user_id: u.name for u in (await s.execute(select(db.MUser).where(db.MUser.factory_id == fid, db.MUser.user_id.in_([k for k, _ in makers] or [0])))).scalars().all()}
        medal = lambda i: ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i + 1}."  # noqa: E731
        text = ("🏆 <b>الأفضل في المنصة</b>\n\n<b>أكبر البوتات جمهوراً</b>\n" +
                ("\n".join(f"{medal(i)} @{x.username} — 👥 {ui.num(users.get(x.id, 0))}" for i, x in enumerate(top)) or "لا توجد بوتات بعد.") +
                "\n\n<b>أكبر الصانعين جمهوراً</b>\n" +
                ("\n".join(f"{medal(i)} {esc(names.get(uid) or uid)} — 🤖 {len(bs)} · 👥 {ui.num(sum(users.get(x.id, 0) for x in bs))}" for i, (uid, bs) in enumerate(makers)) or "—"))
        rows = [[B(f"🤖 @{x.username}", f"m:adm:bc:{x.id}")] for x in top[:5]] + [[B(f"👤 {names.get(uid) or uid}"[:40], f"m:adm:uc:{uid}")] for uid, _ in makers[:3]]
        await m.show(text, kb(rows + [BACK]))
    elif act == "exp":
        bots = await _factory_bots(fid)
        users = await mk.users_by_bot([x.id for x in bots])
        async with db.Session() as s:
            owners = {u.user_id: u for u in (await s.execute(select(db.MUser).where(db.MUser.factory_id == fid))).scalars().all()}
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["bot_id", "bot_username", "bot_name", "type", "status", "admin_lock", "verified", "users", "created", "owner_id", "owner_name", "owner_username"])
        for x in bots:
            adm, o = platform.peek(x.id), owners.get(x.owner_id)
            lk = platform.lock_of(adm)
            w.writerow([x.id, x.username, x.name, templates.get(x.template).ar, x.status, lk["mode"] if lk else "", int(bool(adm.get("verified"))),
                        users.get(x.id, 0), ui.when(x.created), x.owner_id, o.name if o else "", o.username if o else ""])
        await m.bot.send_document(m.chat_id, io.BytesIO(("﻿" + buf.getvalue()).encode("utf-8")), filename="bots.csv",
                                  caption=f"📥 قائمة البوتات: {len(bots)}\nالملف لا يحتوي التوكنات؛ تُعرض من بطاقة كل بوت.")
        await m.answer()
    elif act == "web" and fid == 0:
        await mk.send_web_link(m, "admin")
    elif act in ("wb", "wbr") and fid == 0:
        from . import web
        note = ""
        if act == "wbr":
            n = await m.mgr.refresh_menus()
            note = f"\n\n✅ أُعيد ضبط زر القائمة في {n} بوت."
        tun = m.mgr.tunnel
        if not web.enabled() or m.mgr.web is None:
            state = "⚪ <b>خادم الويب متوقف</b> (WEB_PORT=0 أو المنفذ مشغول). لا مواقع ولا تطبيقات مصغّرة."
        elif web.https():
            src = "نفق تلقائي مؤقت — يتغير مع كل تشغيل" if tun is not None and tun.url == config.PUBLIC_URL else "مضبوط في .env"
            state = (f"🟢 <b>التطبيقات المصغّرة تعمل داخل تيليجرام</b>\n🔗 <code>{esc(config.PUBLIC_URL)}</code>\n({src})\n\n"
                     "كل بوت له موقع يفتح من زر القائمة بجانب خانة الكتابة ومن زر في شاشته الرئيسية، وبوت الصانع يفتح «لوحتي» بالطريقة نفسها.")
        elif web.public():
            state = (f"🟡 <b>الرابط العام http</b>\n🔗 <code>{esc(config.PUBLIC_URL)}</code>\n\n"
                     "المواقع تفتح في المتصفح فقط. تيليجرام لا يفتح صفحة داخله إلا من رابط <b>https</b>.")
        else:
            why = f"\n⚠️ النفق التلقائي: {esc(tun.error)}" if tun is not None and tun.error else ("\n⏳ النفق التلقائي يعمل وينتظر رابطه." if tun is not None else "")
            state = ("🟡 <b>بلا رابط عام</b>\nالمواقع تعمل على هذا الجهاز فقط: <code>" + esc(web.local_url()) + "</code>" + why +
                     "\n\nتيليجرام لا يفتح صفحة داخل البوت إلا من رابط https عام. الحلول:\n"
                     "• على جهازك: ضع <code>AUTO_TUNNEL=1</code> في ملف .env ليفتح المنصة نفقاً مجانياً تلقائياً.\n"
                     "• على سيرفر بنطاق: ضع <code>PUBLIC_URL=https://نطاقك</code>.")
        await m.show("🌐 <b>حالة الويب والتطبيقات المصغّرة</b>\n\n" + state + note,
                     kb([[B("🔄 أعد ضبط أزرار القوائم", "m:adm:wbr")], [B("↗ صفحة المنصة", url=config.PUBLIC_URL)] if web.public() else None, BACK]))
    elif act == "log":
        log = (await db.kv_get(fid, "sys:audit", []) or [])[::-1][:20]
        text = _fit("📜 <b>سجل الإدارة</b> — آخر الإجراءات\n\n", [
            f"<code>{ui.when(e['at'], '%m-%d %H:%M')}</code> {ACTS.get(e['act'], e['act'])}" + (f" · {e['bot']}" if e.get("bot") else "") +
            (f"\n      <i>{esc(e['info'])}</i>" if e.get("info") else "") for e in log], empty="لا توجد إجراءات مسجلة بعد.")
        await m.show(text, kb([[B("🔄 تحديث", "m:adm:log")], BACK]))

    # ── الأنواع ──
    elif act == "t":
        async with db.Session() as s:
            usage = dict((await s.execute(select(db.Bot.template, func.count()).where(db.Bot.factory_id == fid).group_by(db.Bot.template))).all())
        btns = [B(("🔴 " if t.key in p["off_tpls"] else "🟢 ") + f"{t.ar} · {usage.get(t.key, 0)}", f"m:adm:tt:{t.key}") for t in templates.load().values()]
        await m.show("🧩 <b>الأنواع المتاحة للمستخدمين</b>\n\nاضغط أي نوع لإخفائه من قائمة البناء أو إظهاره. البوتات المبنية به مسبقاً تبقى تعمل.\nالرقم = عدد البوتات المبنية بهذا النوع.",
                     kb(ui.grid(btns, 2) + [BACK]))
    elif act == "tt" and arg in templates.load():
        p["off_tpls"].remove(arg) if arg in p["off_tpls"] else p["off_tpls"].append(arg)
        await platform.save(fid)
        await admin_cb(m, ["t"])

    # ── الإذاعة العامة ──
    elif act == "bcm":
        await m.show("📣 <b>الإذاعة</b>\n\n• <b>مستخدمو الصانع:</b> كل من فتح هذا البوت. يدعم أي نوع رسالة.\n"
                     "• <b>أعضاء كل البوتات:</b> رسالة نصية تصل لكل عضو في كل بوت مبني هنا، عبر بوته. استخدمها بحذر.\n"
                     "• <b>أعضاء بوت واحد:</b> من بطاقة البوت ← «📢 رسالة لأعضائه».",
                     kb([[B("👥 مستخدمو الصانع", "m:adm:bcu")], [B("🌍 أعضاء كل البوتات", "m:adm:bca")], BACK]))
    elif act in ("bcu", "bca"):
        m.set_state("adm_bc", to=act)
        await m.show("📝 أرسل الرسالة الآن." + (" (نص فقط)" if act == "bca" else " (نص أو وسائط)") + "\n\n/cancel للإلغاء", cancel)
    elif act == "bcgo":
        job = m.udata.pop("adm_bc", None)
        if not job:
            return await admin_home(m)
        m.x.application.create_task(_admin_broadcast(m, job))
        await platform.audit(fid, m.uid, "bcast", info="مستخدمو الصانع" if job["to"] == "bcu" else "أعضاء كل البوتات")
        await m.show("🚀 بدأ الإرسال. سيصلك تقرير عند الانتهاء.", kb([BACK]))

    # ── اشتراك الصانع ──
    elif act == "fs":
        lines = "\n".join(f"• {esc(x['title'])}" for x in p["fs"]) or "لا توجد قنوات."
        rows = [[B(f"🗑 {x['title']}"[:40], f"m:adm:fsd:{i}")] for i, x in enumerate(p["fs"])]
        await m.show("🔐 <b>اشتراك إجباري للصانع</b>\n\nلا يستطيع أحد استخدام الصانع قبل الاشتراك في هذه القنوات. (بوتات المستخدمين لها اشتراكها الخاص من غرف تحكمها.)\n\n" + lines,
                     kb(rows + [[B("➕ إضافة قناة", "m:adm:fsa")], BACK]))
    elif act == "fsa":
        m.set_state("adm_fs")
        await m.show("➕ اجعل بوت الصانع مشرفاً في القناة، ثم أرسل معرّفها مثل <code>@mychannel</code>.", cancel)
    elif act == "fsd" and arg.isdigit():
        if int(arg) < len(p["fs"]):
            p["fs"].pop(int(arg))
            await platform.save(fid)
        await admin_cb(m, ["fs"])

    # ── رسالة الترويج ──
    elif act == "pm":
        await _promo_menu(m)
    elif act in ("pmt", "sf", "pmw", "pmi", "pme", "pmb"):
        cfg = p["promo"]
        if act in ("pmt", "sf"):
            cfg["on"] = not cfg["on"]
        elif act == "pmw":
            order = ["both", "start", "idle"]
            cfg["when"] = order[(order.index(cfg["when"]) + 1) % 3]
        elif act == "pmi":
            cfg["idle"] = IDLES[(IDLES.index(cfg["idle"]) + 1) % len(IDLES)] if cfg["idle"] in IDLES else 120
        elif act == "pme":
            vals = [v for v, _ in EVERY]
            cfg["every"] = vals[(vals.index(cfg["every"]) + 1) % len(vals)] if cfg["every"] in vals else 86400
        else:
            cfg["btn"] = not cfg["btn"]
        await platform.save(fid)
        await _promo_menu(m)
    elif act == "pmx":
        m.set_state("adm_pmx")
        await m.show("✏️ <b>نص رسالة الترويج</b>\n\nأرسل النص الجديد (يدعم التنسيق).\n\nالرموز التي تُستبدل تلقائياً:\n"
                     "<code>{maker}</code> يوزر الصانع\n<code>{bot}</code> يوزر البوت الذي تظهر فيه\n<code>{name}</code> اسم العضو\n\n"
                     "مثال:\n<code>مرحباً {name} 👋\n🤖 عجبك البوت؟ اصنع بوتك الخاص مجاناً!\n{maker}</code>\n\nأرسل <code>0</code> للعودة إلى النص الافتراضي.",
                     kb([[B("❌ إلغاء", "m:adm:pm")]]))
    elif act == "pmv":
        text, markup = child.promo_render(p["promo"], "ar", maker=m.bot.username, bot="YourBot", name=m.user.first_name, owner_id=m.uid)
        await m.answer()
        await m.send("👁 هكذا تظهر للعضو:")
        await m.send(text, markup)
    elif act == "pml":
        bots = await _factory_bots(fid)
        over = [x for x in bots if platform.peek(x.id).get("promo") is not None]
        rows = [[B(("🟢 " if platform.peek(x.id)["promo"] else "🔴 ") + f"@{x.username}", f"m:adm:bc:{x.id}")] for x in over[:20]]
        await m.show("📋 <b>اختيار البوتات</b>\n\nالوضع العام يسري على كل بوت لم تحدد له شيئاً. لتحديد بوت بعينه: افتح بطاقته واضغط زر «📢 الترويج» للتبديل بين:\n"
                     "• <b>تلقائي</b> — يتبع الوضع العام\n• <b>🟢</b> — تظهر فيه دائماً\n• <b>🔴</b> — لا تظهر فيه أبداً\n\n"
                     "<i>لتظهر الرسالة في بوتات محددة فقط: أوقف الوضع العام ثم فعّلها 🟢 للبوتات التي تريدها.</i>\n\n"
                     + (f"البوتات المحددة الآن ({len(over)}):" if over else "لم تحدد أي بوت بعد."),
                     kb(rows + [[B("🤖 اختر من قائمة البوتات", "m:adm:b:0:all")],
                                [B("♻️ إلغاء كل التحديدات", "m:adm:pmr")] if over else None, [B("⬅️ رسالة الترويج", "m:adm:pm")]]))
    elif act == "pmr":
        for x in await _factory_bots(fid):
            adm = await platform.adm(x.id)
            if adm.get("promo") is not None:
                adm["promo"] = None
                await platform.adm_save(x.id)
        await admin_cb(m, ["pml"])

    # ── إعدادات المنصة ──
    elif act == "s":
        lim = platform.max_bots(p)
        nt = p["notify"]
        onoff = lambda v: "🟢" if v else "⚪"  # noqa: E731
        await m.show("⚙️ <b>إعدادات المنصة</b>\n\n" + ui.rows([
            ("حد البوتات لكل مستخدم", lim or "بلا حد"), ("وضع صيانة الصانع", "🟢 مفعّل" if p["maintenance"] else "⚪ متوقف"),
            ("إشعاري بكل مستخدم جديد", onoff(nt["user"])), ("إشعاري بكل بوت جديد", onoff(nt["bot"])),
            ("التقرير اليومي (9 صباحاً)", onoff(nt["daily"])), ("بوتات محظورة نهائياً", len(p["blocked_bots"]))]) +
            "\n\n<i>وضع صيانة الصانع يوقف بوت الصانع نفسه عن المستخدمين؛ البوتات المصنوعة تبقى تعمل. لإيقاف بوت بعينه افتح بطاقته.</i>",
            kb([[B("🔢 حد البوتات", "m:adm:sl"), B("🛠 " + ("إيقاف الصيانة" if p["maintenance"] else "تفعيل الصيانة"), "m:adm:sm")],
                [B(f"{onoff(nt['user'])} إشعار المستخدم الجديد", "m:adm:sn:user")], [B(f"{onoff(nt['bot'])} إشعار البوت الجديد", "m:adm:sn:bot")],
                [B(f"{onoff(nt['daily'])} التقرير اليومي", "m:adm:sn:daily")],
                [B(f"⛔ البوتات المحظورة ({len(p['blocked_bots'])})", "m:adm:bl")], BACK]))
    elif act == "sm":
        p["maintenance"] = not p["maintenance"]
        await platform.save(fid)
        await admin_cb(m, ["s"])
    elif act == "sn" and arg in ("user", "bot", "daily"):
        p["notify"][arg] = not p["notify"].get(arg, True)
        await platform.save(fid)
        await admin_cb(m, ["s"])
    elif act == "sl":
        m.set_state("adm_max")
        await m.show("🔢 أرسل الحد الأقصى لعدد البوتات لكل مستخدم (0 = بلا حد).", cancel)
    elif act == "bl":
        rows = [[B(f"♻️ ارفع الحظر عن {i}", f"m:adm:blx:{i}")] for i in p["blocked_bots"][-20:]]
        await m.show("⛔ <b>البوتات المحظورة نهائياً</b>\n\nلا يمكن تسجيل هذه البوتات في المنصة. الرقم هو رقم البوت (الجزء الأول من توكنه).\n\n" +
                     ("\n".join(f"• <code>{i}</code>" for i in p["blocked_bots"][-20:]) or "لا توجد بوتات محظورة."),
                     kb(rows + [[B("⬅️ إعدادات المنصة", "m:adm:s")]]))
    elif act == "blx" and arg.isdigit():
        if int(arg) in p["blocked_bots"]:
            p["blocked_bots"].remove(int(arg))
            await platform.save(fid)
            await platform.audit(fid, m.uid, "unban", info=arg)
        await admin_cb(m, ["bl"])

    # ── البلاغات والأخطاء ──
    elif act == "rep":
        async with db.Session() as s:
            reps = (await s.execute(select(db.Report).where(db.Report.factory_id == fid).order_by(db.Report.id.desc()).limit(8))).scalars().all()
        icon = {"bug": "🐞", "abuse": "🚨", "appeal": "📨"}
        text = _fit("🐞 <b>آخر البلاغات</b>\n🐞 مشكلة · 🚨 إساءة · 📨 طلب مراجعة إغلاق\n\n", [
            f"{icon.get(r.kind, '•')} <code>{r.user_id}</code> · {ui.when(r.created, '%m-%d %H:%M')}\n{esc(r.text[:300])}" for r in reps], "\n\n", "لا توجد بلاغات.")
        rows, seen = [], set()
        for r in reps:
            bid = _report_bot(r.text)
            if bid and bid not in seen:
                seen.add(bid)
                rows.append([B(f"🤖 {r.text.split(' ', 1)[0]}"[:40], f"m:adm:bc:{bid}")])
        await m.show(text, kb(rows[:6] + [BACK]))
    elif act == "err":
        recent = list(errors.RECENT)[:8] if fid == 0 else []      # سجل الأخطاء يخص السيرفر كله: لمدير المنصة الرئيسية فقط
        text = _fit("🧯 <b>آخر الأخطاء التقنية</b>\n\n", [f"<b>{e['at']}</b> · {esc(e['where'])}\n<code>{esc(e['err'])}</code>" for e in recent], "\n\n",
                    "لا توجد أخطاء مسجلة منذ آخر تشغيل. ✅", 3600) + "\n\n<i>السجل الكامل في الملف data/errors.log</i>"
        await m.show(text, kb([[B("🔄 تحديث", "m:adm:err")], BACK]))
    else:
        await admin_home(m)


# ───────────────────────── الإدخال النصي ─────────────────────────
async def admin_input(m: mk.M, st: dict, text: str) -> None:  # noqa: C901
    fid, k = m.fid, st["k"]
    p = await platform.get(fid)
    b = await mk.get_bot(m, st["b"], admin=True) if "b" in st else None
    if "b" in st and b is None:
        m.clear_state()
        return
    to_card = kb([[B("⬅️ بطاقة البوت", f"m:adm:bc:{b.id}")]]) if b is not None else None

    if k == "adm_us":
        m.clear_state()
        uid = None
        if text.lstrip("-").isdigit():
            uid = int(text)
        else:
            async with db.Session() as s:
                row = (await s.execute(select(db.MUser).where(db.MUser.factory_id == fid, func.lower(db.MUser.username) == text.lstrip("@").lower()))).scalars().first()
            uid = row.user_id if row else None
        if uid is None:
            await m.send("لم أجد مستخدماً بهذا المعرّف.", kb([[B("⬅️ المستخدمون", "m:adm:u")]]))
        else:
            await admin_user(m, uid)
    elif k == "adm_bs":
        m.clear_state()
        q = text.lstrip("@").lower()
        cond = (db.Bot.id == int(q)) | (db.Bot.owner_id == int(q)) if q.isdigit() else func.lower(db.Bot.username).contains(q)
        async with db.Session() as s:
            bots = list((await s.execute(select(db.Bot).where(cond, *([] if fid == 0 else [db.Bot.factory_id == fid])).order_by(db.Bot.created.desc()).limit(12))).scalars().all())
        if len(bots) == 1:
            return await admin_bot(m, bots[0].id)
        rows = [[B(f"{mk.status_icon(x)} @{x.username}", f"m:adm:bc:{x.id}")] for x in bots]
        await m.send(f"🔍 نتائج «{esc(text)}»: {len(bots)}", kb(rows + [[B("⬅️ البوتات", "m:adm:b:0")]]))
    elif k == "adm_fs":
        ref = text if text.startswith("@") or text.lstrip("-").isdigit() else "@" + text.rsplit("/", 1)[-1]
        try:
            chat = await m.bot.get_chat(int(ref) if ref.lstrip("-").isdigit() else ref)
            me = await m.bot.get_chat_member(chat.id, m.bot.id)
            assert me.status in ("administrator", "creator")
        except Exception:  # noqa: BLE001
            await m.send("⚠️ لم أستطع الوصول. تأكد أن بوت الصانع مشرف في القناة ثم أعد الإرسال.")
            return
        url = f"https://t.me/{chat.username}" if chat.username else (chat.invite_link or "")
        if not url:
            try:
                url = (await m.bot.create_chat_invite_link(chat.id)).invite_link
            except TelegramError:
                url = ""
        p["fs"].append({"chat_id": chat.id, "title": chat.title or str(ref), "url": url})
        await platform.save(fid)
        m.clear_state()
        await m.send("✅ أضيفت القناة.", kb([[B("⬅️ اشتراك الصانع", "m:adm:fs")]]))
    elif k == "adm_max":
        if not text.isdigit():
            await m.send("أرسل رقماً.")
            return
        p["max_bots"] = int(text)
        await platform.save(fid)
        m.clear_state()
        await m.send("✅ تم الحفظ.", kb([[B("⬅️ إعدادات المنصة", "m:adm:s")]]))
    elif k == "adm_ulim":
        if text != "-" and not text.isdigit():
            await m.send("أرسل رقماً، أو <code>-</code> للحد العام.")
            return
        if text == "-":
            p["limits"].pop(str(st["uid"]), None)
        else:
            p["limits"][str(st["uid"])] = int(text)
        await platform.save(fid)
        m.clear_state()
        await admin_user(m, st["uid"])
    elif k == "adm_um":
        m.clear_state()
        back = kb([[B("⬅️ المستخدم", f"m:adm:uc:{st['uid']}")]])
        try:
            await m.bot.send_message(st["uid"], "✉️ <b>رسالة من إدارة المنصة</b>", parse_mode=ParseMode.HTML)
            await m.bot.copy_message(st["uid"], m.chat_id, m.msg.message_id)
            await m.send("✅ وصلت رسالتك.", back)
        except TelegramError:
            await m.send("⚠️ تعذّر الإرسال: المستخدم حظر بوت الصانع أو لم يفتحه.", back)
    elif k == "adm_bc":
        if st["to"] == "bca" and not m.msg.text:
            await m.send("⚠️ هذا النوع من الإذاعة يدعم النص فقط. أرسل نصاً.")
            return
        m.clear_state()
        m.udata["adm_bc"] = {"to": st["to"], "chat": m.chat_id, "mid": m.msg.message_id, "html": ui.html_of(m.msg) or esc(text)}
        await m.send("☝️ هل تؤكد إرسال هذه الرسالة؟", kb([[B("✅ إرسال", "m:adm:bcgo", style="success"), B("❌ إلغاء", "m:adm:bcm", style="danger")]]))
    elif k == "adm_lkd":
        try:
            hours = float(text.replace(",", "."))
            assert 0 < hours <= 24 * 365
        except (ValueError, AssertionError):
            await m.send("أرسل عدد الساعات رقماً، مثل 12.")
            return
        job = _lock_job(m, b.id)
        m.clear_state()
        if job is None:
            return await admin_bot(m, b.id)
        job["sec"] = max(60, int(hours * 3600))
        await _reasons(m, b)
    elif k == "adm_lkr":
        job = _lock_job(m, b.id)
        m.clear_state()
        if job is None:
            return await admin_bot(m, b.id)
        job["reason"] = job["reason_en"] = text[:200]
        await _lock_confirm(m, b)
    elif k == "adm_bm":
        if not m.msg.text:
            await m.send("⚠️ الرسالة لأعضاء بوت آخر تدعم النص فقط. أرسل نصاً.")
            return
        m.clear_state()
        m.udata["adm_bm"] = {"b": b.id, "html": m.msg.text_html}
        n = len(await _members(b.id))
        await m.send(f"☝️ تُرسل هذه الرسالة إلى <b>{ui.num(n)}</b> عضو في @{b.username}. تأكيد؟",
                     kb([[B("✅ إرسال", f"m:adm:bmgo:{b.id}", style="success"), B("❌ إلغاء", f"m:adm:bm:{b.id}", style="danger")]]))
    elif k == "adm_wn":
        m.clear_state()
        adm = await platform.adm(b.id)
        adm["warns"] = (adm.get("warns") or [])[-19:] + [{"at": int(time.time()), "text": text[:500]}]
        await platform.adm_save(b.id)
        ok = await tell_owner(m, b, f"⚠️ <b>تحذير من إدارة المنصة</b> بخصوص بوتك @{b.username}\n\n{esc(text[:1500])}\n\n"
                                    f"هذا التحذير رقم {len(adm['warns'])}. تكرار المخالفة قد يؤدي إلى إغلاق البوت.", _card_btn(m, b))
        await log_act(m, "warn", b, text[:120])
        await m.send("✅ وصل التحذير للمالك." if ok else "⚠️ حُفظ التحذير، لكن تعذّر إيصاله: المالك حظر بوت الصانع.", to_card)
    elif k == "adm_prt":
        html = "" if text == "0" else ui.html_of(m.msg)
        if len(html) > 1000:
            await m.send("⚠️ النص طويل. اختصره إلى أقل من 1000 حرف وأرسله من جديد.")
            return
        m.clear_state()
        adm = await platform.adm(b.id)
        adm["promo_text"] = html
        await platform.adm_save(b.id)
        await m.send("✅ حُفظ النص الخاص بهذا البوت." if adm["promo_text"] else "✅ عاد هذا البوت إلى النص العام.", to_card)
    elif k == "adm_nt":
        m.clear_state()
        adm = await platform.adm(b.id)
        adm["note"] = "" if text == "0" else text[:500]
        await platform.adm_save(b.id)
        await admin_bot(m, b.id)
    elif k == "adm_to":
        if not text.isdigit():
            await m.send("أرسل الآيدي رقماً.")
            return
        async with db.Session() as s:
            new = await s.get(db.MUser, (b.factory_id, int(text)))
        if new is None:
            await m.send("⚠️ هذا المستخدم لم يفتح الصانع بعد. اطلب منه إرسال /start للصانع ثم أعد المحاولة.")
            return
        m.clear_state()
        if new.user_id == b.owner_id:
            await m.send("هو المالك الحالي.", to_card)
            return
        await m.send(f"📤 نقل @{b.username} إلى <b>{esc(new.name)}</b> (<code>{new.user_id}</code>)؟\n\nيفقد المالك الحالي الوصول إليه فوراً.",
                     kb([[B("✅ انقل", f"m:adm:togo:{b.id}:{new.user_id}", style="danger"), B("❌ إلغاء", f"m:adm:bc:{b.id}")]]))
    elif k == "adm_pmx":
        html = "" if text == "0" else ui.html_of(m.msg)
        if len(html) > 1000:
            await m.send("⚠️ النص طويل. اختصره إلى أقل من 1000 حرف وأرسله من جديد.")
            return
        m.clear_state()
        p["promo"]["text"] = html
        await platform.save(fid)
        await platform.audit(fid, m.uid, "promo", info="تعديل النص")
        await m.send("✅ حُفظ نص الترويج.", kb([[B("👁 معاينة", "m:adm:pmv"), B("⬅️ رسالة الترويج", "m:adm:pm")]]))
    elif k == "adm_crd_s":
        target_uid = st["uid"]
        try:
            amt = float(text.replace(",", ".").strip())
            assert amt > 0
        except (ValueError, AssertionError):
            await m.send("⚠️ يرجى إدخال مبلغ رقمي صحيح أكبر من 0 (مثال: 20 أو 15.5).")
            return
        m.clear_state()
        ok, tx, new_bal = await ledger.credit_seller(
            target_uid,
            amt,
            "admin_manual",
            description=f"Manual credit by Platform Admin {m.uid}",
        )
        try:
            await m.bot.send_message(
                target_uid,
                f"🎉 <b>تم شحن رصيدك كبائع!</b>\n\n"
                f"💵 المبلغ: <code>+${amt:.2f}</code>\n"
                f"💳 رصيدك الإجمالي الآن: <code>${new_bal:.2f}</code>\n"
                f"الإشعار من إدارة منصة الصانع.",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass
        await m.send(
            f"✅ تم شحن رصيد البائع بنجاح!\n\n"
            f"👤 البائع: <code>{target_uid}</code>\n"
            f"💵 المبلغ المضاف: <code>+${amt:.2f}</code>\n"
            f"💳 الرصيد الجديد: <code>${new_bal:.2f}</code>",
            kb([[B("⬅️ بطاقة المستخدم", f"m:adm:uc:{target_uid}")]])
        )
    else:
        m.clear_state()
        await admin_home(m)


async def _admin_broadcast(m: mk.M, job: dict) -> None:
    ok = fail = 0
    if job["to"] == "bcu":
        async with db.Session() as s:
            ids = list((await s.execute(select(db.MUser.user_id).where(db.MUser.factory_id == m.fid))).scalars().all())
        for uid in ids:
            try:
                await m.bot.copy_message(uid, job["chat"], job["mid"])
                ok += 1
            except TelegramError:
                fail += 1
            await asyncio.sleep(0.05)
    else:
        for b in await _factory_bots(m.fid, db.Bot.status == "active"):
            app = m.mgr.apps.get(b.id)
            if app is None:
                continue
            for uid in await child.audience(b.id, "pv"):
                try:
                    await app.bot.send_message(uid, job["html"], parse_mode=ParseMode.HTML)
                    ok += 1
                except TelegramError:
                    fail += 1
                await asyncio.sleep(0.05)
    try:
        await m.bot.send_message(m.uid, f"✅ انتهت الإذاعة.\n📬 وصلت: {ok}\n⚠️ لم تصل: {fail}")
    except TelegramError:
        pass
