"""محفظة البائع في الصانع: الرصيد الرئيسي (bot_id=0) الذي تُخصم منه تكلفة المنصة مع كل بيعة في متاجره.

- عرض الرصيد وكشف الحساب.
- الشحن بنجوم تيليجرام (آلي فوري) أو بتحويل يدوي مع إيصال تراجعه الإدارة.
- حد أدنى للشحن (MIN_TOPUP_USD، افتراضياً 10$) لضمان الاستخدام التجاري.
- تنبيه تلقائي حين ينخفض الرصيد تحت حد يختاره البائع.
- شاشات الإدارة: طرق التحويل، ومراجعة إيصالات البائعين.
"""
from __future__ import annotations

import asyncio
import logging
import math
import os
import time
import uuid

from sqlalchemy import select
from telegram import LabeledPrice, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import ApplicationHandlerStop, ContextTypes

from . import db, ui
from .modules import ledger, payments
from .ui import B, esc, kb

log = logging.getLogger("forge.wallet")

MIN_TOPUP_USD = float(os.environ.get("MIN_TOPUP_USD", "10") or 10)
PACKS_USD = (10, 20, 50, 100)
DEFAULT_ALERT_USD = 5.0
_METHODS_KEY = "sys:seller_pay_methods"


def stars_for(usd: float) -> int:
    return int(math.ceil(usd / payments.STAR_RATE_USD))


def money(v: float) -> str:
    return f"${v:,.2f}"


# ───────────────────────── شاشات البائع ─────────────────────────
async def home(m) -> None:
    m.clear_state()
    T = m.t
    bal = await ledger.get_seller_balance_usd(m.uid)
    alert = float(await db.kv_get(0, f"wal:alert:{m.uid}", DEFAULT_ALERT_USD) or 0)
    txs = await ledger.get_seller_transactions(m.uid, limit=5)
    lines = []
    for x in txs:
        sign = "＋" if x.direction == "credit" else "－"
        lines.append(f"{sign} <code>{money(float(x.amount_usd))}</code> · {esc(_kind_label(x.kind, m.lang))} · {ui.when(x.created, '%m-%d %H:%M')}")
    warn = ""
    if bal < max(alert, 0.01):
        warn = "\n⚠️ " + T("رصيدك منخفض — متاجرك ستتوقف عن البيع حين لا يكفي الرصيد تكلفة الطلب.",
                          "Low balance — your stores stop selling when it can't cover an order's cost.") + "\n"
    text = (ui.head(T("💰 رصيدي في الصانع", "💰 My maker balance")) +
            T(f"الرصيد المتاح: <b>{money(bal)}</b>\n", f"Available: <b>{money(bal)}</b>\n") + warn + "\n" +
            T("ℹ️ مع كل بيعة في متاجرك يُخصم من هذا الرصيد <b>سعر المنصة</b> للمنتج، ويبقى لك ربحك كاملاً في متجرك.\n",
              "ℹ️ Each sale in your stores deducts the product's <b>platform price</b> from this balance; your margin stays yours.\n") +
            T(f"🔔 التنبيه عند انخفاض الرصيد تحت: <b>{money(alert)}</b>\n", f"🔔 Low-balance alert below: <b>{money(alert)}</b>\n") +
            ("\n<b>" + T("آخر الحركات", "Recent activity") + "</b>\n" + "\n".join(lines) if lines else ""))
    await m.show(text, kb([
        [B(T("⭐ شحن بالنجوم (فوري)", "⭐ Top up with Stars (instant)"), "m:wals", style="success")],
        [B(T("💳 تحويل يدوي", "💳 Manual transfer"), "m:walm"), B(T("📜 كشف الحساب", "📜 Statement"), "m:walx")],
        [B(T("🔔 حد التنبيه", "🔔 Alert threshold"), "m:walal")],
        [m.home_btn()],
    ]))


