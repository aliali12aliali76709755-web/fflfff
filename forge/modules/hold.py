"""الموافقة اليدوية للطلبات (توفير رأس المال):
طلبات التفاعل وأرقام التفعيل لا تُرسل لمواقع المزودين حتى يوافق مدير المنصة.
- الزبون والبائع يرون الطلب «قيد التنفيذ» دائماً (لا يظهر أنه موقوف).
- المال يُخصم من الزبون والبائع عند الطلب كالمعتاد (فلا يمكن صرفه مرتين).
- المدير يرى الطلبات المعلّقة مع تكلفتها عند أرخص موقع واسمه، فيشحن ذلك الموقع ثم يوافق.
- الموافقة: يُرسل الطلب للموقع (مع التبديل التلقائي). إن فشل يبقى معلّقاً ليعيد المحاولة أو يرفض.
- الرفض: استرجاع كامل للطرفين.
- الحماية: موافقة واحدة فقط لكل طلب حتى لو ضغط المدير مرتين أو من جهازين، ولا يمكن للزبون الإلغاء أثناء التنفيذ.
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from sqlalchemy import select, update

from .. import db

log = logging.getLogger("forge.hold")

HOLD = "__hold__"            # اسم المزود للطلب المعلّق
BUSY = "__approving__"       # أثناء الإرسال للموقع (قفل)
SECS = ("smm", "sms")
KEY = "sys:hold"


async def settings() -> dict[str, bool]:
    d = await db.kv_get(0, KEY, None)
    d = d if isinstance(d, dict) else {}
    import os
    dflt = os.environ.get("PROVIDERS_MOCK") != "1"       # مفعّل افتراضياً في الإنتاج
    return {s: bool(d.get(s, dflt)) for s in SECS}


async def set_enabled(sec: str, on: bool) -> None:
    d = await settings()
    if sec in SECS:
        d[sec] = bool(on)
        await db.kv_set(0, KEY, d)


async def enabled(sec: str) -> bool:
    return (await settings()).get(sec, False)


def is_held(provider_name: str) -> bool:
    return provider_name in (HOLD, BUSY)


def section_of(o: Any) -> str:
    if (o.tpl_key or "") == "sms" or (o.order_id or "").startswith("sms_"):
        return "sms"
    return "smm"


# ── التقدير: أرخص موقع وتكلفته ──
async def estimate(o: Any) -> dict:
    if section_of(o) == "smm":
        from . import smm_agg
        it = smm_agg.get_item(o.service_id)
        if it:
            offs = smm_agg.offers_for(o.service_id, int(o.quantity)) or it.get("offers") or []
            if offs:
                return {"provider": offs[0]["p"], "cost": round(int(o.quantity) / 1000.0 * float(offs[0]["rate"]), 4)}
        from .providers.smm import catalog_source
        from . import catalog as _cat
        svc = next((x for x in catalog_source() if x["id"] == o.service_id), None)
        rate = _cat.effective_cost(await _cat.get_map("smm"), o.service_id, float(svc["rate_per_1k"]) if svc else 0.0)
        provs = await db.kv_get(0, "smm:providers", []) or []
        name = next((p.get("name") for p in provs if p.get("on", True)), "")
        return {"provider": name, "cost": round(int(o.quantity) / 1000.0 * rate, 4)}
    from .providers.sms import SMSManager
    c, _, a = (o.service_id or "").partition("_")
    provs = await db.kv_get(0, "sms:providers", []) or []
    name = next((p.get("name") for p in provs if p.get("on", True)), "")
    return {"provider": name, "cost": round(await SMSManager.platform_base(c, a), 4)}


async def pending(limit: int = 200) -> list[Any]:
    async with db.Session() as s:
        return list((await s.execute(select(db.ServiceOrder).where(
            db.ServiceOrder.provider_name.in_([HOLD, BUSY]),
            db.ServiceOrder.status.in_(["processing", "pending", "queued"]),
        ).order_by(db.ServiceOrder.created).limit(limit))).scalars().all())


async def summary() -> dict:
    """الطلبات المعلّقة + كم يلزم شحنه في كل موقع."""
    rows = await pending()
    out, need = [], {}
    for o in rows:
        e = await estimate(o)
        need[e["provider"] or "—"] = round(need.get(e["provider"] or "—", 0.0) + e["cost"], 4)
        out.append({"id": o.id, "order_id": o.order_id, "sec": section_of(o), "name": o.service_name, "qty": o.quantity,
                    "target": o.target, "price_usd": float(o.price_user_usd), "platform_usd": float(o.cost_platform_usd or 0),
                    "provider": e["provider"], "cost": e["cost"], "busy": o.provider_name == BUSY, "bot_id": o.bot_id,
                    "created": o.created.strftime("%Y-%m-%d %H:%M") if o.created else ""})
    return {"orders": out, "need": need, "total": round(sum(need.values()), 4)}


async def _claim(pk: int) -> Any | None:
    """قفل ذري: يحوّل الطلب من «معلّق» إلى «جارٍ الإرسال» مرة واحدة فقط."""
    async with db.Session() as s:
        r = await s.execute(update(db.ServiceOrder).where(
            db.ServiceOrder.id == pk, db.ServiceOrder.provider_name == HOLD,
            db.ServiceOrder.status.in_(["processing", "pending", "queued"]),
        ).values(provider_name=BUSY))
        await s.commit()
        if r.rowcount != 1:
            return None
        return await s.get(db.ServiceOrder, pk)


async def _release(pk: int) -> None:
    async with db.Session() as s:
        await s.execute(update(db.ServiceOrder).where(db.ServiceOrder.id == pk, db.ServiceOrder.provider_name == BUSY)
                        .values(provider_name=HOLD))
        await s.commit()


async def approve(pk: int, notify=None) -> tuple[bool, str]:
    """يرسل الطلب المعلّق للموقع الآن. يعيد (نجح؟، رسالة)."""
    o = await _claim(pk)
    if o is None:
        return False, "الطلب ليس معلّقاً (نُفّذ أو أُلغي مسبقاً)"
    sec = section_of(o)
    try:
        if sec == "smm":
            from .providers.smm import SMMManager
            ok, poid, pname, pcost = await SMMManager.dispatch_order_with_failover(o.bot_id, o.service_id, o.target, int(o.quantity), force=True)
            if not ok:
                await _release(pk)
                return False, "كل المواقع رفضت الطلب (غالباً الرصيد لا يكفي). اشحن الموقع ثم أعد المحاولة، أو ارفض الطلب."
            async with db.Session() as s:
                row = await s.get(db.ServiceOrder, pk)
                row.provider_name, row.provider_order_id, row.cost_provider_usd = pname, str(poid), float(pcost or 0)
                row.status = "processing"
                row.details = dict(row.details or {}, approved_at=dt.datetime.utcnow().isoformat())
                await s.commit()
            return True, f"✅ أُرسل إلى {pname}"
        from .providers.sms import SMSManager
        c, _, a = (o.service_id or "").partition("_")
        ok, act_id, phone, pname, pcost = await SMSManager.rent_number_with_failover(o.bot_id, c, a, force=True)
        if not ok:
            await _release(pk)
            return False, "لا يوجد رقم متاح أو الرصيد لا يكفي في موقع الأرقام. اشحن ثم أعد المحاولة، أو ارفض الطلب."
        async with db.Session() as s:
            row = await s.get(db.ServiceOrder, pk)
            row.provider_name, row.provider_order_id, row.cost_provider_usd = pname, str(act_id), float(pcost or 0)
            row.target, row.status, row.tpl_key = phone, "waiting_sms", "sms"
            row.details = dict(row.details or {}, rent_time=dt.datetime.utcnow().isoformat(), approved_at=dt.datetime.utcnow().isoformat())
            await s.commit()
            o = row
        if notify:
            try:
                await notify(o, "sms_ready")
            except Exception:  # noqa: BLE001
                log.exception("notify sms_ready")
        return True, f"✅ رقم {phone} من {pname}"
    except Exception as e:  # noqa: BLE001
        log.exception("approve %s failed", pk)
        await _release(pk)
        return False, f"خطأ: {str(e)[:120]}"


async def reject(pk: int, reason: str = "تعذّر تنفيذ الطلب", notify=None) -> tuple[bool, str]:
    """رفض طلب معلّق: استرجاع كامل للزبون والبائع."""
    from . import ledger
    async with db.Session() as s:
        o = await s.get(db.ServiceOrder, pk)
    if o is None or o.provider_name != HOLD:
        return False, "الطلب ليس معلّقاً"
    ok, msg, _ = await ledger.atomic_dual_refund(o.order_id, reason=reason)
    if ok:
        async with db.Session() as s:
            row = await s.get(db.ServiceOrder, pk)
            row.status = "canceled"
            await s.commit()
        if notify:
            try:
                await notify(o, "refund")
            except Exception:  # noqa: BLE001
                pass
    return ok, ("↩️ تم الرفض واسترجاع المبلغ للطرفين" if ok else msg)


async def after_save(order_id: str) -> None:
    """يُستدعى بعد حفظ الطلب: إن كان معلّقاً يُشعَر المدير (في الخلفية، لا يؤخر الزبون)."""
    import asyncio
    async with db.Session() as s:
        o = (await s.execute(select(db.ServiceOrder).where(db.ServiceOrder.order_id == order_id))).scalars().first()
    if o is not None and o.provider_name == HOLD:
        asyncio.get_running_loop().create_task(notify_admins(o))


async def notify_admins(o: Any) -> None:
    """إشعار مدراء المنصة في بوت الصانع بطلب جديد بانتظار الموافقة."""
    from .. import config
    from ..ui import B, kb
    try:
        from ..runtime import manager
        app = manager.maker
    except Exception:  # noqa: BLE001
        return
    if app is None:
        return
    e = await estimate(o)
    sec = "📱 رقم" if section_of(o) == "sms" else "🚀 تفاعل"
    txt = (f"🕒 <b>طلب بانتظار موافقتك</b> — {sec}\n{o.service_name}\n"
           f"الكمية: <b>{o.quantity}</b>\nالهدف: <code>{(o.target or '-')[:120]}</code>\n"
           f"دفع الزبون: ${float(o.price_user_usd):.2f} · التكلفة عند <b>{e['provider'] or '—'}</b>: <b>${e['cost']:.4f}</b>")
    markup = kb([[B("✅ موافقة وإرسال", f"m:hold:ok:{o.id}"), B("↩️ رفض واسترجاع", f"m:hold:no:{o.id}")],
                 [B("🗂 كل الطلبات المعلّقة", "m:hold:list")]])
    for aid in {config.ADMIN_ID, *config.ADMIN_IDS} - {0}:
        try:
            await app.bot.send_message(aid, txt, parse_mode="HTML", reply_markup=markup)
        except Exception:  # noqa: BLE001
            pass
