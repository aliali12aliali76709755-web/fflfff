"""أدوات البائع للبيع أكثر:
- عروض بوقت محدود (عداد تنازلي في المتجر): على كل المتجر، أو قسم، أو منتج.
- نظام الوكلاء: البائع يعطي زبائن معيّنين نسبة خصم ثابتة (أسعار جملة).
- الخصم يُحسب في السيرفر فقط، ولا ينزل السعر أبداً تحت سعر المنصة على البائع (البائع لا يخسر).
- تقرير يومي للبائع + تنبيه «زبون توقف عن الشراء» مع زر إرسال كود خصم شخصي.
"""
from __future__ import annotations

import datetime as dt
import logging
import random
import string
import time

from sqlalchemy import func, select

from .. import config, db

log = logging.getLogger("forge.perks")

SCOPES = ("v2:all", "v2:sec", "v2:pid")
_SALES: dict[int, tuple[float, list]] = {}


def invalidate(bot_id: int) -> None:
    _SALES.pop(bot_id, None)


async def active_sales(bot_id: int) -> list[dict]:
    hit = _SALES.get(bot_id)
    if hit and time.time() - hit[0] < 20:
        return hit[1]
    now = dt.datetime.utcnow()
    async with db.Session() as s:
        rows = (await s.execute(select(db.FlashSale).where(
            db.FlashSale.bot_id == bot_id, db.FlashSale.is_active.is_(True), db.FlashSale.scope.in_(SCOPES),
            db.FlashSale.starts_at <= now, db.FlashSale.expires_at > now))).scalars().all()
    out = [{"id": r.sale_id, "title": r.title, "scope": r.scope.split(":")[1], "target": r.target_id, "pct": float(r.discount_value),
            "ends": int(r.expires_at.replace(tzinfo=dt.timezone.utc).timestamp())} for r in rows]
    _SALES[bot_id] = (time.time(), out)
    return out


async def create_sale(bot_id: int, *, title: str, scope: str, target: str, pct: float, hours: float) -> dict:
    scope = scope if scope in ("all", "sec", "pid") else "all"
    pct = max(1.0, min(float(pct), 90.0))
    hours = max(0.25, min(float(hours), 24 * 30))
    now = dt.datetime.utcnow()
    sid = "fs" + "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
    async with db.Session() as s:
        s.add(db.FlashSale(sale_id=sid, bot_id=bot_id, title=(title or "عرض خاص")[:120], scope=f"v2:{scope}", target_id=(target or "")[:64],
                           discount_type="percent", discount_value=pct, starts_at=now, expires_at=now + dt.timedelta(hours=hours), is_active=True))
        await s.commit()
    invalidate(bot_id)
    return {"id": sid}


async def end_sale(bot_id: int, sale_id: str) -> None:
    async with db.Session() as s:
        r = (await s.execute(select(db.FlashSale).where(db.FlashSale.bot_id == bot_id, db.FlashSale.sale_id == sale_id))).scalars().first()
        if r is not None:
            r.is_active = False
            await s.commit()
    invalidate(bot_id)


# ── الوكلاء ──
async def agents(bot_id: int) -> dict[str, float]:
    d = await db.kv_get(bot_id, "v2:agents", {}) or {}
    return {str(k): float(v) for k, v in d.items()} if isinstance(d, dict) else {}


async def set_agent(bot_id: int, uid: int, pct: float) -> None:
    d = await agents(bot_id)
    pct = max(0.0, min(float(pct), 60.0))
    if pct <= 0:
        d.pop(str(uid), None)
    else:
        d[str(uid)] = round(pct, 2)
    await db.kv_set(bot_id, "v2:agents", d)


async def agent_pct(bot_id: int, uid: int) -> float:
    return float((await agents(bot_id)).get(str(uid), 0.0)) if uid else 0.0


async def best(bot_id: int, uid: int, pid: str, sec: str) -> tuple[float, str]:
    """أفضل نسبة خصم تنطبق (العرض أو الوكيل — لا تُجمع)."""
    pct, label = 0.0, ""
    for sl in await active_sales(bot_id):
        if sl["scope"] == "all" or (sl["scope"] == "sec" and sl["target"] == sec) or (sl["scope"] == "pid" and sl["target"] == pid):
            if sl["pct"] > pct:
                pct, label = sl["pct"], f"🔥 {sl['title']}"
    ap = await agent_pct(bot_id, uid)
    if ap > pct:
        pct, label = ap, "🤝 سعر الوكيل"
    return pct, label