def _kind_label(kind: str, lang: str) -> str:
    ar = lang == "ar"
    names = {
        "platform_cost": ("تكلفة طلب", "Order cost"),
        "order_refund_cost": ("استرجاع تكلفة", "Cost refund"),
        "deposit_stars": ("شحن نجوم", "Stars top-up"),
        "deposit_manual": ("شحن يدوي", "Manual top-up"),
        "admin_manual": ("شحن من الإدارة", "Admin credit"),
        "bonus_first_deposit": ("مكافأة أول شحن", "First top-up bonus"),
    }
    a, e = names.get(kind, (kind, kind))
    return a if ar else e


async def statement(m) -> None:
    T = m.t
    txs = await ledger.get_seller_transactions(m.uid, limit=25)
    if not txs:
        body = T("لا توجد حركات بعد.", "No activity yet.")
    else:
        body = "\n".join(
            f"{'＋' if x.direction == 'credit' else '－'} <code>{money(float(x.amount_usd))}</code> → <code>{money(float(x.balance_after_usd))}</code>"
            f" · {esc(_kind_label(x.kind, m.lang))}" + (f" · <code>{esc(x.ref_id[:18])}</code>" if x.ref_id else "") +
            f"\n   <i>{ui.when(x.created)}</i>" for x in txs)
    await m.show(ui.head(T("📜 كشف الحساب (آخر 25 حركة)", "📜 Statement (last 25)")) + body,
                 kb([[B(T("⬅️ رصيدي", "⬅️ My balance"), "m:wal")]]))


async def stars_menu(m) -> None:
    T = m.t
    rows = [[B(f"⭐ {stars_for(u):,} → {money(u)}", f"m:walsb:{u}")] for u in PACKS_USD]
    rows.append([B(T("⬅️ رصيدي", "⬅️ My balance"), "m:wal")])
    await m.show(ui.head(T("⭐ الشحن بنجوم تيليجرام", "⭐ Top up with Telegram Stars")) +
                 T(f"اختر الباقة، ادفع الفاتورة، ويُضاف الرصيد فوراً وتلقائياً.\nالحد الأدنى للشحن: <b>{money(MIN_TOPUP_USD)}</b>",
                   f"Pick a pack, pay the invoice, and the balance is added instantly.\nMinimum top-up: <b>{money(MIN_TOPUP_USD)}</b>"),
                 kb(rows))


async def send_invoice(m, usd: float) -> None:
    T = m.t
    if usd < MIN_TOPUP_USD or usd not in PACKS_USD:
        return await m.answer(T("باقة غير صالحة", "Invalid pack"), True)
    stars = stars_for(usd)
    await m.answer()
    await m.bot.send_invoice(
        chat_id=m.uid,
        title=T(f"شحن رصيد {money(usd)}", f"Top up {money(usd)}")[:32],
        description=T(f"شحن رصيدك الرئيسي في الصانع بقيمة {money(usd)}", f"Top up your maker balance by {money(usd)}")[:255],
        payload=f"sdep:{m.uid}:{stars}:{uuid.uuid4().hex[:8]}",
        currency="XTR",
        prices=[LabeledPrice(f"{stars} Stars", stars)],
    )


def _parse_payload(payload: str):
    try:
        tag, uid, stars, _n = str(payload).split(":")
        return (int(uid), int(stars)) if tag == "sdep" else None
    except (ValueError, AttributeError):
        return None


async def on_precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.pre_checkout_query
    if q is None:
        return
    p = _parse_payload(q.invoice_payload)
    ok = bool(p and p[0] == q.from_user.id and p[1] == q.total_amount and q.currency == "XTR"
              and q.total_amount * payments.STAR_RATE_USD >= MIN_TOPUP_USD - 0.01)
    try:
        await q.answer(ok=ok, error_message=None if ok else "الفاتورة غير صالحة، أنشئ فاتورة جديدة من «رصيدي».")
    except TelegramError:
        log.warning("maker pre_checkout answer failed", exc_info=True)


