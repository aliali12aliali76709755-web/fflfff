"""قاعدة البيانات: النماذج ودوال الوصول المشتركة."""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
from typing import Any

log = logging.getLogger("forge.db")

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Float, Integer, String, Text, delete, event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from . import config


def now() -> dt.datetime:
    return dt.datetime.utcnow()


def today() -> str:
    return now().strftime("%Y-%m-%d")


class Base(DeclarativeBase):
    pass


class MUser(Base):
    """مستخدم الصانع. factory_id = 0 للصانع الرئيسي، أو رقم البوت لصانع فرعي."""
    __tablename__ = "m_users"
    factory_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    username: Mapped[str] = mapped_column(String(64), default="")
    lang: Mapped[str] = mapped_column(String(8), default="")
    ref_by: Mapped[int] = mapped_column(BigInteger, default=0)
    created: Mapped[dt.datetime] = mapped_column(DateTime, default=now)


class Bot(Base):
    __tablename__ = "bots"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    factory_id: Mapped[int] = mapped_column(BigInteger, default=0, index=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, index=True)
    username: Mapped[str] = mapped_column(String(64), default="")
    name: Mapped[str] = mapped_column(String(128), default="")
    token: Mapped[str] = mapped_column(Text)
    template: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | disabled | error
    error: Mapped[str] = mapped_column(Text, default="")
    created: Mapped[dt.datetime] = mapped_column(DateTime, default=now)


class BUser(Base):
    """مستخدم (أو مجموعة/قناة) داخل بوت مصنوع."""
    __tablename__ = "b_users"
    bot_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    username: Mapped[str] = mapped_column(String(64), default="")
    lang: Mapped[str] = mapped_column(String(8), default="")
    premium: Mapped[bool] = mapped_column(Boolean, default=False)
    kind: Mapped[str] = mapped_column(String(12), default="private")
    joined: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    last_seen: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    msgs: Mapped[int] = mapped_column(Integer, default=0)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)  # المستخدم حظر البوت
    banned: Mapped[bool] = mapped_column(Boolean, default=False)   # المالك حظر المستخدم
    source: Mapped[str] = mapped_column(String(32), default="")


class KV(Base):
    """إعدادات وبيانات هيكلية لكل بوت (تدخل في النسخ الاحتياطية)."""
    __tablename__ = "kv"
    bot_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)


class Rec(Base):
    """سجلات ينتجها المستخدمون: طلبات، تذاكر، حجوزات، إجابات..."""
    __tablename__ = "recs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_id: Mapped[int] = mapped_column(BigInteger, index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, default=0, index=True)
    status: Mapped[str] = mapped_column(String(24), default="")
    data: Mapped[Any] = mapped_column(JSON, default=dict)
    created: Mapped[dt.datetime] = mapped_column(DateTime, default=now)


class Daily(Base):
    __tablename__ = "daily"
    bot_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    day: Mapped[str] = mapped_column(String(10), primary_key=True)
    data: Mapped[Any] = mapped_column(JSON, default=dict)


class Transfer(Base):
    __tablename__ = "transfers"
    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    bot_id: Mapped[int] = mapped_column(BigInteger)
    from_id: Mapped[int] = mapped_column(BigInteger)
    expires: Mapped[dt.datetime] = mapped_column(DateTime)
    used: Mapped[bool] = mapped_column(Boolean, default=False)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    factory_id: Mapped[int] = mapped_column(BigInteger, default=0)
    user_id: Mapped[int] = mapped_column(BigInteger)
    kind: Mapped[str] = mapped_column(String(12))
    text: Mapped[str] = mapped_column(Text)
    created: Mapped[dt.datetime] = mapped_column(DateTime, default=now)


class UserBalance(Base):
    """محفظة رصيد المستخدمين بالدولار. bot_id=0 لمالك البوت في الصانع الرئيسي."""
    __tablename__ = "user_balances"
    bot_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    balance_usd: Mapped[float] = mapped_column(Float, default=0.0)
    updated: Mapped[dt.datetime] = mapped_column(DateTime, default=now, onupdate=now)


class LedgerEntry(Base):
    """سجل الحركات المالية الذرية غير القابل للحذف."""
    __tablename__ = "ledger_entries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tx_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    bot_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    direction: Mapped[str] = mapped_column(String(10))  # credit | debit
    amount_usd: Mapped[float] = mapped_column(Float)
    balance_after_usd: Mapped[float] = mapped_column(Float)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    ref_id: Mapped[str] = mapped_column(String(64), default="")
    description: Mapped[str] = mapped_column(String(255), default="")
    created: Mapped[dt.datetime] = mapped_column(DateTime, default=now, index=True)