async def apply(bot_id: int, uid: int, pid: str, sec: str, price: float, platform_cost: float) -> tuple[float, float, str]:
    """يعيد (السعر بعد الخصم، قيمة الخصم، الوصف). السعر لا ينزل تحت سعر المنصة + سنت."""
    pct, label = await best(bot_id, uid, pid, sec)
    if pct <= 0 or price <= 0:
        return price, 0.0, ""
    floor = round(platform_cost + 0.01, 4) if platform_cost > 0 else 0.01
    new = max(round(price * (1 - pct / 100.0), 4), floor)
    if new >= price:
        return price, 0.0, ""
    return new, round(price - new, 4), label


# ── التقرير اليومي وتنبيه الزبائن المتوقفين ──
COMMERCE = {"store", "digital", "smm", "sms", "tgstars", "smmsms", "megastore"}
OK_STATUSES = ("completed", "processing", "waiting_sms", "queued", "pending")


async def report_conf(bot_id: int) -> dict:
    d = await db.kv_get(bot_id, "v2:reports", {}) or {}
    return {"daily": bool(d.get("daily", True)), "winback": bool(d.get("winback", True)), "wb_pct": float(d.get("wb_pct", 10)),
            "wb_days": int(d.get("wb_days", 14))}


async def day_stats(bot_id: int, since: dt.datetime) -> dict:
    async with db.Session() as s:
        rows = (await s.execute(select(db.ServiceOrder.service_name, func.count(), func.sum(db.ServiceOrder.price_user_usd),
                                       func.sum(db.ServiceOrder.cost_platform_usd))
                                .where(db.ServiceOrder.bot_id == bot_id, db.ServiceOrder.created >= since,
                                       db.ServiceOrder.status.in_(OK_STATUSES))
                                .group_by(db.ServiceOrder.service_name))).all()
        new_c = int((await s.execute(select(func.count()).select_from(db.BUser).where(
            db.BUser.bot_id == bot_id, db.BUser.joined >= since, db.BUser.kind == "private"))).scalar() or 0)
    orders = sum(int(r[1]) for r in rows)
    sales = round(sum(float(r[2] or 0) for r in rows), 2)
    cost = round(sum(float(r[3] or 0) for r in rows), 2)
    top = max(rows, key=lambda r: int(r[1]), default=None)
    return {"orders": orders, "sales": sales, "profit": round(sales - cost, 2), "new": new_c,
            "top": (top[0], int(top[1])) if top else None}


async def inactive_customers(bot_id: int, days: int = 14, limit: int = 5) -> list[dict]:
    """زبائن اشتروا سابقاً ثم توقفوا منذ X يوماً (ولم يُنبَّه عنهم خلال الفترة)."""
    now = db.now()
    cut, old = now - dt.timedelta(days=days), now - dt.timedelta(days=90)
    async with db.Session() as s:
        rows = (await s.execute(select(db.ServiceOrder.user_id, func.max(db.ServiceOrder.created), func.count(), func.sum(db.ServiceOrder.price_user_usd))
                                .where(db.ServiceOrder.bot_id == bot_id, db.ServiceOrder.status.in_(OK_STATUSES),
                                       db.ServiceOrder.created >= old)
                                .group_by(db.ServiceOrder.user_id)
                                .having(func.max(db.ServiceOrder.created) < cut)
                                .order_by(func.sum(db.ServiceOrder.price_user_usd).desc()).limit(40))).all()
        seen = await db.kv_get(bot_id, "v2:wb_seen", {}) or {}
        out = []
        for uid, last, n, total in rows:
            if time.time() - float(seen.get(str(uid), 0)) < days * 86400:
                continue
            u = await s.get(db.BUser, (bot_id, uid))
            if u is not None and (u.banned or u.blocked):
                continue
            out.append({"uid": int(uid), "name": (u.name if u else "") or str(uid), "username": (u.username if u else "") or "",
                        "days": (now - last).days, "orders": int(n), "total": round(float(total or 0), 2)})
            if len(out) >= limit:
                break
    return out


async def mark_seen(bot_id: int, uids: list[int]) -> None:
    seen = await db.kv_get(bot_id, "v2:wb_seen", {}) or {}
    for u in uids:
        seen[str(u)] = time.time()
    if len(seen) > 3000:
        seen = dict(sorted(seen.items(), key=lambda x: -x[1])[:2000])
    await db.kv_set(bot_id, "v2:wb_seen", seen)