async def on_paid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """الشحن الآلي للرصيد الرئيسي بعد تأكيد تيليجرام للدفع (مرة واحدة لكل عملية دفع)."""
    msg = update.effective_message
    sp = msg.successful_payment if msg else None
    if sp is None or update.effective_user is None:
        return
    uid = update.effective_user.id
    p = _parse_payload(sp.invoice_payload)
    if not p or p[0] != uid or p[1] != sp.total_amount or sp.currency != "XTR":
        await msg.reply_text("⚠️ تعذّر تسجيل الدفع تلقائياً. تواصل مع الإدارة مع رقم العملية:\n"
                             f"<code>{esc(sp.telegram_payment_charge_id)}</code>", parse_mode=ParseMode.HTML)
        raise ApplicationHandlerStop
    usd = round(sp.total_amount * payments.STAR_RATE_USD, 4)
    ok, _tx, bal = await ledger.credit_seller(uid, usd, "deposit_stars", ref_id=sp.telegram_payment_charge_id[:64],
                                              description=f"شحن نجوم ({sp.total_amount} ⭐)",
                                              tx_id=f"sstars_{sp.telegram_payment_charge_id}"[:64])
    bonus_txt = ""
    if ok:
        got, _amt, bmsg = await ledger.apply_first_deposit_bonus(uid, usd)
        if got:
            bonus_txt = "\n🎁 " + bmsg
            bal = await ledger.get_seller_balance_usd(uid)
    await msg.reply_text(f"✅ تم شحن رصيدك بـ <b>{money(usd)}</b>.{bonus_txt}\n💰 رصيدك الآن: <b>{money(bal)}</b>",
                         parse_mode=ParseMode.HTML, reply_markup=kb([[B("💰 رصيدي", "m:wal")]]))
    raise ApplicationHandlerStop


async def manual_menu(m) -> None:
    T = m.t
    methods = await db.kv_get(0, _METHODS_KEY, []) or []
    if not methods:
        return await m.show(ui.head(T("💳 التحويل اليدوي", "💳 Manual transfer")) +
                            T("لا توجد طرق تحويل يدوي متاحة حالياً. استخدم الشحن بالنجوم أو تواصل مع الإدارة.",
                              "No manual methods available yet. Use Stars or contact the platform."),
                            kb([[B(T("⬅️ رصيدي", "⬅️ My balance"), "m:wal")]]))
    rows = [[B(f"💳 {x.get('name', '—')}"[:40], f"m:walmp:{i}")] for i, x in enumerate(methods)]
    rows.append([B(T("⬅️ رصيدي", "⬅️ My balance"), "m:wal")])
    await m.show(ui.head(T("💳 التحويل اليدوي", "💳 Manual transfer")) +
                 T(f"اختر طريقة التحويل. بعد التحويل أرسل الإيصال وتراجعه الإدارة.\nالحد الأدنى: <b>{money(MIN_TOPUP_USD)}</b>",
                   f"Pick a method. After paying, send the receipt for review.\nMinimum: <b>{money(MIN_TOPUP_USD)}</b>"), kb(rows))


async def manual_pick(m, idx: int) -> None:
    T = m.t
    methods = await db.kv_get(0, _METHODS_KEY, []) or []
    if not (0 <= idx < len(methods)):
        return await manual_menu(m)
    x = methods[idx]
    m.set_state("wal_amt", idx=idx)
    await m.show(ui.head(f"💳 {esc(x.get('name', ''))}") +
                 (f"🏦 <code>{esc(x.get('account', ''))}</code>\n" if x.get("account") else "") +
                 (f"📌 {esc(x.get('instructions', ''))}\n" if x.get("instructions") else "") +
                 "\n" + T(f"✏️ أرسل المبلغ الذي حوّلته <b>بالدولار</b> (لا يقل عن {MIN_TOPUP_USD:g}).",
                          f"✏️ Send the amount you transferred <b>in USD</b> (min {MIN_TOPUP_USD:g})."),
                 kb([[B(T("❌ إلغاء", "❌ Cancel"), "m:wal")]]))


