"""قاعدة البيانات: النماذج ودوال الوصول المشتركة."""
from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Integer, String, Text, delete, event, func, select
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


engine = create_async_engine(config.DATABASE_URL, pool_pre_ping=True)
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
    async with Session() as s:
        row = await s.get(KV, (bot_id, key))
        if row is None:
            s.add(KV(bot_id=bot_id, key=key, value=value))
        else:
            row.value = value
        await s.commit()


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
async def bump(bot_id: int, **inc: int) -> None:
    """يزيد عدادات اليوم: new, starts, links, groups, msgs, left."""
    day = today()
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


async def daily(bot_ids: list[int], day: str) -> dict[str, int]:
    out: dict[str, int] = {}
    if not bot_ids:
        return out
    async with Session() as s:
        rows = (await s.execute(select(Daily).where(Daily.bot_id.in_(bot_ids), Daily.day == day))).scalars().all()
    for r in rows:
        for k, v in (r.data or {}).items():
            out[k] = out.get(k, 0) + int(v)
    return out
