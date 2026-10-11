"""واجهات برمجة التطبيقات الشاملة للتطبيقات المصغرة (Telegram Mini Apps API)."""
from __future__ import annotations

import datetime as dt
import json
import logging
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


def validate_theme_config(data: dict[str, Any]) -> dict[str, Any]:
    """يتحقق من مطابقة إعدادات التصميم للمخطط الصارم ويمنع أي حقول مجهولة أو كود."""
    clean = {}
    for k, expected_type in STORE_THEME_SCHEMA.items():
        val = data.get(k)
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
    bot_u = req.match_info["bot_username"]
    ctx = await authenticate_miniapp_request(req, bot_u)
    bot = ctx.bot

    # جلب إعدادات الثيم والتصميم
    theme_cfg = await db.kv_get(bot.id, "store:theme_config", {}) or {}
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
        "contact_url": f"https://t.me/{bot.username}",
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
    })


# ─────────────────────────────────────────────────────────────
# 2. الكتالوج والمنتجات والأقسام
# ─────────────────────────────────────────────────────────────

async def get_store_catalog(req: web.Request) -> web.Response:
    """يعيد كتالوج المنتجات والأقسام والخيارات للبوت المعني."""
    bot_u = req.match_info["bot_username"]
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
            stock_cnt = await DigitalManager.get_stock_count(bot.id, s["id"])

            products.append({
                "id": s["id"],
                "category_id": c_key,
                "name": s["name_ar"],
                "description": s.get("desc_ar", ""),
                "price_usd": disc_price,
                "original_price_usd": p_price,
                "has_discount": has_disc,
                "discount_percent": round((1 - disc_price / p_price) * 100) if has_disc and p_price > 0 else 0,
                "input_label": s.get("field_ar", "ID الحساب أو البيانات"),
                "stock_count": stock_cnt,
                "is_instant": stock_cnt > 0,
                "is_manual": True,
                "icon": s.get("icon", "🎮"),
                "image_url": s.get("image_url", ""),
            })

    elif tpl_key == "sms":
        from ..modules.providers.sms import SMS_APPS, SMS_COUNTRIES
        categories = [{"id": c_code, "name": f"{c_info['flag']} {c_info['name_ar']}", "icon": c_info["flag"]} for c_code, c_info in SMS_COUNTRIES.items()]
        for c_code in SMS_COUNTRIES.keys():
            for app_code, a_info in SMS_APPS.items():
                price_usd = await SMSManager.calculate_number_price(bot.id, c_code, app_code)
                products.append({
                    "id": f"{c_code}_{app_code}",
                    "category_id": c_code,
                    "name": f"{a_info['name_ar']} ({c_code.upper()})",
                    "description": f"رقم تفعيل فوري مع استرجاع تلقائي إن لم يصل الرمز",
                    "price_usd": price_usd,
                    "original_price_usd": price_usd,
                    "has_discount": False,
                    "input_label": "",
                    "is_instant": True,
                    "is_manual": False,
                    "icon": a_info["emoji"],
                })

    elif tpl_key == "smm":
        from ..modules.providers.smm import PLATFORMS
        raw_svcs = await SMMManager.get_services_catalog(bot.id)
        categories = [{"id": p_key, "name": f"{p['emoji']} {p['name_ar']}", "icon": p["emoji"]} for p_key, p in PLATFORMS.items()]
        for s in raw_svcs:
            p_price = s["price_per_1k_usd"]
            products.append({
                "id": s["id"],
                "category_id": s["platform"],
                "name": s["name_ar"],
                "description": f"الحد الأدنى: {s['min']} - الحد الأقصى: {s['max']:,}",
                "price_usd": p_price,
                "price_per_1k": p_price,
                "min_qty": s["min"],
                "max_qty": s["max"],
                "input_label": "رابط الحساب أو المنشور",
                "is_instant": True,
                "is_manual": False,
                "icon": "🚀",
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
                "category_id": s.get("category", "stars"),
                "name": s["name_ar"],
                "description": s.get("desc_ar", ""),
                "price_usd": s["price_usd"],
                "original_price_usd": s["price_usd"],
                "has_discount": False,
                "input_label": "اسم المستخدم @username",
                "is_instant": True,
                "is_manual": False,
                "icon": "⭐",
            })

    return web.json_response({
        "ok": True,
        "categories": categories,
        "products": products,
    })


