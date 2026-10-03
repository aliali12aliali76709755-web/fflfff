"""إعدادات المنصة التي يتحكم بها المدير (لكل صانع: الرئيسي = 0، والفرعي = رقم بوته)،
وحالة الإشراف على كل بوت مصنوع (إغلاق، صيانة، ترويج، توثيق...)."""
from __future__ import annotations

import copy
import time

from sqlalchemy import select

from . import config, db

PROMO_DEFAULT = {
    "on": True,          # الوضع العام: تظهر في كل البوتات ما لم يُستثنَ بوت
    "text": "",          # فارغ = النص الافتراضي
    "when": "both",      # start = مع رسالة البداية | idle = بعد انتهاء الاستخدام | both
    "idle": 120,         # ثواني السكون التي نعتبر بعدها أن العضو أنهى استخدامه
    "every": 86400,      # أقل مدة بين ظهورين لنفس العضو (0 = كل مرة)
    "btn": True,         # زر «اصنع بوتك»
}
DEFAULT = {
    "banned": [],        # مستخدمون محظورون من الصانع
    "off_tpls": [],      # قوالب معطّلة
    "fs": [],            # اشتراك إجباري للصانع: [{chat_id, title, url}]
    "max_bots": None,    # None = من .env
    "limits": {},        # حد بوتات خاص بمستخدم: {"<user_id>": n}
    "blocked_bots": [],  # بوتات محظورة نهائياً من التسجيل
    "maintenance": False,
    "promo": PROMO_DEFAULT,
    "notify": {"user": True, "bot": True, "daily": True},   # إشعارات المدير
}
ADM_DEFAULT = {
    "lock": None,        # {"mode": closed|temp|maint, "reason", "reason_en", "until", "at", "by"}
    "promo": None,       # None = يتبع الوضع العام | True = مفعّل دائماً | False = معطّل
    "promo_text": "",    # نص خاص بهذا البوت
    "verified": False,
    "super": False,      # مدير المنصة يدخل غرفة تحكم هذا البوت
    "note": "",
    "warns": [],         # [{"at", "text"}]
    "appeal_at": 0,
}
_cache: dict[int, dict] = {}
_adm: dict[int, dict] = {}


async def get(fid: int) -> dict:
    if fid not in _cache:
        saved = await db.kv_get(fid, "sys:platform", {}) or {}
        p = copy.deepcopy(DEFAULT)
        for k, v in saved.items():
            if k in ("promo", "notify") and isinstance(v, dict):
                p[k].update(v)
            elif k != "footer":
                p[k] = v
        if "promo" not in saved and "footer" in saved:   # ترقية من النسخة السابقة
            p["promo"]["on"] = bool(saved["footer"])
        _cache[fid] = p
    return _cache[fid]


async def save(fid: int) -> None:
    await db.kv_set(fid, "sys:platform", _cache.get(fid) or copy.deepcopy(DEFAULT))


def max_bots(p: dict, uid: int = 0) -> int:
    own = (p.get("limits") or {}).get(str(uid))
    if own is not None:
        return int(own)
    return config.MAX_BOTS_PER_USER if p.get("max_bots") is None else int(p["max_bots"])


def reset_cache() -> None:
    _cache.clear()
    _adm.clear()


# ───────────────────────── حالة الإشراف على بوت ─────────────────────────
def _merge_adm(saved) -> dict:
    a = copy.deepcopy(ADM_DEFAULT)
    if isinstance(saved, dict):
        a.update(saved)
    return a


async def preload() -> None:
    """يحمّل حالة الإشراف لكل البوتات مرة واحدة عند الإقلاع."""
    async with db.Session() as s:
        rows = (await s.execute(select(db.KV).where(db.KV.key == "sys:adm"))).scalars().all()
    for r in rows:
        _adm.setdefault(r.bot_id, _merge_adm(r.value))


async def adm(bot_id: int) -> dict:
    """القاموس نفسه يُشارك بين الصانع والبوت العامل، فأي تعديل يسري فوراً."""
    if bot_id not in _adm:
        _adm[bot_id] = _merge_adm(await db.kv_get(bot_id, "sys:adm"))
    return _adm[bot_id]


def peek(bot_id: int) -> dict:
    return _adm.get(bot_id) or ADM_DEFAULT


async def adm_save(bot_id: int) -> None:
    await db.kv_set(bot_id, "sys:adm", await adm(bot_id))


def adm_drop(bot_id: int) -> None:
    _adm.pop(bot_id, None)


def lock_of(a: dict | None) -> dict | None:
    """الإغلاق الساري (يتجاهل الإغلاق المؤقت المنتهي)."""
    lk = (a or {}).get("lock")
    if not lk:
        return None
    if lk.get("until") and lk["until"] <= time.time():
        return None
    return lk


def admin_lock(bot_data: dict) -> dict | None:
    """إغلاق الإدارة الساري على بوت عامل: إغلاقه هو، أو إغلاق الصانع الفرعي الذي أُنشئ عبره."""
    lk = lock_of(bot_data.get("adm"))
    if lk is not None:
        return lk
    fid = int(bot_data.get("factory_id") or 0)
    if fid:
        parent = lock_of(peek(fid))
        if parent is not None and parent["mode"] != "maint":
            return parent
    return None


def expired() -> list[int]:
    now = time.time()
    return [bid for bid, a in _adm.items() if a.get("lock") and a["lock"].get("until") and a["lock"]["until"] <= now]


# ───────────────────────── الترويج ─────────────────────────
def promo_for(p: dict, a: dict | None) -> dict | None:
    """إعداد الترويج الساري على بوت، أو None إن كان معطّلاً له."""
    cfg = p["promo"]
    own = (a or {}).get("promo")
    if own is False or (own is None and not cfg.get("on")):
        return None
    out = dict(cfg)
    if (a or {}).get("promo_text"):
        out["text"] = a["promo_text"]
    return out


# ───────────────────────── سجل الإدارة ─────────────────────────
async def audit(fid: int, by: int, act: str, bot: str = "", info: str = "") -> None:
    log = await db.kv_get(fid, "sys:audit", []) or []
    log.append({"at": int(time.time()), "by": by, "act": act, "bot": bot, "info": info[:200]})
    await db.kv_set(fid, "sys:audit", log[-150:])
