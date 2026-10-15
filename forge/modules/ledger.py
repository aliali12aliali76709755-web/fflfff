"""سجل العمليات المالية ودفتر الأستاذ (Financial Ledger).
عمليات ذرية، حماية من التكرار والضغط المزدوج (Idempotency)،
وسجلات غير قابلة للحذف نهائياً.
"""
from __future__ import annotations

import asyncio
import functools
import logging
import uuid
from typing import Any
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .. import db
from . import currency

log = logging.getLogger("forge.ledger")

# SQLite لا يدعم قفل الصفوف (FOR UPDATE)، فطلبات متزامنة تقرأ نفس الرصيد ثم تكتب فوقه (صرف مزدوج).
# الحل: قفل داخل العملية لكل عمليات الكتابة المالية عند SQLite. على PostgreSQL يكفي FOR UPDATE ولا يُستخدم هذا القفل.
_SQLITE_LOCKS: dict[int, asyncio.Lock] = {}

# دوال تُستدعى بعد كل بيعة برصيد البائع الجديد (لتنبيه انخفاض الرصيد). تسجّلها طبقة الواجهة (wallet).
LOW_BALANCE_HOOKS: list = []


def _sqlite_lock() -> asyncio.Lock:
    loop = asyncio.get_running_loop()
    lk = _SQLITE_LOCKS.get(id(loop))
    if lk is None:
        lk = _SQLITE_LOCKS[id(loop)] = asyncio.Lock()
    return lk


def _money_write(fn):
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        if db.engine.dialect.name == "sqlite":
            async with _sqlite_lock():
                return await fn(*args, **kwargs)
        return await fn(*args, **kwargs)
    return wrapper


def new_tx_id(prefix: str = "tx") -> str:
    """يولد معرّف معاملة مالية فريد."""
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


async def get_user_balance_usd(bot_id: int, user_id: int) -> float:
    """يعيد رصيد المستخدم بالدولار بدقة عالية."""
    async with db.Session() as s:
        row = await s.get(db.UserBalance, (bot_id, user_id))
        return round(float(row.balance_usd), 4) if row is not None else 0.0


async def get_seller_balance_usd(owner_id: int) -> float:
    """يعيد رصيد البائع الرئيسي بالدولار في صانع البوتات (bot_id=0)."""
    return await get_user_balance_usd(0, owner_id)


async def get_user_balance_display(bot_id: int, user_id: int) -> str:
    """يعيد رصيد المستخدم منسقاً بعملة البوت المعتمدة."""
    usd = await get_user_balance_usd(bot_id, user_id)
    return await currency.format_price_for_bot(bot_id, usd)


async def get_seller_balance_display(owner_id: int) -> str:
    """يعيد رصيد البائع في الصانع الرئيسي منسقاً بالدولار."""
    usd = await get_seller_balance_usd(owner_id)
    return f"${usd:,.2f}"


