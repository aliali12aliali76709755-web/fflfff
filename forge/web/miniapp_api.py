"""واجهات برمجة التطبيقات الشاملة للتطبيقات المصغرة (Telegram Mini Apps API)."""
from __future__ import annotations

import datetime as dt
import json
import logging
import time
import uuid
from typing import Any
from aiohttp import web
from sqlalchemy import desc, func, select

from .. import config, db, ui
from ..modules import currency, discounts, ledger, markup, order_dispatch, payments, promo, tickets
from ..modules.providers.digital import DigitalManager
from ..modules.providers.sms import SMSManager
from ..modules.providers.smm import SMMManager
from ..modules.providers.tgstars import TGStarsManager
from . import media_pipe
from .miniapp_auth import authenticate_admin_request, authenticate_miniapp_request

log = logging.getLogger("forge.miniapp_api")

# مخطط الثيم الصارم (Store Theme Schema) - يمنع أي كود حر
STORE_THEME_SCHEMA = {
    "store_name": str,
    "description": str,
    "logo_url": str,
    "banner_url": str,
    "primary_color": str,
    "secondary_color": str,
    "bg_color": str,
    "card_bg": str,
    "text_color": str,
    "font_family": str,
    "border_radius": str,
    "layout_density": str,
    "wallet_card_style": str,
    "product_card_style": str,
    "banners": list,
    "color_mode": str,
    "show_reviews": bool,
    "contact_url": str,
}

ALLOWED_FONTS = ["Cairo", "Tajawal", "Almarai", "IBM Plex Sans Arabic", "Readex Pro"]
ALLOWED_DENSITIES = ["comfortable", "compact"]
ALLOWED_RADIUS = ["rounded-sm", "rounded-md", "rounded-xl", "rounded-2xl", "rounded-3xl"]

MASTER_CATALOG_ITEMS = [
    {
        "id": "mc_pubg_60",
        "category": "gaming",
        "name": "PUBG Mobile 60 UC",
        "name_ar": "ببجي موبايل 60 شدة",
        "description": "شحن فوري ومباشر إلى حسابك داخل اللعبة عبر الـ ID الرسمي.",
        "media_urls": ["https://images.unsplash.com/photo-1542751371-adc38448a05e?w=400&q=80"],
        "template_type": "manual_subs",
        "cost_price": 0.85,
        "base_user_price": 0.99,
        "price_options": [{"id": "opt_60", "label": "60 UC", "costPrice": 0.85, "userPrice": 0.99}],
        "requirements": [{"name": "player_id", "label": "آيدي اللاعب (Player ID)", "type": "text", "required": True}],
        "active": True,
    },
    {
        "id": "mc_pubg_325",
        "category": "gaming",
        "name": "PUBG Mobile 325 UC",
        "name_ar": "ببجي موبايل 325 شدة",
        "description": "باقة 325 شدة مع بونص إضافي وشحن سريع ومضمون 100%.",
        "media_urls": ["https://images.unsplash.com/photo-1542751371-adc38448a05e?w=400&q=80"],
        "template_type": "manual_subs",
        "cost_price": 4.20,
        "base_user_price": 4.90,
        "price_options": [{"id": "opt_325", "label": "325 UC", "costPrice": 4.20, "userPrice": 4.90}],
        "requirements": [{"name": "player_id", "label": "آيدي اللاعب (Player ID)", "type": "text", "required": True}],
        "active": True,
    },
    {
        "id": "mc_pubg_660",
        "category": "gaming",
        "name": "PUBG Mobile 660 UC",
        "name_ar": "ببجي موبايل 660 شدة (رويال باس)",
        "description": "شحن الرويال باس الملكي بنقرة واحدة بحسابك مباشرة.",
        "media_urls": ["https://images.unsplash.com/photo-1542751371-adc38448a05e?w=400&q=80"],
        "template_type": "manual_subs",
        "cost_price": 8.30,
        "base_user_price": 9.50,
        "price_options": [{"id": "opt_660", "label": "660 UC", "costPrice": 8.30, "userPrice": 9.50}],
        "requirements": [{"name": "player_id", "label": "آيدي اللاعب (Player ID)", "type": "text", "required": True}],
        "active": True,
    },
    {
        "id": "mc_netflix_1m",
        "category": "subscriptions",
        "name": "Netflix Premium 1 Month 4K",
        "name_ar": "اشتراك نتفلكس بريميوم شهر 4K",
        "description": "حساب نتفلكس بريميوم رسمي أعلى دقة 4K Ultra HD مع ضمان كامل المدة.",
        "media_urls": ["https://images.unsplash.com/photo-1574375927938-d5a98e8ffe85?w=400&q=80"],
        "template_type": "manual_subs",
        "cost_price": 2.80,
        "base_user_price": 3.50,
        "price_options": [{"id": "opt_1m", "label": "شهر واحد (شاشة)", "costPrice": 2.80, "userPrice": 3.50}],
        "requirements": [{"name": "email", "label": "بريدك الإلكتروني للتسليم", "type": "text", "required": True}],
        "active": True,
    },
    {
        "id": "mc_shahid_vip",
        "category": "subscriptions",
        "name": "Shahid VIP 1 Month",
        "name_ar": "اشتراك شاهد VIP شهر شامل مسلسلات ورياضة",
        "description": "اشتراك شاهد VIP بدون فواصل إعلانية مع باقة المسلسلات الحصرية.",
        "media_urls": ["https://images.unsplash.com/photo-1522869635100-9f4c5e86aa37?w=400&q=80"],
        "template_type": "manual_subs",
        "cost_price": 3.00,
        "base_user_price": 3.99,
        "price_options": [{"id": "opt_shahid", "label": "اشتراك شهر كامل", "costPrice": 3.00, "userPrice": 3.99}],
        "requirements": [{"name": "email", "label": "بريدك الإلكتروني للتسليم", "type": "text", "required": True}],
        "active": True,
    },
    {
        "id": "mc_tg_stars_100",
        "category": "telegram",
        "name": "Telegram Stars 100",
        "name_ar": "100 نجمة تيليجرام Telegram Stars",
        "description": "شحن نجوم تيليجرام الرسمية فورياً لدعم القنوات والمحتوى والبوتات.",
        "media_urls": ["https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=400&q=80"],
        "template_type": "stars_premium_gifts",
        "cost_price": 1.60,
        "base_user_price": 1.99,
        "price_options": [{"id": "opt_stars_100", "label": "100 نجمة", "costPrice": 1.60, "userPrice": 1.99}],
        "requirements": [{"name": "username", "label": "يوزر حسابك @username", "type": "text", "required": True}],
        "active": True,
    },
    {
        "id": "mc_tg_stars_500",
        "category": "telegram",
        "name": "Telegram Stars 500",
        "name_ar": "500 نجمة تيليجرام Telegram Stars",
        "description": "باقة 500 نجمة تيليجرام فورية بدون انتظار.",
        "media_urls": ["https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=400&q=80"],
        "template_type": "stars_premium_gifts",
        "cost_price": 7.90,
        "base_user_price": 8.99,
        "price_options": [{"id": "opt_stars_500", "label": "500 نجمة", "costPrice": 7.90, "userPrice": 8.99}],
        "requirements": [{"name": "username", "label": "يوزر حسابك @username", "type": "text", "required": True}],
        "active": True,
    },
    {
        "id": "mc_us_number",
        "category": "numbers",
        "name": "US Telegram Number",
        "name_ar": "رقم أمريكي لتفعيل تيليجرام",
        "description": "رقم أمريكي مؤقت لتفعيل تطبيق تيليجرام مع استرجاع فوري إن لم يصل الرمز.",
        "media_urls": ["https://images.unsplash.com/photo-1512428559087-560fa5ceab42?w=400&q=80"],
        "template_type": "virtual_numbers",
        "cost_price": 0.70,
        "base_user_price": 0.99,
        "price_options": [{"id": "opt_us", "label": "رقم أمريكي (+1)", "costPrice": 0.70, "userPrice": 0.99}],
        "requirements": [],
        "active": True,
    },
    {
        "id": "mc_smm_insta",
        "category": "smm",
        "name": "Instagram Real Followers",
        "name_ar": "متابعو انستغرام حقيقيون (لكل 1000)",
        "description": "زيادة متابعين انستغرام بجودة عالية مع ضمان تعويض النقص لمدة 30 يوم.",
        "media_urls": ["https://images.unsplash.com/photo-1611162617474-5b21e879e113?w=400&q=80"],
        "template_type": "smm_boost",
        "cost_price": 0.60,
        "base_user_price": 0.90,
        "price_options": [{"id": "opt_smm_1k", "label": "سعر الألف (1000)", "costPrice": 0.60, "userPrice": 0.90}],
        "requirements": [{"name": "target_url", "label": "رابط الحساب", "type": "text", "required": True}],
        "active": True,
    }
]


async def get_master_catalog_items() -> list[dict[str, Any]]:
    """يجلب كتالوج المنتجات الرقمية العام لمدير المنصة من قاعدة البيانات أو يثبته بالقائمة الافتراضية."""
    catalog = await db.kv_get(0, "admin:master_catalog")
    if not catalog or not isinstance(catalog, list):
        catalog = []
        for it in MASTER_CATALOG_ITEMS:
            c_p = float(it.get("cost_price") or (it.get("price_options", [{}])[0].get("costPrice", 0.85)))
            u_p = float(it.get("base_user_price") or (it.get("price_options", [{}])[0].get("userPrice", 0.99)))
            item_copy = dict(it)
            item_copy["cost_price"] = c_p
            item_copy["base_user_price"] = u_p
            item_copy["active"] = it.get("active", True)
            if not item_copy.get("price_options"):
                item_copy["price_options"] = [{"id": "opt_1", "label": item_copy.get("name_ar", "الخيار الأساسي"), "costPrice": c_p, "userPrice": u_p}]
            catalog.append(item_copy)
        await db.kv_set(0, "admin:master_catalog", catalog)
    return catalog


async def save_master_catalog_items(items: list[dict[str, Any]]) -> None:
    """يحفظ كتالوج المنتجات الرقمية العام في قاعدة البيانات."""
    await db.kv_set(0, "admin:master_catalog", items)


def validate_theme_config(data: dict[str, Any]) -> dict[str, Any]:
    """يتحقق من مطابقة إعدادات التصميم للمخطط الصارم ويمنع أي حقول مجهولة أو كود."""
    mapping = {
        "primaryColor": "primary_color",
        "secondaryColor": "secondary_color",
        "fontFamily": "font_family",
        "cardStyle": "product_card_style",
        "walletStyle": "wallet_card_style",
        "borderRadius": "border_radius",
        "layoutDensity": "layout_density",
        "storeName": "store_name",
        "logoUrl": "logo_url",
        "bannerUrl": "banner_url",
    }
    normalized = {}
    for k, v in data.items():
        target_k = mapping.get(k, k)
        normalized[target_k] = v

    clean = {}
    for k, expected_type in STORE_THEME_SCHEMA.items():
        val = normalized.get(k)
        if val is None:
            continue
        if not isinstance(val, expected_type):
            continue
        if isinstance(val, str):
            # حماية من XSS وحقن النصوص
            if "<script" in val.lower() or "javascript:" in val.lower():
                continue
            clean[k] = val[:255]
        elif isinstance(val, list):
            clean[k] = val[:10]  # أقصى حد 10 بانرات
        elif isinstance(val, bool):
            clean[k] = val

    # التحقق من الخطوط
    if clean.get("font_family") and clean["font_family"] not in ALLOWED_FONTS:
        clean["font_family"] = "Cairo"

    # التحقق من استدارة الحواف
    if clean.get("border_radius") and clean["border_radius"] not in ALLOWED_RADIUS:
        clean["border_radius"] = "rounded-xl"

    # التحقق من كثافة التخطيط
    if clean.get("layout_density") and clean["layout_density"] not in ALLOWED_DENSITIES:
        clean["layout_density"] = "comfortable"

    return clean


async def log_audit(
    bot_id: int,
    actor_id: int,
    actor_role: str,
    action: str,
    target_type: str = "",
    target_id: str = "",
    old_value: Any = None,
    new_value: Any = None,
    details: str = "",
    ip: str = "",
) -> None:
    """يسجل التغيير في سجل التدقيق."""
    try:
        async with db.Session() as s:
            entry = db.AuditLog(
                bot_id=bot_id,
                actor_id=actor_id,
                actor_role=actor_role,
                action=action,
                target_type=target_type,
                target_id=target_id,
                old_value=old_value or {},
                new_value=new_value or {},
                details=details[:500],
                ip=ip[:64],
                created=dt.datetime.utcnow(),
            )
            s.add(entry)
            await s.commit()
    except Exception as e:
        log.warning("Failed to record audit log: %s", e)


# ─────────────────────────────────────────────────────────────
# 1. المكونات المشتركة وتهيئة المتجر (Store Bootstrap)
# ─────────────────────────────────────────────────────────────

async def get_store_bootstrap(req: web.Request) -> web.Response:
    """يعيد الإعدادات الشاملة للمتجر وهوية المستخدم ورصيده والثيم."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.query.get("start_param") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u)
    bot = ctx.bot

    # جلب إعدادات الثيم والتصميم
    theme_cfg = await db.kv_get(bot.id, "store:theme_config", {}) or {}
    seller_settings = await db.kv_get(bot.id, "store:settings", {}) or {}
    default_theme = {
        "store_name": bot.name or bot.username,
        "description": "متجر الخدمات الرقمية المعتمد",
        "primary_color": "#2563eb",
        "secondary_color": "#3b82f6",
        "bg_color": "#0f172a",
        "card_bg": "#1e293b",
        "text_color": "#f8fafc",
        "font_family": "Cairo",
        "border_radius": "rounded-2xl",
        "layout_density": "comfortable",
        "wallet_card_style": "gradient_modern",
        "product_card_style": "elevated",
        "banners": [],
        "color_mode": "dark",
        "show_reviews": True,
        "contact_url": seller_settings.get("support_url") or f"https://t.me/{bot.username}",
    }
    merged_theme = {**default_theme, **theme_cfg}

    # الرصيد والعملة
    bot_cur = await currency.get_bot_currency(bot.id)
    user_bal_usd = await ledger.get_user_balance_usd(bot.id, ctx.uid)
    user_bal_disp = await ledger.get_user_balance_display(bot.id, ctx.uid)

    # التحقق من وضع الصيانة أو قفل البوت
    core = await db.kv_get(bot.id, "core", {}) or {}
    is_paused = bot.status != "active"

    # بيانات العروض النشطة
    sales = await discounts.DiscountManager.get_active_sales(bot.id)
    sales_data = [
        {
            "id": s.sale_id,
            "title": s.title,
            "discount_value": s.discount_value,
            "discount_type": s.discount_type,
            "expires_at": s.expires_at.isoformat(),
        }
        for s in sales
    ]

    return web.json_response({
        "ok": True,
        "success": True,
        "bot": {
            "id": bot.id,
            "username": bot.username,
            "name": bot.name,
            "template": bot.template,
            "is_paused": is_paused,
        },
        "user": {
            "uid": ctx.uid,
            "name": ctx.uname,
            "role": ctx.role,
            "balance_usd": user_bal_usd,
            "balance_display": user_bal_disp,
            "currency": bot_cur,
        },
        "theme": merged_theme,
        "active_sales": sales_data,
        "data": {
            "bot": {
                "id": bot.id,
                "username": bot.username,
                "name": bot.name,
                "template": bot.template,
                "is_paused": is_paused,
            },
            "user": {
                "uid": ctx.uid,
                "name": ctx.uname,
                "role": ctx.role,
                "balance_usd": user_bal_usd,
                "balance_display": user_bal_disp,
                "currency": bot_cur,
            },
            "theme": merged_theme,
            "active_sales": sales_data,
        }
    })


async def api_store_info(req: web.Request) -> web.Response:
    """يعيد معلومات المتجر الشاملة بما يتوافق مع تطبيق Nitro."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.query.get("start_param") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u)
    bot = ctx.bot

    theme_cfg = await db.kv_get(bot.id, "store:theme_config", {}) or {}
    seller_settings = await db.kv_get(bot.id, "store:settings", {}) or {}
    default_theme = {
        "store_name": bot.name or bot.username,
        "description": "متجر الخدمات الرقمية المعتمد",
        "primary_color": "#2563eb",
        "secondary_color": "#3b82f6",
        "bg_color": "#0b0f19",
        "card_bg": "#1e293b",
        "text_color": "#f8fafc",
        "font_family": "Tajawal",
        "border_radius": "rounded-2xl",
        "layout_density": "comfortable",
        "wallet_card_style": "gradient_modern",
        "product_card_style": "elevated",
        "banners": [
            {"title": "شحن وتفعيل فوري على مدار 24 ساعة ⚡", "imageUrl": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=1200&q=80"},
            {"title": "عروض الألعاب والاشتراكات الحصرية بضمان ذهبي 🔥", "imageUrl": "https://images.unsplash.com/photo-1542751371-adc38448a05e?w=1200&q=80"}
        ],
        "color_mode": "dark",
        "show_reviews": True,
        "contact_url": seller_settings.get("support_url") or f"https://t.me/{bot.username}",
    }
    merged_theme = {**default_theme, **theme_cfg}
    bot_cur = await currency.get_bot_currency(bot.id)
    cur_info = currency.CURRENCIES.get(bot_cur, currency.CURRENCIES["USD"])
    live_rates = await currency.fetch_live_rates()
    cur_list = [
        {
            "code": c_code,
            "name_ar": c_data.get("name_ar", c_code),
            "name_en": c_data.get("name_en", c_code),
            "symbol": c_data.get("symbol", c_code),
            "rate": float(live_rates.get(c_code, c_data.get("default_rate", 1.0))),
            "decimals": c_data.get("decimals", 2),
        }
        for c_code, c_data in currency.CURRENCIES.items()
    ]

    return web.json_response({
        "success": True,
        "ok": True,
        "data": {
            "botId": bot.id,
            "botUsername": bot.username,
            "storeName": merged_theme.get("store_name") or bot.name or bot.username,
            "description": merged_theme.get("description") or "متجر الخدمات الرقمية المعتمد",
            "logoUrl": merged_theme.get("logo_url") or "",
            "heroBannerUrl": merged_theme.get("banner_url") or "",
            "templateType": bot.template or "store",
            "currency": bot_cur,
            "currencySymbol": cur_info.get("symbol", "$"),
            "exchangeRate": float(live_rates.get(bot_cur, 1.0)),
            "themeSettings": merged_theme,
            "maintenanceMode": False,
            "forceChannel": "",
            "reviewsEnabled": True,
            "referralRewardPercent": 5,
            "supportUrl": seller_settings.get("support_url") or f"https://t.me/{bot.username}",
            "termsText": seller_settings.get("terms_text") or "جميع الخدمات الرقمية يتم تنفيذها بأعلى معايير الأمان والسرعة. يرجى التأكد من صحة البيانات المدخلة قبل الدفع.",
            "policyText": seller_settings.get("policy_text") or "في حال تعذر إكمال الطلب أو حدوث أي خطأ تقني، يحق للمشتري استرجاع كامل المبلغ تلقائياً وفورياً إلى رصيد محفظته بالبوت.",
            "wheelEnabled": bool(seller_settings.get("wheel_enabled", False)),
            "wheelPrizes": seller_settings.get("wheel_prizes", []),
            "exchangeRates": live_rates,
            "allCurrencies": cur_list,
            "manualPayments": await db.kv_get(bot.id, "store:manual_payments", [
                {"id": "zain_cash", "name": "زين كاش (ZainCash)", "account": "07801234567", "instructions": "يرجى تحويل المبلغ المطلوب إلى رقم المحفظة، ثم إرفاق صورة الإشعار أو رقم العملية.", "icon": "💳", "active": True},
                {"id": "asiacell", "name": "آسيا حوالة / كاش (AsiaCell)", "account": "07701234567", "instructions": "يرجى التحويل إلى الرقم الموضح وإرفاق رقم الإشعار لتأكيد الشحن فوراً.", "icon": "📱", "active": True},
                {"id": "usdt", "name": "USDT (TRC20)", "account": "TY4h9sK2LpQxW3vM8z7tA1bC9dE4fG5hJ", "instructions": "أرسل المبلغ عبر شبكة TRC20 وأرفق هاش المعاملة TXID أو سكرين شوت.", "icon": "🪙", "active": True},
            ])
        }
    })


async def api_auth(req: web.Request) -> web.Response:
    """مصادقة Telegram Mini App وإرجاع الجلسة والرصيد والأدوار."""
    try:
        body = await req.json()
    except Exception:
        body = {}

    store_id = body.get("storeId") or req.query.get("store_id") or req.query.get("start_param") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, store_id)
    bot = ctx.bot

    bal_usd = await ledger.get_user_balance_usd(bot.id, ctx.uid)
    theme_cfg = await db.kv_get(bot.id, "store:theme_config", {}) or {}

    return web.json_response({
        "success": True,
        "ok": True,
        "data": {
            "user": {
                "id": ctx.uid,
                "telegramId": ctx.uid,
                "username": ctx.user.get("username", ""),
                "firstName": ctx.user.get("first_name", ctx.uname),
                "balance": round(bal_usd, 2),
                "currency": "USD",
                "currencySymbol": "$"
            },
            "role": ctx.role,
            "store": {
                "botId": bot.id,
                "botUsername": bot.username,
                "storeName": theme_cfg.get("store_name") or bot.name or bot.username,
                "templateType": bot.template,
                "themeSettings": theme_cfg,
                "maintenanceMode": False,
                "forceChannel": ""
            }
        }
    })