async def on_input(m, st: dict, text: str) -> None:
    """مدخلات نصية/صور لحالات المحفظة (wal_*)."""
    T, k = m.t, st["k"]
    if k == "wal_amt":
        try:
            amt = round(float(text.replace(",", ".").replace("$", "").strip()), 2)
        except ValueError:
            amt = 0.0
        if amt < MIN_TOPUP_USD or amt > 100000:
            return await m.send(T(f"⚠️ أرسل مبلغاً صحيحاً لا يقل عن {MIN_TOPUP_USD:g}$.", f"⚠️ Send a valid amount (min ${MIN_TOPUP_USD:g})."))
        m.set_state("wal_proof", idx=st["idx"], amt=amt)
        return await m.send(T("📸 أرسل الآن لقطة شاشة لإيصال التحويل (أو رقم العملية نصاً).",
                              "📸 Now send a screenshot of the receipt (or the transaction reference)."),
                            kb([[B(T("❌ إلغاء", "❌ Cancel"), "m:wal")]]))
    if k == "wal_proof":
        methods = await db.kv_get(0, _METHODS_KEY, []) or []
        meth = methods[st["idx"]] if 0 <= st["idx"] < len(methods) else {"name": "تحويل"}
        photo = m.msg.photo[-1].file_id if m.msg is not None and m.msg.photo else ""
        if not photo and not text:
            return await m.send(T("أرسل صورة الإيصال أو رقم العملية.", "Send the receipt photo or reference."))
        m.clear_state()
        rc = await payments.create_receipt(0, m.uid, m.user.full_name if m.user else "", (m.user.username or "") if m.user else "",
                                           meth.get("name", "تحويل"), st["amt"], "USD", st["amt"],
                                           proof_file_id=photo, proof_text=text[:1000])
        await m.send(T("✅ استلمنا إيصالك وهو قيد المراجعة. سيصلك إشعار فور شحن رصيدك.",
                       "✅ Receipt received and under review. You'll be notified once credited."), kb([[B(T("💰 رصيدي", "💰 My balance"), "m:wal")]]))
        await _notify_admins_receipt(m, rc, photo)
        return
    if k == "wal_alert":
        try:
            v = max(0.0, min(float(text.replace(",", ".").replace("$", "").strip()), 10000.0))
        except ValueError:
            return await m.send(T("أرسل رقماً، مثال: 5", "Send a number, e.g. 5"))
        m.clear_state()
        await db.kv_set(0, f"wal:alert:{m.uid}", v)
        return await home(m)
    # ── مدخلات الإدارة ──
    if not m.is_admin:
        m.clear_state()
        return
    if k == "wal_adm_amt":
        try:
            amt = round(float(text.replace(",", ".").replace("$", "").strip()), 2)
        except ValueError:
            return await m.send("أرسل مبلغاً رقمياً بالدولار.")
        m.clear_state()
        await _approve(m, st["rid"], amt)
        return
    if k == "wal_adm_cat":
        from .modules import catalog as _cat
        upd, errs = _cat.parse_lines(text)
        for iid, e in upd:
            await _cat.set_entry(st["tpl"], iid, **e)
        await m.send(f"✅ حُدّث {len(upd)} منتج." + (f"\n⚠️ أسطر لم تُفهم: {len(errs)}" if errs else ""))
        return await admin_catalog(m, st["tpl"])
    if k == "wal_adm_margin":
        from .modules.markup import MarkupManager
        t = text.strip().replace(",", ".")
        typ = "fixed" if t.endswith("$") else "percent"
        try:
            val = float(t.rstrip("%$").strip())
            assert 0 <= val <= (1000 if typ == "percent" else 10000)
        except (ValueError, AssertionError):
            return await m.send("أرسل رقماً صحيحاً مثل 15% أو 0.5$")
        m.clear_state()
        await MarkupManager.set_margin_rule(st["key"], typ, val, admin_id=m.uid, note="from maker admin")
        return await admin_finance(m)
    if k == "wal_pm_add":
        parts = [p.strip() for p in text.split("|")]
        if not parts or not parts[0]:
            return await m.send("الصيغة: <code>الاسم | رقم الحساب أو العنوان | التعليمات</code>", parse_mode=ParseMode.HTML)
        methods = await db.kv_get(0, _METHODS_KEY, []) or []
        methods.append({"name": parts[0][:40], "account": (parts[1] if len(parts) > 1 else "")[:200],
                        "instructions": (parts[2] if len(parts) > 2 else "")[:500]})
        await db.kv_set(0, _METHODS_KEY, methods)
        m.clear_state()
        await admin_methods(m)


