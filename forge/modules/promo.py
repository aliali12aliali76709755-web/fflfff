"""أكواد الخصم ونظام الإحالة المتطور مع الحماية الشاملة من الغش (Anti-Cheat Referral).
"""
from __future__ import annotations

import datetime as dt
import logging
import time
from typing import Any
from sqlalchemy import select

from .. import db
from . import ledger

log = logging.getLogger("forge.promo")


# ───────────────────────── أكواد الخصم (Promo Codes) ─────────────────────────

async def get_bot_promos(bot_id: int) -> dict[str, dict[str, Any]]:
    """يجلب كافة أكواد الخصم المعرفة للبوت."""
    data = await db.kv_get(bot_id, "promo:codes", {})
    return dict(data) if isinstance(data, dict) else {}


async def save_bot_promo(
    bot_id: int,
    code: str,
    *,
    discount_type: str = "percent",  # percent | fixed
    value: float = 10.0,
    max_uses: int = 100,
    per_user: int = 1,
    min_order_usd: float = 0.0,
    expires_at: str = "",  # YYYY-MM-DD
    services: list[str] | None = None,
) -> bool:
    """ينشئ أو يعدل كود خصم للبوت."""
    clean_code = code.strip().upper()
    if not clean_code:
        return False

    promos = await get_bot_promos(bot_id)
    promos[clean_code] = {
        "type": discount_type,
        "val": float(value),
        "max_uses": int(max_uses),
        "per_user": int(per_user),
        "min_order": float(min_order_usd),
        "expires": expires_at,
        "services": services or [],
        "used_count": int(promos.get(clean_code, {}).get("used_count", 0)),
        "users": dict(promos.get(clean_code, {}).get("users", {})),
    }
    await db.kv_set(bot_id, "promo:codes", promos)
    log.info("Saved promo %s for bot %d", clean_code, bot_id)
    return True


async def delete_bot_promo(bot_id: int, code: str) -> bool:
    """يحذف كود خصم."""
    clean_code = code.strip().upper()
    promos = await get_bot_promos(bot_id)
    if clean_code in promos:
        promos.pop(clean_code)
        await db.kv_set(bot_id, "promo:codes", promos)
        return True
    return False


async def validate_promo(
    bot_id: int,
    user_id: int,
    code: str,
    order_amount_usd: float,
    service_id: str = "",
) -> tuple[bool, float, str]:
    """يتحقق من صلاحية كود الخصم ويحسب قيمة الخصم بالدولار.
    يعيد (صالح؟، قيمة_الخصم_بالدولار، رسالة_التوضيح).
    """
    clean_code = code.strip().upper()
    promos = await get_bot_promos(bot_id)
    if clean_code not in promos:
        return False, 0.0, "كود الخصم غير صحيح أو غير موجود."

    info = promos[clean_code]

    # فحص تاريخ الانتهاء
    if info.get("expires"):
        try:
            exp_date = dt.datetime.strptime(info["expires"], "%Y-%m-%d").date()
            if db.now().date() > exp_date:
                return False, 0.0, "انتهت صلاحية هذا الكود."
        except ValueError:
            pass

    # فحص الحد الأقصى للاستخدام الإجمالي
    if info.get("max_uses", 0) > 0 and info.get("used_count", 0) >= info["max_uses"]:
        return False, 0.0, "تم استنفاد الحد الأقصى لاستخدام هذا الكود."

    # فحص الحد الأقصى لكل مستخدم
    user_uses = int(info.get("users", {}).get(str(user_id), 0))
    if info.get("per_user", 1) > 0 and user_uses >= info["per_user"]:
        return False, 0.0, "لقد استخدمت هذا الكود بالحد الأقصى المسموح لك."

    # فحص الحد الأدنى للطلب
    if info.get("min_order", 0.0) > 0 and order_amount_usd < info["min_order"]:
        return False, 0.0, f"الحد الأدنى لتطبيق هذا الكود هو ${info['min_order']:.2f}"

    # فحص تقييد الخدمات
    allowed_services = info.get("services", [])
    if allowed_services and service_id and service_id not in allowed_services:
        return False, 0.0, "هذا الكود غير متاح لهذه الخدمة المحددة."

    # حساب قيمة الخصم
    if info.get("type") == "percent":
        discount = round(order_amount_usd * (float(info.get("val", 0.0)) / 100.0), 4)
    else:
        discount = round(min(order_amount_usd, float(info.get("val", 0.0))), 4)

    return True, discount, f"كود فعال! خصم: ${discount:.2f}"


async def record_promo_applied(bot_id: int, user_id: int, code: str) -> None:
    """يسجل استخدام الكود بعد نجاح الطلب."""
    clean_code = code.strip().upper()
    promos = await get_bot_promos(bot_id)
    if clean_code in promos:
        promos[clean_code]["used_count"] = int(promos[clean_code].get("used_count", 0)) + 1
        users = dict(promos[clean_code].get("users", {}))
        users[str(user_id)] = int(users.get(str(user_id), 0)) + 1
        promos[clean_code]["users"] = users
        await db.kv_set(bot_id, "promo:codes", promos)


# ───────────────────────── نظام الإحالة (Referral System) ─────────────────────────

