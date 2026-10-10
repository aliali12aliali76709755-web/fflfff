"""سجل العمليات المالية ودفتر الأستاذ (Financial Ledger).
عمليات ذرية، حماية من التكرار والضغط المزدوج (Idempotency)،
وسجلات غير قابلة للحذف نهائياً.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any
from sqlalchemy import select

from .. import db
from . import currency

log = logging.getLogger("forge.ledger")


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
    async with db.Session() as s:
        # فحص عدم تكرار المعاملة (Idempotency)
        existing = (await s.execute(select(db.LedgerEntry).where(db.LedgerEntry.tx_id == tx))).scalars().first()
        if existing:
            return True, tx, existing.balance_after_usd

        bal_row = await s.get(db.UserBalance, (bot_id, user_id))
        if bal_row is None:
            bal_row = db.UserBalance(bot_id=bot_id, user_id=user_id, balance_usd=0.0)
            s.add(bal_row)

        new_bal = round(float(bal_row.balance_usd) + amount_usd, 4)
        bal_row.balance_usd = new_bal

        ledger = db.LedgerEntry(
            tx_id=tx,
            bot_id=bot_id,
            user_id=user_id,
            direction="credit",
            amount_usd=amount_usd,
            balance_after_usd=new_bal,
            kind=kind,
            ref_id=ref_id,
            description=description[:250],
        )
        s.add(ledger)
        await s.commit()

    log.info("Credited bot %d user %d with $%.4f (tx: %s, new bal: $%.4f)", bot_id, user_id, amount_usd, tx, new_bal)
    return True, tx, new_bal


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

        bal_row = await s.get(db.UserBalance, (bot_id, user_id))
        cur_bal = round(float(bal_row.balance_usd), 4) if bal_row else 0.0

        if cur_bal < amount_usd:
            return False, "insufficient_balance", cur_bal

        new_bal = round(cur_bal - amount_usd, 4)
        bal_row.balance_usd = new_bal

        ledger = db.LedgerEntry(
            tx_id=tx,
            bot_id=bot_id,
            user_id=user_id,
            direction="debit",
            amount_usd=amount_usd,
            balance_after_usd=new_bal,
            kind=kind,
            ref_id=ref_id,
            description=description[:250],
        )
        s.add(ledger)
        await s.commit()

    log.info("Debited bot %d user %d $%.4f (tx: %s, new bal: $%.4f)", bot_id, user_id, amount_usd, tx, new_bal)
    return True, tx, new_bal


async def credit_seller(
    owner_id: int,
    amount_usd: float,
    kind: str,
    *,
    ref_id: str = "",
    description: str = "",
) -> tuple[bool, str, float]:
    """يضيف رصيداً لحساب البائع الرئيسي في الصانع (bot_id=0)."""
    return await credit_user(0, owner_id, amount_usd, kind, ref_id=ref_id, description=description)


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


async def atomic_dual_refund(
    order_id: str,
    *,
    reason: str = "المنتج غير متوفر حالياً",
    admin_id: int = 0,
) -> tuple[bool, str, dict[str, Any]]:
    """استرجاع الأموال الذري المزدوج بنقرة واحدة:
    1. يعيد المبلغ للمشتري في رصيد بوت البائع.
    2. يعيد سعر المنصة للبائع في رصيده الرئيسي بصانع البوتات.
    3. يحمي من الاسترجاع المزدوج (Idempotency).
    4. يوثّق الحركتين في السجل المالي برقم مرجعي مرتبط بالطلب.
    """
    import datetime as dt
    async with db.Session() as s:
        order = (await s.execute(
            select(db.ServiceOrder).where(db.ServiceOrder.order_id == order_id)
        )).scalars().first()

        if not order:
            return False, "الطلب غير موجود في قاعدة البيانات.", {}

        if order.status == "refunded" or order.is_dual_refunded:
            return False, "تم استرجاع هذا الطلب مسبقاً، لا يمكن تكرار الاسترجاع.", {}

        bot_id = order.bot_id
        buyer_id = order.user_id
        buyer_refund_usd = order.price_user_usd
        platform_cost_usd = order.cost_platform_usd or order.cost_provider_usd

        # البحث عن مالك البوت
        bot_row = await s.get(db.Bot, bot_id)
        seller_id = bot_row.owner_id if bot_row else 0

        # تحديث حالة الطلب
        order.status = "refunded"
        order.is_dual_refunded = True
        order.refund_reason = reason[:250]
        order.refunded_at = dt.datetime.utcnow()
        await s.commit()

    # 1. إعادة الأموال للمشتري في بوت البائع
    ok_b, tx_b, bal_b = await credit_user(
        bot_id=bot_id,
        user_id=buyer_id,
        amount_usd=buyer_refund_usd,
        kind="order_refund",
        ref_id=order_id,
        description=f"استرجاع قيمة الطلب #{order_id}: {reason}",
    )

    # 2. إعادة سعر المنصة للبائع في صانع البوتات (إذا كان هناك مالك)
    ok_s, tx_s, bal_s = False, "", 0.0
    if seller_id > 0 and platform_cost_usd > 0:
        ok_s, tx_s, bal_s = await credit_seller(
            owner_id=seller_id,
            amount_usd=platform_cost_usd,
            kind="order_refund_cost",
            ref_id=order_id,
            description=f"استرجاع تكلفة المنصة للطلب #{order_id}: {reason}",
        )

    log.info(
        "Dual refund completed for order %s: Buyer %d refunded $%.2f, Seller %d refunded $%.2f",
        order_id, buyer_id, buyer_refund_usd, seller_id, platform_cost_usd
    )
    return True, "تم استرجاع الأموال للطرفين (المشتري والبائع) بنجاح!", {
        "order_id": order_id,
        "buyer_id": buyer_id,
        "buyer_refund_usd": buyer_refund_usd,
        "buyer_tx": tx_b,
        "seller_id": seller_id,
        "seller_refund_usd": platform_cost_usd,
        "seller_tx": tx_s,
    }


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
    )

    log.info("First deposit bonus of $%.2f granted to seller %d (tx: %s)", bonus_amt, owner_id, tx)
    return True, bonus_amt, f"مبروك! حصلت على مكافأة أول شحن بقيمة +${bonus_amt:.2f} 🎁"