async def _notify_admins_receipt(m, rc, photo: str) -> None:
    from . import config
    text = (f"🧾 <b>إيصال شحن بائع</b>\n👤 {esc(m.user.full_name if m.user else '')} (<code>{m.uid}</code>)"
            f"\n💳 {esc(rc.method)} · <b>{money(rc.amount_usd)}</b>\n🆔 <code>{rc.receipt_id}</code>"
            + (f"\n📝 {esc(rc.proof_text[:300])}" if rc.proof_text else ""))
    markup = kb([[B("✅ قبول بالمبلغ", f"m:walok:{rc.receipt_id}", style="success"), B("✏️ مبلغ آخر", f"m:walam:{rc.receipt_id}")],
                 [B("❌ رفض", f"m:walno:{rc.receipt_id}", style="danger")]])
    for aid in {config.ADMIN_ID, *config.ADMIN_IDS} - {0}:
        try:
            if photo:
                await m.bot.send_photo(aid, photo, caption=text[:1000], parse_mode=ParseMode.HTML, reply_markup=markup)
            else:
                await m.bot.send_message(aid, text, parse_mode=ParseMode.HTML, reply_markup=markup)
        except TelegramError:
            pass


async def _approve(m, rid: str, amount: float | None = None) -> None:
    async with db.Session() as s:
        rc = (await s.execute(select(db.PaymentReceipt).where(db.PaymentReceipt.receipt_id == rid))).scalars().first()
    if rc is None or rc.bot_id != 0:
        return await m.send("الإيصال غير موجود.")
    if amount is not None and amount < MIN_TOPUP_USD:
        return await m.send(f"⚠️ الحد الأدنى للشحن {money(MIN_TOPUP_USD)}.")
    ok, msg, bal = await payments.approve_receipt(rid, f"by {m.uid}", bot_id=0, amount_usd=amount)
    if not ok:
        return await m.send(f"⚠️ {esc(msg)}")
    credited = amount if amount is not None else float(rc.amount_usd)
    got, _b, bmsg = await ledger.apply_first_deposit_bonus(rc.user_id, credited)
    bal = await ledger.get_seller_balance_usd(rc.user_id)
    await m.send(f"✅ شُحن رصيد البائع <code>{rc.user_id}</code> بـ <b>{money(credited)}</b>. رصيده الآن {money(bal)}.")
    try:
        await m.bot.send_message(rc.user_id, f"✅ تمت الموافقة على إيصالك وشُحن رصيدك بـ <b>{money(credited)}</b>."
                                             + (f"\n🎁 {bmsg}" if got else "") + f"\n💰 رصيدك الآن: <b>{money(bal)}</b>",
                                 parse_mode=ParseMode.HTML, reply_markup=kb([[B("💰 رصيدي", "m:wal")]]))
    except TelegramError:
        pass


# ───────────────────────── شاشات الإدارة ─────────────────────────
async def admin_methods(m) -> None:
    methods = await db.kv_get(0, _METHODS_KEY, []) or []
    body = "\n".join(f"• <b>{esc(x.get('name', ''))}</b> — <code>{esc(x.get('account', ''))}</code>" for x in methods) or "لا توجد طرق بعد."
    rows = [[B(f"🗑 {x.get('name', '')}"[:40], f"m:walpd:{i}")] for i, x in enumerate(methods)]
    rows += [[B("➕ إضافة طريقة", "m:walpa", style="success")], [B("🧾 إيصالات البائعين المعلقة", "m:walrc")], [B("⬅️ لوحة الإدارة", "m:adm:home")]]
    await m.show(ui.head("💳 طرق شحن رصيد البائعين") + body, kb(rows))