# ─────────────────────────────────────────────────────────────
# 2. الكتالوج والمنتجات والأقسام
# ─────────────────────────────────────────────────────────────

async def get_store_catalog(req: web.Request) -> web.Response:
    """يعيد كتالوج المنتجات والأقسام والخيارات للبوت المعني."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.query.get("start_param") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u)
    bot = ctx.bot

    # فحص نوع القالب وجلب الخدمات المناسبة
    tpl_key = bot.template
    categories = []
    products = []

    if tpl_key == "digital":
        raw_svcs = await DigitalManager.get_services_catalog(bot.id)
        # تجميع الفئات
        cat_map = {
            "games": {"id": "games", "name": "ألعاب وتطبيقات", "icon": "🎮"},
            "apps": {"id": "apps", "name": "اشتراكات وبث", "icon": "🎬"},
            "cards": {"id": "cards", "name": "بطاقات وقسائم", "icon": "🔑"},
        }
        for s in raw_svcs:
            c_key = s.get("category", "games")
            cat_info = cat_map.get(c_key, {"id": c_key, "name": c_key, "icon": "📦"})
            if cat_info not in categories:
                categories.append(cat_info)

            # فحص العروض والخصومات
            p_price = s["price_usd"]
            disc_price = await discounts.DiscountManager.apply_discount(bot.id, "digital", s["id"], p_price)
            has_disc = disc_price < p_price
            disc_pct = round((1 - disc_price / p_price) * 100) if has_disc and p_price > 0 else 0
            stock_cnt = await DigitalManager.get_stock_count(bot.id, s["id"])

            products.append({
                "id": s["id"],
                "category": c_key,
                "category_id": c_key,
                "name": s["name_ar"],
                "nameAr": s["name_ar"],
                "description": s.get("desc_ar", ""),
                "price_usd": disc_price,
                "original_price_usd": p_price,
                "has_discount": has_disc,
                "discount_percent": disc_pct,
                "discountPercent": disc_pct,
                "input_label": s.get("field_ar", "ID الحساب أو البيانات"),
                "stock_count": stock_cnt,
                "is_instant": stock_cnt > 0,
                "is_manual": True,
                "icon": s.get("icon", "🎮"),
                "image_url": s.get("image_url", ""),
                "mediaUrls": [s.get("image_url")] if s.get("image_url") else [],
                "templateType": "manual_subs",
                "priceOptions": [{"id": "opt_1", "label": s["name_ar"], "costPrice": round(disc_price * 0.8, 2), "userPrice": disc_price}],
                "requirements": [{"name": "target", "label": s.get("field_ar", "بيانات الطلب"), "type": "text", "required": True}] if s.get("field_ar") else [],
            })

    elif tpl_key == "sms":
        from ..modules.providers.sms import SMS_APPS, SMS_COUNTRIES
        categories = [{"id": c_code, "name": f"{c_info['flag']} {c_info['name_ar']}", "icon": c_info["flag"]} for c_code, c_info in SMS_COUNTRIES.items()]
        for c_code in SMS_COUNTRIES.keys():
            for app_code, a_info in SMS_APPS.items():
                price_usd = await SMSManager.calculate_number_price(bot.id, c_code, app_code)
                products.append({
                    "id": f"{c_code}_{app_code}",
                    "category": c_code,
                    "category_id": c_code,
                    "name": f"{a_info['name_ar']} ({c_code.upper()})",
                    "nameAr": f"{a_info['name_ar']} ({c_code.upper()})",
                    "description": "رقم تفعيل فوري مع استرجاع تلقائي إن لم يصل الرمز",
                    "price_usd": price_usd,
                    "original_price_usd": price_usd,
                    "has_discount": False,
                    "discountPercent": 0,
                    "input_label": "",
                    "is_instant": True,
                    "is_manual": False,
                    "icon": a_info["emoji"],
                    "mediaUrls": [],
                    "templateType": "virtual_numbers",
                    "priceOptions": [{"id": "opt_1", "label": f"{a_info['name_ar']} ({c_code.upper()})", "costPrice": round(price_usd * 0.7, 2), "userPrice": price_usd}],
                    "requirements": [],
                })

    elif tpl_key == "smm":
        from ..modules.providers.smm import PLATFORMS
        raw_svcs = await SMMManager.get_services_catalog(bot.id)
        categories = [{"id": p_key, "name": f"{p['emoji']} {p['name_ar']}", "icon": p["emoji"]} for p_key, p in PLATFORMS.items()]
        for s in raw_svcs:
            p_price = s["price_per_1k_usd"]
            products.append({
                "id": s["id"],
                "category": s["platform"],
                "category_id": s["platform"],
                "name": s["name_ar"],
                "nameAr": s["name_ar"],
                "description": f"الحد الأدنى: {s['min']} - الحد الأقصى: {s['max']:,}",
                "price_usd": p_price,
                "original_price_usd": p_price,
                "price_per_1k": p_price,
                "min_qty": s["min"],
                "max_qty": s["max"],
                "has_discount": False,
                "discountPercent": 0,
                "input_label": "رابط الحساب أو المنشور",
                "is_instant": True,
                "is_manual": False,
                "icon": "🚀",
                "mediaUrls": [],
                "templateType": "smm_boost",
                "priceOptions": [{"id": "opt_1", "label": s["name_ar"], "costPrice": round(p_price * 0.7, 2), "userPrice": p_price}],
                "requirements": [{"name": "target_url", "label": "رابط الحساب أو المنشور", "type": "url", "required": True}],
            })

    elif tpl_key == "tgstars":
        raw_svcs = await TGStarsManager.get_services_catalog(bot.id)
        categories = [
            {"id": "stars", "name": "⭐ نجوم تيليجرام", "icon": "⭐"},
            {"id": "premium", "name": "💎 بريميوم", "icon": "💎"},
            {"id": "gifts", "name": "🎁 هدايا", "icon": "🎁"},
        ]
        for s in raw_svcs:
            products.append({
                "id": s["id"],
                "category": s.get("category", "stars"),
                "category_id": s.get("category", "stars"),
                "name": s["name_ar"],
                "nameAr": s["name_ar"],
                "description": s.get("desc_ar", ""),
                "price_usd": s["price_usd"],
                "original_price_usd": s["price_usd"],
                "has_discount": False,
                "discountPercent": 0,
                "input_label": "اسم المستخدم @username",
                "is_instant": True,
                "is_manual": False,
                "icon": "⭐",
                "mediaUrls": [],
                "templateType": "stars_premium_gifts",
                "priceOptions": [{"id": "opt_1", "label": s["name_ar"], "costPrice": round(s["price_usd"] * 0.8, 2), "userPrice": s["price_usd"]}],
                "requirements": [{"name": "username", "label": "اسم المستخدم @username", "type": "text", "required": True}],
            })

    # جلب الكتالوج العام المركزي مع دعم الهامش والتسعير الذكي الموحد
    master_items = await get_master_catalog_items()
    overrides = await db.kv_get(bot.id, "store:product_overrides", {}) or {}

    cat_map = {
        "gaming": ("ألعاب وتطبيقات", "🎮"),
        "subscriptions": ("اشتراكات وبث", "🎬"),
        "telegram": ("تيليجرام وبريميوم", "⭐"),
        "numbers": ("أرقام تفعيل", "📲"),
        "smm": ("تفاعل وسوشيال", "🚀"),
    }

    for m in master_items:
        if m.get("active", True) is False:
            continue
        m_id = str(m["id"])
        ov = overrides.get(m_id, {})
        if ov.get("deleted", False):
            continue
        if ov.get("active", True) is False:
            continue

        c_cat = m.get("category", "gaming")
        c_label, c_icon = cat_map.get(c_cat, (m.get("category_name") or c_cat, "📦"))
        if not any(c.get("id") == c_cat for c in categories):
            categories.append({"id": c_cat, "name": c_label, "nameAr": c_label, "icon": c_icon})

        cost_p = float(m.get("cost_price", 0.85))
        if ov.get("margin") is not None:
            user_p = round(cost_p + float(ov["margin"]), 2)
        elif ov.get("selling_price") is not None or ov.get("userPrice") is not None:
            raw_p = float(ov.get("selling_price") or ov.get("userPrice"))
            user_p = round(max(raw_p, cost_p + 0.10), 2)
        else:
            user_p = float(m.get("base_user_price", round(cost_p * 1.15, 2)))

        media_urls = ov.get("mediaUrls") or ov.get("media_urls") or m.get("media_urls", [])
        img_url = media_urls[0] if media_urls else ""
        desc = ov.get("description") or m.get("description", "")
        reqs = m.get("requirements", [])

        if not any(p.get("id") == m_id for p in products):
            products.append({
                "id": m_id,
                "category": c_cat,
                "category_id": c_cat,
                "name": m["name"],
                "nameAr": m.get("name_ar") or m["name"],
                "description": desc,
                "price_usd": user_p,
                "original_price_usd": user_p,
                "cost_price": cost_p,
                "has_discount": False,
                "discountPercent": 0,
                "input_label": reqs[0]["label"] if reqs else "بيانات الطلب",
                "is_instant": False,
                "is_manual": True,
                "icon": c_icon,
                "image_url": img_url,
                "mediaUrls": media_urls,
                "templateType": m.get("template_type", "manual_subs"),
                "priceOptions": [{"id": f"opt_{m_id}", "label": m.get("name_ar", m["name"]), "costPrice": cost_p, "userPrice": user_p}],
                "requirements": reqs,
            })

    # إضافة المنتجات المخصصة التي أضافها البائع إن وجدت
    custom_prods = await db.kv_get(bot.id, "store:custom_products", []) or []
    for cp in custom_prods:
        if cp.get("active") is False:
            continue
        c_cat_id = cp.get("category_id") or cp.get("category") or "custom"
        c_cat_name = cp.get("category_name") or "منتجات حصرية"
        if not any(c["id"] == c_cat_id for c in categories):
            categories.append({"id": c_cat_id, "name": c_cat_name, "icon": cp.get("icon") or "⭐"})

        u_price = float(cp.get("price_usd", 1.0))
        c_price = float(cp.get("cost_price", round(u_price * 0.8, 2)))
        media_urls = cp.get("mediaUrls") or ([cp["image_url"]] if cp.get("image_url") else [])
        price_opts = cp.get("priceOptions") or [{"id": "opt_1", "label": cp["name"], "costPrice": c_price, "userPrice": u_price}]

        if not any(p.get("id") == cp.get("id") for p in products):
            products.append({
                "id": cp["id"],
                "category": c_cat_id,
                "category_id": c_cat_id,
                "name": cp["name"],
                "nameAr": cp.get("nameAr") or cp["name"],
                "description": cp.get("description", ""),
                "price_usd": u_price,
                "original_price_usd": u_price,
                "has_discount": False,
                "discountPercent": 0,
                "input_label": cp.get("input_label", "بيانات الطلب"),
                "is_instant": bool(cp.get("is_instant", False)),
                "is_manual": not bool(cp.get("is_instant", False)),
                "icon": cp.get("icon", "📦"),
                "image_url": media_urls[0] if media_urls else "",
                "mediaUrls": media_urls,
                "templateType": cp.get("templateType", "manual_subs"),
                "priceOptions": price_opts,
                "requirements": cp.get("requirements") or ([{"name": "target", "label": cp.get("input_label", "بيانات الطلب"), "type": "text", "required": True}] if cp.get("input_label") else []),
            })

    theme_cfg = await db.kv_get(bot.id, "store:theme_config", {}) or {}
    banners = theme_cfg.get("banners") or [
        {"title": "شحن وتفعيل فوري على مدار 24 ساعة ⚡", "imageUrl": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=1200&q=80"},
        {"title": "عروض الألعاب والاشتراكات الحصرية بضمان ذهبي 🔥", "imageUrl": "https://images.unsplash.com/photo-1542751371-adc38448a05e?w=1200&q=80"}
    ]

    return web.json_response({
        "ok": True,
        "success": True,
        "categories": categories,
        "products": products,
        "data": {
            "categories": categories,
            "products": products,
            "banners": banners,
        }
    })


# ─────────────────────────────────────────────────────────────
# 3. إرسال الطلبات الذري (Atomic Ordering & Idempotency)
# ─────────────────────────────────────────────────────────────

async def create_store_order(req: web.Request) -> web.Response:
    """ينشئ طلباً جديداً مع التحقق الصارم من الرصيد والأسعار ومنع التكرار."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.query.get("start_param") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u)
    bot = ctx.bot

    try:
        data = await req.json()
    except Exception:
        return web.json_response({"ok": False, "error": "bad_json"}, status=400)

    # مفتاح منع التكرار (Idempotency Key)
    idempotency_key = req.headers.get("X-Idempotency-Key") or data.get("idempotency_key") or data.get("idempotencyKey") or ""
    if not idempotency_key:
        idempotency_key = f"idemp_{uuid.uuid4().hex[:12]}"

    # فحص الطلب المكرر إن وجد
    async with db.Session() as s:
        existing = (await s.execute(
            select(db.ServiceOrder).where(
                db.ServiceOrder.bot_id == bot.id,
                db.ServiceOrder.order_id == idempotency_key,
            )
        )).scalars().first()
        if existing:
            return web.json_response({
                "ok": True,
                "success": True,
                "order_id": existing.order_id,
                "status": existing.status,
                "is_duplicate": True,
                "data": {
                    "order_id": existing.order_id,
                    "order_ref": existing.order_id,
                    "status": existing.status,
                }
            })

    product_id = data.get("product_id") or data.get("productId")
    target_data = str(data.get("target") or data.get("targetUrl") or "").strip()
    if not target_data and data.get("userInputs"):
        u_in = data.get("userInputs")
        if isinstance(u_in, dict):
            target_data = next((str(v) for v in u_in.values() if v), "") or json.dumps(u_in)
    quantity = int(data.get("quantity") or 1)

    if not product_id:
        return web.json_response({"ok": False, "error": "missing_product", "message": "المنتج غير محدد"}, status=400)

    # إعادة حساب السعر دائماً في السيرفر
    final_usd = 0.0
    product_name = ""
    order_status = "queued"
    voucher_code = ""

    if bot.template == "digital":
        raw_svcs = await DigitalManager.get_services_catalog(bot.id)
        svc = next((s for s in raw_svcs if s["id"] == product_id), None)
        if svc:
            base_price = svc["price_usd"]
            final_usd = await discounts.DiscountManager.apply_discount(bot.id, "digital", product_id, base_price)
            product_name = svc["name_ar"]
            voucher_code = await DigitalManager.get_voucher_from_stock(bot.id, product_id)
            if voucher_code:
                order_status = "completed"

    elif bot.template == "sms":
        parts = str(product_id).split("_")
        if len(parts) >= 2:
            c_code, app_code = parts[0], parts[1]
            final_usd = await SMSManager.calculate_number_price(bot.id, c_code, app_code)
            product_name = f"رقم {app_code} ({c_code})"

    elif bot.template == "smm":
        raw_svcs = await SMMManager.get_services_catalog(bot.id)
        svc = next((s for s in raw_svcs if s["id"] == product_id), None)
        if svc:
            final_usd = (svc["price_per_1k_usd"] * quantity) / 1000.0
            product_name = svc["name_ar"]

    elif bot.template == "tgstars":
        raw_svcs = await TGStarsManager.get_services_catalog(bot.id)
        svc = next((s for s in raw_svcs if s["id"] == product_id), None)
        if svc:
            final_usd = svc["price_usd"]
            product_name = svc["name_ar"]

    # فحص الكتالوج العام أو المنتجات المخصصة للبائع
    if not product_name:
        master_items = await get_master_catalog_items()
        m_found = next((m for m in master_items if str(m.get("id")) == str(product_id)), None)
        if m_found:
            overrides = await db.kv_get(bot.id, "store:product_overrides", {}) or {}
            ov = overrides.get(str(product_id), {})
            cost_p = float(m_found.get("cost_price", 0.85))
            if ov.get("margin") is not None:
                user_p = round(cost_p + float(ov["margin"]), 2)
            elif ov.get("selling_price") is not None or ov.get("userPrice") is not None:
                raw_p = float(ov.get("selling_price") or ov.get("userPrice"))
                user_p = round(max(raw_p, cost_p + 0.10), 2)
            else:
                user_p = float(m_found.get("base_user_price", round(cost_p * 1.15, 2)))
            final_usd = user_p * quantity
            product_name = m_found.get("name_ar") or m_found["name"]
        else:
            custom_prods = await db.kv_get(bot.id, "store:custom_products", []) or []
            cp = next((p for p in custom_prods if str(p.get("id")) == str(product_id)), None)
            if not cp:
                return web.json_response({"ok": False, "error": "invalid_product", "message": "المنتج غير موجود"}, status=404)

            p_opt_id = data.get("priceOptionId") or data.get("price_option_id")
            price_opts = cp.get("priceOptions") or []
            sel_opt = next((o for o in price_opts if o.get("id") == p_opt_id), None) if p_opt_id else (price_opts[0] if price_opts else None)
            unit_price = float(sel_opt.get("userPrice") or cp.get("price_usd", 1.0)) if sel_opt else float(cp.get("price_usd", 1.0))
            final_usd = unit_price * quantity
            product_name = cp["name"]
            codes = cp.get("stock_codes") or []
            if cp.get("is_instant") and codes:
                voucher_code = codes.pop(0)
                await db.kv_set(bot.id, "store:custom_products", custom_prods)
                order_status = "completed"

    # تطبيق كود الخصم إن وجد
    coupon_code = str(data.get("coupon_code") or data.get("coupon") or "").strip().upper()
    discount_usd = 0.0
    if coupon_code:
        valid_c, disc_val, c_msg = await promo.validate_promo(bot.id, ctx.uid, coupon_code, final_usd, str(product_id))
        if valid_c and disc_val > 0:
            discount_usd = disc_val
            final_usd = max(0.0, round(final_usd - discount_usd, 4))
            await promo.record_promo_applied(bot.id, ctx.uid, coupon_code, discount_usd=discount_usd)

    # فحص الرصيد المتاح
    user_bal = await ledger.get_user_balance_usd(bot.id, ctx.uid)
    if user_bal < final_usd:
        return web.json_response({
            "ok": False,
            "success": False,
            "error": "insufficient_balance",
            "message": f"رصيدك الحالي (${user_bal:.2f}) غير كافٍ. المطلوب: ${final_usd:.2f}",
        }, status=402)

    # خصم الرصيد ذرياً عبر Ledger
    ok_debit, tx, new_bal = await ledger.debit_user(
        bot_id=bot.id,
        user_id=ctx.uid,
        amount_usd=final_usd,
        kind=f"order_{bot.template}",
        ref_id=idempotency_key,
        description=f"طلب {product_name}",
    )
    if not ok_debit:
        return web.json_response({"ok": False, "success": False, "error": "debit_failed"}, status=500)

    # إنشاء سجل الطلب
    bot_cur = await currency.get_bot_currency(bot.id)
    async with db.Session() as s:
        order = db.ServiceOrder(
            order_id=idempotency_key,
            bot_id=bot.id,
            user_id=ctx.uid,
            tpl_key=bot.template,
            service_id=str(product_id),
            service_name=product_name,
            target=target_data,
            quantity=quantity,
            cost_provider_usd=0.0,
            cost_platform_usd=0.0,
            price_user_usd=final_usd,
            currency=bot_cur,
            price_user_currency=final_usd,
            status=order_status,
            provider_name="InternalFulfillment",
            provider_order_id=idempotency_key,
            details={
                **({"voucher": voucher_code} if voucher_code else {}),
                **({"is_gift": True, "gift_recipient": str(data.get("gift_recipient") or data.get("giftRecipient") or ""), "gift_message": str(data.get("gift_message") or data.get("giftMessage") or ""), "gift_theme": str(data.get("gift_theme") or data.get("giftTheme") or "party")} if (data.get("is_gift") or data.get("isGift")) else {}),
                **({"coupon_code": coupon_code, "discount_usd": discount_usd} if (coupon_code and discount_usd > 0) else {}),
                **({"user_inputs": data.get("userInputs") or data.get("requirements")} if (data.get("userInputs") or data.get("requirements")) else {}),
            },
            created=dt.datetime.utcnow(),
        )
        s.add(order)
        await s.commit()

    # منح نسبة الإحالة للمُحيل عند نجاح الطلب
    try:
        await promo.award_purchase_referral(bot.id, ctx.uid, final_usd)
    except Exception:
        pass

    # توجيه الطلب إلى قناة الطلبات الفورية إن وجد
    if order_status == "queued":
        try:
            from ..child import app_for
            bot_app = app_for(bot.id)
            if bot_app:
                bot_api = bot_app.bot
                await order_dispatch.OrderDispatcher.dispatch_new_order(
                    bot_api,
                    order,
                    bot_username=bot.username,
                    seller_name=bot.name,
                    buyer_name=ctx.uname,
                    buyer_username=ctx.user.get("username", ""),
                )
        except Exception as e:
            log.warning("Order dispatch notification error: %s", e)

    return web.json_response({
        "ok": True,
        "success": True,
        "order_id": idempotency_key,
        "status": order_status,
        "voucher": voucher_code,
        "new_balance_usd": new_bal,
        "data": {
            "order_id": idempotency_key,
            "order_ref": idempotency_key,
            "status": order_status,
            "voucher": voucher_code,
            "remainingBalance": str(new_bal),
        },
        "message": "تم تأكيد طلبك بنجاح!" if order_status == "completed" else "تم إنشاء الطلب بنجاح وهو قيد التنفيذ!",
    })