# ─────────────────────────────────────────────────────────────
# 3. إرسال الطلبات الذري (Atomic Ordering & Idempotency)
# ─────────────────────────────────────────────────────────────

async def create_store_order(req: web.Request) -> web.Response:
    """ينشئ طلباً جديداً مع التحقق الصارم من الرصيد والأسعار ومنع التكرار."""
    bot_u = req.match_info["bot_username"]
    ctx = await authenticate_miniapp_request(req, bot_u)
    bot = ctx.bot

    try:
        data = await req.json()
    except Exception:
        return web.json_response({"ok": False, "error": "bad_json"}, status=400)

    # مفتاح منع التكرار (Idempotency Key)
    idempotency_key = req.headers.get("X-Idempotency-Key") or data.get("idempotency_key") or ""
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
                "order_id": existing.order_id,
                "status": existing.status,
                "is_duplicate": True,
            })

    product_id = data.get("product_id")
    target_data = str(data.get("target") or "").strip()
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
        if not svc:
            return web.json_response({"ok": False, "error": "invalid_product"}, status=404)
        base_price = svc["price_usd"]
        final_usd = await discounts.DiscountManager.apply_discount(bot.id, "digital", product_id, base_price)
        product_name = svc["name_ar"]

        # فحص المخزون الفوري إن وجد
        voucher_code = await DigitalManager.get_voucher_from_stock(bot.id, product_id)
        if voucher_code:
            order_status = "completed"

    elif bot.template == "sms":
        parts = product_id.split("_")
        if len(parts) >= 2:
            c_code, app_code = parts[0], parts[1]
            final_usd = await SMSManager.calculate_number_price(bot.id, c_code, app_code)
            product_name = f"رقم {app_code} ({c_code})"

    elif bot.template == "smm":
        raw_svcs = await SMMManager.get_services_catalog(bot.id)
        svc = next((s for s in raw_svcs if s["id"] == product_id), None)
        if not svc:
            return web.json_response({"ok": False, "error": "invalid_product"}, status=404)
        final_usd = (svc["price_per_1k_usd"] * quantity) / 1000.0
        product_name = svc["name_ar"]

    elif bot.template == "tgstars":
        raw_svcs = await TGStarsManager.get_services_catalog(bot.id)
        svc = next((s for s in raw_svcs if s["id"] == product_id), None)
        if not svc:
            return web.json_response({"ok": False, "error": "invalid_product"}, status=404)
        final_usd = svc["price_usd"]
        product_name = svc["name_ar"]

    # فحص الرصيد المتاح
    user_bal = await ledger.get_user_balance_usd(bot.id, ctx.uid)
    if user_bal < final_usd:
        return web.json_response({
            "ok": False,
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
        return web.json_response({"ok": False, "error": "debit_failed"}, status=500)

    # إنشاء سجل الطلب
    bot_cur = await currency.get_bot_currency(bot.id)
    async with db.Session() as s:
        order = db.ServiceOrder(
            order_id=idempotency_key,
            bot_id=bot.id,
            user_id=ctx.uid,
            tpl_key=bot.template,
            service_id=product_id,
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
            details={"voucher": voucher_code} if voucher_code else {},
            created=dt.datetime.utcnow(),
        )
        s.add(order)
        await s.commit()

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
        "order_id": idempotency_key,
        "status": order_status,
        "voucher": voucher_code,
        "new_balance_usd": new_bal,
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
    bot_u = req.match_info["bot_username"]
    ctx = await authenticate_miniapp_request(req, bot_u, require_role="seller")

    reader = await req.multipart()
    field = await reader.next()
    if not field:
        return web.json_response({"ok": False, "error": "no_file"}, status=400)

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
        return web.json_response({"ok": True, **res})
    except ValueError as e:
        return web.json_response({"ok": False, "error": str(e)}, status=400)


# ─────────────────────────────────────────────────────────────
# 6. لوحة البائع وإدارة التصميم (Seller Dashboard & Theme)
# ─────────────────────────────────────────────────────────────

async def get_seller_stats(req: web.Request) -> web.Response:
    """يعيد إحصائيات المبيعات والأرباح والطلبات لمالك البوت."""
    bot_u = req.match_info["bot_username"]
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

        total_sales_usd = (await s.execute(
            select(func.coalesce(func.sum(db.ServiceOrder.price_user_usd), 0.0))
            .where(db.ServiceOrder.bot_id == bot.id, db.ServiceOrder.status == "completed")
        )).scalar() or 0.0

    seller_bal = await ledger.get_seller_balance_display(bot.owner_id)

    return web.json_response({
        "ok": True,
        "total_orders": total_orders,
        "completed_orders": completed_orders,
        "pending_orders": pending_orders,
        "total_sales_usd": round(total_sales_usd, 2),
        "seller_balance": seller_bal,
    })


async def save_seller_theme(req: web.Request) -> web.Response:
    """يحفظ إعدادات تصميم المتجر بعد التحقق من الـ schema مع حفظ نسخة استعادة."""
    bot_u = req.match_info["bot_username"]
    ctx = await authenticate_miniapp_request(req, bot_u, require_role="seller")
    bot = ctx.bot

    try:
        raw_data = await req.json()
    except Exception:
        return web.json_response({"ok": False, "error": "bad_json"}, status=400)

    clean_theme = validate_theme_config(raw_data)
    old_theme = await db.kv_get(bot.id, "store:theme_config", {}) or {}

    # حفظ النسخة السابقة في جدول store_design_versions
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

    return web.json_response({"ok": True, "theme": clean_theme, "version": ver_cnt + 1})


async def get_theme_versions(req: web.Request) -> web.Response:
    """يعيد سجل النسخ المحفوظة لتصميم المتجر."""
    bot_u = req.match_info["bot_username"]
    ctx = await authenticate_miniapp_request(req, bot_u, require_role="seller")

    async with db.Session() as s:
        versions = (await s.execute(
            select(db.StoreDesignVersion)
            .where(db.StoreDesignVersion.bot_id == ctx.bot.id)
            .order_by(desc(db.StoreDesignVersion.version_num))
            .limit(10)
        )).scalars().all()

    return web.json_response({
        "ok": True,
        "versions": [
            {
                "id": v.id,
                "version_num": v.version_num,
                "name": v.name,
                "created": v.created.strftime("%Y-%m-%d %H:%M"),
                "config": v.theme_config,
            }
            for v in versions
        ],
    })


# ─────────────────────────────────────────────────────────────
# 7. المساعد الذكي لتخصيص المتجر (AI Store Customizer)
# ─────────────────────────────────────────────────────────────

async def ai_customizer_prompt(req: web.Request) -> web.Response:
    """يحلل طلب البائع النصي ويولد إعدادات ثيم منظمة تتبع الـ schema حصراً."""
    bot_u = req.match_info["bot_username"]
    ctx = await authenticate_miniapp_request(req, bot_u, require_role="seller")

    try:
        body = await req.json()
    except Exception:
        return web.json_response({"ok": False, "error": "bad_json"}, status=400)

    prompt = str(body.get("prompt") or "").strip().lower()
    if not prompt:
        return web.json_response({"ok": False, "error": "missing_prompt"}, status=400)

    # محرك التوليد المنظم للثيمات بناءً على كلمات البائع
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
    elif "بنفسج" in prompt or "purple" in prompt or "نيون" in prompt:
        generated.update({
            "primary_color": "#7c3aed",
            "secondary_color": "#6d28d9",
            "bg_color": "#2e1065",
            "card_bg": "#3b0764",
            "text_color": "#faf5ff",
            "font_family": "Readex Pro",
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
        "suggested_theme": generated,
        "message": "تم إنشاء نموذج التصميم بنجاح! يمكنك معاينته والموافقة عليه لتطبيقه.",
    })


# ─────────────────────────────────────────────────────────────
# 8. لوحة الأدمن المركزية (Admin Dashboard API)
# ─────────────────────────────────────────────────────────────

async def get_admin_overview(req: web.Request) -> web.Response:
    """يعيد الإحصائيات المركزية لمنصة البوتات والمتاجر."""
    ctx = await authenticate_admin_request(req)

    async with db.Session() as s:
        total_bots = (await s.execute(select(func.count(db.Bot.id)))).scalar() or 0
        total_users = (await s.execute(select(func.count(db.BUser.user_id)))).scalar() or 0
        total_orders = (await s.execute(select(func.count(db.ServiceOrder.id)))).scalar() or 0
        total_volume_usd = (await s.execute(select(func.coalesce(func.sum(db.ServiceOrder.price_user_usd), 0.0)))).scalar() or 0.0

    return web.json_response({
        "ok": True,
        "stats": {
            "total_bots": total_bots,
            "total_users": total_users,
            "total_orders": total_orders,
            "total_volume_usd": round(total_volume_usd, 2),
        },
    })


async def get_admin_orders(req: web.Request) -> web.Response:
    """يعيد قائمة الطلبات اليدوية والخدمات مع أزرار التحكم للأدمن."""
    ctx = await authenticate_admin_request(req)

    async with db.Session() as s:
        orders = (await s.execute(
            select(db.ServiceOrder)
            .order_by(desc(db.ServiceOrder.created))
            .limit(100)
        )).scalars().all()

    return web.json_response({
        "ok": True,
        "orders": [
            {
                "order_id": o.order_id,
                "bot_id": o.bot_id,
                "user_id": o.user_id,
                "service_name": o.service_name,
                "target": o.target,
                "price_usd": o.price_user_usd,
                "status": o.status,
                "created": o.created.strftime("%Y-%m-%d %H:%M"),
            }
            for o in orders
        ],
    })


async def admin_dual_refund_action(req: web.Request) -> web.Response:
    """ينفذ الاسترجاع المزدوج الذري لطلب معين."""
    ctx = await authenticate_admin_request(req)

    try:
        body = await req.json()
    except Exception:
        return web.json_response({"ok": False, "error": "bad_json"}, status=400)

    order_id = str(body.get("order_id") or "").strip()
    reason = str(body.get("reason") or "استرجاع يدوي من الأدمن").strip()

    ok, msg, res = await ledger.atomic_dual_refund(order_id, reason=reason)
    if not ok:
        return web.json_response({"ok": False, "error": msg}, status=400)

    await log_audit(
        bot_id=0,
        actor_id=ctx.uid,
        actor_role="admin",
        action="dual_refund",
        target_type="order",
        target_id=order_id,
        details=f"Dual refund performed: {reason}",
    )

    return web.json_response({"ok": True, "message": msg, "details": res})


def setup_routes(app: web.Application) -> None:
    """يسجل كافة مسارات الـ Mini Apps API."""
    u = r"{bot_username:[A-Za-z][A-Za-z0-9_]{3,39}}"

    # 1. المشتري والمتجر
    app.router.add_get(f"/api/miniapp/{u}/bootstrap", get_store_bootstrap)
    app.router.add_get(f"/api/miniapp/{u}/catalog", get_store_catalog)
    app.router.add_post(f"/api/miniapp/{u}/order", create_store_order)
    app.router.add_get(f"/api/miniapp/{u}/reviews/{{product_id}}", get_product_reviews)
    app.router.add_post(f"/api/miniapp/{u}/reviews", add_product_review)

    # 2. البائع والتصميم
    app.router.add_post(f"/api/miniapp/{u}/upload", upload_media_endpoint)
    app.router.add_get(f"/api/miniapp/{u}/seller/stats", get_seller_stats)
    app.router.add_post(f"/api/miniapp/{u}/seller/theme", save_seller_theme)
    app.router.add_get(f"/api/miniapp/{u}/seller/theme/versions", get_theme_versions)
    app.router.add_post(f"/api/miniapp/{u}/seller/ai_customizer", ai_customizer_prompt)

    # 3. الأدمن
    app.router.add_get("/api/admin_app/overview", get_admin_overview)
    app.router.add_get("/api/admin_app/orders", get_admin_orders)
    app.router.add_post("/api/admin_app/dual_refund", admin_dual_refund_action)
