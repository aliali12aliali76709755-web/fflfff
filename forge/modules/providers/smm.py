"""محرك ومزودو خدمات زيادة التفاعل (SMM Panels):
- معمارية الواجهة الموحدة (Base Adapter).
- دعم بروتوكول SMM API v2 القياسي العالمي.
- دعم ربط أكثر من مزود والتبديل التلقائي عند التعطل أو نفاد الرصيد (Failover).
- مزود افتراضي ذكي (Default Mock Adapter) جاهز للتشغيل والتجربة الفورية.
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

log = logging.getLogger("forge.smm")

# المنصات المدعومة وأيقوناتها
PLATFORMS: dict[str, dict[str, str]] = {
    "instagram": {"name_ar": "انستغرام", "name_en": "Instagram", "emoji": "📸"},
    "tiktok": {"name_ar": "تيك توك", "name_en": "TikTok", "emoji": "🎵"},
    "telegram": {"name_ar": "تلغرام", "name_en": "Telegram", "emoji": "📢"},
    "youtube": {"name_ar": "يوتيوب", "name_en": "YouTube", "emoji": "🎬"},
    "x": {"name_ar": "إكس (تويتر)", "name_en": "X (Twitter)", "emoji": "🐦"},
    "facebook": {"name_ar": "فيسبوك", "name_en": "Facebook", "emoji": "👤"},
}

# الخدمات الافتراضية الجاهزة في المحاكي القياسي (أسعار التكلفة الأصلية بالدولار لكل 1000)
MOCK_CATALOG: list[dict[str, Any]] = [
    # انستغرام
    {
        "id": "ig_followers_fast", "platform": "instagram", "category": "followers",
        "name_ar": "متابعين انستغرام حقيقيين مع ضمان", "name_en": "Instagram Real Followers with Refill",
        "rate_per_1k": 0.85, "min": 100, "max": 50000, "refill": True, "avg_time": "15 دقيقة",
        "desc_ar": "حسابات نشطة بجودة عالية وضمان تعويض 30 يوماً.",
    },
    {
        "id": "ig_likes_hq", "platform": "instagram", "category": "likes",
        "name_ar": "إعجابات انستغرام سريعة جداً", "name_en": "Instagram High-Speed Likes",
        "rate_per_1k": 0.18, "min": 50, "max": 20000, "refill": False, "avg_time": "فوري",
        "desc_ar": "بدء فوري وبدون نقص.",
    },
    {
        "id": "ig_views_reels", "platform": "instagram", "category": "views",
        "name_ar": "مشاهدات ريلز واستوري انستغرام", "name_en": "Instagram Reels & Video Views",
        "rate_per_1k": 0.05, "min": 500, "max": 500000, "refill": False, "avg_time": "فوري",
        "desc_ar": "تساعد في تصدر حركة إكسبلور.",
    },
    # تيك توك
    {
        "id": "tt_views_hq", "platform": "tiktok", "category": "views",
        "name_ar": "مشاهدات تيك توك سريعة جداً", "name_en": "TikTok Instant Video Views",
        "rate_per_1k": 0.04, "min": 1000, "max": 1000000, "refill": False, "avg_time": "فوري",
        "desc_ar": "بدء فوري خلال دقيقة وسرعة تصل لـ 500k يومياً.",
    },
    {
        "id": "tt_followers_safe", "platform": "tiktok", "category": "followers",
        "name_ar": "متابعين تيك توك جودة عالية", "name_en": "TikTok High Quality Followers",
        "rate_per_1k": 1.20, "min": 100, "max": 20000, "refill": True, "avg_time": "ساعة",
        "desc_ar": "متابعين آمنين على الحساب مع ضمان تعويض.",
    },
    {
        "id": "tt_likes_real", "platform": "tiktok", "category": "likes",
        "name_ar": "إعجابات تيك توك حقيقية", "name_en": "TikTok Real Post Likes",
        "rate_per_1k": 0.35, "min": 100, "max": 50000, "refill": False, "avg_time": "10 دقائق",
        "desc_ar": "تفاعل حقيقي للفيديوهات.",
    },
    # تلغرام
    {
        "id": "tg_members_channel", "platform": "telegram", "category": "followers",
        "name_ar": "أعضاء قنوات ومجموعات تلغرام", "name_en": "Telegram Channel / Group Members",
        "rate_per_1k": 0.65, "min": 100, "max": 50000, "refill": True, "avg_time": "30 دقيقة",
        "desc_ar": "أعضاء ذوو جودة عالية وثبات ممتاز مع ضمان 30 يوماً.",
    },
    {
        "id": "tg_views_posts", "platform": "telegram", "category": "views",
        "name_ar": "مشاهدات منشورات تلغرام (آخر 5 منشورات)", "name_en": "Telegram Post Views",
        "rate_per_1k": 0.03, "min": 100, "max": 100000, "refill": False, "avg_time": "فوري",
        "desc_ar": "مشاهدات للمنشورات بضغطة واحدة وبدء فوري.",
    },
    {
        "id": "tg_reactions_mix", "platform": "telegram", "category": "likes",
        "name_ar": "تفاعلات ريأكشن تلغرام (إيجابي 👍🔥❤️)", "name_en": "Telegram Post Reactions (Positive)",
        "rate_per_1k": 0.12, "min": 50, "max": 10000, "refill": False, "avg_time": "فوري",
        "desc_ar": "ريأكشنات متنوعة للمنشورات.",
    },
    # يوتيوب
    {
        "id": "yt_views_hq", "platform": "youtube", "category": "views",
        "name_ar": "مشاهدات يوتيوب جودة عالية (أمان تام)", "name_en": "YouTube High Retention Views",
        "rate_per_1k": 1.40, "min": 500, "max": 100000, "refill": True, "avg_time": "ساعة",
        "desc_ar": "مشاهدات آمنة مع نسبة بقاء مرتفعة ومناسبة لتحقيق الشروط.",
    },
    {
        "id": "yt_subs_guaranteed", "platform": "youtube", "category": "followers",
        "name_ar": "مشتركين يوتيوب مع ضمان تعويض", "name_en": "YouTube Subscribers Guaranteed",
        "rate_per_1k": 8.50, "min": 50, "max": 5000, "refill": True, "avg_time": "24 ساعة",
        "desc_ar": "مشتركون ثابتون مع زر إعادة تعويض في حال النقص.",
    },
]


def validate_target_url(platform: str, url: str) -> bool:
    """يتحقق من صحة الرابط المدخل للمنصة بدون طلب أي كلمات مرور."""
    if not url or not isinstance(url, str):
        return False
    u = url.strip()
    if not (u.startswith("http://") or u.startswith("https://") or u.startswith("@") or u.startswith("t.me/")):
        return False

    if platform == "telegram":
        return any(x in u for x in ("t.me/", "telegram.me/", "@"))
    elif platform == "instagram":
        return "instagram.com" in u
    elif platform == "tiktok":
        return "tiktok.com" in u
    elif platform == "youtube":
        return any(x in u for x in ("youtube.com", "youtu.be"))
    elif platform == "x":
        return any(x in u for x in ("x.com", "twitter.com"))
    elif platform == "facebook":
        return any(x in u for x in ("facebook.com", "fb.watch", "fb.com"))
    return True


class BaseSMMAdapter:
    """الواجهة الموحدة لأي مزود خدمات SMM."""
    name: str = "Base"

    async def get_balance(self) -> float:
        raise NotImplementedError

    async def get_services(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    async def add_order(self, service_id: str, link: str, quantity: int) -> dict[str, Any]:
        """يعيد قاموساً يحتوي على: {'order_id': str, 'cost': float, 'status': str}."""
        raise NotImplementedError

    async def get_status(self, order_id: str) -> dict[str, Any]:
        """يعيد قاموساً يحتوي على: {'status': str, 'remains': int, 'start_count': int}."""
        raise NotImplementedError


class StandardSMMAdapter(BaseSMMAdapter):
    """محول لبروتوكول SMM Panel v2 القياسي العالمي."""

    def __init__(self, name: str, api_url: str, api_key: str):
        self.name = name
        self.api_url = api_url.strip()
        self.api_key = api_key.strip()

    async def _post(self, data: dict[str, Any]) -> dict[str, Any]:
        data["key"] = self.api_key
        loop = asyncio.get_running_loop()

        def _req():
            encoded = urllib.parse.urlencode(data).encode("utf-8")
            req = urllib.request.Request(self.api_url, data=encoded, headers={"User-Agent": "BotForge/1.0"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                return json.loads(resp.read().decode())

        return await loop.run_in_executor(None, _req)

    async def get_balance(self) -> float:
        res = await self._post({"action": "balance"})
        return float(res.get("balance", 0.0))

    async def get_services(self) -> list[dict[str, Any]]:
        res = await self._post({"action": "services"})
        if isinstance(res, list):
            return res
        return []

    async def add_order(self, service_id: str, link: str, quantity: int) -> dict[str, Any]:
        res = await self._post({
            "action": "add",
            "service": service_id,
            "link": link,
            "quantity": quantity,
        })
        if "order" in res:
            return {"order_id": str(res["order"]), "status": "pending", "cost": 0.0}
        error_msg = res.get("error", "فشل إرسال الطلب للمزود")
        raise RuntimeError(error_msg)

    async def get_status(self, order_id: str) -> dict[str, Any]:
        res = await self._post({"action": "status", "order": order_id})
        return {
            "status": str(res.get("status", "pending")).lower(),
            "remains": int(res.get("remains", 0)),
            "start_count": int(res.get("start_count", 0)),
        }


class MockSMMAdapter(BaseSMMAdapter):
    """محاكي تشغيلي ذكي جاهز للاستخدام الفوري وللاختبار حتى إدخال المفاتيح."""

    def __init__(self, name: str = "DefaultCatalog"):
        self.name = name

    async def get_balance(self) -> float:
        return 999.0

    async def get_services(self) -> list[dict[str, Any]]:
        return list(MOCK_CATALOG)

    async def add_order(self, service_id: str, link: str, quantity: int) -> dict[str, Any]:
        svc = next((s for s in MOCK_CATALOG if s["id"] == service_id), None)
        cost_per_1k = svc["rate_per_1k"] if svc else 1.0
        cost = round((quantity / 1000.0) * cost_per_1k, 4)
        order_num = f"mock_{int(asyncio.get_running_loop().time() * 1000)}"
        return {"order_id": order_num, "cost": cost, "status": "processing"}

    async def get_status(self, order_id: str) -> dict[str, Any]:
        return {"status": "completed", "remains": 0, "start_count": 100}


class SMMManager:
    """مدير مزودي خدمات التفاعل وتوزيع الطلبات مع التبديل التلقائي (Failover)."""

    @classmethod
    async def get_configured_providers(cls, bot_id: int) -> list[BaseSMMAdapter]:
        """يجلب قائمة المزودين المهيئين للبوت أو المزود الافتراضي."""
        providers_conf = await db.kv_get(bot_id, "smm:providers", [])
        adapters: list[BaseSMMAdapter] = []
        if isinstance(providers_conf, list):
            for p in providers_conf:
                if p.get("on", True) and p.get("api_url") and p.get("api_key"):
                    adapters.append(StandardSMMAdapter(p.get("name", "Custom"), p["api_url"], p["api_key"]))

        # إذا لم يتم ربط أي مزود مخصص، نستخدم المحاكي القياسي الافتراضي
        if not adapters:
            adapters.append(MockSMMAdapter())
        return adapters

    @classmethod
    async def get_services_catalog(cls, bot_id: int) -> list[dict[str, Any]]:
        """يجلب قائمة الخدمات المتاحة مع هوامش أرباح البائع المطبقة."""
        # 1. إعدادات البائع المخصصة للخدمات
        custom_overrides = await db.kv_get(bot_id, "smm:services_override", {})
        # 2. هامش الربح العام للبائع
        margin_conf = await db.kv_get(bot_id, "smm:margin", {"type": "percent", "val": 30.0})

        catalog = list(MOCK_CATALOG)
        services = []
        for s in catalog:
            sid = s["id"]
            over = custom_overrides.get(sid, {})
            if over.get("hide", False):
                continue

            base_cost = float(s["rate_per_1k"])
            # حساب سعر البيع بإضافة هامش ربح البائع
            if over.get("custom_price_usd") is not None:
                final_usd = float(over["custom_price_usd"])
            else:
                m_type = margin_conf.get("type", "percent")
                m_val = float(margin_conf.get("val", 30.0))
                if m_type == "percent":
                    final_usd = round(base_cost * (1.0 + m_val / 100.0), 4)
                else:
                    final_usd = round(base_cost + m_val, 4)

            item = dict(s)
            item["base_cost_per_1k"] = base_cost
            item["price_per_1k_usd"] = final_usd
            if over.get("name_ar"):
                item["name_ar"] = over["name_ar"]
            if over.get("min"):
                item["min"] = over["min"]
            if over.get("max"):
                item["max"] = over["max"]
            services.append(item)

        return services

    @classmethod
    async def dispatch_order_with_failover(
        cls,
        bot_id: int,
        service_id: str,
        link: str,
        quantity: int,
    ) -> tuple[bool, str, str, float]:
        """يرسل الطلب للمزود الأول، وإذا فشل يبدل تلقائياً للمزود الاحتياطي (Failover).
        يعيد (نجاح؟، معرّف_طلب_المزود، اسم_المزود، تكلفة_المزود_بالدولار).
        """
        providers = await cls.get_configured_providers(bot_id)
        last_error = ""

        for prov in providers:
            try:
                res = await prov.add_order(service_id, link, quantity)
                log.info("SMM Order dispatched via provider %s (order: %s)", prov.name, res.get("order_id"))
                return True, res.get("order_id", ""), prov.name, float(res.get("cost", 0.0))
            except Exception as e:
                last_error = str(e)
                log.warning("Provider %s failed for service %s: %s. Trying next...", prov.name, service_id, e)
                continue

        log.error("All SMM providers failed for bot %d service %s: %s", bot_id, service_id, last_error)
        return False, "", "", 0.0