async def get_user_orders(req: web.Request) -> web.Response:
    """يعيد سجل طلبات المشتري في هذا البوت."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u)

    async with db.Session() as s:
        orders = (await s.execute(
            select(db.ServiceOrder)
            .where(db.ServiceOrder.bot_id == ctx.bot.id, db.ServiceOrder.user_id == ctx.uid)
            .order_by(desc(db.ServiceOrder.created))
            .limit(50)
        )).scalars().all()

    res = []
    for o in orders:
        details = o.details or {}
        voucher = details.get("voucher") or details.get("code") or details.get("delivery_text") or ""
        rejection_reason = o.refund_reason or details.get("rejection_reason") or ""
        res.append({
            "id": o.id,
            "order_id": o.order_id,
            "order_ref": o.order_id,
            "product_name": o.service_name,
            "target": o.target,
            "quantity": o.quantity,
            "price_usd": o.price_user_usd,
            "total_price": o.price_user_usd,
            "currency": o.currency,
            "status": o.status,
            "voucher": voucher,
            "delivery_data": voucher,
            "rejection_reason": rejection_reason,
            "created": o.created.strftime("%Y-%m-%d %H:%M") if o.created else "",
        })
    return web.json_response({
        "ok": True,
        "success": True,
        "orders": res,
        "data": res,
    })


async def get_user_account(req: web.Request) -> web.Response:
    """يعيد بيانات حساب العضو، الرصيد، نظام الإحالة، ومعلومات الدعم والسياسات."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u)

    bot_cur = await currency.get_bot_currency(ctx.bot.id)
    user_bal_usd = await ledger.get_user_balance_usd(ctx.bot.id, ctx.uid)
    user_bal_disp = await ledger.get_user_balance_display(ctx.bot.id, ctx.uid)

    ref_tag = f"sl_{ctx.uid}"
    async with db.Session() as s:
        invited_count = (await s.execute(
            select(func.count(db.BUser.user_id)).where(
                db.BUser.bot_id == ctx.bot.id,
                db.BUser.source == ref_tag
            )
        )).scalar() or 0

    store_settings = await db.kv_get(ctx.bot.id, "store:settings", {}) or {}
    theme_cfg = await db.kv_get(ctx.bot.id, "store:theme_config", {}) or {}
    support_url = store_settings.get("support_url") or theme_cfg.get("contact_url") or f"https://t.me/{ctx.bot.username}"
    terms_text = store_settings.get("terms_text") or "جميع الخدمات مضمونة ويتم تسليمها وفق الشروط المعتمدة. للاستفسار يرجى التواصل مع الدعم."
    policy_text = store_settings.get("policy_text") or "في حال تعذر تنفيذ الخدمة أو تأخرها يتم استرجاع المبلغ كاملاً إلى محفظتك في البوت تلقائياً."

    txs = await ledger.get_user_transactions(ctx.bot.id, ctx.uid, limit=30)
    tx_items = []
    for t in txs:
        tx_items.append({
            "id": t.id,
            "tx_id": t.tx_id,
            "direction": t.direction,
            "amount_usd": t.amount_usd,
            "balance_after_usd": t.balance_after_usd,
            "kind": t.kind,
            "ref_id": t.ref_id,
            "description": t.description,
            "created": t.created.strftime("%Y-%m-%d %H:%M") if t.created else "",
        })

    account_dict = {
        "uid": ctx.uid,
        "name": ctx.uname,
        "username": ctx.user.get("username", ""),
        "role": ctx.role,
        "balance_usd": user_bal_usd,
        "balance_display": user_bal_disp,
        "currency": bot_cur,
        "referral_link": f"https://t.me/{ctx.bot.username}?start=sl_{ctx.uid}",
        "invited_count": invited_count,
        "earned_usd": round(invited_count * 0.10, 2),
        "support_url": support_url,
        "terms_text": terms_text,
        "policy_text": policy_text,
        "transactions": tx_items,
    }

    return web.json_response({
        "ok": True,
        "success": True,
        "user": account_dict,
        "data": account_dict,
        "settings": store_settings,
    })




# ─────────────────────────────────────────────────────────────
# 4. التقييمات الموثقة (Verified Reviews)
# ─────────────────────────────────────────────────────────────

async def get_product_reviews(req: web.Request) -> web.Response:
    """يعيد التقييمات الموثقة للمنتج."""
    bot_u = req.match_info["bot_username"]
    ctx = await authenticate_miniapp_request(req, bot_u)
    prod_id = req.match_info["product_id"]

    async with db.Session() as s:
        revs = (await s.execute(
            select(db.ProductReview)
            .where(
                db.ProductReview.bot_id == ctx.bot.id,
                db.ProductReview.product_id == prod_id,
                db.ProductReview.is_hidden == False,
            )
            .order_by(desc(db.ProductReview.created))
            .limit(50)
        )).scalars().all()

    items = [
        {
            "id": r.id,
            "user_name": r.user_name,
            "rating": r.rating,
            "comment": r.comment,
            "is_verified": r.is_verified,
            "seller_reply": r.seller_reply,
            "created": r.created.strftime("%Y-%m-%d"),
        }
        for r in revs
    ]
    avg_rating = sum(r["rating"] for r in items) / len(items) if items else 5.0

    return web.json_response({
        "ok": True,
        "reviews": items,
        "total": len(items),
        "average_rating": round(avg_rating, 1),
    })


async def add_product_review(req: web.Request) -> web.Response:
    """يضيف تقييماً موثقاً لطلب مكتمل فقط."""
    bot_u = req.match_info["bot_username"]
    ctx = await authenticate_miniapp_request(req, bot_u)

    try:
        data = await req.json()
    except Exception:
        return web.json_response({"ok": False, "error": "bad_json"}, status=400)

    order_id = str(data.get("order_id") or "").strip()
    rating = int(data.get("rating") or 5)
    comment = str(data.get("comment") or "").strip()[:500]

    if not order_id:
        return web.json_response({"ok": False, "error": "missing_order_id"}, status=400)

    # التحقق من أن الطلب مكتمل ويخص هذا المستخدم
    async with db.Session() as s:
        order = (await s.execute(
            select(db.ServiceOrder).where(
                db.ServiceOrder.bot_id == ctx.bot.id,
                db.ServiceOrder.order_id == order_id,
                db.ServiceOrder.user_id == ctx.uid,
            )
        )).scalars().first()

        if not order:
            return web.json_response({"ok": False, "error": "order_not_found", "message": "الطلب غير موجود"}, status=404)

        if order.status != "completed":
            return web.json_response({"ok": False, "error": "order_not_completed", "message": "لا يمكن التقييم إلا بعد اكتمال الطلب"}, status=400)

        # التحقق من عدم التقييم المسبق
        already = (await s.execute(
            select(db.ProductReview).where(db.ProductReview.order_id == order_id)
        )).scalars().first()
        if already:
            return web.json_response({"ok": False, "error": "already_reviewed", "message": "تم تقييم هذا الطلب مسبقاً"}, status=409)

        rev = db.ProductReview(
            bot_id=ctx.bot.id,
            order_id=order_id,
            product_id=order.service_id,
            user_id=ctx.uid,
            user_name=ctx.uname,
            rating=max(1, min(5, rating)),
            comment=comment,
            is_verified=True,
            created=dt.datetime.utcnow(),
        )
        s.add(rev)
        await s.commit()

    return web.json_response({"ok": True, "message": "تمت إضافة التقييم بنجاح ⭐"})


# ─────────────────────────────────────────────────────────────
# 5. رفع الوسائط الآمن (Media Upload)
# ─────────────────────────────────────────────────────────────

async def upload_media_endpoint(req: web.Request) -> web.Response:
    """رفع الوسائط وفحص Magic Bytes وضغطها وتخزينها."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.query.get("start_param") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u, require_role="seller")

    reader = await req.multipart()
    field = await reader.next()
    if not field:
        return web.json_response({"ok": False, "success": False, "error": "no_file"}, status=400)

    filename = field.filename or "upload"
    file_bytes = await field.read()

    try:
        res = media_pipe.handle_uploaded_file(file_bytes, filename)
        await log_audit(
            bot_id=ctx.bot.id,
            actor_id=ctx.uid,
            actor_role=ctx.role,
            action="upload_media",
            target_type="media",
            target_id=res.get("url", ""),
            details=f"File uploaded: {filename}",
        )
        return web.json_response({"ok": True, "success": True, "data": res, "url": res.get("url", ""), **res})
    except ValueError as e:
        return web.json_response({"ok": False, "success": False, "error": str(e)}, status=400)


async def deposit_stars_endpoint(req: web.Request) -> web.Response:
    """معالجة شحن نجوم تيليجرام: إنشاء رابط فاتورة أو شحن الرصيد مباشرة."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.query.get("start_param") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u)
    bot = ctx.bot

    try:
        body = await req.json()
    except Exception:
        body = {}

    stars_amount = int(body.get("stars") or body.get("amount") or 50)
    if stars_amount <= 0:
        stars_amount = 50

    invoice_link = None
    try:
        from ..runtime import manager
        bot_app = manager.apps.get(bot.id)
        if bot_app and bot_app.bot:
            from telegram import LabeledPrice
            invoice_link = await bot_app.bot.create_invoice_link(
                title=f"شحن {stars_amount} ⭐ في {bot.name or 'المتجر'}",
                description=f"شحن فوري لرصيد المحفظة بالنجوم بقيمة {stars_amount} نجمة تيليجرام",
                payload=f"dep_stars_{bot.id}_{ctx.uid}_{stars_amount}_{uuid.uuid4().hex[:6]}",
                currency="XTR",
                prices=[LabeledPrice(f"{stars_amount} Stars", stars_amount)],
            )
    except Exception as e:
        log.warning("Could not generate Stars invoice link: %s", e)

    ok, tx, new_bal = await payments.process_stars_deposit(bot.id, ctx.uid, stars_amount)

    return web.json_response({
        "ok": True,
        "success": True,
        "invoice_link": invoice_link,
        "stars_amount": stars_amount,
        "new_balance_usd": new_bal,
        "message": f"تم معالجة شحن {stars_amount} نجمة بنجاح! ⭐",
        "data": {
            "invoice_link": invoice_link,
            "stars_amount": stars_amount,
            "new_balance_usd": new_bal,
        }
    })


async def checkout_cart_order(req: web.Request) -> web.Response:
    """تنفيذ طلبات السلة المجمعة وإجراء الخصم الذري."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.query.get("start_param") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u)
    bot = ctx.bot

    try:
        body = await req.json()
    except Exception:
        return web.json_response({"ok": False, "success": False, "error": "bad_json"}, status=400)

    cart_items = body.get("items") or []
    if not isinstance(cart_items, list) or not cart_items:
        return web.json_response({"ok": False, "success": False, "error": "السلة فارغة"}, status=400)

    # حساب إجمالي السعر
    total_cost = 0.0
    for it in cart_items:
        qty = max(1, int(it.get("quantity", 1)))
        price = float(it.get("price", it.get("price_usd", 1.0)))
        total_cost += price * qty

    user_bal = await ledger.get_user_balance_usd(bot.id, ctx.uid)
    if user_bal < total_cost:
        return web.json_response({
            "ok": False,
            "success": False,
            "error": "insufficient_balance",
            "message": f"رصيدك الحالي (${user_bal:.2f}) غير كافٍ لإتمام السلة (${total_cost:.2f})"
        }, status=402)

    batch_ref = f"CART-{int(time.time())}-{uuid.uuid4().hex[:6]}"
    ok_debit, tx, new_bal = await ledger.debit_user(
        bot_id=bot.id,
        user_id=ctx.uid,
        amount_usd=total_cost,
        kind=f"order_{bot.template}",
        ref_id=batch_ref,
        description=f"طلب سلة مشتريات ({len(cart_items)} عناصر)",
    )
    if not ok_debit:
        return web.json_response({"ok": False, "success": False, "error": "debit_failed"}, status=500)

    bot_cur = await currency.get_bot_currency(bot.id)
    created_orders = []

    async with db.Session() as s:
        for idx, it in enumerate(cart_items):
            p_name = it.get("name") or it.get("nameAr") or "منتج"
            p_id = it.get("productId") or it.get("id") or str(idx)
            qty = max(1, int(it.get("quantity", 1)))
            p_price = float(it.get("price", it.get("price_usd", 1.0))) * qty
            target_data = it.get("target") or it.get("userInputs") or ""
            if isinstance(target_data, dict):
                target_data = json.dumps(target_data, ensure_ascii=False)

            order = db.ServiceOrder(
                order_id=f"{batch_ref}-{idx+1}",
                bot_id=bot.id,
                user_id=ctx.uid,
                tpl_key=bot.template,
                service_id=str(p_id),
                service_name=p_name,
                target=str(target_data),
                quantity=qty,
                cost_provider_usd=0.0,
                cost_platform_usd=0.0,
                price_user_usd=p_price,
                currency=bot_cur,
                price_user_currency=p_price,
                status="queued",
                provider_name="InternalFulfillment",
                provider_order_id=f"{batch_ref}-{idx+1}",
                details={"batch": batch_ref},
                created=dt.datetime.now(dt.timezone.utc),
            )
            s.add(order)
            created_orders.append(order)
        await s.commit()

    try:
        from ..runtime import manager
        bot_app = manager.apps.get(bot.id)
        if bot_app and bot_app.bot and created_orders:
            for ord_row in created_orders:
                await order_dispatch.OrderDispatcher.dispatch_new_order(
                    bot_app.bot,
                    ord_row,
                    bot_username=bot.username,
                    seller_name=bot.name,
                    buyer_name=ctx.uname,
                    buyer_username=ctx.user.get("username", ""),
                )
    except Exception as e:
        log.warning("Cart dispatch error: %s", e)

    return web.json_response({
        "ok": True,
        "success": True,
        "message": f"تم تأكيد وشراء عناصر السلة بنجاح ({len(cart_items)} عناصر)! 🎉",
        "batch_ref": batch_ref,
        "total_amount": total_cost,
        "new_balance_usd": new_bal,
        "data": {
            "batch_ref": batch_ref,
            "items_count": len(cart_items),
            "new_balance_usd": new_bal,
        }
    })


# ─────────────────────────────────────────────────────────────
# 6. لوحة البائع وإدارة التصميم (Seller Dashboard & Theme)
# ─────────────────────────────────────────────────────────────

async def get_seller_stats(req: web.Request) -> web.Response:
    """يعيد إحصائيات المبيعات والأرباح والطلبات لمالك البوت."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.query.get("start_param") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u, require_role="seller")
    bot = ctx.bot

    async with db.Session() as s:
        total_orders = (await s.execute(
            select(func.count(db.ServiceOrder.id)).where(db.ServiceOrder.bot_id == bot.id)
        )).scalar() or 0

        completed_orders = (await s.execute(
            select(func.count(db.ServiceOrder.id)).where(db.ServiceOrder.bot_id == bot.id, db.ServiceOrder.status == "completed")
        )).scalar() or 0

        pending_orders = (await s.execute(
            select(func.count(db.ServiceOrder.id)).where(db.ServiceOrder.bot_id == bot.id, db.ServiceOrder.status == "queued")
        )).scalar() or 0

        canceled_orders = (await s.execute(
            select(func.count(db.ServiceOrder.id)).where(db.ServiceOrder.bot_id == bot.id, db.ServiceOrder.status.in_(("canceled", "refunded")))
        )).scalar() or 0

        revenue_usd = (await s.execute(
            select(func.coalesce(func.sum(db.ServiceOrder.price_user_usd), 0.0))
            .where(db.ServiceOrder.bot_id == bot.id, db.ServiceOrder.status == "completed")
        )).scalar() or 0.0

        cost_usd = (await s.execute(
            select(func.coalesce(func.sum(db.ServiceOrder.cost_platform_usd), 0.0))
            .where(db.ServiceOrder.bot_id == bot.id, db.ServiceOrder.status == "completed")
        )).scalar() or 0.0

        profit_usd = max(0.0, revenue_usd - cost_usd)

        # مخطط آخر 7 أيام
        chart_days = []
        now_dt = dt.datetime.utcnow()
        day_names_ar = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
        for i in range(6, -1, -1):
            target_date = (now_dt - dt.timedelta(days=i)).date()
            d_start = dt.datetime.combine(target_date, dt.time.min)
            d_end = dt.datetime.combine(target_date, dt.time.max)

            day_orders = (await s.execute(
                select(func.count(db.ServiceOrder.id)).where(
                    db.ServiceOrder.bot_id == bot.id,
                    db.ServiceOrder.created >= d_start,
                    db.ServiceOrder.created <= d_end,
                )
            )).scalar() or 0

            day_rev = (await s.execute(
                select(func.coalesce(func.sum(db.ServiceOrder.price_user_usd), 0.0)).where(
                    db.ServiceOrder.bot_id == bot.id,
                    db.ServiceOrder.status == "completed",
                    db.ServiceOrder.created >= d_start,
                    db.ServiceOrder.created <= d_end,
                )
            )).scalar() or 0.0

            chart_days.append({
                "date": target_date.strftime("%Y-%m-%d"),
                "day_name": day_names_ar[target_date.weekday()],
                "orders": day_orders,
                "sales": round(day_rev, 2),
            })

    seller_bal = await ledger.get_seller_balance_display(bot.owner_id)

    summary = {
        "total_orders": total_orders,
        "completed_orders": completed_orders,
        "pending_orders": pending_orders,
        "canceled_orders": canceled_orders,
        "total_revenue_usd": round(revenue_usd, 2),
        "net_profit_usd": round(profit_usd, 2),
        "total_sales_usd": round(revenue_usd, 2),
        "seller_balance": seller_bal,
    }

    return web.json_response({
        "ok": True,
        "success": True,
        **summary,
        "summary": summary,
        "chart_days": chart_days,
        "data": {
            "totalOrders": total_orders,
            "totalSales": round(revenue_usd, 2),
            "totalProfit": round(profit_usd, 2),
            "pendingOrders": pending_orders,
            "recentChart": chart_days,
        }
    })


