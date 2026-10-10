"""محرك وخدمات شحن الألعاب والاشتراكات الرقمية والبطاقات:
- ألعاب (ببجي، فري فاير، روبلوكس، كود).
- اشتراكات (نتفلكس، سبوتيفاي، يوتيوب، ChatGPT).
- بطاقات وقسائم رقمية مع مخزون آلي (Vouchers Stock) أو طابور معالجة آلي (30 - 120 دقيقة).
- إشعار فوري للبائع مع أزرار التنفيذ السريع وتسليم الأكواد.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from ... import db
from .. import ledger

log = logging.getLogger("forge.digital")

DIGITAL_CATALOG: list[dict[str, Any]] = [
    # ── ألعاب (Game Top-Up) ──
    {
        "id": "pubg_60uc", "category": "games", "name_ar": "ببجي موبايل 60 UC 🎮", "name_en": "PUBG Mobile 60 UC",
        "field_ar": "الآيدي (Player ID)", "field_en": "Player ID", "rate_usd": 0.95,
        "desc_ar": "شحن شدات ببجي الرسمية عبر الآيدي.",
    },
    {
        "id": "pubg_325uc", "category": "games", "name_ar": "ببجي موبايل 325 UC 🎮", "name_en": "PUBG Mobile 325 UC",
        "field_ar": "الآيدي (Player ID)", "field_en": "Player ID", "rate_usd": 4.60,
        "desc_ar": "شحن شدات ببجي الرسمية عبر الآيدي.",
    },
    {
        "id": "pubg_660uc", "category": "games", "name_ar": "ببجي موبايل 660 UC (رويال باس) 🎮", "name_en": "PUBG Mobile 660 UC",
        "field_ar": "الآيدي (Player ID)", "field_en": "Player ID", "rate_usd": 9.20,
        "desc_ar": "شحن رويال باس وباقات ببجي الرسمية.",
    },
    {
        "id": "ff_100d", "category": "games", "name_ar": "فري فاير 100 جوهرة 💎", "name_en": "Free Fire 100 Diamonds",
        "field_ar": "الآيدي (Player ID)", "field_en": "Player ID", "rate_usd": 0.90,
        "desc_ar": "شحن جواهر فري فاير الرسمية عبر الآيدي.",
    },
    {
        "id": "ff_520d", "category": "games", "name_ar": "فري فاير 520 جوهرة 💎", "name_en": "Free Fire 520 Diamonds",
        "field_ar": "الآيدي (Player ID)", "field_en": "Player ID", "rate_usd": 4.50,
        "desc_ar": "شحن جواهر فري فاير الرسمية عبر الآيدي.",
    },
    {
        "id": "roblox_800r", "category": "games", "name_ar": "روبلوكس 800 روبوكس (Robux) 🟩", "name_en": "Roblox 800 Robux",
        "field_ar": "اسم المستخدم (Username)", "field_en": "Roblox Username", "rate_usd": 9.50,
        "desc_ar": "شحن روبوكس رسمي لحسابك في روبلوكس.",
    },
    # ── اشتراكات التطبيقات (App Subscriptions) ──
    {
        "id": "net_1m", "category": "apps", "name_ar": "نتفلكس بريميوم 4K (شهر واحد) 🎬", "name_en": "Netflix Premium 4K (1 Month)",
        "field_ar": "البريد الإلكتروني أو رقم الواتساب", "field_en": "Email or WhatsApp", "rate_usd": 3.80,
        "desc_ar": "ملف خاص وضمان كامل طوال مدة الاشتراك.",
    },
    {
        "id": "spot_1m", "category": "apps", "name_ar": "سبوتيفاي بريميوم (شهر واحد) 🎵", "name_en": "Spotify Premium (1 Month)",
        "field_ar": "البريد الإلكتروني لحسابك", "field_en": "Account Email", "rate_usd": 2.20,
        "desc_ar": "ترقية حسابك الخاص إلى بريميوم بدون إعلانات وبأعلى جودة.",
    },
    {
        "id": "yt_1m", "category": "apps", "name_ar": "يوتيوب بريميوم (شهر واحد) 🔴", "name_en": "YouTube Premium (1 Month)",
        "field_ar": "بريد الجيميل (Gmail)", "field_en": "Gmail Address", "rate_usd": 1.90,
        "desc_ar": "دعوة رسمية لعائلتك بدون إعلانات وتشغيل في الخلفية.",
    },
    # ── بطاقات رقمية وقسائم (Gift Cards) ──
    {
        "id": "itunes_10", "category": "cards", "name_ar": "بطاقة أبل آيتونز $10 (أمريكي) 🍏", "name_en": "Apple iTunes $10 US",
        "field_ar": "رقم الهاتف أو البريد لاستلام الكود", "field_en": "Email for Code", "rate_usd": 10.00,
        "desc_ar": "كود رقمي رسمي فوري لشحن متجر آبل الأمريكي.",
    },
    {
        "id": "gplay_10", "category": "cards", "name_ar": "بطاقة جوجل بلاي $10 (أمريكي) 🛒", "name_en": "Google Play $10 US",
        "field_ar": "رقم الهاتف أو البريد لاستلام الكود", "field_en": "Email for Code", "rate_usd": 10.00,
        "desc_ar": "كود رقمي رسمي لشحن رصيد جوجل بلاي الأمريكي.",
    },
    {
        "id": "psn_10", "category": "cards", "name_ar": "بطاقة بلايستيشن ستور $10 (أمريكي) 🎮", "name_en": "PlayStation Network $10 US",
        "field_ar": "رقم الهاتف أو البريد لاستلام الكود", "field_en": "Email for Code", "rate_usd": 10.00,
        "desc_ar": "كود رقمي رسمي لشحن محفظة بلايستيشن PSN.",
    },
]


class DigitalManager:
    """مدير كتالوج الخدمات الرقمية ومخزون القسائم الآلي."""

    @classmethod
    async def get_services_catalog(cls, bot_id: int) -> list[dict[str, Any]]:
        custom_overrides = await db.kv_get(bot_id, "digital:services_override", {})
        margin_conf = await db.kv_get(bot_id, "digital:margin", {"type": "percent", "val": 20.0})

        services = []
        for s in DIGITAL_CATALOG:
            sid = s["id"]
            over = custom_overrides.get(sid, {})
            if over.get("hide", False):
                continue

            base_cost = float(s["rate_usd"])
            if over.get("custom_price_usd") is not None:
                final_usd = float(over["custom_price_usd"])
            else:
                m_type = margin_conf.get("type", "percent")
                m_val = float(margin_conf.get("val", 20.0))
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
    async def get_voucher_from_stock(cls, bot_id: int, service_id: str) -> str | None:
        """يسحب كوداً من مخزون البطاقات الرقمية إن وجد."""
        key = f"digital:stock:{service_id}"
        stock: list[str] = await db.kv_get(bot_id, key, [])
        if stock and isinstance(stock, list) and len(stock) > 0:
            code = stock.pop(0)
            await db.kv_set(bot_id, key, stock)
            log.info("Dispatched digital voucher from stock for bot %d service %s", bot_id, service_id)
            return code
        return None

    @classmethod
    async def add_vouchers_to_stock(cls, bot_id: int, service_id: str, codes: list[str]) -> int:
        """يضيف أكواداً إلى مخزون خدمة محددة."""
        key = f"digital:stock:{service_id}"
        stock: list[str] = await db.kv_get(bot_id, key, []) or []
        for c in codes:
            clean = c.strip()
            if clean and clean not in stock:
                stock.append(clean)
        await db.kv_set(bot_id, key, stock)
        return len(stock)

    @classmethod
    async def get_stock_count(cls, bot_id: int, service_id: str) -> int:
        key = f"digital:stock:{service_id}"
        stock = await db.kv_get(bot_id, key, []) or []
        return len(stock)

    @classmethod
    async def complete_order(cls, bot_id: int, order_id: str, note_or_code: str = "") -> tuple[bool, str]:
        """يعلم الطلب كمكتمل مع تسجيل كود التسليم أو ملاحظة المالك."""
        async with db.Session() as s:
            res = await s.execute(db.select(db.ServiceOrder).where(db.ServiceOrder.order_id == order_id))
            ord_row = res.scalars().first()
            if not ord_row:
                return False, "الطلب غير موجود"
            if ord_row.status == "completed":
                return False, "الطلب مكتمل مسبقاً"

            ord_row.status = "completed"
            ord_row.details = dict(ord_row.details or {}, fulfillment_note=note_or_code)
            await s.commit()
        return True, "تم إكمال الطلب بنجاح"

    @classmethod
    async def cancel_and_refund(cls, bot_id: int, order_id: str, reason: str = "تعذر الشحن") -> tuple[bool, str, float]:
        """يلغي الطلب ويسترجع رصيد الزبون كاملاً في المحفظة."""
        async with db.Session() as s:
            res = await s.execute(db.select(db.ServiceOrder).where(db.ServiceOrder.order_id == order_id))
            ord_row = res.scalars().first()
            if not ord_row:
                return False, "الطلب غير موجود", 0.0
            if ord_row.status in ("completed", "canceled"):
                return False, f"تمت معالجة الطلب مسبقاً ({ord_row.status})", 0.0

            refund_amt = ord_row.price_user_usd
            ok_ref, tx, new_bal = await ledger.credit_user(
                bot_id,
                ord_row.user_id,
                refund_amt,
                kind="digital_refund",
                ref_id=order_id,
                description=f"استرجاع رصيد طلب {ord_row.service_name} ({reason})",
            )
            if not ok_ref:
                return False, "فشل استرجاع الرصيد", 0.0

            ord_row.status = "canceled"
            ord_row.details = dict(ord_row.details or {}, refund_reason=reason, refund_tx=tx)
            await s.commit()
        return True, "تم إلغاء الطلب واسترجاع الرصيد للزبون", new_bal