@_money_write
async def credit_user(
    bot_id: int,
    user_id: int,
    amount_usd: float,
    kind: str,
    *,
    ref_id: str = "",
    description: str = "",
    tx_id: str | None = None,
) -> tuple[bool, str, float]:
    """يضيف رصيداً بالدولار لمحفظة المستخدم أو البائع بشكل ذري ويسجله في دفتر الأستاذ.
    يعيد (نجاح؟، معرّف_المعاملة، الرصيد_الجديد).
    """
    if amount_usd <= 0:
        return False, "invalid_amount", await get_user_balance_usd(bot_id, user_id)

    tx = tx_id or new_tx_id("cr")
    # محاولتان: الثانية لمعالجة سباق إنشاء صف الرصيد لأول مرة من طلبين متزامنين
    for attempt in range(2):
        async with db.Session() as s:
            # فحص عدم تكرار المعاملة (Idempotency) — مع قفل منطقي عبر unique(tx_id)
            existing = (await s.execute(select(db.LedgerEntry).where(db.LedgerEntry.tx_id == tx))).scalars().first()
            if existing:
                return True, tx, existing.balance_after_usd

            # قفل صف الرصيد (FOR UPDATE على PostgreSQL، لا شيء على SQLite المتسلسل)
            bal_row = await s.get(db.UserBalance, (bot_id, user_id), with_for_update=True)
            if bal_row is None:
                bal_row = db.UserBalance(bot_id=bot_id, user_id=user_id, balance_usd=0.0)
                s.add(bal_row)

            new_bal = round(float(bal_row.balance_usd) + amount_usd, 4)
            bal_row.balance_usd = new_bal

            s.add(db.LedgerEntry(
                tx_id=tx, bot_id=bot_id, user_id=user_id, direction="credit",
                amount_usd=amount_usd, balance_after_usd=new_bal, kind=kind,
                ref_id=ref_id, description=description[:250],
            ))
            try:
                await s.commit()
            except IntegrityError:
                # إمّا تكرار tx_id (طلب مكرر) أو سباق إنشاء صف الرصيد: نعيد المحاولة ونقرأ النتيجة
                await s.rollback()
                dup = (await s.execute(select(db.LedgerEntry).where(db.LedgerEntry.tx_id == tx))).scalars().first()
                if dup:
                    return True, tx, dup.balance_after_usd
                if attempt == 0:
                    continue
                raise
        log.info("Credited bot %d user %d with $%.4f (tx: %s, new bal: $%.4f)", bot_id, user_id, amount_usd, tx, new_bal)
        return True, tx, new_bal
    return False, "credit_failed", await get_user_balance_usd(bot_id, user_id)


@_money_write
async def debit_user(
    bot_id: int,
    user_id: int,
    amount_usd: float,
    kind: str,
    *,
    ref_id: str = "",
    description: str = "",
    tx_id: str | None = None,
) -> tuple[bool, str, float]:
    """يخصم رصيداً بالدولار من محفظة المستخدم بشكل ذري مع فحص كفاية الرصيد.
    يعيد (نجاح؟، كود/معرّف_المعاملة، الرصيد_الحالي_أو_الجديد).
    """
    if amount_usd <= 0:
        return False, "invalid_amount", await get_user_balance_usd(bot_id, user_id)

    tx = tx_id or new_tx_id("db")
    async with db.Session() as s:
        # فحص عدم تكرار المعاملة (Idempotency)
        existing = (await s.execute(select(db.LedgerEntry).where(db.LedgerEntry.tx_id == tx))).scalars().first()
        if existing:
            return True, tx, existing.balance_after_usd

        # قفل صف الرصيد قبل الفحص والخصم لمنع الصرف المزدوج عند الطلبات المتزامنة
        bal_row = await s.get(db.UserBalance, (bot_id, user_id), with_for_update=True)
        cur_bal = round(float(bal_row.balance_usd), 4) if bal_row else 0.0

        if bal_row is None or cur_bal < amount_usd:
            return False, "insufficient_balance", cur_bal

        new_bal = round(cur_bal - amount_usd, 4)
        bal_row.balance_usd = new_bal

        s.add(db.LedgerEntry(
            tx_id=tx, bot_id=bot_id, user_id=user_id, direction="debit",
            amount_usd=amount_usd, balance_after_usd=new_bal, kind=kind,
            ref_id=ref_id, description=description[:250],
        ))
        try:
            await s.commit()
        except IntegrityError:
            # طلب خصم مكرر بنفس tx_id: نعيد نتيجة المعاملة الأصلية بدل خصم مزدوج
            await s.rollback()
            dup = (await s.execute(select(db.LedgerEntry).where(db.LedgerEntry.tx_id == tx))).scalars().first()
            if dup:
                return True, tx, dup.balance_after_usd
            raise

    log.info("Debited bot %d user %d $%.4f (tx: %s, new bal: $%.4f)", bot_id, user_id, amount_usd, tx, new_bal)
    return True, tx, new_bal


