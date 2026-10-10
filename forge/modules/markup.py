"""نظام هوامش وأرباح منصة الصانع متعدد المستويات.
قاعدة الأولويات: الأدق يسبق الأعم
Variant -> Product -> Category -> Template -> Seller -> Global Platform
"""
from __future__ import annotations

import logging
import time
from typing import Any
from forge import db

log = logging.getLogger("forge.markup")


class MarkupManager:
    """إدارة نسب وأرباح المنصة وحماية أرضية الأسعار."""

    @staticmethod
    async def get_effective_margin(
        *,
        owner_id: int,
        tpl_key: str = "",
        category_id: str = "",
        product_id: str = "",
        variant_id: str = "",
    ) -> tuple[str, float, str]:
        """يعيد (نوع_الهامش: percent/fixed, قيمة_الهامش, المستوى_المطبق)."""
        rules = await db.kv_get(0, "sys:markup_rules", {}) or {}

        # 1. Variant level
        if variant_id and f"var:{variant_id}" in rules:
            r = rules[f"var:{variant_id}"]
            return r.get("type", "percent"), float(r.get("val", 0.0)), "variant"

        # 2. Product level
        if product_id and f"prd:{product_id}" in rules:
            r = rules[f"prd:{product_id}"]
            return r.get("type", "percent"), float(r.get("val", 0.0)), "product"

        # 3. Category level
        if category_id and f"cat:{category_id}" in rules:
            r = rules[f"cat:{category_id}"]
            return r.get("type", "percent"), float(r.get("val", 0.0)), "category"

        # 4. Template level
        if tpl_key and f"tpl:{tpl_key}" in rules:
            r = rules[f"tpl:{tpl_key}"]
            return r.get("type", "percent"), float(r.get("val", 0.0)), "template"

        # 5. Specific Seller level
        if owner_id and f"usr:{owner_id}" in rules:
            r = rules[f"usr:{owner_id}"]
            return r.get("type", "percent"), float(r.get("val", 0.0)), "seller"

        # 6. Global Platform level (default 10%)
        glob = rules.get("global", {"type": "percent", "val": 10.0})
        return glob.get("type", "percent"), float(glob.get("val", 10.0)), "global"

    @classmethod
    async def calculate_platform_cost(
        cls,
        provider_cost_usd: float,
        *,
        owner_id: int,
        tpl_key: str = "",
        category_id: str = "",
        product_id: str = "",
        variant_id: str = "",
    ) -> float:
        """يحسب سعر التكلفة النهائي على البائع (تكلفة المزود + نسبة المنصة).
        هذا هو السعر الذي يراه البائع كسعر المنصة ولا يرى التكلفة الأصلية للمزود.
        """
        m_type, m_val, _ = await cls.get_effective_margin(
            owner_id=owner_id,
            tpl_key=tpl_key,
            category_id=category_id,
            product_id=product_id,
            variant_id=variant_id,
        )
        if m_type == "fixed":
            return round(provider_cost_usd + m_val, 4)
        return round(provider_cost_usd * (1.0 + (m_val / 100.0)), 4)

    @classmethod
    async def validate_seller_price(
        cls,
        seller_price_usd: float,
        provider_cost_usd: float,
        *,
        owner_id: int,
        tpl_key: str = "",
        category_id: str = "",
        product_id: str = "",
        variant_id: str = "",
    ) -> tuple[bool, float, str]:
        """يتحقق من أن سعر بيع البائع أعلى من أو يساوي سعر المنصة (أرضية السعر).
        يعيد (مقبول؟، سعر_أرضية_المنصة، رسالة_تنبيه).
        """
        floor_price = await cls.calculate_platform_cost(
            provider_cost_usd,
            owner_id=owner_id,
            tpl_key=tpl_key,
            category_id=category_id,
            product_id=product_id,
            variant_id=variant_id,
        )
        if seller_price_usd < floor_price:
            return (
                False,
                floor_price,
                f"لا يمكنك تحديد سعر أقل من سعر المنصة الإلزامي (${floor_price:.2f}).",
            )
        return True, floor_price, ""

    @staticmethod
    async def set_margin_rule(
        level_key: str,
        margin_type: str,
        margin_value: float,
        *,
        admin_id: int,
        note: str = "",
    ) -> None:
        """يضبط قاعدة هامش للمنصة مع توثيق التعديل في السجل."""
        rules = await db.kv_get(0, "sys:markup_rules", {}) or {}
        old_rule = rules.get(level_key, {"type": "percent", "val": 10.0})
        rules[level_key] = {"type": margin_type, "val": float(margin_value), "updated": int(time.time())}
        await db.kv_set(0, "sys:markup_rules", rules)

        # Audit log
        audit = await db.kv_get(0, "sys:markup_audit", []) or []
        audit.append({
            "at": int(time.time()),
            "by": admin_id,
            "target": level_key,
            "old": old_rule,
            "new": {"type": margin_type, "val": float(margin_value)},
            "note": note,
        })
        await db.kv_set(0, "sys:markup_audit", audit[-100:])

    @staticmethod
    async def get_all_rules() -> dict[str, Any]:
        """يعيد كافة قواعد وهوامش المنصة."""
        return await db.kv_get(0, "sys:markup_rules", {}) or {}

    @staticmethod
    async def get_audit_log(limit: int = 20) -> list[dict[str, Any]]:
        """يعيد آخر سجلات التعديلات على هوامش المنصة."""
        audit = await db.kv_get(0, "sys:markup_audit", []) or []
        return audit[::-1][:limit]