async def admin_receipts(m) -> None:
    async with db.Session() as s:
        rows = (await s.execute(select(db.PaymentReceipt).where(db.PaymentReceipt.bot_id == 0, db.PaymentReceipt.status == "pending")
                                .order_by(db.PaymentReceipt.id.desc()).limit(20))).scalars().all()
    if not rows:
        return await m.show(ui.head("🧾 إيصالات البائعين") + "لا توجد إيصالات معلقة ✅", kb([[B("⬅️ طرق الشحن", "m:walpm")]]))
    btns = [[B(f"{money(r.amount_usd)} · {r.user_name or r.user_id}"[:40], f"m:walrv:{r.receipt_id}")] for r in rows]
    btns.append([B("⬅️ طرق الشحن", "m:walpm")])
    await m.show(ui.head(f"🧾 إيصالات البائعين المعلقة ({len(rows)})"), kb(btns))


async def admin_receipt_view(m, rid: str) -> None:
    async with db.Session() as s:
        rc = (await s.execute(select(db.PaymentReceipt).where(db.PaymentReceipt.receipt_id == rid))).scalars().first()
    if rc is None or rc.bot_id != 0:
        return await admin_receipts(m)
    text = (f"🧾 <b>{esc(rc.receipt_id)}</b>\n👤 {esc(rc.user_name)} (<code>{rc.user_id}</code>)\n💳 {esc(rc.method)} · <b>{money(rc.amount_usd)}</b>"
            f"\n📌 الحالة: {rc.status}" + (f"\n📝 {esc(rc.proof_text[:500])}" if rc.proof_text else ""))
    markup = kb([[B("✅ قبول", f"m:walok:{rid}", style="success"), B("✏️ مبلغ آخر", f"m:walam:{rid}")],
                 [B("❌ رفض", f"m:walno:{rid}", style="danger")], [B("⬅️ الإيصالات", "m:walrc")]])
    if rc.proof_file_id:
        try:
            await m.bot.send_photo(m.uid, rc.proof_file_id, caption=text[:1000], parse_mode=ParseMode.HTML, reply_markup=markup)
            return await m.answer()
        except TelegramError:
            pass
    await m.show(text, markup)


async def admin_finance(m) -> None:
    """أرقام المنصة المالية: المبيعات، إيراد المنصة، أرصدة البائعين، والهوامش."""
    import datetime as dt
    from sqlalchemy import func
    from .modules.markup import MarkupManager
    now = db.now()
    out = []
    async with db.Session() as s:
        for label, days in (("اليوم", 1), ("7 أيام", 7), ("30 يوماً", 30)):
            since = now - dt.timedelta(days=days)
            q = select(func.count(db.ServiceOrder.id), func.coalesce(func.sum(db.ServiceOrder.price_user_usd), 0),
                       func.coalesce(func.sum(db.ServiceOrder.cost_platform_usd), 0),
                       func.coalesce(func.sum(db.ServiceOrder.cost_provider_usd), 0)).where(
                db.ServiceOrder.created >= since, db.ServiceOrder.status.notin_(("refunded", "canceled", "failed")))
            n, sales, plat, prov = (await s.execute(q)).one()
            out.append(f"<b>{label}</b>: {n} طلب · مبيعات {money(float(sales))} · إيراد المنصة {money(float(plat))}"
                       + (f" · تكلفة المزودين {money(float(prov))}" if float(prov) else ""))
        liab = float((await s.execute(select(func.coalesce(func.sum(db.UserBalance.balance_usd), 0)).where(db.UserBalance.bot_id == 0))).scalar() or 0)
        deps = float((await s.execute(select(func.coalesce(func.sum(db.LedgerEntry.amount_usd), 0)).where(
            db.LedgerEntry.bot_id == 0, db.LedgerEntry.direction == "credit",
            db.LedgerEntry.kind.in_(("deposit_stars", "deposit_manual")), db.LedgerEntry.created >= now - dt.timedelta(days=30)))).scalar() or 0)
    rules = await MarkupManager.get_all_rules()
    g = rules.get("global", {"type": "percent", "val": 10.0})
    tpl_lines = [f"• {k[4:]}: {v.get('val')}{'%' if v.get('type', 'percent') == 'percent' else '$'}" for k, v in rules.items() if k.startswith("tpl:")]
    text = (ui.head("📈 الأرباح والهوامش") + "\n".join(out) +
            f"\n\n💰 شحنات البائعين (30 يوماً): <b>{money(deps)}</b>\n🏦 مجموع أرصدة البائعين الحالية: <b>{money(liab)}</b>"
            f"\n\n<b>هامش المنصة العام:</b> {g.get('val')}{'%' if g.get('type', 'percent') == 'percent' else '$'}"
            + ("\n" + "\n".join(tpl_lines) if tpl_lines else "")
            + "\n\n<i>سعر المنصة على البائع = تكلفة المنتج + هامش المنصة.</i>")
    await m.show(text, kb([[B("✏️ الهامش العام", "m:walmg:global")],
                           [B("🎮 رقمي", "m:walmg:tpl:digital"), B("📈 تفاعل", "m:walmg:tpl:smm")],
                           [B("📱 أرقام", "m:walmg:tpl:sms"), B("⭐ نجوم", "m:walmg:tpl:tgstars")],
                           [B("🧩 كتالوج المنصة وربط المزودين", "m:walcat:smm")],
                           [B("⬅️ لوحة الإدارة", "m:adm:home")]]))