async def credit_seller(
    owner_id: int,
    amount_usd: float,
    kind: str,
    *,
    ref_id: str = "",
    description: str = "",
    tx_id: str | None = None,
) -> tuple[bool, str, float]:
    """يضيف رصيداً لحساب البائع الرئيسي في الصانع (bot_id=0)."""
    return await credit_user(0, owner_id, amount_usd, kind, ref_id=ref_id, description=description, tx_id=tx_id)


async def debit_seller(
    owner_id: int,
    amount_usd: float,
    kind: str,
    *,
    ref_id: str = "",
    description: str = "",
) -> tuple[bool, str, float]:
    """يخصم تكلفة المنصة بالدولار من حساب البائع الرئيسي في الصانع (bot_id=0).
    إذا لم يكن رصيد البائع كافياً، تفشل العملية مباشرة دون كشف السبب للزبون.
    """
    ok, tx, bal = await debit_user(0, owner_id, amount_usd, kind, ref_id=ref_id, description=description)
    if not ok:
        log.warning("Seller %d debit failed (amount: $%.4f, balance: $%.4f)", owner_id, amount_usd, bal)
    return ok, tx, bal


async def get_user_transactions(bot_id: int, user_id: int, limit: int = 10) -> list[db.LedgerEntry]:
    """يعيد آخر سجلات مالية للمستخدم."""
    async with db.Session() as s:
        rows = (await s.execute(
            select(db.LedgerEntry)
            .where(db.LedgerEntry.bot_id == bot_id, db.LedgerEntry.user_id == user_id)
            .order_by(db.LedgerEntry.created.desc())
            .limit(limit)
        )).scalars().all()
        return list(rows)


async def get_seller_transactions(owner_id: int, limit: int = 20) -> list[db.LedgerEntry]:
    """يعيد سجل الحركات المالية للبائع في الصانع الرئيسي."""
    return await get_user_transactions(0, owner_id, limit=limit)


async def _move(s, bot_id: int, user_id: int, amount_usd: float, direction: str, kind: str,
                *, ref_id: str, description: str, tx: str) -> float | None:
    """حركة واحدة داخل جلسة قائمة (بلا commit). يعيد الرصيد الجديد، أو None إن لم يكفِ الرصيد للخصم."""
    bal_row = await s.get(db.UserBalance, (bot_id, user_id), with_for_update=True)
    if bal_row is None:
        if direction == "debit":
            return None
        bal_row = db.UserBalance(bot_id=bot_id, user_id=user_id, balance_usd=0.0)
        s.add(bal_row)
    cur = round(float(bal_row.balance_usd or 0.0), 4)
    if direction == "debit":
        if cur + 1e-9 < amount_usd:
            return None
        new_bal = round(cur - amount_usd, 4)
    else:
        new_bal = round(cur + amount_usd, 4)
    bal_row.balance_usd = new_bal
    s.add(db.LedgerEntry(
        tx_id=tx, bot_id=bot_id, user_id=user_id, direction=direction,
        amount_usd=round(amount_usd, 4), balance_after_usd=new_bal, kind=kind,
        ref_id=ref_id[:64], description=description[:250],
    ))
    return new_bal


