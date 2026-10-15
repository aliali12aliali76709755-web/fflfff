"""أدوات مدير المنصة:
- لوحة الأرباح: ربحك (سعر المنصة − تكلفة الموقع) حسب الموقع، المتجر، والقسم + دخل الاشتراكات.
- تنبيه رصيد المواقع: إشعار في الصانع عندما ينزل رصيد أي موقع تحت الحد.
- كشف الاحتيال: زبائن بنسبة استرجاع عالية، ومتاجر عليها شكاوى.
- الإذاعة الجماعية من أي بوت بالمعرّف (نص/صورة/زر) مع تقرير الإرسال.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
import time

from sqlalchemy import func, select

from .. import config, db

log = logging.getLogger("forge.insights")

DONE = ("completed", "processing", "waiting_sms", "queued", "pending")
SEC_OF = {"smm": "smm", "sms": "sms", "digital": "digital", "tgstars": "tgstars", "master": "digital", "store": "digital"}


# ── الأرباح ──
async def profits(days: int = 30) -> dict:
    since = db.now() - dt.timedelta(days=max(1, min(days, 365)))
    from . import hold
    async with db.Session() as s:
        rows = (await s.execute(select(db.ServiceOrder.provider_name, db.ServiceOrder.bot_id, db.ServiceOrder.tpl_key,
                                       func.count(), func.sum(db.ServiceOrder.cost_platform_usd), func.sum(db.ServiceOrder.cost_provider_usd),
                                       func.sum(db.ServiceOrder.price_user_usd))
                                .where(db.ServiceOrder.created >= since, db.ServiceOrder.status.in_(DONE))
                                .group_by(db.ServiceOrder.provider_name, db.ServiceOrder.bot_id, db.ServiceOrder.tpl_key))).all()
        names = {b.id: b.username for b in (await s.execute(select(db.Bot).where(db.Bot.id.in_({r[1] for r in rows} or {0})))).scalars().all()}
        subs_in = float((await s.execute(select(func.coalesce(func.sum(db.LedgerEntry.amount_usd), 0)).where(
            db.LedgerEntry.bot_id == 0, db.LedgerEntry.kind == "subscription", db.LedgerEntry.direction == "debit",
            db.LedgerEntry.created >= since))).scalar() or 0)
    by_p: dict[str, dict] = {}
    by_b: dict[str, dict] = {}
    by_s: dict[str, dict] = {}
    tot = {"orders": 0, "intake": 0.0, "cost": 0.0, "sales": 0.0}
    for prov, bid, tpl, n, intake, cost, sales in rows:
        intake, cost, sales, n = float(intake or 0), float(cost or 0), float(sales or 0), int(n)
        p = "⏳ بانتظار موافقتك" if hold.is_held(prov or "") else (prov or "—")
        for bucket, key in ((by_p, p), (by_b, "@" + (names.get(bid) or str(bid))), (by_s, SEC_OF.get(tpl, tpl or "—"))):
            e = bucket.setdefault(key, {"orders": 0, "intake": 0.0, "cost": 0.0})
            e["orders"] += n
            e["intake"] += intake
            e["cost"] += cost
        tot["orders"] += n
        tot["intake"] += intake
        tot["cost"] += cost
        tot["sales"] += sales

    def fin(d):
        out = [{"name": k, "orders": v["orders"], "intake": round(v["intake"], 2), "cost": round(v["cost"], 2),
                "profit": round(v["intake"] - v["cost"], 2)} for k, v in d.items()]
        return sorted(out, key=lambda x: -x["profit"])
    return {"days": days, "orders": tot["orders"], "sales": round(tot["sales"], 2), "intake": round(tot["intake"], 2),
            "cost": round(tot["cost"], 2), "profit": round(tot["intake"] - tot["cost"], 2), "subs": round(subs_in, 2),
            "total": round(tot["intake"] - tot["cost"] + subs_in, 2),
            "by_provider": fin(by_p), "by_store": fin(by_b)[:30], "by_section": fin(by_s)}


# ── تنبيه رصيد المواقع ──
_LAST_BAL = 0.0
_ALERTED: dict[str, float] = {}


async def alert_conf() -> dict:
    d = await db.kv_get(0, "sys:bal_alert", {}) or {}
    return {"on": bool(d.get("on", True)), "min": float(d.get("min", 5.0))}


async def balances() -> list[dict]:
    from .providers.sms import SMSManager
    from .smm_agg import providers_conf
    from .providers.smm import StandardSMMAdapter
    out = []

    async def one(sec, ad):
        try:
            return {"sec": sec, "name": ad.name, "balance": round(float(await asyncio.wait_for(ad.get_balance(), 20)), 4)}
        except Exception as e:  # noqa: BLE001
            return {"sec": sec, "name": ad.name, "error": str(e)[:100]}
    tasks = [one("smm", StandardSMMAdapter(p["name"], p["api_url"], p["api_key"])) for p in await providers_conf()]
    sms_ads = [a for a in await SMSManager.get_configured_providers(0) if a.__class__.__name__ != "MockSMSAdapter"]
    tasks += [one("sms", a) for a in sms_ads]
    if tasks:
        out = list(await asyncio.gather(*tasks))
    return out


async def check_balances(notify) -> list[dict]:
    """كل 30 دقيقة: ينبّه المدير مرة كل 6 ساعات لكل موقع نزل رصيده تحت الحد."""
    global _LAST_BAL
    if time.time() - _LAST_BAL < 1800:
        return []
    _LAST_BAL = time.time()
    c = await alert_conf()
    if not c["on"]:
        return []
    low = []
    for r in await balances():
        if "balance" in r and r["balance"] < c["min"] and time.time() - _ALERTED.get(r["name"], 0) > 6 * 3600:
            _ALERTED[r["name"]] = time.time()
            low.append(r)
    if low and notify:
        await notify("🔔 <b>رصيد مواقع منخفض</b>\n" + "\n".join(f"• {r['name']}: <b>${r['balance']:.2f}</b>" for r in low) +
                     f"\n\nالحد المحدد: ${c['min']:.2f} — اشحن حتى لا تتوقف الطلبات.")
    return low


# ── كشف الاحتيال ──
async def risk(days: int = 30) -> dict:
    since = db.now() - dt.timedelta(days=days)
    async with db.Session() as s:
        rows = (await s.execute(select(db.ServiceOrder.bot_id, db.ServiceOrder.user_id, func.count(),
                                       func.sum(func.cast(db.ServiceOrder.status.in_(["refunded", "canceled"]), db.Integer)))
                                .where(db.ServiceOrder.created >= since)
                                .group_by(db.ServiceOrder.bot_id, db.ServiceOrder.user_id))).all()
        sus = []
        for bid, uid, n, rf in rows:
            n, rf = int(n), int(rf or 0)
            if rf >= 3 and rf / max(n, 1) >= 0.5:
                u = await s.get(db.BUser, (bid, uid))
                sus.append({"bot_id": bid, "uid": uid, "name": (u.name if u else "") or str(uid), "username": (u.username if u else "") or "",
                            "orders": n, "refunds": rf})
        import re
        cnt: dict[int, int] = {}
        for txt in (await s.execute(select(db.Report.text).where(db.Report.kind == "complaint", db.Report.created >= since))).scalars().all():
            mm = re.search(r"\[(\d+)\]", txt or "")
            if mm:
                cnt[int(mm.group(1))] = cnt.get(int(mm.group(1)), 0) + 1
        comp = sorted(cnt.items(), key=lambda x: -x[1])[:30]
        bots = {b.id: b for b in (await s.execute(select(db.Bot).where(db.Bot.id.in_([c[0] for c in comp] + [x["bot_id"] for x in sus] or [0])))).scalars().all()}
    for x in sus:
        x["store"] = "@" + (bots[x["bot_id"]].username if x["bot_id"] in bots else str(x["bot_id"]))
    stores = [{"bot_id": bid, "store": "@" + (bots[bid].username if bid in bots else str(bid)), "owner": bots[bid].owner_id if bid in bots else 0,
               "complaints": int(n)} for bid, n in comp if bid]
    return {"customers": sorted(sus, key=lambda x: -x["refunds"])[:50], "stores": stores}


# ── الإذاعة من أي بوت ──
_JOBS: dict[str, dict] = {}


async def find_bot(username: str):
    u = (username or "").strip().lstrip("@").lower()
    if not u:
        return None
    async with db.Session() as s:
        return (await s.execute(select(db.Bot).where(func.lower(db.Bot.username) == u))).scalars().first()


async def broadcast(bot_username: str, text: str, *, photo: str = "", btn_text: str = "", btn_url: str = "") -> tuple[bool, str, str]:
    """يبدأ إذاعة في الخلفية من بوت محدد. يعيد (نجح؟، رسالة، معرّف المهمة)."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.error import Forbidden, RetryAfter

    from ..runtime import manager
    b = await find_bot(bot_username)
    if b is None:
        return False, "لا يوجد بوت بهذا المعرّف في المنصة", ""
    app = manager.apps.get(b.id)
    if app is None:
        return False, f"البوت @{b.username} غير مشغّل الآن", ""
    if any(j["bot"] == b.id and j["state"] == "running" for j in _JOBS.values()):
        return False, "توجد إذاعة جارية لهذا البوت، انتظر حتى تنتهي", ""
    async with db.Session() as s:
        uids = list((await s.execute(select(db.BUser.user_id).where(db.BUser.bot_id == b.id, db.BUser.kind == "private",
                                                                    db.BUser.blocked.is_(False), db.BUser.banned.is_(False)))).scalars().all())
    jid = f"bc{int(time.time())}{b.id % 1000}"
    job = {"id": jid, "bot": b.id, "username": b.username, "total": len(uids), "sent": 0, "failed": 0, "blocked": 0, "state": "running",
           "started": time.time()}
    _JOBS[jid] = job
    markup = InlineKeyboardMarkup([[InlineKeyboardButton(btn_text[:60], url=btn_url)]]) if btn_text and btn_url.startswith(("https://", "http://", "tg://")) else None

    async def run():
        for uid in uids:
            for _attempt in range(2):
                try:
                    if photo:
                        await app.bot.send_photo(uid, photo, caption=text[:1024] or None, parse_mode="HTML", reply_markup=markup)
                    else:
                        await app.bot.send_message(uid, text, parse_mode="HTML", reply_markup=markup, disable_web_page_preview=False)
                    job["sent"] += 1
                    break
                except RetryAfter as e:
                    await asyncio.sleep(float(getattr(e, "retry_after", 3)) + 0.5)
                except Forbidden:
                    job["blocked"] += 1
                    async with db.Session() as s:
                        row = await s.get(db.BUser, (b.id, uid))
                        if row is not None:
                            row.blocked = True
                            await s.commit()
                    break
                except Exception:  # noqa: BLE001
                    job["failed"] += 1
                    break
            await asyncio.sleep(0.04)
        job["state"] = "done"
        job["ended"] = time.time()
        try:
            if manager.maker is not None:
                for aid in {config.ADMIN_ID, *config.ADMIN_IDS} - {0}:
                    await manager.maker.bot.send_message(aid, f"📣 انتهت الإذاعة من @{b.username}\n✅ وصلت: {job['sent']}\n🚫 حاظرون: {job['blocked']}\n⚠️ فشل: {job['failed']}")
        except Exception:  # noqa: BLE001
            pass
    asyncio.get_running_loop().create_task(run())
    return True, f"بدأ الإرسال من @{b.username} إلى {len(uids)} مستخدم", jid


def jobs() -> list[dict]:
    return sorted(_JOBS.values(), key=lambda j: -j["started"])[:10]