async def admin_catalog(m, tpl: str) -> None:
    """ربط منتجات المنصة بالمزود: رقم الخدمة لدى المزود + التكلفة الحقيقية + إخفاء/إظهار."""
    from .modules import catalog as _cat
    from .modules.providers import digital as pd, smm as psm, sms as pss, tgstars as pts
    cmap = await _cat.get_map(tpl)
    if tpl == "smm":
        items = [(x["id"], x.get("name_ar", x["id"]), float(x["rate_per_1k"]), "/1k") for x in psm.MOCK_CATALOG]
    elif tpl == "tgstars":
        items = [(x["id"], x.get("name_ar", x["id"]), float(x["rate_usd"]), "") for x in pts.TGSTARS_CATALOG]
    elif tpl == "digital":
        items = [(x["id"], x.get("name_ar", x["id"]), float(x["rate_usd"]), "") for x in pd.DIGITAL_CATALOG]
    else:
        items = [(f"{c}_{a}", f"{ci.get('flag', '')} {ai.get('name_en', a)}", pss.SMSManager.base_cost(c, a), "")
                 for c, ci in pss.SMS_COUNTRIES.items() for a, ai in pss.SMS_APPS.items()][:40]
    lines = []
    for iid, name, default, unit in items[:40]:
        e = cmap.get(iid) or {}
        cost = _cat.effective_cost(cmap, iid, default)
        lines.append(("🚫 " if e.get("off") else "") + f"<code>{iid}</code> · {esc(str(name))[:28]} · ${cost:g}{unit}"
                     + (f" · 🔗{esc(str(e['ps']))}" if e.get("ps") else ""))
    text = (ui.head(f"🧩 كتالوج المنصة: {tpl}") + "\n".join(lines) +
            "\n\n✏️ للتعديل أرسل سطراً لكل منتج:\n<code>المعرّف | رقم الخدمة لدى المزود | التكلفة الحقيقية</code>"
            "\nللإخفاء: <code>المعرّف | off</code> وللإظهار: <code>المعرّف | on</code>")
    m.set_state("wal_adm_cat", tpl=tpl)
    await m.show(text[:4000], kb([[B("🎮 رقمي", "m:walcat:digital"), B("📈 تفاعل", "m:walcat:smm")],
                                  [B("📱 أرقام", "m:walcat:sms"), B("⭐ نجوم", "m:walcat:tgstars")],
                                  [B("⬅️ الأرباح والهوامش", "m:walfin")]]))


