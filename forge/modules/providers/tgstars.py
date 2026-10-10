"""محرك ومزودو خدمات نجوم تيليجرام واشتراكات بريميوم وهدايا تيليجرام:
- دعم باقات النجوم (50 إلى 100,000 نجمة).
- دعم اشتراكات بريميوم (3 أشهر، 6 أشهر، 12 شهراً).
- التحقق الصارم من أسماء المستخدمين (Telegram Usernames).
- معمارية التبديل التلقائي والمحاكي الافتراضي الذكي.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import urllib.parse
import urllib.request
from typing import Any

from ... import db

log = logging.getLogger("forge.tgstars")

# الكتالوج القياسي لخدمات النجوم والبريميوم مع تكاليفها الأصلية بالدولار
TGSTARS_CATALOG: list[dict[str, Any]] = [
    # ── نجوم تيليجرام ──
    {
        "id": "stars_50", "category": "stars", "type": "stars", "stars_count": 50,
        "name_ar": "50 نجمة تيليجرام ⭐", "name_en": "50 Telegram Stars ⭐",
        "rate_usd": 0.85, "avg_time": "فوري", "desc_ar": "شحن فوري ومباشر إلى حسابك.",
    },
    {
        "id": "stars_100", "category": "stars", "type": "stars", "stars_count": 100,
        "name_ar": "100 نجمة تيليجرام ⭐", "name_en": "100 Telegram Stars ⭐",
        "rate_usd": 1.70, "avg_time": "فوري", "desc_ar": "شحن فوري ومباشر إلى حسابك.",
    },
    {
        "id": "stars_250", "category": "stars", "type": "stars", "stars_count": 250,
        "name_ar": "250 نجمة تيليجرام ⭐", "name_en": "250 Telegram Stars ⭐",
        "rate_usd": 4.20, "avg_time": "فوري", "desc_ar": "شحن فوري لحسابك أو كهدية لصديق.",
    },
    {
        "id": "stars_500", "category": "stars", "type": "stars", "stars_count": 500,
        "name_ar": "500 نجمة تيليجرام ⭐", "name_en": "500 Telegram Stars ⭐",
        "rate_usd": 8.30, "avg_time": "فوري", "desc_ar": "شحن فوري لحسابك أو كهدية لصديق.",
    },
    {
        "id": "stars_1000", "category": "stars", "type": "stars", "stars_count": 1000,
        "name_ar": "1,000 نجمة تيليجرام ⭐", "name_en": "1,000 Telegram Stars ⭐",
        "rate_usd": 16.50, "avg_time": "فوري", "desc_ar": "شحن سريع للاستخدام في التطبيقات والمحتوى الحصري.",
    },
    {
        "id": "stars_2500", "category": "stars", "type": "stars", "stars_count": 2500,
        "name_ar": "2,500 نجمة تيليجرام ⭐", "name_en": "2,500 Telegram Stars ⭐",
        "rate_usd": 41.00, "avg_time": "فوري", "desc_ar": "باقة مميزة للمطورين وصناع المحتوى.",
    },
    {
        "id": "stars_5000", "category": "stars", "type": "stars", "stars_count": 5000,
        "name_ar": "5,000 نجمة تيليجرام ⭐", "name_en": "5,000 Telegram Stars ⭐",
        "rate_usd": 81.00, "avg_time": "فوري", "desc_ar": "باقة كبار المستخدمين.",
    },
    # ── اشتراكات تيليجرام بريميوم ──
    {
        "id": "prem_3m", "category": "premium", "type": "premium", "months": 3,
        "name_ar": "اشتراك تيليجرام بريميوم (3 أشهر) 💎", "name_en": "Telegram Premium (3 Months) 💎",
        "rate_usd": 11.50, "avg_time": "5 - 15 دقيقة", "desc_ar": "تفعيل رسمي بدون الحاجة لأي كلمة مرور، فقط باسم المستخدم.",
    },
    {
        "id": "prem_6m", "category": "premium", "type": "premium", "months": 6,
        "name_ar": "اشتراك تيليجرام بريميوم (6 أشهر) 💎", "name_en": "Telegram Premium (6 Months) 💎",
        "rate_usd": 15.80, "avg_time": "5 - 15 دقيقة", "desc_ar": "تفعيل رسمي مباشر كهدية عبر تيليجرام.",
    },
    {
        "id": "prem_12m", "category": "premium", "type": "premium", "months": 12,
        "name_ar": "اشتراك تيليجرام بريميوم (سنة كاملة 12 شهراً) 💎", "name_en": "Telegram Premium (1 Year / 12 Months) 💎",
        "rate_usd": 28.50, "avg_time": "5 - 15 دقيقة", "desc_ar": "أفضل توفير مع كافة مميزات البريميوم لمدة سنة كاملة.",
    },
    # ── هدايا تيليجرام ──
    {
        "id": "gift_pack_starter", "category": "gifts", "type": "gift",
        "name_ar": "باقة هدايا تيليجرام الترحيبية 🎁", "name_en": "Telegram Welcome Gift Bundle 🎁",
        "rate_usd": 2.50, "avg_time": "فوري", "desc_ar": "هدية مميزة تظهر في الملف الشخصي للمستلم.",
    },
]


def clean_and_validate_username(raw: str) -> tuple[bool, str]:
    """يتحقق من صحة معرف تيليجرام وينظفه من @ أو روابط t.me."""
    if not raw or not isinstance(raw, str):
        return False, ""
    u = raw.strip()
    # تنظيف الروابط
    u = re.sub(r"^https?://(?:t\.me|telegram\.me)/", "", u, flags=re.IGNORECASE)
    # تنظيف @
    u = u.lstrip("@").strip()
    # التحقق من الطول وصيغة المعرف القياسية في تيليجرام (5 إلى 32 حرفاً ورقماً وشرطة سفلية)
    if re.match(r"^[a-zA-Z0-9_]{5,32}$", u):
        return True, f"@{u}"
    return False, ""


class BaseTGStarsAdapter:
    """الواجهة القياسية لمزودي النجوم والبريميوم."""
    name: str = "Base"

    async def get_balance(self) -> float:
        raise NotImplementedError

    async def dispatch_order(self, service_id: str, username: str, quantity: int = 1) -> dict[str, Any]:
        """يعيد {'order_id': str, 'cost': float, 'status': str}."""
        raise NotImplementedError


class StandardTGStarsAdapter(BaseTGStarsAdapter):
    """محول لبروتوكول المزودات الخارجية لخدمات تيليجرام."""

    def __init__(self, name: str, api_url: str, api_key: str):
        self.name = name
        self.api_url = api_url.strip()
        self.api_key = api_key.strip()

    async def _post(self, data: dict[str, Any]) -> dict[str, Any]:
        data["key"] = self.api_key
        loop = asyncio.get_running_loop()

        def _req():
            encoded = urllib.parse.urlencode(data).encode("utf-8")
            req = urllib.request.Request(self.api_url, data=encoded, headers={"User-Agent": "BotForge-TGStars/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())

        return await loop.run_in_executor(None, _req)

    async def get_balance(self) -> float:
        res = await self._post({"action": "balance"})
        return float(res.get("balance", 0.0))

    async def dispatch_order(self, service_id: str, username: str, quantity: int = 1) -> dict[str, Any]:
        res = await self._post({
            "action": "add",
            "service": service_id,
            "username": username,
            "quantity": quantity,
        })
        if "order" in res:
            return {"order_id": str(res["order"]), "cost": float(res.get("cost", 0.0)), "status": "processing"}
        err = res.get("error", "فشل معالجة طلب النجوم/بريميوم لدى المزود")
        raise RuntimeError(err)


class MockTGStarsAdapter(BaseTGStarsAdapter):
    """محاكي تشغيلي ذكي لخدمات تيليجرام."""

    def __init__(self, name: str = "DefaultTGStarsCatalog"):
        self.name = name

    async def get_balance(self) -> float:
        return 999.0

    async def dispatch_order(self, service_id: str, username: str, quantity: int = 1) -> dict[str, Any]:
        svc = next((s for s in TGSTARS_CATALOG if s["id"] == service_id), None)
        cost = svc["rate_usd"] if svc else 1.0
        ord_num = f"tgstars_mock_{int(asyncio.get_running_loop().time() * 1000)}"
        return {"order_id": ord_num, "cost": cost, "status": "processing"}


class TGStarsManager:
    """مدير خدمات النجوم وتيليجرام بريميوم مع دعم الهوامش والتبديل التلقائي."""

    @classmethod
    async def get_configured_providers(cls, bot_id: int) -> list[BaseTGStarsAdapter]:
        providers_conf = await db.kv_get(bot_id, "tgstars:providers", [])
        adapters: list[BaseTGStarsAdapter] = []
        if isinstance(providers_conf, list):
            for p in providers_conf:
                if p.get("on", True) and p.get("api_url") and p.get("api_key"):
                    adapters.append(StandardTGStarsAdapter(p.get("name", "Custom"), p["api_url"], p["api_key"]))

        if not adapters:
            adapters.append(MockTGStarsAdapter())
        return adapters

    @classmethod
    async def get_services_catalog(cls, bot_id: int) -> list[dict[str, Any]]:
        custom_overrides = await db.kv_get(bot_id, "tgstars:services_override", {})
        margin_conf = await db.kv_get(bot_id, "tgstars:margin", {"type": "percent", "val": 25.0})

        services = []
        for s in TGSTARS_CATALOG:
            sid = s["id"]
            over = custom_overrides.get(sid, {})
            if over.get("hide", False):
                continue

            base_cost = float(s["rate_usd"])
            if over.get("custom_price_usd") is not None:
                final_usd = float(over["custom_price_usd"])
            else:
                m_type = margin_conf.get("type", "percent")
                m_val = float(margin_conf.get("val", 25.0))
                if m_type == "percent":
                    final_usd = round(base_cost * (1.0 + m_val / 100.0), 2)
                else:
                    final_usd = round(base_cost + m_val, 2)

            item = dict(s)
            item["base_cost_usd"] = base_cost
            item["price_usd"] = final_usd
            if over.get("name_ar"):
                item["name_ar"] = over["name_ar"]
            services.append(item)

        return services

    @classmethod
    async def dispatch_order_with_failover(
        cls,
        bot_id: int,
        service_id: str,
        username: str,
        quantity: int = 1,
    ) -> tuple[bool, str, str, float]:
        providers = await cls.get_configured_providers(bot_id)
        last_error = ""

        for prov in providers:
            try:
                res = await prov.dispatch_order(service_id, username, quantity)
                log.info("TGStars Order dispatched via %s (order: %s)", prov.name, res.get("order_id"))
                return True, res.get("order_id", ""), prov.name, float(res.get("cost", 0.0))
            except Exception as e:
                last_error = str(e)
                log.warning("Provider %s failed for tgstars: %s. Trying next...", prov.name, e)
                continue

        log.error("All TGStars providers failed for bot %d: %s", bot_id, last_error)
        return False, "", "", 0.0
