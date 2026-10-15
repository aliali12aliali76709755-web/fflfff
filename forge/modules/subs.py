"""اشتراك البائعين (أصحاب البوتات التجارية):
- إنشاء بوت تجاري يحتاج اشتراكاً فعّالاً (أو تجربة مجانية مرة واحدة لكل بائع).
- الدفع من رصيد البائع في الصانع، والتجديد التلقائي من الرصيد عند الانتهاء.
- عند انتهاء الاشتراك بلا تجديد: متاجره تتوقف عن البيع (الزبون يرى «غير متوفر مؤقتاً»، ورصيده محفوظ) حتى يجدد.
- المدير يحدد: السعر، المدة، أيام التجربة، وتفعيل/إيقاف النظام كله. المدراء معفون دائماً.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time

from .. import config, db

log = logging.getLogger("forge.subs")

KEY = "sys:subs"
COMMERCE = {"store", "digital", "smm", "sms", "tgstars", "smmsms", "megastore"}
_LOCKS: dict[int, asyncio.Lock] = {}


def _lock(uid: int) -> asyncio.Lock:
    return _LOCKS.setdefault(uid, asyncio.Lock())


async def conf() -> dict:
    d = await db.kv_get(0, KEY, None)
    d = d if isinstance(d, dict) else {}
    on_default = os.environ.get("PROVIDERS_MOCK") != "1"       # مفعّل في الإنتاج
    return {"on": bool(d.get("on", on_default)), "price": float(d.get("price", 10.0)), "days": int(d.get("days", 30)),
            "trial_days": int(d.get("trial_days", 3))}


async def set_conf(**kw) -> dict:
    c = await conf()
    if "on" in kw:
        c["on"] = bool(kw["on"])
    if "price" in kw:
        c["price"] = round(max(0.0, min(float(kw["price"]), 10000.0)), 2)
    if "days" in kw:
        c["days"] = max(1, min(int(kw["days"]), 366))
    if "trial_days" in kw:
        c["trial_days"] = max(0, min(int(kw["trial_days"]), 60))
    await db.kv_set(0, KEY, c)
    return c


async def state(uid: int) -> dict:
    d = await db.kv_get(0, f"sub:{uid}", None)
    d = d if isinstance(d, dict) else {}
    return {"until": float(d.get("until", 0)), "trial_used": bool(d.get("trial_used")), "auto": bool(d.get("auto", True)),
            "paid": int(d.get("paid", 0)), "warned": float(d.get("warned", 0))}


async def _save(uid: int, st: dict) -> None:
    await db.kv_set(0, f"sub:{uid}", st)


async def active(uid: int) -> bool:
    if config.is_admin(uid):
        return True
    c = await conf()
    if not c["on"]:
        return True
    return (await state(uid))["until"] > time.time()


async def needs(uid: int, tpl_key: str) -> bool:
    """هل يحتاج إنشاء/تشغيل بوت من هذا النوع اشتراكاً غير متوفر؟"""
    return tpl_key in COMMERCE and not await active(uid)


async def start_trial(uid: int) -> tuple[bool, str]:
    c = await conf()
    async with _lock(uid):
        st = await state(uid)
        if st["trial_used"] or c["trial_days"] <= 0:
            return False, "استخدمت التجربة المجانية مسبقاً"
        st["trial_used"] = True
        st["until"] = max(st["until"], time.time()) + c["trial_days"] * 86400
        await _save(uid, st)
    return True, f"🎁 فُعّلت التجربة المجانية {c['trial_days']} أيام"


async def buy(uid: int, *, auto: bool = False) -> tuple[bool, str]:
    """يشتري/يجدد من رصيد البائع في الصانع. محمي من الخصم المزدوج."""
    from . import ledger
    c = await conf()
    async with _lock(uid):
        st = await state(uid)
        if auto and st["until"] > time.time():
            return False, "ما زال فعّالاً"
        n = st["paid"] + 1
        if c["price"] > 0:
            ok, _tx, bal = await ledger.debit_seller(uid, c["price"], "subscription", ref_id=f"sub_{uid}_{n}",
                                                     description=f"اشتراك المتاجر {c['days']} يوماً")
            if not ok:
                return False, f"رصيدك في الصانع (${bal:.2f}) لا يكفي سعر الاشتراك (${c['price']:.2f})"
        st["paid"] = n
        st["until"] = max(st["until"], time.time()) + c["days"] * 86400
        st["warned"] = 0
        await _save(uid, st)
    return True, f"✅ اشتراكك فعّال حتى {time.strftime('%Y-%m-%d', time.gmtime(st['until']))}"


async def set_auto(uid: int, on: bool) -> None:
    st = await state(uid)
    st["auto"] = bool(on)
    await _save(uid, st)


async def grant(uid: int, days: int) -> dict:
    """منحة من المدير (أيام مجانية)."""
    st = await state(uid)
    st["until"] = max(st["until"], time.time()) + max(0, int(days)) * 86400
    await _save(uid, st)
    return st


async def store_open(bot_id: int, seller_id: int) -> bool:
    """هل يبيع هذا المتجر الآن؟ (يُستدعى قبل كل عملية شراء)."""
    if not seller_id:
        return True
    c = await conf()
    if not c["on"] or config.is_admin(seller_id):
        return True
    b = await _bot(bot_id)
    if b is None or b.template not in COMMERCE:
        return True
    return (await state(seller_id))["until"] > time.time()


_BOT_TPL: dict[int, tuple[float, object]] = {}


async def _bot(bot_id: int):
    hit = _BOT_TPL.get(bot_id)
    if hit and time.time() - hit[0] < 120:
        return hit[1]
    async with db.Session() as s:
        b = await s.get(db.Bot, bot_id)
    _BOT_TPL[bot_id] = (time.time(), b)
    return b


async def sellers_with_commerce() -> list[int]:
    from sqlalchemy import select
    async with db.Session() as s:
        return list({x for x in (await s.execute(select(db.Bot.owner_id).where(db.Bot.template.in_(list(COMMERCE)),
                                                                              db.Bot.status.in_(["active", "error"])))).scalars().all()})


_LAST_SWEEP = 0.0


async def sweep(notify=None) -> dict:
    """كل ساعة: تجديد تلقائي من الرصيد، تذكير قبل الانتهاء بيوم، وإشعار عند التوقف."""
    global _LAST_SWEEP
    if time.time() - _LAST_SWEEP < 3600:
        return {}
    _LAST_SWEEP = time.time()
    c = await conf()
    if not c["on"]:
        return {}
    out = {"renewed": 0, "warned": 0, "expired": 0}
    now = time.time()
    for uid in await sellers_with_commerce():
        if config.is_admin(uid):
            continue
        st = await state(uid)
        left = st["until"] - now
        if left <= 0 and st["auto"] and st["paid"] + (1 if st["trial_used"] else 0) > 0:
            ok, msg = await buy(uid, auto=True)
            if ok:
                out["renewed"] += 1
                if notify:
                    await notify(uid, f"🔄 جُدّد اشتراك متاجرك تلقائياً من رصيدك.\n{msg}")
                continue
        st = await state(uid)
        left = st["until"] - now
        if 0 < left < 86400 and now - st["warned"] > 20 * 3600:
            st["warned"] = now
            await _save(uid, st)
            out["warned"] += 1
            if notify:
                await notify(uid, f"⏰ اشتراك متاجرك ينتهي خلال أقل من يوم.\nتأكد أن رصيدك في الصانع يكفي ${c['price']:.2f} ليتجدد تلقائياً.")
        elif left <= 0 and now - st["warned"] > 20 * 3600:
            st["warned"] = now
            await _save(uid, st)
            out["expired"] += 1
            if notify:
                await notify(uid, "⛔ انتهى اشتراك متاجرك فتوقفت عن البيع (أرصدة زبائنك محفوظة).\nجدد الاشتراك من «💎 اشتراكي» لتعود فوراً.")
    return out