# ───────────────────────── الموجّه ─────────────────────────
async def cb(m, act: str, arg: str) -> None:
    T = m.t
    if act == "wal":
        return await home(m)
    if act == "walx":
        return await statement(m)
    if act == "wals":
        return await stars_menu(m)
    if act == "walsb":
        try:
            return await send_invoice(m, float(arg))
        except ValueError:
            return await m.answer()
    if act == "walm":
        return await manual_menu(m)
    if act == "walmp":
        return await manual_pick(m, int(arg) if arg.isdigit() else -1)
    if act == "walal":
        m.set_state("wal_alert")
        return await m.show(T("🔔 أرسل الحد الذي تريد التنبيه عنده بالدولار (0 لإيقاف التنبيه).",
                              "🔔 Send the alert threshold in USD (0 to disable)."), kb([[B(T("❌ إلغاء", "❌ Cancel"), "m:wal")]]))
    # ── الإدارة ──
    if not m.is_admin:
        return await m.answer()
    if act == "walpm":
        return await admin_methods(m)
    if act == "walfin":
        return await admin_finance(m)
    if act == "walcat":
        return await admin_catalog(m, arg if arg in ("smm", "tgstars", "digital", "sms") else "smm")
    if act == "walmg":
        key = ":".join(arg_full) if (arg_full := (m.q.data or "").split(":")[2:]) else "global"
        m.set_state("wal_adm_margin", key=key)
        return await m.show(f"✏️ أرسل هامش المنصة لـ <b>{esc(key)}</b>:\n• نسبة: <code>15%</code>\n• مبلغ ثابت: <code>0.5$</code>",
                            kb([[B("❌ إلغاء", "m:walfin")]]))
    if act == "walpa":
        m.set_state("wal_pm_add")
        return await m.show("➕ أرسل الطريقة بالصيغة:\n<code>الاسم | رقم الحساب أو العنوان | التعليمات</code>\n\nمثال:\n<code>زين كاش | 07700000000 | حوّل ثم أرسل لقطة الإيصال</code>",
                            kb([[B("❌ إلغاء", "m:walpm")]]))
    if act == "walpd":
        methods = await db.kv_get(0, _METHODS_KEY, []) or []
        if arg.isdigit() and int(arg) < len(methods):
            methods.pop(int(arg))
            await db.kv_set(0, _METHODS_KEY, methods)
        return await admin_methods(m)
    if act == "walrc":
        return await admin_receipts(m)
    if act == "walrv":
        return await admin_receipt_view(m, arg)
    if act == "walok":
        await m.answer()
        return await _approve(m, arg)
    if act == "walam":
        m.set_state("wal_adm_amt", rid=arg)
        await m.answer()
        return await m.send("✏️ أرسل المبلغ الذي وصل فعلاً بالدولار:")
    if act == "walno":
        async with db.Session() as s:
            rc = (await s.execute(select(db.PaymentReceipt).where(db.PaymentReceipt.receipt_id == arg))).scalars().first()
        ok, msg = await payments.reject_receipt(arg, f"by {m.uid}", bot_id=0)
        await m.answer(msg, True)
        if ok and rc is not None:
            try:
                await m.bot.send_message(rc.user_id, "❌ تم رفض إيصال الشحن. تأكد من التحويل وأرسل الإيصال من جديد، أو تواصل مع الإدارة.",
                                         reply_markup=kb([[B("💰 رصيدي", "m:wal")]]))
            except TelegramError:
                pass


# ───────────────────────── تنبيه انخفاض الرصيد ─────────────────────────
_ALERT_LAST: dict[int, float] = {}


async def low_balance_hook(seller_id: int, balance: float) -> None:
    """يُستدعى بعد كل بيعة: ينبّه البائع (مرة كل 12 ساعة كحد أقصى) إن نزل رصيده تحت الحد الذي اختاره."""
    try:
        thr = float(await db.kv_get(0, f"wal:alert:{seller_id}", DEFAULT_ALERT_USD) or 0)
        if thr <= 0 or balance >= thr or time.time() - _ALERT_LAST.get(seller_id, 0) < 43200:
            return
        _ALERT_LAST[seller_id] = time.time()
        from .runtime import manager
        if manager.maker is None:
            return
        await manager.maker.bot.send_message(
            seller_id,
            f"🔔 <b>رصيدك في الصانع منخفض: {money(balance)}</b>\nاشحن رصيدك حتى لا تتوقف متاجرك عن البيع.",
            parse_mode=ParseMode.HTML, reply_markup=kb([[B("⭐ اشحن الآن", "m:wals", style="success")], [B("💰 رصيدي", "m:wal")]]))
    except Exception:  # noqa: BLE001
        log.debug("low balance alert failed", exc_info=True)


ledger.LOW_BALANCE_HOOKS.append(low_balance_hook)