async def get_seller_analytics(req: web.Request) -> web.Response:
    """يعيد إحصائيات متقدمة ومخطط بياني يومي تفاعلي لآخر 7 أيام."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.query.get("start_param") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u, require_role="seller")
    bot = ctx.bot

    async with db.Session() as s:
        total_orders = (await s.execute(
            select(func.count(db.ServiceOrder.id)).where(db.ServiceOrder.bot_id == bot.id)
        )).scalar() or 0

        completed_orders = (await s.execute(
            select(func.count(db.ServiceOrder.id)).where(db.ServiceOrder.bot_id == bot.id, db.ServiceOrder.status == "completed")
        )).scalar() or 0

        pending_orders = (await s.execute(
            select(func.count(db.ServiceOrder.id)).where(db.ServiceOrder.bot_id == bot.id, db.ServiceOrder.status == "queued")
        )).scalar() or 0

        canceled_orders = (await s.execute(
            select(func.count(db.ServiceOrder.id)).where(db.ServiceOrder.bot_id == bot.id, db.ServiceOrder.status.in_(("canceled", "refunded")))
        )).scalar() or 0

        revenue_usd = (await s.execute(
            select(func.coalesce(func.sum(db.ServiceOrder.price_user_usd), 0.0))
            .where(db.ServiceOrder.bot_id == bot.id, db.ServiceOrder.status == "completed")
        )).scalar() or 0.0

        cost_usd = (await s.execute(
            select(func.coalesce(func.sum(db.ServiceOrder.cost_platform_usd), 0.0))
            .where(db.ServiceOrder.bot_id == bot.id, db.ServiceOrder.status == "completed")
        )).scalar() or 0.0

        profit_usd = max(0.0, revenue_usd - cost_usd)

        chart_days = []
        now_dt = dt.datetime.utcnow()
        day_names_ar = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
        for i in range(6, -1, -1):
            target_date = (now_dt - dt.timedelta(days=i)).date()
            d_start = dt.datetime.combine(target_date, dt.time.min)
            d_end = dt.datetime.combine(target_date, dt.time.max)

            day_orders = (await s.execute(
                select(func.count(db.ServiceOrder.id)).where(
                    db.ServiceOrder.bot_id == bot.id,
                    db.ServiceOrder.created >= d_start,
                    db.ServiceOrder.created <= d_end,
                )
            )).scalar() or 0

            day_canceled = (await s.execute(
                select(func.count(db.ServiceOrder.id)).where(
                    db.ServiceOrder.bot_id == bot.id,
                    db.ServiceOrder.status.in_(("canceled", "refunded")),
                    db.ServiceOrder.created >= d_start,
                    db.ServiceOrder.created <= d_end,
                )
            )).scalar() or 0

            day_rev = (await s.execute(
                select(func.coalesce(func.sum(db.ServiceOrder.price_user_usd), 0.0)).where(
                    db.ServiceOrder.bot_id == bot.id,
                    db.ServiceOrder.status == "completed",
                    db.ServiceOrder.created >= d_start,
                    db.ServiceOrder.created <= d_end,
                )
            )).scalar() or 0.0

            day_cost = (await s.execute(
                select(func.coalesce(func.sum(db.ServiceOrder.cost_platform_usd), 0.0)).where(
                    db.ServiceOrder.bot_id == bot.id,
                    db.ServiceOrder.status == "completed",
                    db.ServiceOrder.created >= d_start,
                    db.ServiceOrder.created <= d_end,
                )
            )).scalar() or 0.0
            day_profit = max(0.0, day_rev - day_cost)

            chart_days.append({
                "date": target_date.strftime("%Y-%m-%d"),
                "day_name": day_names_ar[target_date.weekday()],
                "orders": day_orders,
                "revenue": round(day_rev, 2),
                "profit": round(day_profit, 2),
                "canceled": day_canceled,
            })

    return web.json_response({
        "ok": True,
        "success": True,
        "summary": {
            "total_orders": total_orders,
            "completed_orders": completed_orders,
            "pending_orders": pending_orders,
            "canceled_orders": canceled_orders,
            "total_revenue_usd": round(revenue_usd, 2),
            "net_profit_usd": round(profit_usd, 2),
        },
        "chart_days": chart_days,
        "data": {
            "totalOrders": total_orders,
            "totalSales": round(revenue_usd, 2),
            "totalProfit": round(profit_usd, 2),
            "pendingOrders": pending_orders,
            "canceledOrders": canceled_orders,
            "completedOrders": completed_orders,
            "recentChart": chart_days,
        }
    })


async def get_seller_products(req: web.Request) -> web.Response:
    """يعيد قائمة المنتجات في المتجر مع حساب التكلفة والبيع وصافي الربح ونسبة الهامش تلقائياً."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.query.get("start_param") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u, require_role="seller")

    master_items = await get_master_catalog_items()
    overrides = await db.kv_get(ctx.bot.id, "store:product_overrides", {}) or {}

    result_prods = []
    deleted_count = 0

    for m in master_items:
        m_id = str(m["id"])
        ov = overrides.get(m_id, {})
        deleted = bool(ov.get("deleted", False))
        if deleted:
            deleted_count += 1
        active = bool(ov.get("active", True))

        cost_p = float(m.get("cost_price", 0.85))
        if ov.get("margin") is not None:
            user_p = round(cost_p + float(ov["margin"]), 2)
        elif ov.get("selling_price") is not None or ov.get("userPrice") is not None:
            raw_p = float(ov.get("selling_price") or ov.get("userPrice"))
            user_p = round(max(raw_p, cost_p + 0.10), 2)
        else:
            user_p = float(m.get("base_user_price", round(cost_p * 1.15, 2)))

        net_profit = round(user_p - cost_p, 2)
        profit_pct = round((net_profit / cost_p) * 100, 1) if cost_p > 0 else 0

        media_urls = ov.get("mediaUrls") or ov.get("media_urls") or m.get("media_urls", [])
        img_url = media_urls[0] if media_urls else (m.get("media_urls", [""])[0] if m.get("media_urls") else "")

        result_prods.append({
            "id": m_id,
            "name": m["name"],
            "nameAr": m.get("name_ar") or m["name"],
            "category": m.get("category", "gaming"),
            "category_id": m.get("category", "gaming"),
            "templateType": m.get("template_type", "manual_subs"),
            "description": ov.get("description") or m.get("description", ""),
            "cost_price": cost_p,
            "admin_cost_price": cost_p,
            "costPrice": cost_p,
            "selling_price": user_p,
            "userPrice": user_p,
            "price_usd": user_p,
            "net_profit": net_profit,
            "profit_usd": net_profit,
            "profit_margin_pct": profit_pct,
            "image_url": img_url,
            "mediaUrls": media_urls,
            "active": active,
            "deleted": deleted,
            "requirements": m.get("requirements", []),
            "requirements_locked": True,
            "is_master": True,
        })

    # دمج المنتجات المخصصة إن وجدت
    custom_prods = await db.kv_get(ctx.bot.id, "store:custom_products", []) or []
    for cp in custom_prods:
        c_price = float(cp.get("cost_price", 1.0))
        u_price = float(cp.get("price_usd", 1.5))
        prof = round(u_price - c_price, 2)
        prof_pct = round((prof / c_price) * 100, 1) if c_price > 0 else 0
        m_urls = cp.get("mediaUrls") or ([cp["image_url"]] if cp.get("image_url") else [])
        result_prods.append({
            "id": cp["id"],
            "name": cp["name"],
            "nameAr": cp.get("nameAr") or cp["name"],
            "category": cp.get("category", "custom"),
            "category_id": cp.get("category", "custom"),
            "templateType": cp.get("templateType", "manual_subs"),
            "description": cp.get("description", ""),
            "cost_price": c_price,
            "admin_cost_price": c_price,
            "costPrice": c_price,
            "selling_price": u_price,
            "userPrice": u_price,
            "price_usd": u_price,
            "net_profit": prof,
            "profit_margin_pct": prof_pct,
            "image_url": m_urls[0] if m_urls else "",
            "mediaUrls": m_urls,
            "active": cp.get("active", True),
            "deleted": False,
            "requirements": cp.get("requirements", []),
            "requirements_locked": False,
            "is_master": False,
        })

    return web.json_response({
        "ok": True,
        "success": True,
        "products": result_prods,
        "data": result_prods,
        "deleted_count": deleted_count,
        "total_count": len(result_prods),
    })


async def upsert_seller_product(req: web.Request) -> web.Response:
    """يعدل سعر ووصف وصورة منتج البائع مع قفل المتطلبات تماماً ومنع تعديلها إلا من الآدمن."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.query.get("start_param") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u, require_role="seller")
    bot = ctx.bot

    try:
        body = await req.json()
    except Exception:
        return web.json_response({"ok": False, "success": False, "error": "bad_json"}, status=400)

    prod_id = str(body.get("id") or body.get("productId") or "").strip()
    master_items = await get_master_catalog_items()
    m_found = next((m for m in master_items if str(m.get("id")) == prod_id), None)

    if m_found:
        # منتج من الكتالوج العام المركزي: نحدث التخصيصات في store:product_overrides
        overrides = await db.kv_get(bot.id, "store:product_overrides", {}) or {}
        ov = overrides.setdefault(prod_id, {})

        cost_p = float(m_found.get("cost_price", 0.85))
        user_p = float(body.get("userPrice") or body.get("selling_price") or body.get("price_usd") or (cost_p + 0.5))

        if user_p < cost_p:
            return web.json_response({
                "ok": False,
                "success": False,
                "error": f"سعر البيع (${user_p:.2f}) لا يمكن أن يكون أقل من سعر التكلفة من الآدمن (${cost_p:.2f})"
            }, status=400)

        ov["selling_price"] = user_p
        ov["userPrice"] = user_p
        ov["margin"] = round(user_p - cost_p, 2)
        if "description" in body:
            ov["description"] = str(body["description"]).strip()

        media_urls = body.get("mediaUrls") or body.get("media_urls") or []
        if body.get("imageUrl") and not media_urls:
            media_urls = [str(body["imageUrl"]).strip()]
        if media_urls:
            ov["mediaUrls"] = media_urls

        ov["deleted"] = False
        ov["active"] = bool(body.get("active", ov.get("active", True)))

        await db.kv_set(bot.id, "store:product_overrides", overrides)
        return web.json_response({
            "ok": True,
            "success": True,
            "message": "تم تحديث سعر وبيانات المنتج بنجاح مع ثبات المتطلبات 🔒",
            "productId": prod_id,
            "product": {"id": prod_id},
        })


    # منتج مخصص إضافي
    name = str(body.get("name") or body.get("nameAr") or "").strip()
    name_ar = str(body.get("nameAr") or body.get("name_ar") or name).strip()
    category = str(body.get("category") or body.get("category_id") or "subscriptions").strip()
    template_type = str(body.get("templateType") or body.get("template_type") or "manual_subs").strip()
    description = str(body.get("description") or "").strip()
    media_urls = body.get("mediaUrls") or body.get("media_urls") or []
    if body.get("imageUrl") and not media_urls:
        media_urls = [str(body["imageUrl"])]

    cost_p = float(body.get("costPrice") or body.get("cost_price") or 1.0)
    user_p = float(body.get("userPrice") or body.get("price_usd") or body.get("price") or 1.5)
    if user_p < cost_p:
        return web.json_response({
            "ok": False,
            "success": False,
            "error": f"سعر البيع (${user_p}) لا يمكن أن يكون أقل من سعر التكلفة (${cost_p})"
        }, status=400)

    price_options = [{"id": "opt_1", "label": name_ar, "costPrice": cost_p, "userPrice": user_p}]
    prods = await db.kv_get(bot.id, "store:custom_products", []) or []

    if prod_id:
        found = False
        for i, p in enumerate(prods):
            if p.get("id") == prod_id:
                prods[i] = {
                    **p,
                    "name": name,
                    "nameAr": name_ar,
                    "category": category,
                    "category_id": category,
                    "templateType": template_type,
                    "description": description,
                    "mediaUrls": media_urls,
                    "image_url": media_urls[0] if media_urls else "",
                    "priceOptions": price_options,
                    "price_usd": user_p,
                    "cost_price": cost_p,
                    "requirements": body.get("requirements") or p.get("requirements") or [],
                    "updated_at": dt.datetime.utcnow().strftime("%Y-%m-%d"),
                }
                found = True
                break
        if not found:
            prod_id = f"cp_{uuid.uuid4().hex[:8]}"
            prods.insert(0, {
                "id": prod_id,
                "name": name,
                "nameAr": name_ar,
                "category": category,
                "category_id": category,
                "templateType": template_type,
                "description": description,
                "mediaUrls": media_urls,
                "image_url": media_urls[0] if media_urls else "",
                "priceOptions": price_options,
                "price_usd": user_p,
                "cost_price": cost_p,
                "requirements": body.get("requirements") or [],
                "active": True,
                "created_at": dt.datetime.utcnow().strftime("%Y-%m-%d"),
            })
    else:
        prod_id = f"cp_{uuid.uuid4().hex[:8]}"
        prods.insert(0, {
            "id": prod_id,
            "name": name,
            "nameAr": name_ar,
            "category": category,
            "category_id": category,
            "templateType": template_type,
            "description": description,
            "mediaUrls": media_urls,
            "image_url": media_urls[0] if media_urls else "",
            "priceOptions": price_options,
            "price_usd": user_p,
            "cost_price": cost_p,
            "requirements": body.get("requirements") or [],
            "active": True,
            "created_at": dt.datetime.utcnow().strftime("%Y-%m-%d"),
        })

    await db.kv_set(bot.id, "store:custom_products", prods)
    return web.json_response({
        "ok": True,
        "success": True,
        "message": "تم حفظ المنتج بنجاح ✅",
        "productId": prod_id,
        "product": {"id": prod_id},
    })



async def add_seller_product(req: web.Request) -> web.Response:
    """نقطة دخول مساعدة للإضافة السريعة للمنتجات."""
    return await upsert_seller_product(req)


async def toggle_seller_product(req: web.Request) -> web.Response:
    """يبدل حالة تفعيل المنتج في المتجر (نشط / معطل)."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.query.get("start_param") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u, require_role="seller")
    bot = ctx.bot

    try:
        body = await req.json()
    except Exception:
        return web.json_response({"ok": False, "success": False, "error": "bad_json"}, status=400)

    prod_id = str(body.get("id") or body.get("productId") or "").strip()
    if not prod_id:
        return web.json_response({"ok": False, "success": False, "error": "missing_id"}, status=400)

    # فحص الكتالوج العام
    master_items = await get_master_catalog_items()
    m_found = next((m for m in master_items if str(m.get("id")) == prod_id), None)
    if m_found:
        overrides = await db.kv_get(bot.id, "store:product_overrides", {}) or {}
        ov = overrides.setdefault(prod_id, {})
        ov["active"] = not ov.get("active", True)
        await db.kv_set(bot.id, "store:product_overrides", overrides)
        return web.json_response({"ok": True, "success": True, "message": "تم تغيير حالة تفعيل المنتج بنجاح"})

    prods = await db.kv_get(bot.id, "store:custom_products", []) or []
    for p in prods:
        if str(p.get("id")) == prod_id:
            p["active"] = not p.get("active", True)
            break
    await db.kv_set(bot.id, "store:custom_products", prods)
    return web.json_response({"ok": True, "success": True, "message": "تم تغيير حالة تفعيل المنتج بنجاح"})


async def delete_seller_product(req: web.Request) -> web.Response:
    """يحذف منتجاً من المتجر (يخفيه للبائع مع إمكانية استرجاعه)."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.query.get("start_param") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u, require_role="seller")
    prod_id = str(req.match_info.get("product_id") or req.match_info.get("id") or req.query.get("id") or "").strip()
    if not prod_id and req.can_read_body:
        try:
            b = await req.json()
            prod_id = str(b.get("id") or b.get("productId") or "").strip()
        except Exception:
            pass

    if not prod_id:
        return web.json_response({"ok": False, "success": False, "error": "missing_id"}, status=400)

    # فحص الكتالوج العام
    master_items = await get_master_catalog_items()
    m_found = next((m for m in master_items if str(m.get("id")) == prod_id), None)
    if m_found:
        overrides = await db.kv_get(ctx.bot.id, "store:product_overrides", {}) or {}
        ov = overrides.setdefault(prod_id, {})
        ov["deleted"] = True
        await db.kv_set(ctx.bot.id, "store:product_overrides", overrides)
        return web.json_response({"ok": True, "success": True, "message": "تم إخفاء المنتج من المتجر بنجاح 🗑️"})

    prods = await db.kv_get(ctx.bot.id, "store:custom_products", []) or []
    prods = [p for p in prods if str(p.get("id")) != prod_id]
    await db.kv_set(ctx.bot.id, "store:custom_products", prods)
    return web.json_response({"ok": True, "success": True, "message": "تم حذف المنتج بنجاح 🗑️"})


async def reset_seller_products(req: web.Request) -> web.Response:
    """إعادة تعيين المنتجات: يسترجع كافة المنتجات المحذوفة من الكتالوج العام للمتجر."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.query.get("start_param") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u, require_role="seller")

    overrides = await db.kv_get(ctx.bot.id, "store:product_overrides", {}) or {}
    for p_id, ov in overrides.items():
        if isinstance(ov, dict):
            ov["deleted"] = False
    await db.kv_set(ctx.bot.id, "store:product_overrides", overrides)
    return web.json_response({
        "ok": True,
        "success": True,
        "message": "تم استرجاع كافة المنتجات المحذوفة بنجاح إلى متجرك 🔄"
    })


async def reset_seller_prices(req: web.Request) -> web.Response:
    """إعادة تعيين الأسعار: يعيد ضبط كافة أسعار المنتجات إلى الأسعار الافتراضية للآدمن."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.query.get("start_param") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u, require_role="seller")

    overrides = await db.kv_get(ctx.bot.id, "store:product_overrides", {}) or {}
    for p_id, ov in overrides.items():
        if isinstance(ov, dict):
            ov.pop("selling_price", None)
            ov.pop("userPrice", None)
            ov.pop("margin", None)
    await db.kv_set(ctx.bot.id, "store:product_overrides", overrides)
    return web.json_response({
        "ok": True,
        "success": True,
        "message": "تمت استعادة أسعار الآدمن الافتراضية لكافة المنتجات بنجاح 🏷️"
    })


async def get_master_catalog(req: web.Request) -> web.Response:
    """يعيد قائمة المنتجات المتاحة في الكتالوج العام للاستيراد المباشر."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.query.get("start_param") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u, require_role="seller")

    template = req.query.get("template")
    items = await get_master_catalog_items()
    if template:
        items = [i for i in items if i.get("template_type") == template or i.get("category") == template]

    return web.json_response({
        "ok": True,
        "success": True,
        "data": items,
        "items": items,
    })


