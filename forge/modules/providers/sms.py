"""محرك ومزودو خدمات أرقام التفعيل الافتراضية (SMS Virtual Numbers):
- اختيار الدولة والتطبيق (Telegram, WhatsApp, Google, etc.).
- طلب الرقم، عداد الوقت، استقبال كود الـ SMS تلقائياً.
- إلغاء فوري واسترجاع الرصيد تلقائياً وذرياً في حال عدم وصول الكود.
- دعم بروتوكول SMS-Activate القياسي العالمي ومحاكي تشغيلي ذكي جاهز.
"""
from __future__ import annotations

import asyncio
import json
import logging
import urllib.parse
import urllib.request
from typing import Any

from ... import db
from .. import ledger

log = logging.getLogger("forge.sms")

# قائمة الدول المدعومة وأعلامها
SMS_COUNTRIES: dict[str, dict[str, Any]] = {
    "iq": {"name_ar": "العراق", "name_en": "Iraq", "flag": "🇮🇶", "id": 11, "mult": 1.2},
    "eg": {"name_ar": "مصر", "name_en": "Egypt", "flag": "🇪🇬", "id": 21, "mult": 1.0},
    "sa": {"name_ar": "السعودية", "name_en": "Saudi Arabia", "flag": "🇸🇦", "id": 14, "mult": 1.5},
    "us": {"name_ar": "الولايات المتحدة", "name_en": "USA", "flag": "🇺🇸", "id": 187, "mult": 0.9},
    "gb": {"name_ar": "المملكة المتحدة", "name_en": "UK", "flag": "🇬🇧", "id": 16, "mult": 1.3},
    "ru": {"name_ar": "روسيا", "name_en": "Russia", "flag": "🇷🇺", "id": 0, "mult": 0.8},
    "tr": {"name_ar": "تركيا", "name_en": "Turkey", "flag": "🇹🇷", "id": 62, "mult": 1.1},
    "id": {"name_ar": "إندونيسيا", "name_en": "Indonesia", "flag": "🇮🇩", "id": 6, "mult": 0.85},
    "ma": {"name_ar": "المغرب", "name_en": "Morocco", "flag": "🇲🇦", "id": 37, "mult": 1.1},
    "dz": {"name_ar": "الجزائر", "name_en": "Algeria", "flag": "🇩🇿", "id": 58, "mult": 1.15},
}

# قائمة التطبيقات والخدمات المدعومة وتكاليفها الأساسية بالدولار
SMS_APPS: dict[str, dict[str, Any]] = {
    "tg": {"name_ar": "تلغرام (Telegram)", "name_en": "Telegram", "emoji": "📢", "code": "tg", "base_cost": 0.40},
    "wa": {"name_ar": "واتساب (WhatsApp)", "name_en": "WhatsApp", "emoji": "💬", "code": "wa", "base_cost": 0.50},
    "tt": {"name_ar": "تيك توك (TikTok)", "name_en": "TikTok", "emoji": "🎵", "code": "lf", "base_cost": 0.25},
    "ig": {"name_ar": "انستغرام (Instagram)", "name_en": "Instagram", "emoji": "📸", "code": "ig", "base_cost": 0.20},
    "go": {"name_ar": "جوجل / جيميل (Google)", "name_en": "Google / Gmail", "emoji": "🔍", "code": "go", "base_cost": 0.30},
    "tw": {"name_ar": "إكس / تويتر (X/Twitter)", "name_en": "X (Twitter)", "emoji": "🐦", "code": "tw", "base_cost": 0.25},
    "fb": {"name_ar": "فيسبوك (Facebook)", "name_en": "Facebook", "emoji": "👤", "code": "fb", "base_cost": 0.20},
}


class BaseSMSAdapter:
    name: str = "Base"

    async def get_balance(self) -> float:
        raise NotImplementedError

    async def get_number(self, country: str, app: str) -> dict[str, Any]:
        """يعيد {'activation_id': str, 'phone': str, 'cost': float}."""
        raise NotImplementedError

    async def check_sms(self, activation_id: str) -> dict[str, Any]:
        """يعيد {'status': 'waiting' | 'received' | 'canceled', 'code': str}."""
        raise NotImplementedError

    async def cancel_number(self, activation_id: str) -> bool:
        raise NotImplementedError