@_money_write
async def purchase(
    *,
    bot_id: int,
    buyer_id: int,
    price_usd: float,
    seller_id: int,
    platform_cost_usd: float,
    order_id: str,
    kind: str = "order",
    description: str = "",
) -> tuple[bool, str, float]:
    """عملية الشراء الذرية الكاملة في معاملة واحدة:
    1. يخصم سعر البيع من رصيد الزبون داخل بوت البائع.
    2. يخصم سعر المنصة (تكلفة المزود + هامش المنصة) من رصيد البائع الرئيسي في الصانع (bot_id=0).
    إمّا تنجح الحركتان معاً أو لا يُخصم شيء إطلاقاً. ومعرّفات المعاملات مشتقة من رقم الطلب فلا يتكرر الخصم.
    يعيد (نجاح؟، السبب: ok | insufficient_balance | seller_insufficient | invalid_amount | duplicate، رصيد_الزبون).
    """
    if price_usd <= 0 or platform_cost_usd < 0:
        return False, "invalid_amount", await get_user_balance_usd(bot_id, buyer_id)
    tx_buy, tx_cost = f"buy_{order_id}", f"cost_{order_id}"
    async with db.Session() as s:
        dup = (await s.execute(select(db.LedgerEntry).where(db.LedgerEntry.tx_id == tx_buy))).scalars().first()
        if dup:
            return True, "duplicate", dup.balance_after_usd
        # ترتيب ثابت للأقفال (رصيد البائع في الصانع bot_id=0 أولاً) لتجنّب الجمود بين طلبين متزامنين
        seller_short, sb = False, None
        if seller_id and platform_cost_usd > 0:
            sb = await _move(s, 0, seller_id, platform_cost_usd, "debit", "platform_cost",
                             ref_id=order_id, description=f"تكلفة المنصة للطلب #{order_id}", tx=tx_cost)
            seller_short = sb is None
        bb = await _move(s, bot_id, buyer_id, price_usd, "debit", kind,
                         ref_id=order_id, description=description or f"شراء الطلب #{order_id}", tx=tx_buy)
        if bb is None or seller_short:
            await s.rollback()
            # نبلغ الزبون بنقص رصيده أولاً؛ نقص رصيد البائع لا يُكشف للزبون إلا كـ «غير متوفر مؤقتاً»
            reason = "insufficient_balance" if bb is None else "seller_insufficient"
            return False, reason, await get_user_balance_usd(bot_id, buyer_id)
        try:
            await s.commit()
        except IntegrityError:
            await s.rollback()
            dup = (await s.execute(select(db.LedgerEntry).where(db.LedgerEntry.tx_id == tx_buy))).scalars().first()
            if dup:
                return True, "duplicate", dup.balance_after_usd
            return False, "insufficient_balance", await get_user_balance_usd(bot_id, buyer_id)
    log.info("Purchase %s: buyer %d -$%.4f, seller %d -$%.4f", order_id, buyer_id, price_usd, seller_id, platform_cost_usd)
    if sb is not None and LOW_BALANCE_HOOKS:
        for hook in LOW_BALANCE_HOOKS:
            try:
                asyncio.get_running_loop().create_task(hook(seller_id, sb))
            except Exception:  # noqa: BLE001
                pass
    return True, "ok", bb


async def _net_paid(s, bot_id: int, user_id: int, order_id: str) -> float:
    """صافي ما دفعه طرف ما فعلياً لطلب معيّن = مجموع الخصومات − مجموع المسترجَع، من دفتر الأستاذ لا من بيانات الطلب."""
    rows = (await s.execute(select(db.LedgerEntry).where(
        db.LedgerEntry.bot_id == bot_id, db.LedgerEntry.user_id == user_id, db.LedgerEntry.ref_id == order_id,
    ))).scalars().all()
    paid = sum(float(r.amount_usd) for r in rows if r.direction == "debit")
    back = sum(float(r.amount_usd) for r in rows if r.direction == "credit" and r.kind in ("order_refund", "order_refund_cost", "sms_refund"))
    return round(max(paid - back, 0.0), 4)