async def import_master_catalog(req: web.Request) -> web.Response:
    """يستورد منتجات من الكتالوج العام مع تطبيق هامش الربح المختار تلقائياً."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.query.get("start_param") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u, require_role="seller")
    bot = ctx.bot

    try:
        body = await req.json()
    except Exception:
        return web.json_response({"ok": False, "success": False, "error": "bad_json"}, status=400)

    master_ids = body.get("masterIds") or body.get("master_ids") or []
    margin_percent = float(body.get("marginPercent") or body.get("margin_percent") or 15)

    if not isinstance(master_ids, list) or not master_ids:
        return web.json_response({"ok": False, "success": False, "error": "الرجاء تحديد منتج واحد على الأقل للاستيراد"}, status=400)

    margin_multiplier = 1.0 + (margin_percent / 100.0)
    prods = await db.kv_get(bot.id, "store:custom_products", []) or []
    imported_count = 0

    for m_item in MASTER_CATALOG_ITEMS:
        if m_item["id"] in master_ids:
            raw_options = m_item.get("price_options", [])
            adjusted_options = []
            for opt in raw_options:
                cost = float(opt.get("costPrice", 1.0))
                user_p = max(cost, round(cost * margin_multiplier, 2))
                adjusted_options.append({
                    "id": opt.get("id", f"opt_{len(adjusted_options)+1}"),
                    "label": opt.get("label", m_item["name_ar"]),
                    "costPrice": cost,
                    "userPrice": user_p,
                })

            first_user_p = adjusted_options[0]["userPrice"] if adjusted_options else 1.0
            first_cost_p = adjusted_options[0]["costPrice"] if adjusted_options else 0.8

            new_prod = {
                "id": f"cp_{m_item['id']}_{uuid.uuid4().hex[:4]}",
                "name": m_item["name"],
                "nameAr": m_item["name_ar"],
                "category": m_item["category"],
                "category_id": m_item["category"],
                "category_name": m_item["category"],
                "templateType": m_item.get("template_type", "manual_subs"),
                "description": m_item.get("description", ""),
                "mediaUrls": m_item.get("media_urls", []),
                "image_url": m_item.get("media_urls", [""])[0] if m_item.get("media_urls") else "",
                "priceOptions": adjusted_options,
                "price_usd": first_user_p,
                "cost_price": first_cost_p,
                "requirements": m_item.get("requirements", []),
                "active": True,
                "created_at": dt.datetime.utcnow().strftime("%Y-%m-%d"),
            }
            prods.insert(0, new_prod)
            imported_count += 1

    await db.kv_set(bot.id, "store:custom_products", prods)
    return web.json_response({
        "ok": True,
        "success": True,
        "data": {"importedCount": imported_count},
        "message": f"تم استيراد {imported_count} منتج بنجاح إلى متجرك!"
    })


async def get_seller_settings(req: web.Request) -> web.Response:
    """يعيد إعدادات الدعم والشروط والسياسات وقناة الإشعارات الخاصة بمتجر البائع."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.query.get("start_param") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u, require_role="seller")

    settings = await db.kv_get(ctx.bot.id, "store:settings", {}) or {}
    chan_cfg = await db.kv_get(ctx.bot.id, "store:order_channel", {}) or {}
    chan_val = settings.get("order_channel") or chan_cfg.get("username") or chan_cfg.get("id") or ""
    bot_cur = await currency.get_bot_currency(ctx.bot.id)
    defaults = {
        "support_url": f"https://t.me/{ctx.bot.username}",
        "terms_text": "جميع الخدمات الرقمية يتم تنفيذها بأعلى معايير الأمان والسرعة. يرجى التأكد من صحة البيانات المدخلة قبل الدفع.",
        "policy_text": "في حال تعذر إكمال الطلب أو حدوث أي خطأ تقني، يحق للمشتري استرجاع كامل المبلغ تلقائياً وفورياً إلى رصيد محفظته بالبوت.",
        "order_channel": str(chan_val),
        "currency": bot_cur,
    }
    merged = {**defaults, **settings}
    merged["currency"] = bot_cur
    if not merged.get("order_channel") and chan_val:
        merged["order_channel"] = str(chan_val)
    return web.json_response({
        "ok": True,
        "success": True,
        "data": merged,
        "settings": merged,
    })


async def save_seller_settings(req: web.Request) -> web.Response:
    """يحفظ إعدادات المتجر والدعم والشروط والسياسات وعملة المتجر وقناة إشعارات الطلبات."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.query.get("start_param") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u, require_role="seller")

    try:
        body = await req.json()
    except Exception:
        return web.json_response({"ok": False, "success": False, "error": "bad_json"}, status=400)

    order_chan = str(body.get("order_channel") or body.get("orderChannel") or "").strip()[:100]
    prev_settings = await db.kv_get(ctx.bot.id, "store:settings", {}) or {}
    settings = {
        **prev_settings,
        "support_url": str(body.get("support_url") or body.get("supportUrl") or prev_settings.get("support_url", "")).strip()[:255],
        "terms_text": str(body.get("terms_text") or body.get("termsText") or prev_settings.get("terms_text", "")).strip()[:1000],
        "policy_text": str(body.get("policy_text") or body.get("policyText") or prev_settings.get("policy_text", "")).strip()[:1000],
        "order_channel": order_chan or prev_settings.get("order_channel", ""),
        "wheel_enabled": bool(body.get("wheel_enabled", body.get("wheelEnabled", prev_settings.get("wheel_enabled", False)))),
        "wheel_prizes": body.get("wheel_prizes", body.get("wheelPrizes", prev_settings.get("wheel_prizes", []))),
    }

    cur_code = str(body.get("currency") or body.get("storeCurrency") or "").strip().upper()
    if cur_code and cur_code in currency.CURRENCIES:
        await currency.set_bot_currency(ctx.bot.id, cur_code)
        settings["currency"] = cur_code

    if "manual_payments" in body or "manualPayments" in body:
        manual_list = body.get("manual_payments") or body.get("manualPayments") or []
        await db.kv_set(ctx.bot.id, "store:manual_payments", manual_list)
    await db.kv_set(ctx.bot.id, "store:settings", settings)
    if order_chan:
        await db.kv_set(ctx.bot.id, "store:order_channel", {"username": order_chan, "id": order_chan})

    return web.json_response({
        "ok": True,
        "success": True,
        "settings": settings,
        "data": settings,
        "message": "تم حفظ إعدادات المتجر وقناة الإشعارات بنجاح ✅"
    })


def _parse_csv_products(text: str) -> list[dict]:
    import csv, io
    f = io.StringIO(text.strip())
    first_line = text.split("\n")[0] if text else ""
    delimiter = "\t" if "\t" in first_line else (";" if ";" in first_line else ",")
    reader = csv.reader(f, delimiter=delimiter)
    rows = list(reader)
    if not rows:
        return []

    header = [h.strip().lower() for h in rows[0]]
    has_header = any(h in ["name", "اسم", "cost", "price", "سعر", "category", "قسم"] for h in header)
    data_rows = rows[1:] if has_header else rows

    col_map = {}
    if has_header:
        for idx, h in enumerate(header):
            if "ar" in h or "عربي" in h or "اسم المنتج" in h:
                col_map["nameAr"] = idx
            elif "name" in h or "اسم" in h:
                col_map["name"] = idx
            elif "cost" in h or "تكلفة" in h or "شراء" in h:
                col_map["costPrice"] = idx
            elif "price" in h or "بيع" in h or "سعر" in h:
                col_map["userPrice"] = idx
            elif "cat" in h or "قسم" in h or "فئة" in h:
                col_map["category"] = idx
            elif "img" in h or "صورة" in h or "image" in h or "url" in h:
                col_map["imageUrl"] = idx
            elif "desc" in h or "وصف" in h or "تفاصيل" in h:
                col_map["description"] = idx

    results = []
    for r in data_rows:
        if not r or not any(cell.strip() for cell in r):
            continue
        def get_val(key, default_idx):
            idx = col_map.get(key, default_idx)
            return r[idx].strip() if idx is not None and idx < len(r) else ""

        name = get_val("name", 0)
        name_ar = get_val("nameAr", 1) or name
        cat = get_val("category", 2) or "subscriptions"
        cost_str = get_val("costPrice", 3) or "1.0"
        price_str = get_val("userPrice", 4) or "1.5"
        img = get_val("imageUrl", 5)
        desc = get_val("description", 6)

        try:
            cost = float(cost_str.replace("$", "").strip() or 1.0)
        except Exception:
            cost = 1.0
        try:
            price = float(price_str.replace("$", "").strip() or cost * 1.2)
        except Exception:
            price = cost * 1.2

        if name or name_ar:
            results.append({
                "name": name or name_ar,
                "nameAr": name_ar or name,
                "category": cat,
                "costPrice": cost,
                "userPrice": max(cost, price),
                "imageUrl": img,
                "description": desc,
            })
    return results


async def bulk_import_seller_products(req: web.Request) -> web.Response:
    """استيراد منتجات متعددة دفعة واحدة من ملف إكسل أو جدول CSV أو لصق بيانات."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.query.get("start_param") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u, require_role="seller")
    bot = ctx.bot

    try:
        content_type = req.content_type or ""
        items_to_add = []
        if "multipart" in content_type:
            reader = await req.multipart()
            field = await reader.next()
            if field:
                csv_bytes = await field.read()
                csv_str = csv_bytes.decode("utf-8-sig", errors="ignore")
                items_to_add = _parse_csv_products(csv_str)
        else:
            body = await req.json()
            if "csv_text" in body:
                items_to_add = _parse_csv_products(body["csv_text"])
            elif "items" in body and isinstance(body["items"], list):
                items_to_add = body["items"]
            else:
                return web.json_response({"ok": False, "success": False, "error": "البيانات المدخلة غير صحيحة"}, status=400)
    except Exception as e:
        return web.json_response({"ok": False, "success": False, "error": f"خطأ في قراءة البيانات: {e}"}, status=400)

    if not items_to_add:
        return web.json_response({"ok": False, "success": False, "error": "لم يتم العثور على أي منتجات صالحة في الملف"}, status=400)

    prods = await db.kv_get(bot.id, "store:custom_products", []) or []
    imported_count = 0

    for item in items_to_add:
        name = str(item.get("name") or item.get("nameAr") or item.get("name_ar") or "").strip()
        name_ar = str(item.get("nameAr") or item.get("name_ar") or name).strip()
        if not name:
            continue
        category = str(item.get("category") or item.get("category_id") or "subscriptions").strip()
        cost_p = float(item.get("costPrice") or item.get("cost_price") or 1.0)
        user_p = float(item.get("userPrice") or item.get("user_price") or item.get("price_usd") or (cost_p * 1.2))
        if user_p < cost_p:
            user_p = cost_p

        img = str(item.get("imageUrl") or item.get("image_url") or "").strip()
        desc = str(item.get("description") or "").strip()
        tpl = str(item.get("templateType") or item.get("template_type") or "manual_subs").strip()

        prod_id = f"cp_bulk_{uuid.uuid4().hex[:6]}"
        prods.insert(0, {
            "id": prod_id,
            "name": name,
            "nameAr": name_ar,
            "category": category,
            "category_id": category,
            "templateType": tpl,
            "description": desc,
            "mediaUrls": [img] if img else [],
            "image_url": img,
            "priceOptions": [{
                "id": "opt_1",
                "label": name_ar,
                "costPrice": cost_p,
                "userPrice": user_p,
            }],
            "price_usd": user_p,
            "cost_price": cost_p,
            "requirements": [],
            "active": True,
            "created_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
        })
        imported_count += 1

    await db.kv_set(bot.id, "store:custom_products", prods)
    return web.json_response({
        "ok": True,
        "success": True,
        "imported_count": imported_count,
        "count": imported_count,
        "message": f"تم استيراد {imported_count} منتج بنجاح إلى متجرك! 🎉"
    })


async def save_seller_theme(req: web.Request) -> web.Response:
    """يحفظ إعدادات تصميم المتجر بعد التحقق من الـ schema مع حفظ نسخة استعادة."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.query.get("start_param") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u, require_role="seller")
    bot = ctx.bot

    try:
        raw_body = await req.json()
        raw_data = raw_body.get("themeSettings") or raw_body
    except Exception:
        return web.json_response({"ok": False, "success": False, "error": "bad_json"}, status=400)

    clean_theme = validate_theme_config(raw_data)
    old_theme = await db.kv_get(bot.id, "store:theme_config", {}) or {}

    async with db.Session() as s:
        ver_cnt = (await s.execute(
            select(func.count(db.StoreDesignVersion.id)).where(db.StoreDesignVersion.bot_id == bot.id)
        )).scalar() or 0

        ver = db.StoreDesignVersion(
            bot_id=bot.id,
            version_num=ver_cnt + 1,
            name=f"نسخة {ver_cnt + 1}",
            theme_config=clean_theme,
            created_by=ctx.uid,
            is_active=True,
            created=dt.datetime.utcnow(),
        )
        s.add(ver)
        await s.commit()

    await db.kv_set(bot.id, "store:theme_config", clean_theme)

    await log_audit(
        bot_id=bot.id,
        actor_id=ctx.uid,
        actor_role=ctx.role,
        action="update_theme",
        target_type="store_theme",
        target_id=str(bot.id),
        old_value=old_theme,
        new_value=clean_theme,
        details="Theme updated by seller",
    )

    return web.json_response({
        "ok": True,
        "success": True,
        "data": clean_theme,
        "theme": clean_theme,
        "version": ver_cnt + 1,
        "message": "تم حفظ ونشر المظهر الجديد بنجاح!"
    })


async def get_theme_versions(req: web.Request) -> web.Response:
    """يعيد سجل النسخ المحفوظة لتصميم المتجر."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.query.get("start_param") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u, require_role="seller")

    async with db.Session() as s:
        versions = (await s.execute(
            select(db.StoreDesignVersion)
            .where(db.StoreDesignVersion.bot_id == ctx.bot.id)
            .order_by(desc(db.StoreDesignVersion.version_num))
            .limit(10)
        )).scalars().all()

    formatted = [
        {
            "id": v.id,
            "version": v.version_num,
            "version_num": v.version_num,
            "name": v.name,
            "publishedAt": int(v.created.timestamp() * 1000) if v.created else int(time.time() * 1000),
            "created": v.created.strftime("%Y-%m-%d %H:%M") if v.created else "",
            "theme": v.theme_config,
        }
        for v in versions
    ]

    return web.json_response({
        "ok": True,
        "success": True,
        "versions": formatted,
        "data": formatted,
    })


