"""نظام العروض والخصومات المؤقتة (Flash Sales) للبائع.
يتيح تفعيل خصومات محددة بالوقت مع منع النزول تحت سعر المنصة.
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Any
from sqlalchemy import select, and_
from forge import db
from .markup import MarkupManager

log = logging.getLogger("forge.discounts")


class DiscountManager:
    """إدارة وتطبيق العروض والخصومات المؤقتة للبائع."""

    @classmethod
    async def create_flash_sale(
        cls,
        *,
        bot_id: int,
        title: str,
        scope: str,  # all | category | product | variant
        target_id: str,
        discount_type: str,  # percent | fixed
        discount_value: float,
        duration_hours: float,
    ) -> tuple[bool, str, str]:
        """ينشئ عرضاً مؤقتاً جديداً."""
        if discount_value <= 0:
            return False, "", "قيمة الخصم يجب أن تكون أكبر من الصفر."

        now = dt.datetime.utcnow()
        expires = now + dt.timedelta(hours=duration_hours)
        sale_id = f"sale_{int(now.timestamp())}_{bot_id % 1000}"

        async with db.Session() as s:
            sale = db.FlashSale(
                sale_id=sale_id,
                bot_id=bot_id,
                title=title,
                scope=scope,
                target_id=target_id,
                discount_type=discount_type,
                discount_value=discount_value,
                starts_at=now,
                expires_at=expires,
                is_active=True,
            )
            s.add(sale)
            await s.commit()

        return True, sale_id, f"تم تفعيل العرض بنجاح لمدة {int(duration_hours)} ساعة!"

    @staticmethod
    async def get_active_sales(bot_id: int) -> list[db.FlashSale]:
        """يعيد قائمة العروض النشطة حالياً في البوت."""
        now = dt.datetime.utcnow()
        async with db.Session() as s:
            rows = (await s.execute(
                select(db.FlashSale).where(
                    and_(
                        db.FlashSale.bot_id == bot_id,
                        db.FlashSale.is_active == True,
                        db.FlashSale.expires_at > now,
                    )
                ).order_by(db.FlashSale.expires_at.asc())
            )).scalars().all()
            return list(rows)

    @classmethod
    async def get_discount_for_item(
        cls,
        *,
        bot_id: int,
        category_id: str = "",
        product_id: str = "",
        variant_id: str = "",
    ) -> db.FlashSale | None:
        """يعيد أكثر عرض خصم مناسب للعنصر إن وجد."""
        sales = await cls.get_active_sales(bot_id)
        if not sales:
            return None

        # الأولوية: variant -> product -> category -> all
        for s in sales:
            if s.scope == "variant" and s.target_id == variant_id:
                return s
        for s in sales:
            if s.scope == "product" and s.target_id == product_id:
                return s
        for s in sales:
            if s.scope == "category" and s.target_id == category_id:
                return s
        for s in sales:
            if s.scope == "all":
                return s
        return None

    @classmethod
    async def calculate_discounted_price(
        cls,
        original_price_usd: float,
        *,
        bot_id: int,
        owner_id: int,
        provider_cost_usd: float = 0.0,
        tpl_key: str = "",
        category_id: str = "",
        product_id: str = "",
        variant_id: str = "",
    ) -> tuple[float, float, str, int]:
        """يحسب السعر بعد الخصم مع التحقق من عدم كسر أرضية سعر المنصة.
        يعيد (السعر_النهائي, مبلغ_الخصم, شارة_الوقت_المتبقي, الثواني_المتبقية).
        """
        sale = await cls.get_discount_for_item(
            bot_id=bot_id,
            category_id=category_id,
            product_id=product_id,
            variant_id=variant_id,
        )
        if not sale:
            return original_price_usd, 0.0, "", 0

        # حساب الخصم المبدئي
        if sale.discount_type == "percent":
            discount_amt = round(original_price_usd * (sale.discount_value / 100.0), 4)
        else:
            discount_amt = round(sale.discount_value, 4)

        discounted_price = max(0.01, round(original_price_usd - discount_amt, 4))

        # حماية سعر أرضية المنصة للبائع
        if provider_cost_usd > 0:
            floor_price = await MarkupManager.calculate_platform_cost(
                provider_cost_usd,
                owner_id=owner_id,
                tpl_key=tpl_key,
                category_id=category_id,
                product_id=product_id,
                variant_id=variant_id,
            )
            # لا يسمح بالسقوط تحت سعر المنصة
            if discounted_price < floor_price:
                discounted_price = floor_price
                discount_amt = max(0.0, original_price_usd - floor_price)

        remaining_sec = max(0, int((sale.expires_at - dt.datetime.utcnow()).total_seconds()))
        hours = remaining_sec // 3600
        mins = (remaining_sec % 3600) // 60
        badge = f"🔥 متبقي {hours}س {mins}د" if hours > 0 else f"🔥 متبقي {mins}د"

        return discounted_price, discount_amt, badge, remaining_sec