@_money_write
async def atomic_dual_refund(
    order_id: str,
    *,
    reason: str = "المنتج غير متوفر حالياً",
    admin_id: int = 0,
) -> tuple[bool, str, dict[str, Any]]:
    """استرجاع ذري مزدوج في معاملة واحدة:
    1. يعيد للمشتري ما دفعه فعلاً (من دفتر الأستاذ).
    2. يعيد للبائع ما خُصم منه فعلاً كتكلفة منصة — لا أكثر (لا يُرد ما لم يُخصم).
    3. تحديث حالة الطلب والحركتان في نفس المعاملة: إمّا كله أو لا شيء، ولا يتكرر.
    """
    import datetime as dt
    async with db.Session() as s:
        order = (await s.execute(
            select(db.ServiceOrder).where(db.ServiceOrder.order_id == order_id).with_for_update()
        )).scalars().first()
        if not order:
            return False, "الطلب غير موجود في قاعدة البيانات.", {}
        if order.status in ("refunded", "canceled") or order.is_dual_refunded:
            return False, "تم استرجاع هذا الطلب مسبقاً، لا يمكن تكرار الاسترجاع.", {}

        bot_id, buyer_id = order.bot_id, order.user_id
        bot_row = await s.get(db.Bot, bot_id)
        seller_id = bot_row.owner_id if bot_row else 0

        buyer_refund = await _net_paid(s, bot_id, buyer_id, order_id)
        seller_refund = await _net_paid(s, 0, seller_id, order_id) if seller_id else 0.0

        if buyer_refund > 0:
            await _move(s, bot_id, buyer_id, buyer_refund, "credit", "order_refund", ref_id=order_id,
                        description=f"استرجاع قيمة الطلب #{order_id}: {reason}", tx=f"rfbuy_{order_id}")
        if seller_refund > 0:
            await _move(s, 0, seller_id, seller_refund, "credit", "order_refund_cost", ref_id=order_id,
                        description=f"استرجاع تكلفة المنصة للطلب #{order_id}: {reason}", tx=f"rfsell_{order_id}")

        order.status = "refunded"
        order.is_dual_refunded = True
        order.refund_reason = reason[:250]
        order.refunded_at = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
        try:
            await s.commit()
        except IntegrityError:
            await s.rollback()
            return False, "تم استرجاع هذا الطلب مسبقاً، لا يمكن تكرار الاسترجاع.", {}

    log.info("Dual refund %s: buyer %d +$%.4f, seller %d +$%.4f (by %s)",
             order_id, buyer_id, buyer_refund, seller_id, seller_refund, admin_id or "system")
    return True, "تم استرجاع الأموال للطرفين (المشتري والبائع) بنجاح!", {
        "order_id": order_id,
        "buyer_id": buyer_id,
        "buyer_refund_usd": buyer_refund,
        "buyer_tx": f"rfbuy_{order_id}" if buyer_refund > 0 else "",
        "seller_id": seller_id,
        "seller_refund_usd": seller_refund,
        "seller_tx": f"rfsell_{order_id}" if seller_refund > 0 else "",
    }


@_money_write
async def partial_dual_refund(order_id: str, fraction: float, *, reason: str = "تنفيذ جزئي") -> tuple[bool, float]:
    """استرجاع جزئي (تنفيذ ناقص من المزود): يُرد للمشتري والبائع نفس النسبة مما دفعاه فعلاً، مرة واحدة فقط."""
    fraction = max(0.0, min(1.0, float(fraction)))
    if fraction <= 0:
        return False, 0.0
    if fraction >= 0.999:
        ok, _m, res = await atomic_dual_refund(order_id, reason=reason)
        return ok, float(res.get("buyer_refund_usd", 0) if ok else 0)
    async with db.Session() as s:
        order = (await s.execute(select(db.ServiceOrder).where(db.ServiceOrder.order_id == order_id).with_for_update())).scalars().first()
        if not order or order.is_dual_refunded or order.status in ("refunded", "canceled"):
            return False, 0.0
        bot_row = await s.get(db.Bot, order.bot_id)
        seller_id = bot_row.owner_id if bot_row else 0
        b_amt = round(await _net_paid(s, order.bot_id, order.user_id, order_id) * fraction, 4)
        s_amt = round(await _net_paid(s, 0, seller_id, order_id) * fraction, 4) if seller_id else 0.0
        if b_amt > 0:
            await _move(s, order.bot_id, order.user_id, b_amt, "credit", "order_refund", ref_id=order_id,
                        description=f"استرجاع جزئي للطلب #{order_id}: {reason}", tx=f"rfpbuy_{order_id}")
        if s_amt > 0:
            await _move(s, 0, seller_id, s_amt, "credit", "order_refund_cost", ref_id=order_id,
                        description=f"استرجاع جزئي لتكلفة المنصة #{order_id}: {reason}", tx=f"rfpsell_{order_id}")
        order.status = "completed"
        order.is_dual_refunded = True
        order.refund_reason = reason[:250]
        try:
            await s.commit()
        except IntegrityError:
            await s.rollback()
            return False, 0.0
    return True, b_amt