class PaymentReceipt(Base):
    """إيصالات الدفع والشحن (يدوي/آلي/نجوم)."""
    __tablename__ = "payment_receipts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    receipt_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    bot_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_name: Mapped[str] = mapped_column(String(128), default="")
    username: Mapped[str] = mapped_column(String(64), default="")
    method: Mapped[str] = mapped_column(String(64))
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(16))
    amount_usd: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)  # pending | approved | rejected
    proof_file_id: Mapped[str] = mapped_column(String(255), default="")
    proof_text: Mapped[str] = mapped_column(Text, default="")
    seller_note: Mapped[str] = mapped_column(String(255), default="")
    created: Mapped[dt.datetime] = mapped_column(DateTime, default=now, index=True)
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class ServiceOrder(Base):
    """طلبات الخدمات (تفاعل، أرقام، نجوم، ألعاب واشتراكات)."""
    __tablename__ = "service_orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    bot_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    tpl_key: Mapped[str] = mapped_column(String(32), index=True)
    service_id: Mapped[str] = mapped_column(String(64))
    service_name: Mapped[str] = mapped_column(String(255))
    target: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    cost_provider_usd: Mapped[float] = mapped_column(Float, default=0.0)
    cost_platform_usd: Mapped[float] = mapped_column(Float, default=0.0)
    price_user_usd: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(16), default="USD")
    price_user_currency: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    provider_name: Mapped[str] = mapped_column(String(64), default="")
    provider_order_id: Mapped[str] = mapped_column(String(128), default="")
    details: Mapped[Any] = mapped_column(JSON, default=dict)
    created: Mapped[dt.datetime] = mapped_column(DateTime, default=now, index=True)
    updated: Mapped[dt.datetime] = mapped_column(DateTime, default=now, onupdate=now)


_pool_args = {"pool_pre_ping": True}
if not config.DATABASE_URL.startswith("sqlite"):
    _pool_args.update(pool_size=4, max_overflow=2, pool_timeout=10, pool_recycle=60)

engine = create_async_engine(config.DATABASE_URL, **_pool_args)
Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

if config.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_pragmas(conn, _):  # pragma: no cover
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=15000")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()


async def init() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ───────────────────────── KV ─────────────────────────
async def kv_get(bot_id: int, key: str, default: Any = None) -> Any:
    async with Session() as s:
        row = await s.get(KV, (bot_id, key))
        return default if row is None else row.value


async def kv_set(bot_id: int, key: str, value: Any) -> None:
    for attempt in range(3):
        try:
            async with Session() as s:
                row = await s.get(KV, (bot_id, key))
                if row is None:
                    s.add(KV(bot_id=bot_id, key=key, value=value))
                else:
                    row.value = value
                await s.commit()
            break
        except Exception:
            if attempt == 2:
                raise
            await asyncio.sleep(0.04 * (attempt + 1))



async def kv_all(bot_id: int) -> dict[str, Any]:
    async with Session() as s:
        rows = (await s.execute(select(KV).where(KV.bot_id == bot_id))).scalars().all()
        return {r.key: r.value for r in rows}


async def kv_replace_all(bot_id: int, data: dict[str, Any]) -> None:
    async with Session() as s:
        await s.execute(delete(KV).where(KV.bot_id == bot_id, KV.key.notlike("sys:%")))
        for k, v in data.items():
            if not k.startswith("sys:"):
                s.add(KV(bot_id=bot_id, key=k, value=v))
        await s.commit()


# ───────────────────────── Records ─────────────────────────
async def rec_add(bot_id: int, kind: str, data: dict, user_id: int = 0, status: str = "") -> int:
    async with Session() as s:
        r = Rec(bot_id=bot_id, kind=kind, data=data, user_id=user_id, status=status)
        s.add(r)
        await s.commit()
        return r.id


async def rec_get(bot_id: int, rid: int) -> Rec | None:
    async with Session() as s:
        r = await s.get(Rec, rid)
        return r if r is not None and r.bot_id == bot_id else None


