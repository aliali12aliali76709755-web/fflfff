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