class StandardSMSAdapter(BaseSMSAdapter):
    """محول لبروتوكول SMS-Activate العالمي."""

    def __init__(self, name: str, api_url: str, api_key: str):
        self.name = name
        self.api_url = api_url.strip()
        self.api_key = api_key.strip()

    async def _get(self, params: dict[str, Any]) -> str:
        params["api_key"] = self.api_key
        loop = asyncio.get_running_loop()

        def _req():
            qs = urllib.parse.urlencode(params)
            url = f"{self.api_url}?{qs}" if "?" not in self.api_url else f"{self.api_url}&{qs}"
            req = urllib.request.Request(url, headers={"User-Agent": "BotForge-SMS/1.0"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                return resp.read().decode()

        return await loop.run_in_executor(None, _req)

    async def get_balance(self) -> float:
        res = await self._get({"action": "getBalance"})
        if "ACCESS_BALANCE" in res:
            return float(res.split(":")[1])
        return 0.0

    async def get_number(self, country: str, app: str) -> dict[str, Any]:
        c_info = SMS_COUNTRIES.get(country, {"id": 0})
        a_info = SMS_APPS.get(app, {"code": "tg", "base_cost": 0.5})
        res = await self._get({
            "action": "getNumber",
            "country": c_info["id"],
            "service": a_info["code"],
        })
        # التنسيق القياسي: ACCESS_NUMBER:ID:PHONE
        if res.startswith("ACCESS_NUMBER"):
            parts = res.split(":")
            return {"activation_id": parts[1], "phone": f"+{parts[2]}", "cost": a_info["base_cost"]}
        raise RuntimeError(f"SMS Provider error: {res}")

    async def check_sms(self, activation_id: str) -> dict[str, Any]:
        res = await self._get({"action": "getStatus", "id": activation_id})
        # STATUS_OK:CODE أو STATUS_WAIT_CODE أو STATUS_CANCEL
        if res.startswith("STATUS_OK"):
            code = res.split(":")[1]
            return {"status": "received", "code": code}
        elif "STATUS_CANCEL" in res:
            return {"status": "canceled", "code": ""}
        return {"status": "waiting", "code": ""}

    async def cancel_number(self, activation_id: str) -> bool:
        res = await self._get({"action": "setStatus", "id": activation_id, "status": 8})
        return "ACCESS_CANCEL" in res


class MockSMSAdapter(BaseSMSAdapter):
    """محاكي أرقام تفعيل ذكي للتجربة الفورية وتوليد أكواد واقعية."""

    def __init__(self, name: str = "DefaultSMSMock"):
        self.name = name

    async def get_balance(self) -> float:
        return 999.0

    async def get_number(self, country: str, app: str) -> dict[str, Any]:
        c_info = SMS_COUNTRIES.get(country, {"flag": "🌐", "id": 1})
        prefixes = {"iq": "96477", "eg": "2010", "sa": "9665", "us": "1202", "gb": "447", "ru": "79"}
        pref = prefixes.get(country, "1")
        now_ms = int(asyncio.get_running_loop().time() * 1000)
        phone = f"+{pref}{str(now_ms)[-7:]}"
        act_id = f"sms_act_{now_ms}"
        return {"activation_id": act_id, "phone": phone, "cost": SMS_APPS.get(app, {}).get("base_cost", 0.40)}

    async def check_sms(self, activation_id: str) -> dict[str, Any]:
        # محاكاة وصول الكود بعد طلب الفحص
        import random
        code = str(random.randint(100000, 999999))
        return {"status": "received", "code": code}

    async def cancel_number(self, activation_id: str) -> bool:
        return True


class SMSManager:
    """مدير أرقام التفعيل وتوزيع الطلبات وحساب الأسعار."""

    @classmethod
    async def get_configured_providers(cls, bot_id: int) -> list[BaseSMSAdapter]:
        providers_conf = await db.kv_get(bot_id, "sms:providers", [])
        adapters: list[BaseSMSAdapter] = []
        if isinstance(providers_conf, list):
            for p in providers_conf:
                if p.get("on", True) and p.get("api_url") and p.get("api_key"):
                    adapters.append(StandardSMSAdapter(p.get("name", "Custom"), p["api_url"], p["api_key"]))

        if not adapters:
            adapters.append(MockSMSAdapter())
        return adapters

    @classmethod
    async def calculate_number_price(cls, bot_id: int, country: str, app: str) -> float:
        """يحسب سعر بيع الرقم للزبون بالدولار بناءً على هامش ربح البائع."""
        margin_conf = await db.kv_get(bot_id, "sms:margin", {"type": "percent", "val": 35.0})
        overrides = await db.kv_get(bot_id, "sms:overrides", {})

        key = f"{country}_{app}"
        if overrides.get(key, {}).get("price_usd"):
            return float(overrides[key]["price_usd"])

        c_info = SMS_COUNTRIES.get(country, {"mult": 1.0})
        a_info = SMS_APPS.get(app, {"base_cost": 0.40})
        base = round(a_info["base_cost"] * c_info.get("mult", 1.0), 2)

        m_type = margin_conf.get("type", "percent")
        m_val = float(margin_conf.get("val", 35.0))
        if m_type == "percent":
            return round(base * (1.0 + m_val / 100.0), 2)
        return round(base + m_val, 2)

    @classmethod
    async def rent_number_with_failover(
        cls,
        bot_id: int,
        country: str,
        app: str,
    ) -> tuple[bool, str, str, str, float]:
        """يطلب رقماً من المزود الأول، وإذا فشل يبدل للمزود الاحتياطي.
        يعيد (نجاح؟، activation_id، phone_number، provider_name، cost_usd).
        """
        providers = await cls.get_configured_providers(bot_id)
        last_error = ""

        for prov in providers:
            try:
                res = await prov.get_number(country, app)
                log.info("SMS Number rented via %s: %s (act_id: %s)", prov.name, res.get("phone"), res.get("activation_id"))
                return True, res["activation_id"], res["phone"], prov.name, float(res.get("cost", 0.0))
            except Exception as e:
                last_error = str(e)
                log.warning("SMS Provider %s failed for %s-%s: %s", prov.name, country, app, e)
                continue

        log.error("All SMS providers failed for bot %d: %s", bot_id, last_error)
        return False, "", "", "", 0.0

    @classmethod
    async def check_sms_code(cls, bot_id: int, activation_id: str, provider_name: str) -> dict[str, Any]:
        """يفحص وصول كود الـ SMS من المزود."""
        providers = await cls.get_configured_providers(bot_id)
        prov = next((p for p in providers if p.name == provider_name), providers[0])
        try:
            return await prov.check_sms(activation_id)
        except Exception as e:
            log.warning("Error checking SMS status: %s", e)
            return {"status": "waiting", "code": ""}

    @classmethod
    async def cancel_number_and_refund(
        cls,
        bot_id: int,
        user_id: int,
        order_id: str,
        reason: str = "إلغاء لعدم وصول الكود",
    ) -> tuple[bool, str, float]:
        """يلغي الرقم ويسترجع رصيد الزبون كاملاً تلقائياً وذرياً في دفتر الأستاذ."""
        async with db.Session() as s:
            res = await s.execute(db.select(db.ServiceOrder).where(db.ServiceOrder.order_id == order_id))
            ord_row = res.scalars().first()
            if not ord_row:
                return False, "الطلب غير موجود", 0.0
            if ord_row.status in ("completed", "canceled"):
                return False, f"تمت معالجة الطلب مسبقاً ({ord_row.status})", 0.0

            # 1. إلغاء لدى المزود إن أمكن
            providers = await cls.get_configured_providers(bot_id)
            prov = next((p for p in providers if p.name == ord_row.provider_name), providers[0])
            try:
                await prov.cancel_number(ord_row.provider_order_id)
            except Exception:
                pass

            # 2. استرجاع الرصيد للمستخدم ذرياً
            refund_amount = ord_row.price_user_usd
            ok_ref, tx, new_bal = await ledger.credit_user(
                bot_id,
                user_id,
                refund_amount,
                kind="sms_refund",
                ref_id=order_id,
                description=f"استرجاع رصيد رقم {ord_row.target} ({reason})",
            )
            if not ok_ref:
                return False, "فشل استرجاع الرصيد في دفتر الأستاذ", 0.0

            ord_row.status = "canceled"
            ord_row.details = dict(ord_row.details or {}, refund_reason=reason, refund_tx=tx)
            await s.commit()

        log.info("SMS Order %s canceled and refunded $%.2f to user %d", order_id, refund_amount, user_id)
        return True, "تم إلغاء الرقم واسترجاع رصيدك كاملاً بنجاح", new_bal