async def rec_list(bot_id: int, kind: str, user_id: int | None = None, status: str | None = None,
                   limit: int = 50, offset: int = 0, newest: bool = True) -> list[Rec]:
    q = select(Rec).where(Rec.bot_id == bot_id, Rec.kind == kind)
    if user_id is not None:
        q = q.where(Rec.user_id == user_id)
    if status is not None:
        q = q.where(Rec.status == status)
    q = q.order_by(Rec.id.desc() if newest else Rec.id.asc()).limit(limit).offset(offset)
    async with Session() as s:
        return list((await s.execute(q)).scalars().all())


async def rec_count(bot_id: int, kind: str, user_id: int | None = None, status: str | None = None) -> int:
    q = select(func.count()).select_from(Rec).where(Rec.bot_id == bot_id, Rec.kind == kind)
    if user_id is not None:
        q = q.where(Rec.user_id == user_id)
    if status is not None:
        q = q.where(Rec.status == status)
    async with Session() as s:
        return int((await s.execute(q)).scalar() or 0)


async def rec_update(bot_id: int, rid: int, data: dict | None = None, status: str | None = None) -> None:
    async with Session() as s:
        r = await s.get(Rec, rid)
        if r is None or r.bot_id != bot_id:
            return
        if data is not None:
            r.data = data
        if status is not None:
            r.status = status
        await s.commit()


async def rec_del(bot_id: int, rid: int) -> None:
    async with Session() as s:
        await s.execute(delete(Rec).where(Rec.bot_id == bot_id, Rec.id == rid))
        await s.commit()


# ───────────────────────── Counters ─────────────────────────
_BUMP_LOCK: asyncio.Lock | None = None
_BUMP_BUFFER: dict[tuple[int, str], dict[str, int]] = {}
_BUMP_TASK: asyncio.Task | None = None


def _get_bump_lock() -> asyncio.Lock:
    global _BUMP_LOCK
    if _BUMP_LOCK is None:
        _BUMP_LOCK = asyncio.Lock()
    return _BUMP_LOCK


async def _bump_flush_loop() -> None:
    while True:
        await asyncio.sleep(2.0)
        try:
            await _flush_bumps()
        except Exception as e:
            log.warning("Bump flush loop error: %s", e)


async def _flush_bumps() -> None:
    global _BUMP_BUFFER
    if not _BUMP_BUFFER:
        return
    async with _get_bump_lock():
        batch = _BUMP_BUFFER
        _BUMP_BUFFER = {}

    for (bot_id, day), inc in batch.items():
        for attempt in range(3):
            try:
                async with Session() as s:
                    row = await s.get(Daily, (bot_id, day))
                    if row is None:
                        row = Daily(bot_id=bot_id, day=day, data={})
                        s.add(row)
                    d = dict(row.data or {})
                    for k, v in inc.items():
                        d[k] = int(d.get(k, 0)) + v
                    row.data = d
                    await s.commit()
                break
            except Exception as e:
                if attempt == 2:
                    log.warning("Flush bump exhausted for bot %d: %s", bot_id, e)
                await asyncio.sleep(0.04 * (attempt + 1))


async def bump(bot_id: int, **inc: int) -> None:
    """يزيد عدادات اليوم فورياً في الذاكرة دون قفل قاعدة البيانات، وتُحفظ كل ثانيتين تلقائياً."""
    global _BUMP_TASK
    if _BUMP_TASK is None:
        try:
            loop = asyncio.get_running_loop()
            _BUMP_TASK = loop.create_task(_bump_flush_loop())
        except RuntimeError:
            pass

    day = today()
    key = (bot_id, day)
    async with _get_bump_lock():
        cur = _BUMP_BUFFER.setdefault(key, {})
        for k, v in inc.items():
            cur[k] = cur.get(k, 0) + v


async def daily(bot_ids: list[int], day: str) -> dict[str, int]:
    out: dict[str, int] = {}
    if not bot_ids:
        return out
    async with Session() as s:
        rows = (await s.execute(select(Daily).where(Daily.bot_id.in_(bot_ids), Daily.day == day))).scalars().all()
    for r in rows:
        for k, v in (r.data or {}).items():
            out[k] = out.get(k, 0) + int(v)

    # دمج العدادات اللحظية من الذاكرة لضمان دقة الأرقام في نفس اللحظة
    async with _get_bump_lock():
        for (b_id, d_day), b_inc in _BUMP_BUFFER.items():
            if b_id in bot_ids and d_day == day:
                for k, v in b_inc.items():
                    out[k] = out.get(k, 0) + int(v)

    return out