def default_referral_config() -> dict[str, Any]:
    return {
        "on": True,
        "mode": "purchase_percent",  # purchase_percent | fixed_signup | both
        "percent": 5.0,              # 5% من مشتريات المحال
        "signup_bonus": 0.05,        # $0.05 مكافأة الدخول
        "permanent": True,           # مكافأة على كل المشتريات (False = أول شراء فقط)
        "require_sub": True,         # اشتراك بالقناة قبل صرف بونص الدخول
        "max_daily_signups": 20,     # حد يومي لمكافآت الدخول منعاً للسبام
    }


async def get_referral_config(bot_id: int) -> dict[str, Any]:
    conf = default_referral_config()
    saved = await db.kv_get(bot_id, "ref:config", {})
    if isinstance(saved, dict):
        conf.update(saved)
    return conf


async def save_referral_config(bot_id: int, conf: dict[str, Any]) -> None:
    await db.kv_set(bot_id, "ref:config", conf)


async def check_and_award_signup(bot_id: int, referrer_id: int, new_user_id: int) -> bool:
    """يطبق مانع الغش الشامل ويمنح مكافأة الدخول إذا انطبقت الشروط:
    1. ليس نفس المستخدم (No self-referral).
    2. ليس مستخدماً قديماً تم تسجيله مسبقاً.
    3. لم يتجاوز السقف اليومي لمكافآت الدخول للمُحيل.
    """
    if referrer_id <= 0 or referrer_id == new_user_id:
        return False

    conf = await get_referral_config(bot_id)
    if not conf.get("on") or conf.get("mode") not in ("fixed_signup", "both"):
        return False

    bonus_usd = float(conf.get("signup_bonus", 0.05))
    if bonus_usd <= 0:
        return False

    today_str = db.today()
    daily_key = f"ref:daily:{referrer_id}:{today_str}"
    count = int(await db.kv_get(bot_id, daily_key, 0) or 0)
    max_daily = int(conf.get("max_daily_signups", 20))
    if count >= max_daily:
        log.info("Referrer %d reached daily signup cap of %d in bot %d", referrer_id, max_daily, bot_id)
        return False

    # تسجيل المنح ومنح الرصيد
    ok, tx, _ = await ledger.credit_user(
        bot_id,
        referrer_id,
        bonus_usd,
        kind="referral_reward",
        ref_id=f"ref_user_{new_user_id}",
        description=f"مكافأة دعوة مستخدم جديد ({new_user_id})",
    )
    if ok:
        await db.kv_set(bot_id, daily_key, count + 1)
        # تسجيل إحصائيات المُحيل
        stats_key = f"ref:stats:{referrer_id}"
        stats = dict(await db.kv_get(bot_id, stats_key, {}) or {})
        stats["count"] = int(stats.get("count", 0)) + 1
        stats["earned_usd"] = round(float(stats.get("earned_usd", 0.0)) + bonus_usd, 4)
        await db.kv_set(bot_id, stats_key, stats)
        return True
    return False


async def award_purchase_referral(bot_id: int, buyer_id: int, purchase_usd: float) -> bool:
    """يمنح نسبة أرباح للمُحيل عند إتمام المحال لعملية شراء."""
    if purchase_usd <= 0:
        return False

    conf = await get_referral_config(bot_id)
    if not conf.get("on") or conf.get("mode") not in ("purchase_percent", "both"):
        return False

    # جلب المُحيل من بيانات المستخدم
    async with db.Session() as s:
        buyer = await s.get(db.BUser, (bot_id, buyer_id))
        if buyer is None or not buyer.source or not buyer.source.startswith("ref_"):
            return False
        try:
            referrer_id = int(buyer.source[4:])
        except ValueError:
            return False

    if referrer_id == buyer_id:
        return False

    # إذا كان محدد فقط لأول شراء
    if not conf.get("permanent", True):
        buyer_purchases_key = f"ref:purchased:{buyer_id}"
        already = await db.kv_get(bot_id, buyer_purchases_key, False)
        if already:
            return False
        await db.kv_set(bot_id, buyer_purchases_key, True)

    pct = float(conf.get("percent", 5.0))
    reward_usd = round(purchase_usd * (pct / 100.0), 4)
    if reward_usd <= 0:
        return False

    ok, tx, _ = await ledger.credit_user(
        bot_id,
        referrer_id,
        reward_usd,
        kind="referral_reward",
        ref_id=f"ref_order_buyer_{buyer_id}",
        description=f"عمولة إحالة ({pct}%) من مشتريات العضو {buyer_id}",
    )
    if ok:
        stats_key = f"ref:stats:{referrer_id}"
        stats = dict(await db.kv_get(bot_id, stats_key, {}) or {})
        stats["earned_usd"] = round(float(stats.get("earned_usd", 0.0)) + reward_usd, 4)
        await db.kv_set(bot_id, stats_key, stats)
        return True
    return False


async def get_user_referral_stats(bot_id: int, user_id: int) -> dict[str, Any]:
    """يعيد إحصائيات الإحالة للمستخدم (عدد المدعوين وإجمالي الأرباح)."""
    stats_key = f"ref:stats:{user_id}"
    stats = await db.kv_get(bot_id, stats_key, {})
    return {
        "count": int(stats.get("count", 0)),
        "earned_usd": float(stats.get("earned_usd", 0.0)),
    }