async def platform_cost_for(owner_id: int, provider_cost_usd: float, *, tpl_key: str = "",
                            category_id: str = "", product_id: str = "", variant_id: str = "") -> float:
    """سعر المنصة على البائع = تكلفة المزود + هامش المنصة (حسب قواعد الهوامش في لوحة الإدارة)."""
    if provider_cost_usd <= 0:
        return 0.0
    from .markup import MarkupManager
    return await MarkupManager.calculate_platform_cost(
        provider_cost_usd, owner_id=owner_id, tpl_key=tpl_key,
        category_id=category_id, product_id=product_id, variant_id=variant_id,
    )


async def apply_first_deposit_bonus(
    owner_id: int,
    deposit_amount_usd: float,
) -> tuple[bool, float, str]:
    """يفحص ويطبّق مكافأة أول شحن للبائع في صانع البوتات:
    - تُسجل كحركة مستقلة في السجل المالي (bonus_first_deposit).
    - لا تحتسب كأرباح للمنصة.
    - تطبق مرة واحدة فقط لكل بائع.
    """
    import datetime as dt
    cfg = await db.kv_get(0, "sys:bonus_config", {
        "enabled": False,
        "type": "percent",
        "value": 10.0,
        "min_deposit": 10.0,
        "max_bonus": 50.0,
        "expires_at": None,
    }) or {}

    if not cfg.get("enabled"):
        return False, 0.0, "حملة المكافأة غير مفعلة."

    # فحص تاريخ انتهاء الحملة
    if cfg.get("expires_at"):
        try:
            exp = dt.datetime.fromisoformat(cfg["expires_at"])
            if dt.datetime.utcnow() > exp:
                return False, 0.0, "انتهت فترة حملة مكافأة أول شحن."
        except Exception:
            pass

    # فحص الحد الأدنى للشحن
    min_dep = float(cfg.get("min_deposit", 0.0))
    if deposit_amount_usd < min_dep:
        return False, 0.0, f"المبلغ أقل من الحد الأدنى للمكافأة (${min_dep:.2f})."

    # فحص هل حصل البائع على المكافأة سابقاً
    async with db.Session() as s:
        existing = (await s.execute(
            select(db.LedgerEntry).where(
                db.LedgerEntry.bot_id == 0,
                db.LedgerEntry.user_id == owner_id,
                db.LedgerEntry.kind == "bonus_first_deposit",
            )
        )).scalars().first()
        if existing:
            return False, 0.0, "حصل البائع على مكافأة أول شحن مسبقاً."

    # حساب قيمة المكافأة
    b_type = cfg.get("type", "percent")
    b_val = float(cfg.get("value", 10.0))
    max_bonus = float(cfg.get("max_bonus", 50.0))

    if b_type == "fixed":
        bonus_amt = round(min(b_val, max_bonus), 4)
    else:
        bonus_amt = round(min(deposit_amount_usd * (b_val / 100.0), max_bonus), 4)

    if bonus_amt <= 0:
        return False, 0.0, "قيمة المكافأة صفر."

    # إضافة المكافأة في السجل المالي
    ok, tx, new_bal = await credit_seller(
        owner_id=owner_id,
        amount_usd=bonus_amt,
        kind="bonus_first_deposit",
        description=f"مكافأة أول شحن ترويجية (${bonus_amt:.2f})",
        tx_id=f"bonus1_{owner_id}",   # مرة واحدة لكل بائع حتى مع شحنتين متزامنتين
    )

    log.info("First deposit bonus of $%.2f granted to seller %d (tx: %s)", bonus_amt, owner_id, tx)
    return True, bonus_amt, f"مبروك! حصلت على مكافأة أول شحن بقيمة +${bonus_amt:.2f} 🎁"