async def send_winback(bot_id: int, uid: int, app_bot) -> tuple[bool, str]:
    """ينشئ كود خصم شخصي (استخدام واحد، 7 أيام) ويرسله للزبون من بوت المتجر."""
    from . import promo
    conf = await report_conf(bot_id)
    code = "BACK" + "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
    exp = (dt.date.today() + dt.timedelta(days=7)).isoformat()
    await promo.save_bot_promo(bot_id, code, discount_type="percent", value=conf["wb_pct"], max_uses=1, per_user=1,
                               min_order_usd=0, expires_at=exp)
    try:
        await app_bot.send_message(uid, f"🎁 اشتقنالك!\nهذا كود خصم {conf['wb_pct']:g}% خاص فيك على طلبك القادم:\n\n<code>{code}</code>\n\nصالح 7 أيام — استخدمه عند الشراء ✨",
                                   parse_mode="HTML")
    except Exception as e:  # noqa: BLE001
        return False, f"تعذّر الإرسال (ربما حظر البوت): {str(e)[:60]}"
    await mark_seen(bot_id, [uid])
    return True, f"✅ أُرسل كود {code} للزبون"


_LAST_DAY: dict[int, str] = {}


async def daily_reports(mgr) -> int:
    """كل يوم بعد التاسعة مساءً بالتوقيت المحلي: تقرير لكل بائع تجاري من داخل بوت متجره."""
    from ..ui import B, kb
    local = db.now() + dt.timedelta(hours=config.TZ_HOURS)
    if local.hour < 21:
        return 0
    day = local.strftime("%Y-%m-%d")
    since = dt.datetime.combine(local.date(), dt.time()) - dt.timedelta(hours=config.TZ_HOURS)
    sent = 0
    for bot_id, app in list(mgr.apps.items()):
        if _LAST_DAY.get(bot_id) == day:
            continue
        b = await _bot(bot_id)
        if b is None or b.template not in COMMERCE:
            _LAST_DAY[bot_id] = day
            continue
        if await db.kv_get(bot_id, "v2:report_day", "") == day:
            _LAST_DAY[bot_id] = day
            continue
        _LAST_DAY[bot_id] = day
        await db.kv_set(bot_id, "v2:report_day", day)
        conf = await report_conf(bot_id)
        try:
            lines, rows = [], []
            if conf["daily"]:
                st = await day_stats(bot_id, since)
                lines.append(f"📊 <b>تقرير اليوم</b> — {day}\n"
                             f"🛒 الطلبات: <b>{st['orders']}</b>\n💵 المبيعات: <b>${st['sales']:.2f}</b>\n"
                             f"📈 ربحك: <b>${st['profit']:.2f}</b>\n👤 زبائن جدد: <b>{st['new']}</b>" +
                             (f"\n🏆 الأكثر مبيعاً: {st['top'][0][:50]} ({st['top'][1]})" if st["top"] else ""))
            if conf["winback"]:
                ina = await inactive_customers(bot_id, conf["wb_days"])
                if ina:
                    lines.append("\n💤 <b>زبائن توقفوا عن الشراء:</b>")
                    for c in ina:
                        nm = f"@{c['username']}" if c["username"] else c["name"][:20]
                        lines.append(f"• {nm} — آخر طلب قبل {c['days']} يوم ({c['orders']} طلبات، ${c['total']:.2f})")
                        rows.append([B(f"🎁 أرسل خصم {conf['wb_pct']:g}% لـ {nm}"[:60], f"o:wb:{c['uid']}")])
                    await mark_seen(bot_id, [c["uid"] for c in ina])
            if lines:
                await app.bot.send_message(b.owner_id, "\n".join(lines), parse_mode="HTML", reply_markup=kb(rows) if rows else None)
                sent += 1
        except Exception:  # noqa: BLE001
            log.debug("daily report %s failed", bot_id, exc_info=True)
    return sent


_BOTS: dict[int, tuple[float, object]] = {}


async def _bot(bot_id: int):
    hit = _BOTS.get(bot_id)
    if hit and time.time() - hit[0] < 600:
        return hit[1]
    async with db.Session() as s:
        b = await s.get(db.Bot, bot_id)
    _BOTS[bot_id] = (time.time(), b)
    return b
