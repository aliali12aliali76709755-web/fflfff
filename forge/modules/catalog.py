"""ربط كتالوج المنصة بالمزودين الحقيقيين: لكل منتج داخلي (مثل ig_followers_fast) يحدد مدير المنصة
رقم الخدمة لدى المزود، والتكلفة الحقيقية، وإظهاره أو إخفاءه. التكلفة هنا هي أساس سعر المنصة على البائع.

الصيغة المخزنة في KV للمنصة (bot_id=0):
    "<tpl>:catalog_map" = {"<internal_id>": {"ps": "<provider service id>", "cost": 0.95, "off": False}}
"""
from __future__ import annotations

from typing import Any

from .. import db

TPLS = ("smm", "tgstars", "digital", "sms")


def key(tpl: str) -> str:
    return f"{tpl}:catalog_map"


async def get_map(tpl: str) -> dict[str, dict[str, Any]]:
    m = await db.kv_get(0, key(tpl), {}) or {}
    return m if isinstance(m, dict) else {}


async def set_entry(tpl: str, item_id: str, *, ps: str | None = None, cost: float | None = None, off: bool | None = None) -> None:
    m = await get_map(tpl)
    e = dict(m.get(item_id) or {})
    if ps is not None:
        e["ps"] = str(ps)[:64]
    if cost is not None:
        e["cost"] = round(float(cost), 6)
    if off is not None:
        e["off"] = bool(off)
    m[item_id] = e
    await db.kv_set(0, key(tpl), m)


def provider_service(cmap: dict, item_id: str) -> str:
    """رقم الخدمة لدى المزود إن ربطه المدير، وإلا المعرّف الداخلي نفسه."""
    return str((cmap.get(item_id) or {}).get("ps") or item_id)


def effective_cost(cmap: dict, item_id: str, default: float) -> float:
    c = (cmap.get(item_id) or {}).get("cost")
    try:
        return float(c) if c is not None else float(default)
    except (TypeError, ValueError):
        return float(default)


def is_off(cmap: dict, item_id: str) -> bool:
    return bool((cmap.get(item_id) or {}).get("off"))


def parse_lines(text: str) -> tuple[list[tuple[str, dict]], list[str]]:
    """يحلّل سطور المدير: «المعرّف | رقم الخدمة لدى المزود | التكلفة» و «المعرّف | off/on».
    يعيد (التعديلات، الأخطاء)."""
    out, errs = [], []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        iid = parts[0]
        if not iid or len(iid) > 64:
            errs.append(line)
            continue
        if len(parts) == 2 and parts[1].lower() in ("off", "on", "اخفاء", "إخفاء", "اظهار", "إظهار"):
            out.append((iid, {"off": parts[1].lower() in ("off", "اخفاء", "إخفاء")}))
            continue
        upd: dict[str, Any] = {}
        if len(parts) >= 2 and parts[1]:
            upd["ps"] = parts[1]
        if len(parts) >= 3 and parts[2]:
            try:
                c = float(parts[2].replace(",", ".").replace("$", ""))
                assert 0 <= c < 100000
                upd["cost"] = c
            except (ValueError, AssertionError):
                errs.append(line)
                continue
        if upd:
            out.append((iid, upd))
        else:
            errs.append(line)
    return out, errs