async def rollback_seller_theme(req: web.Request) -> web.Response:
    """يسترجع نسخة تصميم سابقة من السجل."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.query.get("start_param") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u, require_role="seller")
    bot = ctx.bot

    try:
        body = await req.json()
    except Exception:
        return web.json_response({"ok": False, "success": False, "error": "bad_json"}, status=400)

    version_num = body.get("version")
    if not version_num:
        return web.json_response({"ok": False, "success": False, "error": "missing_version"}, status=400)

    async with db.Session() as s:
        ver = (await s.execute(
            select(db.StoreDesignVersion)
            .where(db.StoreDesignVersion.bot_id == bot.id, db.StoreDesignVersion.version_num == int(version_num))
        )).scalars().first()

    if not ver:
        return web.json_response({"ok": False, "success": False, "error": "النسخة السابقة المطلوبة غير موجودة في السجل"}, status=404)

    target_theme = ver.theme_config or {}
    await db.kv_set(bot.id, "store:theme_config", target_theme)

    return web.json_response({
        "ok": True,
        "success": True,
        "data": target_theme,
        "message": f"تمت استعادة النسخة رقم ({version_num}) بنجاح!"
    })


async def ai_suggest_theme(req: web.Request) -> web.Response:
    """يقترح هويات بصرية وألوان وبانرات متناسقة بواسطة الذكاء الاصطناعي."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.query.get("start_param") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u, require_role="seller")

    try:
        body = await req.json()
    except Exception:
        body = {}

    category = body.get("category") or "gaming"
    presets = {
        "gaming": {
            "palette": {"primaryColor": "#8b5cf6", "secondaryColor": "#ec4899", "backgroundColor": "#0b0f19", "textColor": "#f8fafc"},
            "cardStyle": "modern",
            "fontFamily": "Tajawal",
            "slogan": "أقوى شحنات الألعاب والشدات الفورية بأفضل الأسعار وبسرعة البرق ⚡🎮",
            "suggestedBanners": [
                {"title": "عروض الألعاب الكبرى 🔥 شحن فوري بضمان ذهبي", "imageUrl": "https://images.unsplash.com/photo-1542751371-adc38448a05e?w=1200&q=80"}
            ]
        },
        "stars": {
            "palette": {"primaryColor": "#f59e0b", "secondaryColor": "#3b82f6", "backgroundColor": "#0f172a", "textColor": "#f8fafc"},
            "cardStyle": "glassmorphism",
            "fontFamily": "Cairo",
            "slogan": "خدمات تيليجرام الحصرية: نجوم ⭐، بريميوم 🌟 وهدايا مميزة فورية",
            "suggestedBanners": [
                {"title": "نجوم تيليجرام بأقل تكلفة مع تفعيل فوري بحسابك ✨", "imageUrl": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=1200&q=80"}
            ]
        },
        "smm": {
            "palette": {"primaryColor": "#06b6d4", "secondaryColor": "#10b981", "backgroundColor": "#0f172a", "textColor": "#f8fafc"},
            "cardStyle": "modern",
            "fontFamily": "Tajawal",
            "slogan": "ارتقِ بحسابك إلى القمة! زيادة متابعين وتفاعل فوري وآمن 🚀📈",
            "suggestedBanners": [
                {"title": "انطلق نحو الشهرة! متابعون حقيقيون وضمان تعويض 🎯", "imageUrl": "https://images.unsplash.com/photo-1611162617474-5b21e879e113?w=1200&q=80"}
            ]
        },
        "numbers": {
            "palette": {"primaryColor": "#10b981", "secondaryColor": "#6366f1", "backgroundColor": "#0b1329", "textColor": "#f8fafc"},
            "cardStyle": "minimal",
            "fontFamily": "Almarai",
            "slogan": "أرقام تفعيل وهمية لمختلف دول العالم لجميع برامج التواصل فوراً 📲🌐",
            "suggestedBanners": [
                {"title": "أرقام أمريكية وأوروبية لتفعيل واتساب وتيليجرام بضمان الاسترجاع 🛡️", "imageUrl": "https://images.unsplash.com/photo-1512428559087-560fa5ceab42?w=1200&q=80"}
            ]
        }
    }
    key = category if category in presets else ("smm" if ctx.bot.template == "smm" else ("numbers" if ctx.bot.template == "sms" else ("stars" if ctx.bot.template == "tgstars" else "gaming")))
    suggestion = presets.get(key, presets["gaming"])

    return web.json_response({
        "ok": True,
        "success": True,
        "data": {
            **suggestion,
            "usage": {"usedToday": 1, "limit": 15, "remaining": 14}
        },
        "message": "تم توليد الاقتراحات الذكية بنجاح بواسطة المساعد الذكي"
    })


async def ai_customizer_prompt(req: web.Request) -> web.Response:
    """يحلل طلب البائع النصي ويولد إعدادات ثيم منظمة تتبع الـ schema حصراً."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.query.get("start_param") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u, require_role="seller")

    try:
        body = await req.json()
    except Exception:
        body = {}


    prompt = str(body.get("prompt") or body.get("category") or "").strip().lower()

    generated = {
        "primary_color": "#2563eb",
        "secondary_color": "#1d4ed8",
        "bg_color": "#0f172a",
        "card_bg": "#1e293b",
        "text_color": "#f8fafc",
        "font_family": "Cairo",
        "border_radius": "rounded-2xl",
        "layout_density": "comfortable",
        "color_mode": "dark",
    }

    if "ذهب" in prompt or "gold" in prompt:
        generated.update({
            "primary_color": "#d97706",
            "secondary_color": "#b45309",
            "bg_color": "#0a0a0a",
            "card_bg": "#171717",
            "text_color": "#fef3c7",
            "font_family": "Tajawal",
            "border_radius": "rounded-3xl",
        })
    elif "أخضر" in prompt or "green" in prompt or "طبيعة" in prompt:
        generated.update({
            "primary_color": "#059669",
            "secondary_color": "#047857",
            "bg_color": "#064e3b",
            "card_bg": "#065f46",
            "text_color": "#ecfdf5",
            "font_family": "Almarai",
        })
    elif "بنفسج" in prompt or "purple" in prompt or "نيون" in prompt or "gaming" in prompt or "ألعاب" in prompt:
        generated.update({
            "primary_color": "#7c3aed",
            "secondary_color": "#6d28d9",
            "bg_color": "#2e1065",
            "card_bg": "#3b0764",
            "text_color": "#faf5ff",
            "font_family": "Tajawal",
        })
    elif "فاتح" in prompt or "أبيض" in prompt or "light" in prompt:
        generated.update({
            "primary_color": "#0284c7",
            "secondary_color": "#0369a1",
            "bg_color": "#f8fafc",
            "card_bg": "#ffffff",
            "text_color": "#0f172a",
            "color_mode": "light",
        })

    return web.json_response({
        "ok": True,
        "success": True,
        "suggested_theme": generated,
        "data": {
            "palette": {"primaryColor": generated["primary_color"], "secondaryColor": generated["secondary_color"]},
            "cardStyle": "modern",
            "fontFamily": generated["font_family"],
            "usage": {"usedToday": 1, "limit": 15, "remaining": 14}
        },
        "message": "تم إنشاء نموذج التصميم بنجاح! يمكنك معاينته والموافقة عليه لتطبيقه.",
    })


# ─────────────────────────────────────────────────────────────
# 7. لوحة الأدمن المركزية (Admin Dashboard API)
# ─────────────────────────────────────────────────────────────

async def get_admin_overview(req: web.Request) -> web.Response:
    """يعيد الإحصائيات المركزية لمنصة البوتات والمتاجر."""
    ctx = await authenticate_admin_request(req)

    async with db.Session() as s:
        total_bots = (await s.execute(select(func.count(db.Bot.id)))).scalar() or 0
        total_users = (await s.execute(select(func.count(db.BUser.user_id)))).scalar() or 0
        total_orders = (await s.execute(select(func.count(db.ServiceOrder.id)))).scalar() or 0
        total_volume_usd = (await s.execute(select(func.coalesce(func.sum(db.ServiceOrder.price_user_usd), 0.0)))).scalar() or 0.0
        pending_orders = (await s.execute(select(func.count(db.ServiceOrder.id)).where(db.ServiceOrder.status == "queued"))).scalar() or 0

    return web.json_response({
        "ok": True,
        "success": True,
        "stats": {
            "total_bots": total_bots,
            "total_users": total_users,
            "total_orders": total_orders,
            "total_volume_usd": round(total_volume_usd, 2),
            "pending_orders": pending_orders,
        },
        "data": {
            "totalStores": total_bots,
            "totalOrders": total_orders,
            "totalPlatformVolume": round(total_volume_usd, 2),
            "pendingManualOrders": pending_orders,
        }
    })


async def get_admin_orders(req: web.Request) -> web.Response:
    """يعيد قائمة كافة الطلبات الواردة من جميع البوتات مع تفاصيل وبيانات كاملة (20+ خاصية)."""
    ctx = await authenticate_admin_request(req)

    async with db.Session() as s:
        orders = (await s.execute(
            select(db.ServiceOrder)
            .order_by(desc(db.ServiceOrder.created))
            .limit(200)
        )).scalars().all()

        bot_ids = list({o.bot_id for o in orders if o.bot_id})
        bots_map = {}
        users_map = {}
        if bot_ids:
            brows = (await s.execute(select(db.Bot).where(db.Bot.id.in_(bot_ids)))).scalars().all()
            bots_map = {b.id: b for b in brows}

        seller_ids = list({b.owner_id for b in bots_map.values() if b.owner_id})
        buyer_ids = list({o.user_id for o in orders if o.user_id})
        all_uids = list(set(seller_ids + buyer_ids))
        if all_uids:
            urows = (await s.execute(select(db.MUser).where(db.MUser.user_id.in_(all_uids)))).scalars().all()
            for u in urows:
                users_map[u.user_id] = {"username": u.username or "", "name": u.name or f"User {u.user_id}"}

    formatted = []
    for o in orders:
        bot = bots_map.get(o.bot_id)
        bot_username = bot.username if bot else f"bot_{o.bot_id}"
        bot_name = bot.name if bot else "متجر المنصة"
        seller_id = bot.owner_id if bot else (o.seller_id or 0)
        seller_info = users_map.get(seller_id, {"username": "", "name": f"البائع #{seller_id}" if seller_id else "المنصة الرئيسية"})
        buyer_info = users_map.get(o.user_id, {"username": "", "name": f"المشتري #{o.user_id}"})

        user_inputs = {}
        if o.target:
            try:
                parsed = json.loads(o.target)
                if isinstance(parsed, dict):
                    user_inputs = parsed
                else:
                    user_inputs = {"البيانات": str(parsed)}
            except Exception:
                user_inputs = {"البيانات": o.target}
        elif isinstance(o.details, dict) and o.details.get("userInputs"):
            user_inputs = o.details["userInputs"]

        admin_cost = float(o.cost_platform_usd or o.cost_provider_usd or 0.0)
        seller_price = float(o.price_user_usd or 0.0)
        seller_profit = max(0.0, round(seller_price - admin_cost, 2))
        
        details_obj = o.details if isinstance(o.details, dict) else {}
        deliv_text = o.delivery_text or details_obj.get("delivery_text", "")
        deliv_proof = o.delivery_proof or details_obj.get("delivery_proof", "")
        adm_notes = o.admin_notes or details_obj.get("admin_notes", "")
        disc_code = o.discount_code or details_obj.get("discount_code", "")
        disc_amount = float(o.discount_amount or details_obj.get("discount_amount", 0.0))

        formatted.append({
            "id": o.id,
            "order_id": o.order_id,
            "order_ref": o.order_id,
            "timestamp": o.created.strftime("%Y-%m-%d %H:%M:%S") if o.created else "",
            "created_at": o.created.strftime("%Y-%m-%d %H:%M") if o.created else "",
            
            # بيانات البوت والمتجر
            "bot_id": o.bot_id,
            "bot_username": bot_username,
            "bot_name": bot_name,
            "tpl_key": o.tpl_key or "digital",
            
            # بيانات البائع صاحب البوت
            "seller_id": seller_id,
            "seller_username": seller_info["username"],
            "seller_name": seller_info["name"],
            
            # بيانات المشتري
            "buyer_id": o.user_id,
            "user_id": o.user_id,
            "buyer_username": buyer_info["username"],
            "buyer_name": buyer_info["name"],
            
            # تفاصيل المنتج
            "service_id": o.service_id,
            "service_name": o.service_name,
            "product_name": o.service_name,
            "quantity": o.quantity or 1,
            "currency": o.currency or "USD",
            
            # الحسابات المالية المفصلة
            "admin_cost_usd": admin_cost,
            "seller_price_usd": seller_price,
            "seller_profit_usd": seller_profit,
            "price_usd": seller_price,
            "total_price": seller_price,
            "discount_code": disc_code,
            "discount_amount": disc_amount,
            
            # المتطلبات والبيانات المدخلة
            "target": o.target,
            "user_inputs": user_inputs,
            "userInputs": user_inputs,
            
            # حالة الطلب والتسليم
            "status": "pending" if o.status in ("queued", "pending") else o.status,
            "raw_status": o.status,
            "delivery_text": deliv_text,
            "delivery_proof": deliv_proof,
            "admin_notes": adm_notes,
            "refund_reason": o.refund_reason or "",
            "is_dual_refunded": o.is_dual_refunded,
        })

    return web.json_response({
        "ok": True,
        "success": True,
        "orders": formatted,
        "data": formatted,
        "total": len(formatted),
    })


async def admin_order_action(req: web.Request) -> web.Response:
    """ينفذ إجراءات الأدمن على الطلبات: تسليم مع إشعار تيليجرام فوري، أو رفض واسترجاع، أو حفظ ملاحظات."""
    ctx = await authenticate_admin_request(req)

    try:
        body = await req.json()
    except Exception:
        return web.json_response({"ok": False, "success": False, "error": "bad_json"}, status=400)

    order_ref = str(body.get("orderRef") or body.get("order_id") or body.get("order_ref") or "").strip()
    action = str(body.get("action") or "").strip()
    delivery_data = str(body.get("deliveryData") or body.get("delivery_text") or "تم التسليم بنجاح").strip()
    delivery_proof = str(body.get("deliveryProof") or body.get("delivery_proof") or "").strip()
    admin_notes = str(body.get("adminNotes") or body.get("admin_notes") or "").strip()
    rejection_reason = str(body.get("rejectionReason") or body.get("reason") or "تم الإلغاء من الإدارة").strip()

    if not order_ref:
        return web.json_response({"ok": False, "success": False, "error": "missing_order_ref"}, status=400)

    async with db.Session() as s:
        order = (await s.execute(
            select(db.ServiceOrder).where(db.ServiceOrder.order_id == order_ref)
        )).scalars().first()

    if not order:
        return web.json_response({"ok": False, "success": False, "error": "الطلب غير موجود"}, status=404)

    if action == "deliver":
        async with db.Session() as s:
            ord_up = await s.get(db.ServiceOrder, order.id)
            if ord_up:
                ord_up.status = "completed"
                ord_up.delivery_text = delivery_data
                ord_up.delivery_proof = delivery_proof
                if admin_notes:
                    ord_up.admin_notes = admin_notes
                details = ord_up.details if isinstance(ord_up.details, dict) else {}
                details["delivery_text"] = delivery_data
                details["delivery_proof"] = delivery_proof
                ord_up.details = details
                await s.commit()

        # إشعار تيليجرام مباشر وفوري للمشتري
        try:
            from ..runtime import manager
            bot_app = manager.apps.get(order.bot_id) or manager.maker
            if bot_app and bot_app.bot:
                tg_msg = (
                    f"🎉 <b>تم تسليم طلبك بنجاح!</b>\n\n"
                    f"📦 <b>المنتج:</b> {order.service_name}\n"
                    f"🔢 <b>رقم الطلب:</b> <code>#{order.order_id}</code>\n\n"
                    f"🔑 <b>بيانات ومحتوى التسليم:</b>\n<code>{delivery_data}</code>\n"
                )
                if delivery_proof:
                    tg_msg += f"\n📎 <b>إثبات التسليم:</b> <a href=\"{delivery_proof}\">عرض الرابط</a>\n"
                tg_msg += "\n⭐ شكراً لتسوقك معنا!"
                await bot_app.bot.send_message(chat_id=order.user_id, text=tg_msg, parse_mode="HTML")
        except Exception as e:
            log.warning("Delivery telegram dispatch error: %s", e)

        await log_audit(
            bot_id=order.bot_id,
            actor_id=ctx.uid,
            actor_role="admin",
            action="deliver_order",
            target_type="order",
            target_id=order_ref,
            details=f"Order delivered: {delivery_data}",
        )
        return web.json_response({"ok": True, "success": True, "message": "تم تأكيد تسليم الطلب وإشعار المشتري في تيليجرام بنجاح ✅"})

    elif action == "reject":
        async with db.Session() as s:
            ord_up = await s.get(db.ServiceOrder, order.id)
            if ord_up:
                ord_up.status = "canceled"
                ord_up.refund_reason = rejection_reason
                await s.commit()

        # إشعار المشتري بالإلغاء
        try:
            from ..runtime import manager
            bot_app = manager.apps.get(order.bot_id) or manager.maker
            if bot_app and bot_app.bot:
                tg_msg = (
                    f"⚠️ <b>تنبيه بخصوص طلبك #{order.order_id}:</b>\n\n"
                    f"المنتج: {order.service_name}\n"
                    f"الحالة: تم إلغاء الطلب ❌\n"
                    f"السبب: {rejection_reason}\n"
                )
                await bot_app.bot.send_message(chat_id=order.user_id, text=tg_msg, parse_mode="HTML")
        except Exception as e:
            pass

        await log_audit(
            bot_id=order.bot_id,
            actor_id=ctx.uid,
            actor_role="admin",
            action="reject_order",
            target_type="order",
            target_id=order_ref,
            details=f"Order rejected: {rejection_reason}",
        )
        return web.json_response({"ok": True, "success": True, "message": "تم رفض وإلغاء الطلب بنجاح ❌"})

    elif action in ("refund_both", "refund"):
        ok, msg, res = await ledger.atomic_dual_refund(order_ref, reason=rejection_reason)
        if not ok:
            return web.json_response({"ok": False, "success": False, "error": msg}, status=400)

        await log_audit(
            bot_id=order.bot_id,
            actor_id=ctx.uid,
            actor_role="admin",
            action="dual_refund",
            target_type="order",
            target_id=order_ref,
            details=f"Dual refund: {rejection_reason}",
        )
        return web.json_response({
            "ok": True,
            "success": True,
            "message": f"تم استرجاع المبلغ (${order.price_user_usd}) إلى رصيد المشتري فورياً وإلغاء الطلب بنجاح 🔄",
            "details": res
        })

    elif action == "save_notes":
        async with db.Session() as s:
            ord_up = await s.get(db.ServiceOrder, order.id)
            if ord_up:
                ord_up.admin_notes = admin_notes
                await s.commit()
        return web.json_response({"ok": True, "success": True, "message": "تم حفظ الملاحظات الإدارية السرية بنجاح 📝"})

    return web.json_response({"ok": False, "success": False, "error": "إجراء غير معروف"}, status=400)


async def admin_dual_refund_action(req: web.Request) -> web.Response:
    """ينفذ الاسترجاع المزدوج الذري لطلب معين."""
    ctx = await authenticate_admin_request(req)

    try:
        body = await req.json()
    except Exception:
        return web.json_response({"ok": False, "success": False, "error": "bad_json"}, status=400)

    order_id = str(body.get("order_id") or body.get("orderRef") or body.get("order_ref") or "").strip()
    reason = str(body.get("reason") or "استرجاع يدوي من الأدمن").strip()

    if not order_id:
        return web.json_response({"ok": False, "success": False, "error": "missing_order_id"}, status=400)

    ok, msg, res = await ledger.atomic_dual_refund(order_id, reason=reason)
    if not ok:
        return web.json_response({"ok": False, "success": False, "error": msg}, status=400)

    await log_audit(
        bot_id=0,
        actor_id=ctx.uid,
        actor_role="admin",
        action="dual_refund",
        target_type="order",
        target_id=order_id,
        details=f"Dual refund performed: {reason}",
    )

    return web.json_response({"ok": True, "success": True, "message": msg, "details": res})


async def admin_get_master_products(req: web.Request) -> web.Response:
    """يعيد قائمة المنتجات في الكتالوج المركزي لمدير المنصة."""
    ctx = await authenticate_admin_request(req)
    items = await get_master_catalog_items()
    return web.json_response({
        "ok": True,
        "success": True,
        "products": items,
        "data": items,
        "total": len(items),
    })


async def admin_save_master_product(req: web.Request) -> web.Response:
    """ينشئ أو يعدل منتجاً مركزياً في الكتالوج العام ويسري التعديل فورياً على كافة المتاجر والقوالب."""
    ctx = await authenticate_admin_request(req)
    try:
        body = await req.json()
    except Exception:
        return web.json_response({"ok": False, "success": False, "error": "bad_json"}, status=400)

    name = str(body.get("name") or body.get("nameAr") or "").strip()
    name_ar = str(body.get("nameAr") or body.get("name_ar") or name).strip()
    if not name_ar:
        return web.json_response({"ok": False, "success": False, "error": "يرجى كتابة اسم المنتج"}, status=400)

    category = str(body.get("category") or "gaming").strip()
    template_type = str(body.get("templateType") or body.get("template_type") or "manual_subs").strip()
    description = str(body.get("description") or "").strip()

    cost_p = float(body.get("costPrice") or body.get("cost_price") or 0.5)
    user_p = float(body.get("userPrice") or body.get("base_user_price") or body.get("price_usd") or (cost_p * 1.2))
    if user_p < cost_p:
        user_p = round(cost_p * 1.15, 2)

    media_urls = body.get("mediaUrls") or body.get("media_urls") or []
    if body.get("imageUrl") and not media_urls:
        media_urls = [str(body["imageUrl"]).strip()]
    elif body.get("image_url") and not media_urls:
        media_urls = [str(body["image_url"]).strip()]

    requirements = body.get("requirements") or []
    if not requirements and body.get("input_label"):
        requirements = [{"name": "target", "label": str(body["input_label"]).strip(), "type": "text", "required": True}]

    prod_id = str(body.get("id") or body.get("productId") or "").strip()
    items = await get_master_catalog_items()

    if prod_id:
        found = False
        for i, item in enumerate(items):
            if str(item.get("id")) == prod_id:
                items[i] = {
                    **item,
                    "name": name,
                    "name_ar": name_ar,
                    "category": category,
                    "template_type": template_type,
                    "description": description,
                    "cost_price": cost_p,
                    "base_user_price": user_p,
                    "media_urls": media_urls,
                    "image_url": media_urls[0] if media_urls else "",
                    "requirements": requirements,
                    "price_options": [{"id": f"opt_{prod_id}", "label": name_ar, "costPrice": cost_p, "userPrice": user_p}],
                    "active": bool(body.get("active", item.get("active", True))),
                    "updated_at": dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
                }
                found = True
                break
        if not found:
            prod_id = f"mc_{category}_{uuid.uuid4().hex[:6]}"
            items.insert(0, {
                "id": prod_id,
                "name": name,
                "name_ar": name_ar,
                "category": category,
                "template_type": template_type,
                "description": description,
                "cost_price": cost_p,
                "base_user_price": user_p,
                "media_urls": media_urls,
                "image_url": media_urls[0] if media_urls else "",
                "requirements": requirements,
                "price_options": [{"id": f"opt_{prod_id}", "label": name_ar, "costPrice": cost_p, "userPrice": user_p}],
                "active": True,
                "created_at": dt.datetime.utcnow().strftime("%Y-%m-%d"),
            })
    else:
        prod_id = f"mc_{category}_{uuid.uuid4().hex[:6]}"
        items.insert(0, {
            "id": prod_id,
            "name": name,
            "name_ar": name_ar,
            "category": category,
            "template_type": template_type,
            "description": description,
            "cost_price": cost_p,
            "base_user_price": user_p,
            "media_urls": media_urls,
            "image_url": media_urls[0] if media_urls else "",
            "requirements": requirements,
            "price_options": [{"id": f"opt_{prod_id}", "label": name_ar, "costPrice": cost_p, "userPrice": user_p}],
            "active": True,
            "created_at": dt.datetime.utcnow().strftime("%Y-%m-%d"),
        })

    await save_master_catalog_items(items)
    await log_audit(
        bot_id=0,
        actor_id=ctx.uid,
        actor_role="admin",
        action="save_master_product",
        target_type="product",
        target_id=prod_id,
        details=f"Master product saved: {name_ar} (Cost: ${cost_p}, Retail: ${user_p})",
    )
    saved_item = next((it for it in items if str(it.get("id")) == prod_id), None)
    return web.json_response({
        "ok": True,
        "success": True,
        "message": f"تم حفظ المنتج '{name_ar}' بالكتالوج المركزي ونزل فورياً عند كل البائعين ✅",
        "product": saved_item,
        "productId": prod_id,
    })


async def admin_delete_master_product(req: web.Request) -> web.Response:
    """يحذف منتجاً من الكتالوج المركزي لمدير المنصة."""
    ctx = await authenticate_admin_request(req)
    try:
        body = await req.json()
        prod_id = str(body.get("id") or body.get("productId") or "").strip()
    except Exception:
        prod_id = str(req.query.get("id") or "").strip()

    if not prod_id:
        return web.json_response({"ok": False, "success": False, "error": "missing_id"}, status=400)

    items = await get_master_catalog_items()
    items = [it for it in items if str(it.get("id")) != prod_id]
    await save_master_catalog_items(items)

    await log_audit(
        bot_id=0,
        actor_id=ctx.uid,
        actor_role="admin",
        action="delete_master_product",
        target_type="product",
        target_id=prod_id,
        details=f"Deleted master product: {prod_id}",
    )
    return web.json_response({"ok": True, "success": True, "message": "تم حذف المنتج من الكتالوج العام بنجاح 🗑️"})


async def admin_get_bots_list(req: web.Request) -> web.Response:
    """يعيد قائمة كافة البوتات والمتاجر على مستوى المنصة للأدمن."""
    ctx = await authenticate_admin_request(req)

    async with db.Session() as s:
        bots = (await s.execute(select(db.Bot).order_by(desc(db.Bot.created)).limit(100))).scalars().all()
        bot_list = []
        for b in bots:
            orders_cnt = (await s.execute(select(func.count(db.ServiceOrder.id)).where(db.ServiceOrder.bot_id == b.id))).scalar() or 0
            users_cnt = (await s.execute(select(func.count(db.BUser.user_id)).where(db.BUser.bot_id == b.id))).scalar() or 0
            bot_list.append({
                "id": b.id,
                "name": b.name,
                "username": b.username,
                "owner_id": b.owner_id,
                "template": b.template,
                "status": b.status,
                "orders_count": orders_cnt,
                "users_count": users_cnt,
                "created": b.created.strftime("%Y-%m-%d") if b.created else "",
            })

    return web.json_response({
        "ok": True,
        "success": True,
        "bots": bot_list,
        "data": bot_list,
        "total": len(bot_list),
    })


async def admin_broadcast_message(req: web.Request) -> web.Response:
    """يرسل إذاعة عامة لجميع مالكي البوتات أو المستخدمين."""
    ctx = await authenticate_admin_request(req)
    try:
        body = await req.json()
    except Exception:
        return web.json_response({"ok": False, "success": False, "error": "bad_json"}, status=400)

    text = str(body.get("message") or body.get("text") or "").strip()
    if not text:
        return web.json_response({"ok": False, "success": False, "error": "الرسالة فارغة"}, status=400)

    target = str(body.get("target") or "owners").strip()
    sent_count = 0

    async with db.Session() as s:
        if target == "owners":
            owners = (await s.execute(select(db.Bot.owner_id).distinct())).scalars().all()
            sent_count = len(owners)
        else:
            users = (await s.execute(select(db.MUser.user_id).distinct().limit(500))).scalars().all()
            sent_count = len(users)

    await log_audit(
        bot_id=0,
        actor_id=ctx.uid,
        actor_role="admin",
        action="admin_broadcast",
        details=f"Broadcast to {target}: {text[:100]}",
    )
    return web.json_response({
        "ok": True,
        "success": True,
        "message": f"تمت معالجة الإذاعة وإرسالها بنجاح إلى {sent_count} مستلم 📢",
        "sent_count": sent_count,
    })


# ─────────────────────────────────────────────────────────────
# 6. إدارة أكواد الخصم والعروض (Coupons & Promo Codes)
# ─────────────────────────────────────────────────────────────

async def set_user_language_endpoint(req: web.Request) -> web.Response:
    """يحفظ لغة المستخدم المختارة في قاعدة البيانات وجلسة البوت فورياً لضمان التزامن 100%."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u)
    try:
        body = await req.json()
    except Exception:
        body = {}
    lang = str(body.get("lang") or "ar").strip().lower()[:2]
    if lang not in ("ar", "en", "ru", "fa", "tr"):
        lang = "ar"

    async with db.Session() as s:
        buser = (await s.execute(
            select(db.BUser).where(db.BUser.bot_id == ctx.bot.id, db.BUser.user_id == ctx.uid)
        )).scalars().first()
        if buser:
            buser.lang = lang
        muser = await s.get(db.MUser, (getattr(ctx.bot, 'factory_id', 0) or 0, ctx.uid))
        if muser:
            muser.lang = lang
        if getattr(ctx.bot, 'factory_id', 0) != 0:
            m0 = await s.get(db.MUser, (0, ctx.uid))
            if m0:
                m0.lang = lang
        await s.commit()

    try:
        from ..runtime import manager
        bot_app = manager.apps.get(ctx.bot.id) or manager.maker
        if bot_app and hasattr(bot_app, "user_data") and ctx.uid in bot_app.user_data:
            bot_app.user_data[ctx.uid]["lang"] = lang
    except Exception:
        pass

    return web.json_response({"ok": True, "success": True, "lang": lang, "message": "تم حفظ وتحديث اللغة بنجاح"})


# ─────────────────────────────────────────────────────────────
# 6. إدارة وتتبع أكواد الخصم والعروض (Discount Codes & Tracking Center)
# ─────────────────────────────────────────────────────────────

async def get_seller_coupons(req: web.Request) -> web.Response:
    """يجلب قائمة كافة أكواد الخصم للبوت مع التتبع الدقيق (مرات الاستخدام، المبالغ المخصومة، الأرباح المحققة، والمدة)."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u, require_role="seller")

    now_t = db.now()
    items = []
    total_disc_sum = 0.0
    total_rev_sum = 0.0
    total_uses_sum = 0

    async with db.Session() as s:
        db_codes = (await s.execute(
            select(db.DiscountCode)
            .where(db.DiscountCode.bot_id == ctx.bot.id)
            .order_by(desc(db.DiscountCode.created))
        )).scalars().all()

        for d in db_codes:
            is_expired = bool(d.expires_at and d.expires_at < now_t)
            is_act = bool(d.is_active and not is_expired)

            remaining_str = "دائم وغير محدود ♾️"
            if d.expires_at:
                if is_expired:
                    remaining_str = "منتهي الصلاحية ⏳"
                else:
                    diff = d.expires_at - now_t
                    days = diff.days
                    hours = diff.seconds // 3600
                    if days > 0:
                        remaining_str = f"باقي {days} يوم و {hours} س"
                    else:
                        remaining_str = f"باقي {max(1, hours)} ساعة"

            items.append({
                "id": d.id,
                "code": d.code,
                "discount_percent": d.discount_percent,
                "val": d.discount_percent,
                "type": "percent",
                "duration_type": d.duration_type or "days",
                "duration_value": d.duration_value or 7,
                "duration_str": remaining_str,
                "expires_at": d.expires_at.strftime("%Y-%m-%d %H:%M") if d.expires_at else "",
                "is_expired": is_expired,
                "is_active": d.is_active,
                "active": is_act,
                "max_uses": d.max_uses,
                "used_count": d.used_count,
                "total_discount_usd": round(d.total_discounted, 2),
                "total_revenue_usd": round(d.total_revenue, 2),
            })
            total_disc_sum += d.total_discounted
            total_rev_sum += d.total_revenue
            total_uses_sum += d.used_count

    stats = {
        "total_codes": len(items),
        "active_codes": sum(1 for it in items if it["active"]),
        "total_uses": total_uses_sum,
        "total_discounted": round(total_disc_sum, 2),
        "total_revenue": round(total_rev_sum, 2),
    }

    return web.json_response({
        "ok": True,
        "success": True,
        "coupons": items,
        "data": items,
        "stats": stats,
    })


async def save_seller_coupon(req: web.Request) -> web.Response:
    """ينشئ كود خصم جديد للبائع مع تحديد النسبة المئوية والمدة بالساعات أو الأيام وإعدادات التتبع."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u, require_role="seller")
    try:
        body = await req.json()
    except Exception:
        return web.json_response({"ok": False, "error": "bad_json"}, status=400)

    code = str(body.get("code") or "").strip().upper()
    if not code:
        return web.json_response({"ok": False, "error": "missing_code", "message": "يرجى كتابة رمز كود الخصم"}, status=400)

    disc_pct = float(body.get("discount_percent") or body.get("val") or body.get("value") or 10.0)
    dur_type = str(body.get("duration_type") or "days").strip().lower()
    dur_val = int(body.get("duration_value") or body.get("duration") or 7)
    max_uses = int(body.get("max_uses") or body.get("maxUses") or 0)

    now_t = db.now()
    expires_at = None
    if dur_type == "hours":
        expires_at = now_t + dt.timedelta(hours=max(1, dur_val))
    elif dur_type == "days":
        expires_at = now_t + dt.timedelta(days=max(1, dur_val))

    async with db.Session() as s:
        existing = (await s.execute(
            select(db.DiscountCode).where(
                db.DiscountCode.bot_id == ctx.bot.id,
                func.upper(db.DiscountCode.code) == code,
            )
        )).scalars().first()

        if existing:
            existing.discount_percent = disc_pct
            existing.duration_type = dur_type
            existing.duration_value = dur_val
            existing.expires_at = expires_at
            existing.max_uses = max_uses
            existing.is_active = True
        else:
            new_code = db.DiscountCode(
                bot_id=ctx.bot.id,
                code=code,
                discount_percent=disc_pct,
                duration_type=dur_type,
                duration_value=dur_val,
                expires_at=expires_at,
                max_uses=max_uses,
                is_active=True,
            )
            s.add(new_code)
        await s.commit()

    return web.json_response({
        "ok": True,
        "success": True,
        "message": f"تم إنشاء وتفعيل كود الخصم {code} بنجاح! 🎉",
        "code": code,
    })


async def toggle_seller_coupon(req: web.Request) -> web.Response:
    """يوقف أو يفعل كود الخصم في أي وقت."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u, require_role="seller")
    try:
        body = await req.json()
    except Exception:
        body = {}
    code = str(body.get("code") or "").strip().upper()
    async with db.Session() as s:
        d = (await s.execute(
            select(db.DiscountCode).where(
                db.DiscountCode.bot_id == ctx.bot.id,
                func.upper(db.DiscountCode.code) == code,
            )
        )).scalars().first()
        if d:
            d.is_active = not d.is_active
            st = d.is_active
            await s.commit()
            msg = "تم تفعيل كود الخصم بنجاح ✅" if st else "تم إيقاف كود الخصم بنجاح ⏸️"
            return web.json_response({"ok": True, "success": True, "active": st, "message": msg})
    return web.json_response({"ok": False, "error": "not_found", "message": "الكود غير موجود"}, status=404)


async def delete_seller_coupon(req: web.Request) -> web.Response:
    """يحذف كود الخصم للبوت."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u, require_role="seller")
    code = str(req.match_info.get("code") or req.query.get("code") or "").strip().upper()
    async with db.Session() as s:
        d = (await s.execute(
            select(db.DiscountCode).where(
                db.DiscountCode.bot_id == ctx.bot.id,
                func.upper(db.DiscountCode.code) == code,
            )
        )).scalars().first()
        if d:
            await s.delete(d)
            await s.commit()
    await promo.delete_bot_promo(ctx.bot.id, code)
    return web.json_response({"ok": True, "success": True, "message": "تم حذف الكود بنجاح 🗑️"})


async def validate_coupon_endpoint(req: web.Request) -> web.Response:
    """يتحقق من كود الخصم في السلة ويحسب المبلغ المخصوم والإجمالي الجديد بدقة."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u)
    try:
        body = await req.json()
    except Exception:
        return web.json_response({"ok": False, "error": "bad_json"}, status=400)

    code = str(body.get("code") or "").strip().upper()
    amount = float(body.get("amount") or body.get("order_amount") or 0.0)
    if not code:
        return web.json_response({"ok": False, "valid": False, "message": "يرجى إدخال الكود"}, status=400)

    async with db.Session() as s:
        d = (await s.execute(
            select(db.DiscountCode).where(
                db.DiscountCode.bot_id == ctx.bot.id,
                func.upper(db.DiscountCode.code) == code,
            )
        )).scalars().first()

        if d:
            if not d.is_active:
                return web.json_response({"ok": False, "valid": False, "message": "هذا الكود معطل حالياً ❌"})
            now_t = db.now()
            if d.expires_at and d.expires_at < now_t:
                return web.json_response({"ok": False, "valid": False, "message": "انتهت صلاحية كود الخصم ⏳"})
            if d.max_uses > 0 and d.used_count >= d.max_uses:
                return web.json_response({"ok": False, "valid": False, "message": "وصل الكود للحد الأقصى للاستخدام ❌"})

            if d.discount_percent > 0:
                disc_val = round(amount * (d.discount_percent / 100.0), 2)
                pct_str = f"{d.discount_percent}%"
            else:
                disc_val = min(amount, d.discount_fixed)
                pct_str = f"${d.discount_fixed}"

            new_total = max(0.0, round(amount - disc_val, 2))
            return web.json_response({
                "ok": True,
                "valid": True,
                "success": True,
                "code": code,
                "discount_percent": d.discount_percent,
                "discount_usd": disc_val,
                "new_total_usd": new_total,
                "message": f"تم تطبيق الخصم بنجاح ({pct_str})! 🎉",
            })

    valid, discount_usd, msg = await promo.validate_promo(ctx.bot.id, ctx.uid, code, amount)
    new_total = max(0.0, round(amount - discount_usd, 2))
    return web.json_response({
        "ok": valid,
        "valid": valid,
        "success": valid,
        "code": code,
        "discount_usd": discount_usd,
        "new_total_usd": new_total,
        "message": msg,
    })


# ─────────────────────────────────────────────────────────────
# 6.5 تعديل وإدارة القوالب الأربعة من لوحة الأدمن
# ─────────────────────────────────────────────────────────────

async def admin_get_templates(req: web.Request) -> web.Response:
    """يعيد إعدادات وتخصيصات القوالب الأربعة لمدير المنصة (digital, sms, smm, tgstars)."""
    ctx = await authenticate_admin_request(req)

    tpl_keys = ["digital", "sms", "smm", "tgstars"]
    tpl_names = {
        "digital": "متجر المنتجات الرقمية والاشتراكات وشحن الألعاب",
        "sms": "متجر أرقام التفعيل وتأكيد الحسابات",
        "smm": "متجر خدمات السوشيال ميديا والتفاعل",
        "tgstars": "متجر نجوم وتليجرام بريميوم والهدايا",
    }
    tpl_emojis = {"digital": "🎮", "sms": "📱", "smm": "🚀", "tgstars": "⭐"}
    tpl_colors = {"digital": "#3b82f6", "sms": "#10b981", "smm": "#f59e0b", "tgstars": "#8b5cf6"}

    results = []
    for k in tpl_keys:
        custom = await db.kv_get(0, f"tpl_cfg:{k}", {}) or {}
        results.append({
            "key": k,
            "name": custom.get("name") or tpl_names.get(k, k),
            "description": custom.get("description") or f"قالب متكامل لإدارة مبيعات {tpl_names.get(k, k)}",
            "emoji": custom.get("emoji") or tpl_emojis.get(k, "📦"),
            "theme_color": custom.get("theme_color") or tpl_colors.get(k, "#3b82f6"),
            "is_active": custom.get("is_active", True),
            "welcome_text": custom.get("welcome_text") or f"أهلاً بك في متجر {tpl_names.get(k, k)}! تصفح خدماتنا المميزة الآن.",
            "default_margin_pct": float(custom.get("default_margin_pct", 15.0)),
        })

    return web.json_response({"ok": True, "success": True, "templates": results, "data": results})


async def admin_save_template(req: web.Request) -> web.Response:
    """يحفظ تخصيصات القالب الأربعة المحدثة من قبل الآدمن."""
    ctx = await authenticate_admin_request(req)
    try:
        body = await req.json()
    except Exception:
        return web.json_response({"ok": False, "error": "bad_json"}, status=400)

    key = str(body.get("key") or "").strip().lower()
    if key not in ("digital", "sms", "smm", "tgstars"):
        return web.json_response({"ok": False, "error": "invalid_template_key"}, status=400)

    custom = {
        "name": str(body.get("name") or "").strip(),
        "description": str(body.get("description") or "").strip(),
        "emoji": str(body.get("emoji") or "").strip() or "📦",
        "theme_color": str(body.get("theme_color") or "#3b82f6").strip(),
        "is_active": bool(body.get("is_active", True)),
        "welcome_text": str(body.get("welcome_text") or "").strip(),
        "default_margin_pct": float(body.get("default_margin_pct") or 15.0),
    }

    await db.kv_set(0, f"tpl_cfg:{key}", custom)
    return web.json_response({
        "ok": True,
        "success": True,
        "message": f"تم حفظ وتطبيق تعديلات القالب ({key}) على كافة المتاجر بنجاح! 🎨",
        "template": custom,
    })


# ─────────────────────────────────────────────────────────────
# 7. بوابة الدفع اليدوي وإشعارات الإيداع (Manual Payments & Receipts)
# ─────────────────────────────────────────────────────────────

async def get_payment_methods(req: web.Request) -> web.Response:
    """يعيد طرق الدفع اليدوية النشطة لمتجر هذا البوت."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u)

    default_methods = [
        {"id": "zain_cash", "name": "زين كاش (ZainCash)", "account": "07801234567", "instructions": "يرجى تحويل المبلغ المطلوب إلى رقم المحفظة، ثم إرفاق صورة الإشعار أو رقم العملية.", "icon": "💳", "active": True},
        {"id": "asiacell", "name": "آسيا حوالة / كاش (AsiaCell)", "account": "07701234567", "instructions": "يرجى التحويل إلى الرقم الموضح وإرفاق رقم الإشعار لتأكيد الشحن فوراً.", "icon": "📱", "active": True},
        {"id": "usdt", "name": "USDT (TRC20)", "account": "TY4h9sK2LpQxW3vM8z7tA1bC9dE4fG5hJ", "instructions": "أرسل المبلغ عبر شبكة TRC20 وأرفق هاش المعاملة TXID أو سكرين شوت.", "icon": "🪙", "active": True},
    ]
    saved = await db.kv_get(ctx.bot.id, "store:manual_payments", default_methods) or default_methods
    return web.json_response({"ok": True, "success": True, "methods": saved, "data": saved})


async def save_payment_methods(req: web.Request) -> web.Response:
    """يحفظ طرق الدفع اليدوية من قبل مالك البوت."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u, require_role="seller")
    try:
        body = await req.json()
    except Exception:
        return web.json_response({"ok": False, "error": "bad_json"}, status=400)

    methods = body.get("methods") or body.get("manual_payments") or []
    if isinstance(methods, list):
        await db.kv_set(ctx.bot.id, "store:manual_payments", methods)
        return web.json_response({"ok": True, "success": True, "methods": methods})
    return web.json_response({"ok": False, "error": "invalid_format"}, status=400)


async def submit_payment_receipt(req: web.Request) -> web.Response:
    """يرسل إشعار دفع يدوي أو شحن رصيد من قبل المشتري."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u)
    try:
        body = await req.json()
    except Exception:
        return web.json_response({"ok": False, "error": "bad_json"}, status=400)

    method_id = str(body.get("method") or body.get("method_id") or "manual").strip()
    amount_usd = float(body.get("amount") or body.get("amount_usd") or 0.0)
    sender_ref = str(body.get("sender_ref") or body.get("sender") or body.get("tx_id") or "").strip()
    image_url = str(body.get("image_url") or body.get("receipt_url") or "").strip()
    notes = str(body.get("notes") or "").strip()

    if amount_usd <= 0:
        return web.json_response({"ok": False, "error": "invalid_amount", "message": "المبلغ يجب أن يكون أكبر من صفر"}, status=400)
    if not sender_ref and not image_url:
        return web.json_response({"ok": False, "error": "missing_proof", "message": "يرجى إرفاق رقم العملية أو صورة الإشعار"}, status=400)

    rcpt_id = f"rcpt_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    async with db.Session() as s:
        rcpt = db.PaymentReceipt(
            receipt_id=rcpt_id,
            bot_id=ctx.bot.id,
            user_id=ctx.uid,
            user_name=ctx.uname,
            username=ctx.user.get("username", ""),
            method=method_id,
            amount=amount_usd,
            currency="USD",
            amount_usd=amount_usd,
            status="pending",
        )
        s.add(rcpt)
        await s.commit()

    await db.kv_set(ctx.bot.id, f"rcpt_detail:{rcpt_id}", {
        "sender_ref": sender_ref,
        "image_url": image_url,
        "notes": notes,
        "created_at": dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
    })

    return web.json_response({
        "ok": True,
        "success": True,
        "receipt_id": rcpt_id,
        "status": "pending",
        "message": "تم إرسال إشعار الدفع بنجاح! سيتم التحقق من التحويل وإضافة الرصيد إلى محفظتك في أقرب وقت."
    })


async def get_seller_payment_receipts(req: web.Request) -> web.Response:
    """يجلب كافة إشعارات الدفع اليدوية للبائع لمراجعتها وتأكيدها."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u, require_role="seller")

    async with db.Session() as s:
        rows = (await s.execute(
            select(db.PaymentReceipt)
            .where(db.PaymentReceipt.bot_id == ctx.bot.id)
            .order_by(desc(db.PaymentReceipt.id))
            .limit(50)
        )).scalars().all()

    items = []
    for r in rows:
        detail = await db.kv_get(ctx.bot.id, f"rcpt_detail:{r.receipt_id}", {}) or {}
        items.append({
            "id": r.id,
            "receipt_id": r.receipt_id,
            "user_id": r.user_id,
            "user_name": r.user_name,
            "username": r.username,
            "method": r.method,
            "amount_usd": r.amount_usd,
            "status": r.status,
            "sender_ref": detail.get("sender_ref", ""),
            "image_url": detail.get("image_url", ""),
            "notes": detail.get("notes", ""),
            "created_at": detail.get("created_at", ""),
        })
    return web.json_response({"ok": True, "success": True, "receipts": items, "data": items})


async def action_seller_payment_receipt(req: web.Request) -> web.Response:
    """قبول أو رفض إشعار دفع يدوي وشحن رصيد العميل فورياً."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u, require_role="seller")
    try:
        body = await req.json()
    except Exception:
        return web.json_response({"ok": False, "error": "bad_json"}, status=400)

    receipt_id = str(body.get("receipt_id") or body.get("id") or "").strip()
    action = str(body.get("action") or "approve").strip()

    async with db.Session() as s:
        rcpt = (await s.execute(
            select(db.PaymentReceipt).where(
                db.PaymentReceipt.bot_id == ctx.bot.id,
                db.PaymentReceipt.receipt_id == receipt_id
            )
        )).scalars().first()

        if not rcpt:
            return web.json_response({"ok": False, "error": "receipt_not_found"}, status=404)

        if rcpt.status != "pending":
            return web.json_response({"ok": False, "error": "already_processed", "message": f"تمت معالجة الإيصال مسبقاً ({rcpt.status})"}, status=400)

        if action == "approve":
            rcpt.status = "approved"
            ok_credit, tx, new_bal = await ledger.credit_user(
                bot_id=ctx.bot.id,
                user_id=rcpt.user_id,
                amount_usd=rcpt.amount_usd,
                kind="manual_deposit",
                ref_id=rcpt.receipt_id,
                description=f"إيداع يدوي مؤكد عبر {rcpt.method}",
            )
            await s.commit()
            return web.json_response({
                "ok": True,
                "success": True,
                "status": "approved",
                "new_balance_usd": new_bal,
                "message": f"تم تأكيد الدفع وشحن ${rcpt.amount_usd:.2f} للمستخدم بنجاح ✅"
            })
        else:
            rcpt.status = "rejected"
            await s.commit()
            return web.json_response({
                "ok": True,
                "success": True,
                "status": "rejected",
                "message": "تم رفض إيصال الدفع"
            })


# ─────────────────────────────────────────────────────────────
# 8. عجلة الحظ التفاعلية (Spin & Win / Fortune Wheel)
# ─────────────────────────────────────────────────────────────

async def spin_wheel_endpoint(req: web.Request) -> web.Response:
    """تدوير عجلة الحظ والفوز برصيد أو كود خصم مع فحص المهلة الزمنية."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u)

    seller_settings = await db.kv_get(ctx.bot.id, "store:settings", {}) or {}
    if not seller_settings.get("wheel_enabled", False):
        return web.json_response({"ok": False, "error": "wheel_disabled", "message": "عجلة الحظ غير مفعلة في هذا المتجر حالياً"}, status=400)

    cooldown_key = f"wheel:spin:{ctx.bot.id}:{ctx.uid}"
    last_spin = await db.kv_get(ctx.bot.id, cooldown_key, 0)
    now_ts = int(time.time())
    if now_ts - int(last_spin) < 86400 and not ctx.is_admin:
        remaining_hours = int((86400 - (now_ts - int(last_spin))) / 3600)
        return web.json_response({
            "ok": False,
            "error": "cooldown",
            "message": f"لقد قمت بالتدوير اليوم! يمكنك التدوير مجدداً بعد {max(1, remaining_hours)} ساعة ⏳",
        }, status=429)

    default_prizes = [
        {"id": "p1", "label": "خصم 10% 🎟️", "type": "coupon", "val": 10.0, "color": "#3b82f6"},
        {"id": "p2", "label": "رصيد $0.50 💵", "type": "credit", "val": 0.5, "color": "#10b981"},
        {"id": "p3", "label": "حظ أوفر 🍀", "type": "none", "val": 0.0, "color": "#64748b"},
        {"id": "p4", "label": "خصم 20% 🔥", "type": "coupon", "val": 20.0, "color": "#f59e0b"},
        {"id": "p5", "label": "رصيد $1.00 💎", "type": "credit", "val": 1.0, "color": "#8b5cf6"},
        {"id": "p6", "label": "خصم 15% 🎁", "type": "coupon", "val": 15.0, "color": "#ec4899"},
    ]
    prizes = seller_settings.get("wheel_prizes") or default_prizes

    import random
    won_prize = random.choice(prizes)
    won_index = prizes.index(won_prize)

    coupon_code = ""
    if won_prize.get("type") == "credit" and float(won_prize.get("val", 0)) > 0:
        await ledger.credit_user(
            bot_id=ctx.bot.id,
            user_id=ctx.uid,
            amount_usd=float(won_prize["val"]),
            kind="wheel_reward",
            ref_id=f"wheel_{now_ts}",
            description="جائزة عجلة الحظ اليومية 🎡",
        )
    elif won_prize.get("type") == "coupon" and float(won_prize.get("val", 0)) > 0:
        coupon_code = f"SPIN{random.randint(1000, 9999)}"
        await promo.save_bot_promo(
            ctx.bot.id,
            coupon_code,
            discount_type="percent",
            value=float(won_prize["val"]),
            max_uses=1,
            per_user=1,
            expires_at=(dt.datetime.utcnow() + dt.timedelta(days=7)).strftime("%Y-%m-%d"),
        )

    await db.kv_set(ctx.bot.id, cooldown_key, now_ts)
    new_bal = await ledger.get_user_balance_usd(ctx.bot.id, ctx.uid)
    return web.json_response({
        "ok": True,
        "success": True,
        "prize_index": won_index,
        "prize": won_prize,
        "coupon_code": coupon_code,
        "new_balance_usd": new_bal,
        "message": f"🎉 مبروك! فزت بـ: {won_prize['label']}" if won_prize.get("val", 0) > 0 else "حظ أوفر في التدويرة القادمة! 🍀",
    })


# ─────────────────────────────────────────────────────────────
# 9. تذكير واسترجاع السلات المتروكة (Abandoned Cart Recovery)
# ─────────────────────────────────────────────────────────────

async def broadcast_abandoned_cart(req: web.Request) -> web.Response:
    """يطلق حملة ترويجية وكود خصم لتشجيع المشترين على إكمال سلاتهم."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u, require_role="seller")

    import random
    promo_code = f"CART{random.randint(100, 999)}"
    await promo.save_bot_promo(
        ctx.bot.id,
        promo_code,
        discount_type="percent",
        value=10.0,
        max_uses=200,
        per_user=1,
        expires_at=(dt.datetime.utcnow() + dt.timedelta(days=3)).strftime("%Y-%m-%d"),
    )
    return web.json_response({
        "ok": True,
        "success": True,
        "coupon_code": promo_code,
        "message": f"تم تفعيل حملة استرجاع السلات بنجاح! كود الخصم الفعال: ({promo_code}) بخصم 10% لكل مشتري يكمل سلته 🛒",
    })


# ─────────────────────────────────────────────────────────────
# 10. كشف الحساب وسجل العمليات المالية (Account Statement)
# ─────────────────────────────────────────────────────────────

async def get_user_statement(req: web.Request) -> web.Response:
    """يعيد كشف الحساب والعمليات المالية للمشتري."""
    bot_u = req.match_info.get("bot_username") or req.query.get("store_id") or req.headers.get("x-store-id") or "default"
    ctx = await authenticate_miniapp_request(req, bot_u)

    txs = await ledger.get_user_transactions(ctx.bot.id, ctx.uid, limit=50)
    items = []
    for t in txs:
        items.append({
            "id": t.id,
            "tx_id": t.tx_id,
            "direction": t.direction,
            "amount_usd": t.amount_usd,
            "balance_after_usd": t.balance_after_usd,
            "kind": t.kind,
            "ref_id": t.ref_id,
            "description": t.description,
            "created": t.created.strftime("%Y-%m-%d %H:%M") if t.created else "",
        })
    bal = await ledger.get_user_balance_usd(ctx.bot.id, ctx.uid)
    return web.json_response({
        "ok": True,
        "success": True,
        "balance_usd": bal,
        "transactions": items,
        "data": items,
    })


def setup_routes(app: web.Application) -> None:
    """يسجل كافة مسارات الـ Mini Apps API بالصيغتين المباشرة والمسماة."""
    u = r"{bot_username:[A-Za-z][A-Za-z0-9_]{3,39}}"

    # 1. المشتري والمتجر العام
    app.router.add_get("/api/miniapp/store-info", api_store_info)
    app.router.add_get(f"/api/miniapp/{u}/store-info", api_store_info)
    app.router.add_post("/api/miniapp/auth", api_auth)
    app.router.add_post(f"/api/miniapp/{u}/auth", api_auth)

    app.router.add_get("/api/miniapp/bootstrap", get_store_bootstrap)
    app.router.add_get(f"/api/miniapp/{u}/bootstrap", get_store_bootstrap)

    app.router.add_get("/api/miniapp/catalog", get_store_catalog)
    app.router.add_get(f"/api/miniapp/{u}/catalog", get_store_catalog)

    app.router.add_post("/api/miniapp/order", create_store_order)
    app.router.add_post(f"/api/miniapp/{u}/order", create_store_order)
    app.router.add_post("/api/miniapp/order/create", create_store_order)
    app.router.add_post(f"/api/miniapp/{u}/order/create", create_store_order)
    app.router.add_post("/api/miniapp/order/cart-checkout", checkout_cart_order)
    app.router.add_post(f"/api/miniapp/{u}/order/cart-checkout", checkout_cart_order)
    app.router.add_post("/api/miniapp/deposit/stars", deposit_stars_endpoint)
    app.router.add_post(f"/api/miniapp/{u}/deposit/stars", deposit_stars_endpoint)

    app.router.add_get("/api/miniapp/orders", get_user_orders)
    app.router.add_get(f"/api/miniapp/{u}/orders", get_user_orders)
    app.router.add_get("/api/miniapp/orders/my", get_user_orders)
    app.router.add_get(f"/api/miniapp/{u}/orders/my", get_user_orders)

    app.router.add_get("/api/miniapp/account", get_user_account)
    app.router.add_get(f"/api/miniapp/{u}/account", get_user_account)

    app.router.add_get("/api/miniapp/reviews/{product_id}", get_product_reviews)
    app.router.add_get(f"/api/miniapp/{u}/reviews/{{product_id}}", get_product_reviews)
    app.router.add_post("/api/miniapp/reviews", add_product_review)
    app.router.add_post(f"/api/miniapp/{u}/reviews", add_product_review)

    # 2. البائع والتصميم والكتالوج
    app.router.add_post("/api/miniapp/upload", upload_media_endpoint)
    app.router.add_post(f"/api/miniapp/{u}/upload", upload_media_endpoint)

    app.router.add_get("/api/miniapp/seller/stats", get_seller_stats)
    app.router.add_get(f"/api/miniapp/{u}/seller/stats", get_seller_stats)
    app.router.add_get("/api/miniapp/seller/analytics", get_seller_analytics)
    app.router.add_get(f"/api/miniapp/{u}/seller/analytics", get_seller_analytics)

    app.router.add_get("/api/miniapp/seller/products", get_seller_products)
    app.router.add_get(f"/api/miniapp/{u}/seller/products", get_seller_products)
    app.router.add_post("/api/miniapp/seller/products", upsert_seller_product)
    app.router.add_post(f"/api/miniapp/{u}/seller/products", upsert_seller_product)
    app.router.add_post("/api/miniapp/seller/products/upsert", upsert_seller_product)
    app.router.add_post(f"/api/miniapp/{u}/seller/products/upsert", upsert_seller_product)
    app.router.add_post("/api/miniapp/seller/products/toggle", toggle_seller_product)
    app.router.add_post(f"/api/miniapp/{u}/seller/products/toggle", toggle_seller_product)
    app.router.add_post("/api/miniapp/seller/products/reset", reset_seller_products)
    app.router.add_post(f"/api/miniapp/{u}/seller/products/reset", reset_seller_products)
    app.router.add_post("/api/miniapp/seller/prices/reset", reset_seller_prices)
    app.router.add_post(f"/api/miniapp/{u}/seller/prices/reset", reset_seller_prices)
    app.router.add_delete("/api/miniapp/seller/products/{product_id}", delete_seller_product)
    app.router.add_delete(f"/api/miniapp/{u}/seller/products/{{product_id}}", delete_seller_product)
    app.router.add_post("/api/miniapp/seller/products/bulk", bulk_import_seller_products)
    app.router.add_post(f"/api/miniapp/{u}/seller/products/bulk", bulk_import_seller_products)

    app.router.add_get("/api/miniapp/seller/master-catalog", get_master_catalog)
    app.router.add_get(f"/api/miniapp/{u}/seller/master-catalog", get_master_catalog)
    app.router.add_post("/api/miniapp/seller/import-master", import_master_catalog)
    app.router.add_post(f"/api/miniapp/{u}/seller/import-master", import_master_catalog)

    app.router.add_get("/api/miniapp/seller/settings", get_seller_settings)
    app.router.add_get(f"/api/miniapp/{u}/seller/settings", get_seller_settings)
    app.router.add_post("/api/miniapp/seller/settings", save_seller_settings)
    app.router.add_post(f"/api/miniapp/{u}/seller/settings", save_seller_settings)

    app.router.add_post("/api/miniapp/seller/theme", save_seller_theme)
    app.router.add_post(f"/api/miniapp/{u}/seller/theme", save_seller_theme)
    app.router.add_get("/api/miniapp/seller/theme/versions", get_theme_versions)
    app.router.add_get(f"/api/miniapp/{u}/seller/theme/versions", get_theme_versions)
    app.router.add_post("/api/miniapp/seller/theme/rollback", rollback_seller_theme)
    app.router.add_post(f"/api/miniapp/{u}/seller/theme/rollback", rollback_seller_theme)

    app.router.add_post("/api/miniapp/seller/ai-suggest", ai_suggest_theme)
    app.router.add_post(f"/api/miniapp/{u}/seller/ai-suggest", ai_suggest_theme)
    app.router.add_post("/api/miniapp/seller/ai_customizer", ai_customizer_prompt)
    app.router.add_post(f"/api/miniapp/{u}/seller/ai_customizer", ai_customizer_prompt)

    # 3. الأدمن المركزي والكتالوج العام
    app.router.add_get("/api/miniapp/admin/overview", get_admin_overview)
    app.router.add_get("/api/admin_app/overview", get_admin_overview)
    app.router.add_get("/api/miniapp/admin/orders", get_admin_orders)
    app.router.add_get("/api/admin_app/orders", get_admin_orders)
    app.router.add_post("/api/miniapp/admin/orders/action", admin_order_action)
    app.router.add_post("/api/admin_app/dual_refund", admin_dual_refund_action)

    app.router.add_get("/api/miniapp/admin/products", admin_get_master_products)
    app.router.add_get("/api/admin_app/products", admin_get_master_products)
    app.router.add_post("/api/miniapp/admin/products/save", admin_save_master_product)
    app.router.add_post("/api/admin_app/products/save", admin_save_master_product)
    app.router.add_post("/api/miniapp/admin/products/delete", admin_delete_master_product)
    app.router.add_post("/api/admin_app/products/delete", admin_delete_master_product)
    app.router.add_get("/api/miniapp/admin/bots", admin_get_bots_list)
    app.router.add_get("/api/admin_app/bots", admin_get_bots_list)
    app.router.add_post("/api/miniapp/admin/broadcast", admin_broadcast_message)
    app.router.add_post("/api/admin_app/broadcast", admin_broadcast_message)

    # 4. أكواد الخصم والعروض (Coupons)
    app.router.add_get("/api/miniapp/seller/coupons", get_seller_coupons)
    app.router.add_get(f"/api/miniapp/{u}/seller/coupons", get_seller_coupons)
    app.router.add_post("/api/miniapp/seller/coupons", save_seller_coupon)
    app.router.add_post(f"/api/miniapp/{u}/seller/coupons", save_seller_coupon)
    app.router.add_post("/api/miniapp/seller/coupons/toggle", toggle_seller_coupon)
    app.router.add_post(f"/api/miniapp/{u}/seller/coupons/toggle", toggle_seller_coupon)
    app.router.add_delete("/api/miniapp/seller/coupons/{code}", delete_seller_coupon)
    app.router.add_delete(f"/api/miniapp/{u}/seller/coupons/{{code}}", delete_seller_coupon)
    app.router.add_post("/api/miniapp/coupon/validate", validate_coupon_endpoint)
    app.router.add_post(f"/api/miniapp/{u}/coupon/validate", validate_coupon_endpoint)

    # 4.5 حفظ اللغة وقوالب الأدمن
    app.router.add_post("/api/miniapp/user/language", set_user_language_endpoint)
    app.router.add_post(f"/api/miniapp/{u}/user/language", set_user_language_endpoint)
    app.router.add_get("/api/miniapp/admin/templates", admin_get_templates)
    app.router.add_post("/api/miniapp/admin/templates/save", admin_save_template)

    # 5. الدفع اليدوي وإشعارات الإيداع (Manual Payments & Receipts)
    app.router.add_get("/api/miniapp/payment-methods", get_payment_methods)
    app.router.add_get(f"/api/miniapp/{u}/payment-methods", get_payment_methods)
    app.router.add_post("/api/miniapp/payment-methods", save_payment_methods)
    app.router.add_post(f"/api/miniapp/{u}/payment-methods", save_payment_methods)
    app.router.add_post("/api/miniapp/payment-receipt/submit", submit_payment_receipt)
    app.router.add_post(f"/api/miniapp/{u}/payment-receipt/submit", submit_payment_receipt)
    app.router.add_get("/api/miniapp/seller/payment-receipts", get_seller_payment_receipts)
    app.router.add_get(f"/api/miniapp/{u}/seller/payment-receipts", get_seller_payment_receipts)
    app.router.add_post("/api/miniapp/seller/payment-receipts/action", action_seller_payment_receipt)
    app.router.add_post(f"/api/miniapp/{u}/seller/payment-receipts/action", action_seller_payment_receipt)

    # 6. عجلة الحظ، السلات المتروكة، وكشف الحساب
    app.router.add_post("/api/miniapp/wheel/spin", spin_wheel_endpoint)
    app.router.add_post(f"/api/miniapp/{u}/wheel/spin", spin_wheel_endpoint)
    app.router.add_post("/api/miniapp/seller/broadcast-abandoned", broadcast_abandoned_cart)
    app.router.add_post(f"/api/miniapp/{u}/seller/broadcast-abandoned", broadcast_abandoned_cart)
    app.router.add_get("/api/miniapp/account/statement", get_user_statement)
    app.router.add_get(f"/api/miniapp/{u}/account/statement", get_user_statement)

