"""واجهة برمجية نظيفة للتطبيق المصغّر الجديد (v2): متجر الزبون، لوحة البائع، لوحة المدير.

كل المسارات تحت /api/v2/{bot_username}/... وتتحقق من هوية تيليجرام (initData).
القواعد:
- كل الأسعار تُحسب في السيرفر (لا يُقبل أي سعر من المتصفح).
- المال كله عبر ledger (شراء ذري، استرجاع مزدوج، شحن بالنجوم بعد تأكيد الدفع فقط).
- إعدادات المتجر الظاهرة للزبون (الاسم، الشعار، الدعم، الأسئلة، الشروط، الباقات...) في kv: "v2:store".
"""
from __future__ import annotations

import asyncio

import datetime as dt
import json
import logging
import time
import uuid
from typing import Any

from aiohttp import web
from sqlalchemy import String, desc, func, select

from .. import config, db
from ..modules import catalog as pcat
from ..modules import currency, ledger, payments, promo
from ..modules.markup import MarkupManager
from ..modules.providers.digital import DIGITAL_CATALOG, DigitalManager
from ..modules.providers.smm import MOCK_CATALOG, PLATFORMS, SMMManager
from ..modules.providers.sms import SMS_APPS, SMS_COUNTRIES, SMSManager
from ..modules.providers.tgstars import TGSTARS_CATALOG, TGStarsManager
from . import miniapp_api as v1
from .miniapp_auth import AuthContext, authenticate_miniapp_request

log = logging.getLogger("forge.store_api")

SECTIONS = {
    "digital": {"ar": "الألعاب والاشتراكات", "en": "Games & Subscriptions", "icon": "🎮"},
    "smm": {"ar": "زيادة التفاعل", "en": "Social Boost", "icon": "🚀"},
    "sms": {"ar": "أرقام التفعيل", "en": "Activation Numbers", "icon": "📱"},
    "tgstars": {"ar": "نجوم وبريميوم تيليجرام", "en": "Telegram Stars & Premium", "icon": "⭐"},
    "master": {"ar": "منتجات المنصة", "en": "Platform products", "icon": "🛍"},
    "custom": {"ar": "منتجات المتجر", "en": "Store products", "icon": "✨"},
}
DIGITAL_CATS = {"games": ("ألعاب", "Games", "🎮"), "apps": ("اشتراكات وبث", "Subscriptions", "🎬"), "cards": ("بطاقات وقسائم", "Gift cards", "🎟")}
TG_CATS = {"stars": ("نجوم", "Stars", "⭐"), "premium": ("بريميوم", "Premium", "💎"), "gifts": ("هدايا", "Gifts", "🎁")}
STORE_DEFAULTS: dict[str, Any] = {
    "name": "", "desc": "", "logo": "", "banner": "", "accent": "#6d5dfc", "theme": "auto",
    "announcement": "",
    "ads": [],                                        # [{img, text, url}] شريط إعلانات بصور متعددة
    "ticker": {"text": "", "mode": "scroll"},        # نص إعلاني متحرك أو ثابت
    "bg": "",                                         # صورة خلفية المتجر (اختيارية)
    "support": {"username": "", "whatsapp": "", "email": "", "channel": "", "links": []},
    "faq_enabled": False, "faq": [],
    "terms": "", "help": "",
    "packages": [5, 10, 20, 50, 100], "custom_min": 1.0, "custom_max": 1000.0,
    "stars_enabled": True,
    "currencies": [],      # العملات المتاحة للزبون (فارغ = الكل)
}
SECTION_KEYS = {"digital": "digital", "smm": "smm", "sms": "sms", "tgstars": "tgstars"}


# ───────────────────────── أدوات مشتركة ─────────────────────────
def _ok(**kw) -> web.Response:
    return web.json_response({"ok": True, **kw})


def _err(code: str, msg: str = "", status: int = 400) -> web.Response:
    return web.json_response({"ok": False, "error": code, "message": msg or code}, status=status)


async def _body(req: web.Request) -> dict:
    try:
        b = await req.json()
        return b if isinstance(b, dict) else {}
    except Exception:
        return {}


async def _ctx(req: web.Request, role: str | None = None) -> AuthContext:
    return await authenticate_miniapp_request(req, req.match_info.get("bot_username") or "default", require_role=role)


def _parts(bot: db.Bot) -> tuple[str, ...]:
    p = v1.TEMPLATE_PARTS.get(bot.template, (bot.template,))
    out = tuple(x for x in p if x in SECTION_KEYS)
    if bot.template in ("digital", "megastore", "store"):
        out = out + ("master",)
    return out + ("custom",)


async def store_cfg(bot_id: int) -> dict[str, Any]:
    cfg = dict(STORE_DEFAULTS)
    saved = await db.kv_get(bot_id, "v2:store", {}) or {}
    if isinstance(saved, dict):
        cfg.update(saved)
    sup = dict(STORE_DEFAULTS["support"])
    sup.update(cfg.get("support") or {})
    cfg["support"] = sup
    return cfg


def _clean_str(v: Any, n: int) -> str:
    return str(v or "").strip()[:n]


def _clean_url(v: Any) -> str:
    u = _clean_str(v, 500)
    return u if u.startswith(("https://", "http://", "/media/", "tg://")) else ""


async def _currencies(bot_id: int, allowed: list[str] | None = None) -> list[dict]:
    rates = await currency.fetch_live_rates()
    out = []
    for code, info in currency.CURRENCIES.items():
        if code == "POINTS" or (allowed and code not in allowed and code != "USD"):
            continue
        rate = await currency.get_effective_rate(bot_id, code) if bot_id else float(rates.get(code, info["default_rate"]))
        out.append({"code": code, "ar": info["name_ar"], "en": info["name_en"], "symbol": info["symbol"],
                    "decimals": info.get("decimals", 2), "rate": rate})
    return out


async def _user_prefs(bot_id: int, uid: int) -> tuple[str, str]:
    lang, cur = "", ""
    async with db.Session() as s:
        row = await s.get(db.BUser, (bot_id, uid))
        if row is not None:
            lang = (row.lang or "")[:2]
    cur = await db.kv_get(bot_id, f"v2:ucur:{uid}", "") or ""
    return lang, cur


# ───────────────────────── الكتالوج الموحّد ─────────────────────────
_CAT_CACHE: dict[tuple[int, str], tuple[float, dict]] = {}


def invalidate(bot_id: int) -> None:
    for k in [k for k in _CAT_CACHE if k[0] == bot_id]:
        _CAT_CACHE.pop(k, None)
    db.kv_invalidate(bot_id)
    try:
        from . import miniapp_auth
        miniapp_auth.invalidate_resolve_cache(bot_id)
    except Exception:
        pass


def _kind_name(metric: str, plat: str, ar: bool) -> str:
    from ..modules.smm_agg import FOLLOW_WORD, METRIC_NAMES, VIEW_WORD
    a, e = (FOLLOW_WORD.get(plat) if metric == "followers" else VIEW_WORD.get(plat) if metric == "views" else None) or METRIC_NAMES.get(metric, (metric, metric))
    return a if ar else e


async def build_catalog(bot: db.Bot, lang: str = "ar") -> dict[str, Any]:
    """الكتالوج مع كاش 60 ثانية لكل متجر (يُمسح عند أي تعديل من البائع أو المدير)."""
    key = (bot.id, lang)
    hit = _CAT_CACHE.get(key)
    if hit and time.time() - hit[0] < 60:
        return hit[1]
    data = await _build_catalog(bot, lang)
    hidden = set(await db.kv_get(bot.id, "v2:hidden", []) or [])      # منتجات أخفاها البائع
    data = dict(data, products=[p for p in data["products"] if p["id"] not in hidden])
    _CAT_CACHE[key] = (time.time(), data)
    return data


async def _build_catalog(bot: db.Bot, lang: str = "ar") -> dict[str, Any]:
    """أقسام وفئات ومنتجات المتجر بصيغة موحّدة مع الأسعار النهائية بالدولار."""
    ar = lang == "ar"
    parts = _parts(bot)
    secs, cats, prods = [], [], []

    def sec(k):
        secs.append({"id": k, "name": SECTIONS[k]["ar" if ar else "en"], "icon": SECTIONS[k]["icon"]})

    if "digital" in parts:
        sec("digital")
        for ck, (a, e, ic) in DIGITAL_CATS.items():
            cats.append({"id": f"digital:{ck}", "sec": "digital", "name": a if ar else e, "icon": ic})
        for s in await DigitalManager.get_services_catalog(bot.id):
            stock = await DigitalManager.get_stock_count(bot.id, s["id"])
            prods.append({"id": s["id"], "sec": "digital", "cat": f"digital:{s.get('category', 'games')}",
                          "name": s["name_ar"] if ar else s.get("name_en", s["name_ar"]), "desc": s.get("desc_ar", ""),
                          "icon": s.get("icon", "🎮"), "img": s.get("image_url", ""), "price_usd": float(s["price_usd"]), "_base": float(s.get("base_cost_usd", 0)),
                          "unit": "item", "min": 1, "max": 10,
                          "target": {"label": s.get("field_ar", "") if ar else s.get("field_en", s.get("field_ar", "")), "kind": "text"} if s.get("field_ar") else None,
                          "instant": stock > 0, "stock": stock})
    if "smm" in parts:
        sec("smm")
        from ..modules.providers.smm import platforms_with_services
        for pk in platforms_with_services():
            p = PLATFORMS[pk]
            cats.append({"id": f"smm:{pk}", "sec": "smm", "name": p["name_ar"] if ar else p["name_en"], "icon": p["emoji"]})
        for s in await SMMManager.get_services_catalog(bot.id):
            prods.append({"id": s["id"], "sec": "smm", "cat": f"smm:{s['platform']}",
                          "name": s["name_ar"] if ar else s.get("name_en", s["name_ar"]), "desc": s.get("desc_ar", ""),
                          "icon": PLATFORMS.get(s["platform"], {}).get("emoji", "🚀"), "img": "",
                          "price_usd": float(s["price_per_1k_usd"]), "_base": float(s.get("base_cost_per_1k", 0)), "unit": "1k", "min": int(s["min"]), "max": int(s["max"]),
                          "target": {"label": "رابط الحساب أو المنشور" if ar else "Account or post link", "kind": "url"},
                          "instant": True, "eta": s.get("avg_time", ""), "refill": bool(s.get("refill")),
                          "kind": s.get("category", ""), "kind_name": _kind_name(s.get("category", ""), s["platform"], ar)})
    if "sms" in parts:
        sec("sms")
        from ..modules.markup import floor_pricer
        smap = await pcat.get_map("sms")
        sfloor = await floor_pricer(bot.id, "sms")
        mconf = await db.kv_get(bot.id, "sms:margin", {"type": "percent", "val": 35.0}) or {}
        sover = await db.kv_get(bot.id, "sms:overrides", {}) or {}
        for ck, ci in SMS_COUNTRIES.items():
            cats.append({"id": f"sms:{ck}", "sec": "sms", "name": ci["name_ar"] if ar else ci["name_en"], "icon": ci.get("flag", "🌐")})
            for ak, ai in SMS_APPS.items():
                pid = f"{ck}_{ak}"
                if pcat.is_off(smap, pid):
                    continue
                base = SMSManager.base_cost(ck, ak, smap)
                fl = round(sfloor(base, pid) + 0.0049, 2)
                if (sover.get(pid) or {}).get("price_usd"):
                    price = float(sover[pid]["price_usd"])
                elif mconf.get("type") == "fixed":
                    price = round(base + float(mconf.get("val", 0)), 2)
                else:
                    price = round(base * (1 + float(mconf.get("val", 35.0)) / 100.0), 2)
                prods.append({"id": pid, "sec": "sms", "cat": f"sms:{ck}",
                              "name": f"{ai['name_ar'] if ar else ai['name_en']} — {ci['name_ar'] if ar else ci['name_en']}",
                              "desc": "رقم فوري، ويُسترجع المبلغ إن لم يصل الكود" if ar else "Instant number, refunded if no code arrives",
                              "icon": ai.get("emoji", "📱"), "img": "", "price_usd": max(price, fl), "_base": base,
                              "unit": "item", "min": 1, "max": 1, "target": None, "instant": True})
    if "tgstars" in parts:
        sec("tgstars")
        for ck, (a, e, ic) in TG_CATS.items():
            cats.append({"id": f"tgstars:{ck}", "sec": "tgstars", "name": a if ar else e, "icon": ic})
        for s in await TGStarsManager.get_services_catalog(bot.id):
            prods.append({"id": s["id"], "sec": "tgstars", "cat": f"tgstars:{s.get('category', 'stars')}",
                          "name": s["name_ar"] if ar else s.get("name_en", s["name_ar"]), "desc": s.get("desc_ar", ""),
                          "icon": TG_CATS.get(s.get("category", "stars"), ("", "", "⭐"))[2], "img": "",
                          "price_usd": float(s["price_usd"]), "_base": float(s.get("base_cost_usd", 0)), "unit": "item", "min": 1, "max": 1,
                          "target": {"label": "يوزر الحساب @username" if ar else "Account @username", "kind": "username"}, "instant": True})
    if "master" in parts:
        overrides = await db.kv_get(bot.id, "store:product_overrides", {}) or {}
        added = False
        for m in await v1.get_master_catalog_items():
            mid = str(m.get("id"))
            ov = overrides.get(mid) or {}
            if m.get("active", True) is False or ov.get("deleted") or ov.get("active") is False or ov.get("hidden"):
                continue
            q = await v1._quote_item(bot, mid, 1)
            if not q.ok or q.tpl != "master":
                continue
            if not added:
                sec("master")
                cats.append({"id": "master:all", "sec": "master", "name": SECTIONS["master"]["ar" if ar else "en"], "icon": "🛍"})
                added = True
            reqs = m.get("requirements") or []
            prods.append({"id": mid, "sec": "master", "cat": "master:all", "name": m.get("name_ar") or m.get("name", ""),
                          "desc": ov.get("description") or m.get("description", ""), "icon": "🛍",
                          "img": (ov.get("mediaUrls") or m.get("media_urls") or [""])[0], "price_usd": q.price_usd,
                          "unit": "item", "min": 1, "max": 10,
                          "target": {"label": reqs[0].get("label", ""), "kind": "text"} if reqs else None, "instant": False})
    custom = await db.kv_get(bot.id, "store:custom_products", []) or []
    shown = [c for c in custom if c.get("active", True) is not False]
    if shown:
        sec("custom")
        cat_ids = set()
        for cp in shown:
            cid = f"custom:{cp.get('category_id') or 'all'}"
            if cid not in cat_ids:
                cat_ids.add(cid)
                cats.append({"id": cid, "sec": "custom", "name": cp.get("category_name") or SECTIONS["custom"]["ar" if ar else "en"], "icon": cp.get("icon") or "✨"})
            opts = cp.get("priceOptions") or []
            price = float((opts[0] if opts else {}).get("userPrice") or cp.get("price_usd", 0) or 0)
            prods.append({"id": str(cp.get("id")), "sec": "custom", "cat": cid, "name": cp.get("name", ""), "desc": cp.get("description", ""),
                          "icon": cp.get("icon") or "✨", "img": (cp.get("mediaUrls") or [""])[0] if cp.get("mediaUrls") else cp.get("image", ""),
                          "price_usd": price, "unit": "item", "min": 1, "max": 10,
                          "target": {"label": cp.get("input_label") or ("بيانات الطلب" if ar else "Order details"), "kind": "text"} if cp.get("needs_input", True) else None,
                          "instant": bool(cp.get("is_instant") and cp.get("stock_codes"))})
    return {"sections": secs, "categories": cats, "products": prods}


# ───────────────────────── الزبون ─────────────────────────
async def boot(req: web.Request) -> web.Response:
    ctx = await _ctx(req)
    bot = ctx.bot
    cfg = await store_cfg(bot.id)
    lang, cur = (await _user_prefs(bot.id, ctx.uid)) if not ctx.is_guest else ("", "")
    if not lang:
        lang = (ctx.user.get("language_code") or "ar")[:2]
    lang = "ar" if lang not in ("ar", "en") else lang
    store_cur = await currency.get_bot_currency(bot.id)
    bal = 0.0 if ctx.is_guest else await ledger.get_user_balance_usd(bot.id, ctx.uid)
    maint = await v1._store_in_maintenance(ctx)
    faq = cfg["faq"] if cfg.get("faq_enabled") and cfg.get("faq") else []
    return _ok(
        store={"id": bot.id, "username": bot.username, "name": cfg["name"] or bot.name or bot.username, "desc": cfg["desc"],
               "logo": cfg["logo"], "banner": cfg["banner"], "accent": cfg["accent"], "theme": cfg["theme"],
               "announcement": cfg["announcement"], "tpl": bot.template, "currency": store_cur,
               "support": cfg["support"], "faq": faq, "terms": cfg["terms"], "help": cfg["help"],
               "packages": cfg["packages"], "custom_min": cfg["custom_min"], "custom_max": cfg["custom_max"],
               "stars_enabled": bool(cfg["stars_enabled"]), "star_rate_usd": payments.STAR_RATE_USD,
               "maintenance": maint, "bot_link": f"https://t.me/{bot.username}",
               "ads": cfg["ads"], "ticker": cfg["ticker"], "bg": cfg["bg"], "platform": await _platform_info(bot)},
        user={"uid": ctx.uid, "name": ctx.uname, "username": ctx.user.get("username", ""), "role": ctx.role, "is_owner": ctx.is_owner, "is_admin": ctx.is_admin,
              "is_guest": ctx.is_guest, "lang": lang, "currency": cur or store_cur, "balance_usd": bal},
        currencies=await _currencies(bot.id, cfg.get("currencies") or None),
    )


async def _platform_info(bot: db.Bot) -> dict:
    """دعم المنصة (صانع البوتات) لشكاوى الزبائن ضد صاحب المتجر."""
    try:
        from ..runtime import manager
        mk = manager.maker.bot.username if manager.maker is not None else ""
    except Exception:
        mk = ""
    return {"name": config.BRAND, "report_url": f"https://t.me/{mk}?start=report_{bot.id}" if mk else ""}


async def prefs(req: web.Request) -> web.Response:
    """حفظ لغة وعملة الزبون — اللغة نفسها تُستخدم في أزرار البوت."""
    ctx = await _ctx(req)
    b = await _body(req)
    lang = _clean_str(b.get("lang"), 2)
    cur = _clean_str(b.get("currency"), 8).upper()
    if lang in ("ar", "en"):
        async with db.Session() as s:
            row = await s.get(db.BUser, (ctx.bot.id, ctx.uid))
            if row is None:
                row = db.BUser(bot_id=ctx.bot.id, user_id=ctx.uid, name=ctx.uname[:128], source="miniapp")
                s.add(row)
            row.lang = lang
            await s.commit()
        from ..child import touch_forget
        touch_forget(ctx.bot.id, ctx.uid)
        try:
            from ..runtime import manager
            app = manager.apps.get(ctx.bot.id)
            if app is not None:
                app.user_data[ctx.uid]["lang"] = lang      # يتغيّر في البوت فوراً
        except Exception:
            pass
    if cur and cur in currency.CURRENCIES:
        await db.kv_set(ctx.bot.id, f"v2:ucur:{ctx.uid}", cur)
    return _ok()


async def catalog_ep(req: web.Request) -> web.Response:
    ctx = await _ctx(req)
    lang = (req.query.get("lang") or "ar")[:2]
    c = await build_catalog(ctx.bot, lang)
    return _ok(sections=c["sections"], categories=c["categories"],
               products=[{k: v for k, v in p.items() if not k.startswith("_")} for p in c["products"]])


async def quote_ep(req: web.Request) -> web.Response:
    ctx = await _ctx(req)
    b = await _body(req)
    try:
        qty = int(b.get("quantity") or 1)
    except (TypeError, ValueError):
        qty = 0
    q = await v1._quote_item(ctx.bot, str(b.get("product_id") or ""), qty)
    if not q.ok:
        return _err(q.error, "الكمية أو المنتج غير صالح")
    price = q.price_usd
    disc, msg = 0.0, ""
    code = _clean_str(b.get("coupon"), 32).upper()
    if code:
        ok, d, msg = await promo.validate_promo(ctx.bot.id, ctx.uid, code, price, str(b.get("product_id")))
        disc = min(float(d), price) if ok else 0.0
    return _ok(price_usd=round(price, 4), discount_usd=round(disc, 4), total_usd=round(price - disc, 4), coupon_msg=msg)


async def wallet_ep(req: web.Request) -> web.Response:
    ctx = await _ctx(req)
    cfg = await store_cfg(ctx.bot.id)
    methods = [{"id": m.get("id"), "name": m.get("name"), "account": m.get("account", ""), "instructions": m.get("instructions", ""),
                "currency": m.get("currency", "USD"), "min": m.get("min", 1), "max": m.get("max", 10000)}
               for m in await payments.get_active_payment_methods(ctx.bot.id) if m.get("id") != "telegram_stars"]
    txs = await ledger.get_user_transactions(ctx.bot.id, ctx.uid, limit=30)
    async with db.Session() as s:
        pend = (await s.execute(select(db.PaymentReceipt).where(db.PaymentReceipt.bot_id == ctx.bot.id, db.PaymentReceipt.user_id == ctx.uid)
                                .order_by(db.PaymentReceipt.id.desc()).limit(10))).scalars().all()
    return _ok(balance_usd=await ledger.get_user_balance_usd(ctx.bot.id, ctx.uid),
               packages=cfg["packages"], custom_min=cfg["custom_min"], custom_max=cfg["custom_max"],
               stars_enabled=bool(cfg["stars_enabled"]), star_rate_usd=payments.STAR_RATE_USD, methods=methods,
               transactions=[{"dir": t.direction, "amount_usd": float(t.amount_usd), "after_usd": float(t.balance_after_usd), "kind": t.kind,
                              "desc": t.description, "at": t.created.strftime("%Y-%m-%d %H:%M") if t.created else ""} for t in txs],
               receipts=[{"id": r.receipt_id, "method": r.method, "amount_usd": float(r.amount_usd), "status": r.status,
                          "at": r.created.strftime("%Y-%m-%d %H:%M") if getattr(r, "created", None) else ""} for r in pend])


async def deposit_stars(req: web.Request) -> web.Response:
    """فاتورة نجوم بباقة أو بمبلغ مخصص بالدولار. الشحن يتم فقط بعد تأكيد تيليجرام."""
    ctx = await _ctx(req)
    cfg = await store_cfg(ctx.bot.id)
    if not cfg["stars_enabled"]:
        return _err("disabled", "الشحن بالنجوم غير مفعّل في هذا المتجر")
    b = await _body(req)
    try:
        usd = float(b.get("usd") or 0)
    except (TypeError, ValueError):
        usd = 0
    if not (float(cfg["custom_min"]) <= usd <= float(cfg["custom_max"])):
        return _err("invalid_amount", f"المبلغ بين {cfg['custom_min']}$ و {cfg['custom_max']}$")
    stars = max(1, int(round(usd / payments.STAR_RATE_USD)))
    if stars > payments.STARS_MAX:
        return _err("invalid_amount", "المبلغ أكبر من حد فاتورة النجوم")
    try:
        from ..runtime import manager
        app = manager.apps.get(ctx.bot.id)
        link = await payments.create_stars_invoice_link(app.bot, ctx.bot.id, ctx.uid, stars) if app else None
    except Exception as e:
        log.warning("stars invoice failed: %s", e)
        link = None
    if not link:
        return _err("invoice_failed", "تعذّر إنشاء الفاتورة حالياً", 503)
    return _ok(invoice_link=link, stars=stars, usd=round(stars * payments.STAR_RATE_USD, 2))


async def deposit_receipt(req: web.Request) -> web.Response:
    """إيصال تحويل يدوي: المبلغ بعملة الطريقة + رقم العملية + صورة اختيارية (multipart)."""
    ctx = await _ctx(req)
    proof_url, fields = "", {}
    if req.content_type.startswith("multipart/"):
        reader = await req.multipart()
        async for part in reader:
            if part.name == "image" and part.filename:
                raw = await part.read(decode=False)
                if len(raw) > 8 * 1024 * 1024:
                    return _err("too_large", "الصورة أكبر من 8MB")
                try:
                    from . import media_pipe
                    proof_url = media_pipe.handle_uploaded_file(bytes(raw), part.filename or "proof.jpg").get("url", "")
                except Exception as e:
                    return _err("bad_image", str(e))
            elif part.name:
                fields[part.name] = (await part.text())[:2000]
    else:
        fields = await _body(req)
    methods = {m.get("id"): m for m in await payments.get_active_payment_methods(ctx.bot.id)}
    m = methods.get(fields.get("method_id"))
    if m is None:
        return _err("bad_method", "طريقة الدفع غير متاحة")
    try:
        amount = float(str(fields.get("amount") or "0").replace(",", "."))
    except ValueError:
        amount = 0
    cur = (m.get("currency") or "USD").upper()
    usd = await currency.currency_to_usd(amount, cur, ctx.bot.id) if cur != "USD" else amount
    if usd <= 0 or usd < float(m.get("min") or 0) or usd > float(m.get("max") or 100000):
        return _err("invalid_amount", "المبلغ خارج حدود هذه الطريقة")
    ref = _clean_str(fields.get("ref"), 500)
    if not ref and not proof_url:
        return _err("missing_proof", "أرسل رقم العملية أو صورة الإيصال")
    rc = await payments.create_receipt(ctx.bot.id, ctx.uid, ctx.uname, ctx.user.get("username", ""), m.get("name", ""),
                                       amount, cur, round(usd, 4), proof_file_id="", proof_text=(ref + ("\n" + proof_url if proof_url else "")).strip())
    try:
        from ..runtime import manager
        from ..ui import B, kb
        app = manager.apps.get(ctx.bot.id)
        if app:
            txt = (f"🧾 <b>إيصال شحن جديد</b>\n👤 {ctx.uname} (<code>{ctx.uid}</code>)\n💳 {m.get('name')} · {amount:g} {cur} (≈ ${usd:.2f})"
                   + (f"\n📝 {ref[:200]}" if ref else ""))
            mk = kb([[B("✅ قبول", f"t:rcpt_ok:{rc.receipt_id}", style="success"), B("❌ رفض", f"t:rcpt_no:{rc.receipt_id}", style="danger")]])
            if proof_url and config.PUBLIC_URL:
                await app.bot.send_photo(ctx.bot.owner_id, f"{config.PUBLIC_URL}{proof_url}", caption=txt, parse_mode="HTML", reply_markup=mk)
            else:
                await app.bot.send_message(ctx.bot.owner_id, txt, parse_mode="HTML", reply_markup=mk)
    except Exception:
        log.debug("receipt notify failed", exc_info=True)
    return _ok(receipt_id=rc.receipt_id, message="استلمنا الإيصال وهو قيد المراجعة")


async def account_ep(req: web.Request) -> web.Response:
    ctx = await _ctx(req)
    stats = await promo.get_user_referral_stats(ctx.bot.id, ctx.uid)
    conf = await promo.get_referral_config(ctx.bot.id)
    async with db.Session() as s:
        n_orders = (await s.execute(select(func.count(db.ServiceOrder.id)).where(db.ServiceOrder.bot_id == ctx.bot.id, db.ServiceOrder.user_id == ctx.uid))).scalar() or 0
        spent = float((await s.execute(select(func.coalesce(func.sum(db.ServiceOrder.price_user_usd), 0)).where(
            db.ServiceOrder.bot_id == ctx.bot.id, db.ServiceOrder.user_id == ctx.uid, db.ServiceOrder.status.notin_(("refunded", "canceled"))))).scalar() or 0)
    return _ok(referral={"on": bool(conf.get("on")), "link": f"https://t.me/{ctx.bot.username}?start=ref_{ctx.uid}",
                         "percent": conf.get("percent", 0), "count": stats["count"], "earned_usd": stats["earned_usd"]},
               orders=n_orders, spent_usd=round(spent, 2))


# ───────────────────────── لوحة البائع ─────────────────────────
async def _sales(bot_id: int | None, days: int) -> dict:
    since = db.now() - dt.timedelta(days=days)
    cond = [db.ServiceOrder.created >= since, db.ServiceOrder.status.notin_(("refunded", "canceled", "failed"))]
    if bot_id is not None:
        cond.append(db.ServiceOrder.bot_id == bot_id)
    async with db.Session() as s:
        n, sales, cost = (await s.execute(select(func.count(db.ServiceOrder.id), func.coalesce(func.sum(db.ServiceOrder.price_user_usd), 0),
                                                 func.coalesce(func.sum(db.ServiceOrder.cost_platform_usd), 0)).where(*cond))).one()
    return {"orders": int(n), "sales_usd": round(float(sales), 2), "cost_usd": round(float(cost), 2), "profit_usd": round(float(sales) - float(cost), 2)}


async def _series(bot_id: int | None, days: int = 14) -> list[dict]:
    since = (db.now() - dt.timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    cond = [db.ServiceOrder.created >= since, db.ServiceOrder.status.notin_(("refunded", "canceled", "failed"))]
    if bot_id is not None:
        cond.append(db.ServiceOrder.bot_id == bot_id)
    async with db.Session() as s:
        rows = (await s.execute(select(db.ServiceOrder.created, db.ServiceOrder.price_user_usd).where(*cond))).all()
    by = {}
    for c, p in rows:
        k = c.strftime("%m-%d")
        by[k] = by.get(k, 0.0) + float(p or 0)
    out = []
    for i in range(days):
        d = (since + dt.timedelta(days=i)).strftime("%m-%d")
        out.append({"d": d, "v": round(by.get(d, 0.0), 2)})
    return out


async def s_overview(req: web.Request) -> web.Response:
    ctx = await _ctx(req, "seller")
    bid = ctx.bot.id
    async with db.Session() as s:
        customers = (await s.execute(select(func.count()).select_from(db.BUser).where(db.BUser.bot_id == bid, db.BUser.kind == "private"))).scalar() or 0
        pend_rc = (await s.execute(select(func.count(db.PaymentReceipt.id)).where(db.PaymentReceipt.bot_id == bid, db.PaymentReceipt.status == "pending"))).scalar() or 0
        pend_ord = (await s.execute(select(func.count(db.ServiceOrder.id)).where(db.ServiceOrder.bot_id == bid, db.ServiceOrder.status.in_(("queued", "pending"))))).scalar() or 0
        cust_bal = float((await s.execute(select(func.coalesce(func.sum(db.UserBalance.balance_usd), 0)).where(db.UserBalance.bot_id == bid))).scalar() or 0)
    return _ok(today=await _sales(bid, 1), week=await _sales(bid, 7), month=await _sales(bid, 30), series=await _series(bid),
               customers=customers, pending_receipts=pend_rc, pending_orders=pend_ord, customers_balance_usd=round(cust_bal, 2),
               maker_balance_usd=await ledger.get_seller_balance_usd(ctx.bot.owner_id))


def _order_dict(o: db.ServiceOrder, with_cost: bool = True) -> dict:
    d = o.details or {}
    out = {"order_id": o.order_id, "bot_id": o.bot_id, "user_id": o.user_id, "sec": o.tpl_key, "service": o.service_name, "target": o.target,
           "qty": o.quantity, "price_usd": float(o.price_user_usd), "status": o.status, "provider": "" if o.provider_name in ("__hold__", "__approving__") else o.provider_name,
           "delivery": o.delivery_text or d.get("voucher", "") or d.get("sms_code", ""), "reason": o.refund_reason or "",
           "at": o.created.strftime("%Y-%m-%d %H:%M") if o.created else ""}
    if with_cost:
        out["cost_usd"] = float(o.cost_platform_usd or 0)
    return out


async def s_orders(req: web.Request) -> web.Response:
    ctx = await _ctx(req, "seller")
    st = req.query.get("status", "")
    q = select(db.ServiceOrder).where(db.ServiceOrder.bot_id == ctx.bot.id)
    if st:
        q = q.where(db.ServiceOrder.status.in_(st.split(",")))
    term = _clean_str(req.query.get("q"), 64)
    if term:
        q = q.where((db.ServiceOrder.order_id.contains(term)) | (db.ServiceOrder.target.contains(term)) | (db.ServiceOrder.service_name.contains(term)))
    async with db.Session() as s:
        rows = (await s.execute(q.order_by(desc(db.ServiceOrder.created)).limit(100))).scalars().all()
    return _ok(orders=[_order_dict(o) for o in rows])


async def s_order_action(req: web.Request) -> web.Response:
    """البائع يسترجع طلباً لم يُنفّذ بعد (قيد الانتظار) للطرفين."""
    ctx = await _ctx(req, "seller")
    b = await _body(req)
    oid = _clean_str(b.get("order_id"), 64)
    async with db.Session() as s:
        o = (await s.execute(select(db.ServiceOrder).where(db.ServiceOrder.order_id == oid))).scalars().first()
    if o is None or o.bot_id != ctx.bot.id:
        return _err("not_found", "الطلب غير موجود", 404)
    if b.get("action") == "refund":
        if o.status not in ("queued", "pending") and not ctx.is_admin:
            return _err("not_allowed", "يمكن استرجاع الطلبات التي لم تُنفّذ بعد فقط")
        ok, msg, _ = await ledger.atomic_dual_refund(oid, reason=_clean_str(b.get("reason"), 200) or "إلغاء من المتجر")
        if ok:
            await _notify_user(ctx.bot.id, o.user_id, f"↩️ أُلغي طلبك #{oid[-8:]} وأُعيد المبلغ لرصيدك.")
        return _ok(message=msg) if ok else _err("failed", msg)
    return _err("bad_action")


async def _notify_user(bot_id: int, uid: int, text: str) -> None:
    try:
        from ..runtime import manager
        app = manager.apps.get(bot_id)
        if app:
            await app.bot.send_message(uid, text)
    except Exception:
        pass


async def s_pricing(req: web.Request) -> web.Response:
    """هوامش البائع لكل قسم + قائمة المنتجات بسعر المنصة وسعر البيع، مع الإخفاء والسعر المخصص."""
    ctx = await _ctx(req, "seller")
    bot = ctx.bot
    if req.method == "POST":
        b = await _body(req)
        secname = b.get("sec")
        if secname in SECTION_KEYS and "margin" in b:
            mg = b["margin"] or {}
            t = "fixed" if mg.get("type") == "fixed" else "percent"
            try:
                v = max(0.0, min(float(mg.get("val", 0)), 1000.0))
            except (TypeError, ValueError):
                return _err("bad_margin")
            await db.kv_set(bot.id, f"{secname}:margin", {"type": t, "val": v})
        pid = _clean_str(b.get("product_id"), 64)
        if pid and "hidden" in b:
            hidden = set(await db.kv_get(bot.id, "v2:hidden", []) or [])
            (hidden.add if b["hidden"] else hidden.discard)(pid)
            await db.kv_set(bot.id, "v2:hidden", sorted(hidden))
        if pid and "price_usd" in b and secname in ("digital", "smm", "tgstars"):
            ov_key = f"{secname}:services_override"
            ov = await db.kv_get(bot.id, ov_key, {}) or {}
            e = dict(ov.get(pid) or {})
            if b["price_usd"] in (None, ""):
                e.pop("custom_price_usd", None)
            else:
                try:
                    e["custom_price_usd"] = max(0.0, float(b["price_usd"]))
                except (TypeError, ValueError):
                    return _err("bad_price")
            ov[pid] = e
            await db.kv_set(bot.id, ov_key, ov)
        if pid and "price_usd" in b and secname == "sms":
            ov = await db.kv_get(bot.id, "sms:overrides", {}) or {}
            if b["price_usd"] in (None, ""):
                ov.pop(pid, None)
            else:
                ov[pid] = {"price_usd": max(0.0, float(b["price_usd"]))}
            await db.kv_set(bot.id, "sms:overrides", ov)
    if req.method == "POST":
        invalidate(bot.id)
    cat = await _build_catalog(bot, "ar")
    hidden = set(await db.kv_get(bot.id, "v2:hidden", []) or [])
    from ..modules.markup import floor_pricer
    margins = {k: await db.kv_get(bot.id, f"{k}:margin", {"type": "percent", "val": {"smm": 30, "sms": 35, "digital": 20, "tgstars": 25}[k]})
               for k in SECTION_KEYS if k in _parts(bot)}
    floors = {k: await floor_pricer(bot.id, k) for k in margins}
    floor = {k: await MarkupManager.get_effective_margin(owner_id=bot.owner_id, tpl_key=k) for k in margins}
    items = []
    for p in cat["products"]:
        if p["sec"] not in margins:
            continue
        cost = floors[p["sec"]](float(p.get("_base", 0)), p["id"])
        items.append({"id": p["id"], "sec": p["sec"], "name": p["name"], "unit": p["unit"], "price_usd": p["price_usd"],
                      "cost_usd": round(cost, 4), "profit_usd": round(p["price_usd"] - cost, 4), "hidden": p["id"] in hidden})
    return _ok(margins=margins, items=items, platform_margins={k: {"type": v[0], "val": v[1]} for k, v in floor.items()})


async def s_customers(req: web.Request) -> web.Response:
    ctx = await _ctx(req, "seller")
    bid = ctx.bot.id
    term = _clean_str(req.query.get("q"), 64).lstrip("@")
    q = select(db.BUser).where(db.BUser.bot_id == bid, db.BUser.kind == "private")
    if term:
        q = q.where((db.BUser.username.contains(term)) | (db.BUser.name.contains(term)) | (func.cast(db.BUser.user_id, String).contains(term)))
    async with db.Session() as s:
        users = (await s.execute(q.order_by(desc(db.BUser.last_seen)).limit(60))).scalars().all()
        bals = {r.user_id: float(r.balance_usd) for r in (await s.execute(select(db.UserBalance).where(
            db.UserBalance.bot_id == bid, db.UserBalance.user_id.in_([u.user_id for u in users] or [0])))).scalars().all()}
    return _ok(customers=[{"uid": u.user_id, "name": u.name, "username": u.username, "lang": u.lang, "banned": u.banned,
                           "balance_usd": bals.get(u.user_id, 0.0), "last_seen": u.last_seen.strftime("%Y-%m-%d") if u.last_seen else ""} for u in users])


async def s_customer_action(req: web.Request) -> web.Response:
    ctx = await _ctx(req, "seller")
    b = await _body(req)
    try:
        uid = int(b.get("uid"))
    except (TypeError, ValueError):
        return _err("bad_user")
    act = b.get("action")
    if act in ("credit", "debit"):
        try:
            amt = round(float(b.get("amount_usd")), 4)
            assert 0 < amt <= 10000
        except (TypeError, ValueError, AssertionError):
            return _err("bad_amount", "مبلغ غير صالح")
        note = _clean_str(b.get("note"), 200) or ("إضافة رصيد من المتجر" if act == "credit" else "خصم رصيد من المتجر")
        fn = ledger.credit_user if act == "credit" else ledger.debit_user
        ok, tx, bal = await fn(ctx.bot.id, uid, amt, "seller_adjust", description=note)
        if not ok:
            return _err("failed", "الرصيد غير كافٍ للخصم" if act == "debit" else "تعذّر التنفيذ")
        if act == "credit":
            await _notify_user(ctx.bot.id, uid, f"🎁 أُضيف لرصيدك ${amt:.2f}\n{note}")
        return _ok(balance_usd=bal)
    if act in ("ban", "unban"):
        async with db.Session() as s:
            row = await s.get(db.BUser, (ctx.bot.id, uid))
            if row is None:
                return _err("not_found", status=404)
            row.banned = act == "ban"
            await s.commit()
        from ..child import touch_forget
        touch_forget(ctx.bot.id, uid)
        return _ok()
    if act == "message":
        text = _clean_str(b.get("text"), 3500)
        if not text:
            return _err("empty")
        await _notify_user(ctx.bot.id, uid, text)
        return _ok()
    return _err("bad_action")


async def s_payments(req: web.Request) -> web.Response:
    """طرق الدفع اليدوية + باقات الشحن + حدود المبلغ المخصص + النجوم."""
    ctx = await _ctx(req, "seller")
    bid = ctx.bot.id
    if req.method == "POST":
        b = await _body(req)
        if isinstance(b.get("methods"), list):
            out = []
            for i, m in enumerate(b["methods"][:15]):
                if not isinstance(m, dict) or not _clean_str(m.get("name"), 60):
                    continue
                cur = _clean_str(m.get("currency"), 8).upper() or "USD"
                out.append({"id": _clean_str(m.get("id"), 32) or f"m{uuid.uuid4().hex[:6]}", "name": _clean_str(m.get("name"), 60),
                            "account": _clean_str(m.get("account"), 200), "instructions": _clean_str(m.get("instructions"), 600),
                            "currency": cur if cur in currency.CURRENCIES else "USD", "on": bool(m.get("on", True)),
                            "min": max(0.0, float(m.get("min") or 1)), "max": max(1.0, float(m.get("max") or 10000)), "fee_type": "seller", "fee_val": 0.0})
            await payments.save_payment_methods(bid, out)
        cfg = await db.kv_get(bid, "v2:store", {}) or {}
        if isinstance(b.get("packages"), list):
            pk = sorted({round(float(x), 2) for x in b["packages"] if str(x).replace(".", "", 1).isdigit() and 0 < float(x) <= 10000})[:8]
            cfg["packages"] = pk or STORE_DEFAULTS["packages"]
        for k in ("custom_min", "custom_max"):
            if k in b:
                try:
                    cfg[k] = max(0.1, min(float(b[k]), 100000))
                except (TypeError, ValueError):
                    pass
        if "stars_enabled" in b:
            cfg["stars_enabled"] = bool(b["stars_enabled"])
        if "store_currency" in b and b["store_currency"] in currency.CURRENCIES:
            await currency.set_bot_currency(bid, b["store_currency"])
        if isinstance(b.get("manual_rates"), dict):
            for code, r in list(b["manual_rates"].items())[:60]:
                if code in currency.CURRENCIES:
                    try:
                        await currency.set_manual_rate(bid, code, float(r) if r not in (None, "") else None)
                    except (TypeError, ValueError):
                        pass
        await db.kv_set(bid, "v2:store", cfg)
    cfg = await store_cfg(bid)
    methods = [dict({"currency": "USD", "on": False}, **m) for m in await payments.get_payment_methods(bid) if m.get("id") != "telegram_stars"]
    return _ok(methods=methods, packages=cfg["packages"], custom_min=cfg["custom_min"], custom_max=cfg["custom_max"],
               stars_enabled=cfg["stars_enabled"], store_currency=await currency.get_bot_currency(bid),
               manual_rates=await db.kv_get(bid, "cur:manual_rates", {}) or {}, currencies=await _currencies(bid))


async def s_receipts(req: web.Request) -> web.Response:
    ctx = await _ctx(req, "seller")
    if req.method == "POST":
        b = await _body(req)
        rid = _clean_str(b.get("receipt_id"), 64)
        async with db.Session() as s:
            rc = (await s.execute(select(db.PaymentReceipt).where(db.PaymentReceipt.receipt_id == rid))).scalars().first()
        if rc is None or rc.bot_id != ctx.bot.id:
            return _err("not_found", status=404)
        if b.get("action") == "approve":
            amt = b.get("amount_usd")
            ok, msg, _ = await payments.approve_receipt(rid, "", bot_id=ctx.bot.id, amount_usd=float(amt) if amt not in (None, "") else None)
            if ok:
                await _notify_user(ctx.bot.id, rc.user_id, f"✅ تم قبول إيصالك وشحن رصيدك بـ ${float(amt) if amt not in (None, '') else rc.amount_usd:.2f}")
        else:
            ok, msg = await payments.reject_receipt(rid, _clean_str(b.get("reason"), 200), bot_id=ctx.bot.id)
            if ok:
                await _notify_user(ctx.bot.id, rc.user_id, "❌ تم رفض إيصال الشحن. " + (_clean_str(b.get("reason"), 200) or "تواصل مع الدعم."))
        if not ok:
            return _err("failed", msg)
    st = req.query.get("status", "pending")
    async with db.Session() as s:
        rows = (await s.execute(select(db.PaymentReceipt).where(db.PaymentReceipt.bot_id == ctx.bot.id, db.PaymentReceipt.status == st)
                                .order_by(db.PaymentReceipt.id.desc()).limit(50))).scalars().all()
    return _ok(receipts=[{"id": r.receipt_id, "uid": r.user_id, "name": r.user_name, "username": r.username, "method": r.method,
                          "amount": float(r.amount), "currency": r.currency, "amount_usd": float(r.amount_usd), "proof": r.proof_text,
                          "status": r.status} for r in rows])


async def s_marketing(req: web.Request) -> web.Response:
    """أكواد الخصم + إعدادات الإحالة + رسالة جماعية للزبائن."""
    ctx = await _ctx(req, "seller")
    bid = ctx.bot.id
    if req.method == "POST":
        b = await _body(req)
        act = b.get("action")
        if act == "coupon_save":
            code = _clean_str(b.get("code"), 32).upper()
            if not code.replace("_", "").isalnum():
                return _err("bad_code", "الكود أحرف وأرقام فقط")
            try:
                await promo.save_bot_promo(bid, code, discount_type="fixed" if b.get("type") == "fixed" else "percent",
                                           value=max(0.0, float(b.get("value") or 0)), max_uses=int(b.get("max_uses") or 100),
                                           per_user=int(b.get("per_user") or 1), min_order_usd=float(b.get("min_order") or 0),
                                           expires_at=_clean_str(b.get("expires"), 10))
            except (TypeError, ValueError):
                return _err("bad_values")
        elif act == "coupon_delete":
            await promo.delete_bot_promo(bid, _clean_str(b.get("code"), 32))
        elif act == "referral":
            conf = await promo.get_referral_config(bid)
            conf["on"] = bool(b.get("on"))
            try:
                conf["percent"] = max(0.0, min(float(b.get("percent", conf["percent"])), 50.0))
                conf["signup_bonus"] = max(0.0, min(float(b.get("signup_bonus", conf["signup_bonus"])), 5.0))
            except (TypeError, ValueError):
                return _err("bad_values")
            await promo.save_referral_config(bid, conf)
        elif act == "broadcast":
            text = _clean_str(b.get("text"), 3500)
            if not text:
                return _err("empty", "اكتب نص الرسالة")
            last = float(await db.kv_get(bid, "v2:last_bc", 0) or 0)
            if time.time() - last < 600:
                return _err("too_soon", "انتظر 10 دقائق بين كل رسالة جماعية")
            await db.kv_set(bid, "v2:last_bc", time.time())
            import asyncio
            asyncio.get_running_loop().create_task(_broadcast(bid, text))
            return _ok(message="بدأ الإرسال للزبائن")
    promos = await promo.get_bot_promos(bid)
    return _ok(coupons=[{"code": k, "type": v.get("type"), "value": v.get("val"), "max_uses": v.get("max_uses"), "used": v.get("used_count", 0),
                         "per_user": v.get("per_user"), "min_order": v.get("min_order"), "expires": v.get("expires")} for k, v in promos.items()],
               referral=await promo.get_referral_config(bid))


async def _broadcast(bot_id: int, text: str) -> None:
    import asyncio
    from ..runtime import manager
    app = manager.apps.get(bot_id)
    if app is None:
        return
    async with db.Session() as s:
        uids = (await s.execute(select(db.BUser.user_id).where(db.BUser.bot_id == bot_id, db.BUser.kind == "private",
                                                                db.BUser.blocked.is_(False), db.BUser.banned.is_(False)))).scalars().all()
    for uid in uids:
        try:
            await app.bot.send_message(uid, text)
        except Exception:
            pass
        await asyncio.sleep(0.05)


async def s_store(req: web.Request) -> web.Response:
    """مظهر المتجر + الدعم + الأسئلة الشائعة + الشروط والمساعدة."""
    ctx = await _ctx(req, "seller")
    bid = ctx.bot.id
    if req.method == "POST":
        b = await _body(req)
        cfg = await db.kv_get(bid, "v2:store", {}) or {}
        for k, n in (("name", 60), ("desc", 300), ("announcement", 300), ("terms", 4000), ("help", 4000)):
            if k in b:
                cfg[k] = _clean_str(b[k], n)
        for k in ("logo", "banner"):
            if k in b:
                cfg[k] = _clean_url(b[k])
        if "accent" in b:
            a = _clean_str(b["accent"], 7)
            cfg["accent"] = a if len(a) == 7 and a.startswith("#") and all(c in "0123456789abcdefABCDEF" for c in a[1:]) else "#6d5dfc"
        if b.get("theme") in ("auto", "dark", "light"):
            cfg["theme"] = b["theme"]
        if isinstance(b.get("support"), dict):
            sp = b["support"]
            links = [{"label": _clean_str(x.get("label"), 30), "url": _clean_url(x.get("url"))} for x in (sp.get("links") or [])[:6]
                     if isinstance(x, dict) and _clean_url(x.get("url"))]
            cfg["support"] = {"username": _clean_str(sp.get("username"), 40).lstrip("@"), "whatsapp": _clean_str(sp.get("whatsapp"), 20),
                              "email": _clean_str(sp.get("email"), 80), "channel": _clean_str(sp.get("channel"), 60).lstrip("@"), "links": links}
        if "bg" in b:
            cfg["bg"] = _clean_url(b["bg"])
        if isinstance(b.get("ads"), list):
            cfg["ads"] = [{"img": _clean_url(x.get("img")), "text": _clean_str(x.get("text"), 80), "url": _clean_url(x.get("url"))}
                          for x in b["ads"][:10] if isinstance(x, dict) and _clean_url(x.get("img"))]
        if isinstance(b.get("ticker"), dict):
            cfg["ticker"] = {"text": _clean_str(b["ticker"].get("text"), 300), "mode": "static" if b["ticker"].get("mode") == "static" else "scroll"}
        if "faq_enabled" in b:
            cfg["faq_enabled"] = bool(b["faq_enabled"])
        if isinstance(b.get("faq"), list):
            cfg["faq"] = [{"q": _clean_str(x.get("q"), 200), "a": _clean_str(x.get("a"), 1500)} for x in b["faq"][:30]
                          if isinstance(x, dict) and _clean_str(x.get("q"), 200)]
        if isinstance(b.get("currencies"), list):
            cfg["currencies"] = [c for c in b["currencies"] if c in currency.CURRENCIES][:60]
        await db.kv_set(bid, "v2:store", cfg)
        invalidate(bid)
    return _ok(store=await store_cfg(bid))


async def upload_ep(req: web.Request) -> web.Response:
    ctx = await _ctx(req, "seller")
    reader = await req.multipart()
    async for part in reader:
        if part.name in ("file", "image") and part.filename:
            raw = await part.read(decode=False)
            if len(raw) > 8 * 1024 * 1024:
                return _err("too_large", "الملف أكبر من 8MB")
            try:
                from . import media_pipe
                r = media_pipe.handle_uploaded_file(bytes(raw), part.filename)
                return _ok(url=r.get("url", ""))
            except Exception as e:
                return _err("bad_file", str(e))
    return _err("no_file")


# ───────────────────────── لوحة المدير ─────────────────────────
async def a_overview(req: web.Request) -> web.Response:
    await _ctx(req, "admin")
    async with db.Session() as s:
        bots = (await s.execute(select(func.count(db.Bot.id)))).scalar() or 0
        active = (await s.execute(select(func.count(db.Bot.id)).where(db.Bot.status == "active"))).scalar() or 0
        sellers = (await s.execute(select(func.count(func.distinct(db.Bot.owner_id))))).scalar() or 0
        liab = float((await s.execute(select(func.coalesce(func.sum(db.UserBalance.balance_usd), 0)).where(db.UserBalance.bot_id == 0))).scalar() or 0)
        pend_rc = (await s.execute(select(func.count(db.PaymentReceipt.id)).where(db.PaymentReceipt.bot_id == 0, db.PaymentReceipt.status == "pending"))).scalar() or 0
        queued = (await s.execute(select(func.count(db.ServiceOrder.id)).where(db.ServiceOrder.status.in_(("queued", "pending"))))).scalar() or 0
    from .. import plat as platform
    p0 = await platform.get(0)
    return _ok(today=await _sales(None, 1), week=await _sales(None, 7), month=await _sales(None, 30), series=await _series(None),
               bots=bots, active_bots=active, sellers=sellers, sellers_balance_usd=round(liab, 2), pending_topups=pend_rc,
               queued_orders=queued, maintenance=bool(p0.get("maintenance")))


async def a_sellers(req: web.Request) -> web.Response:
    ctx = await _ctx(req, "admin")
    if req.method == "POST":
        b = await _body(req)
        try:
            uid = int(b.get("owner_id"))
            amt = round(float(b.get("amount_usd")), 4)
            assert 0 < amt <= 100000
        except (TypeError, ValueError, AssertionError):
            return _err("bad_values")
        fn = ledger.credit_seller if b.get("action") == "credit" else ledger.debit_seller
        ok, _tx, bal = await fn(uid, amt, "admin_manual", description=f"by admin {ctx.uid}")
        if not ok:
            return _err("failed", "الرصيد غير كافٍ")
        return _ok(balance_usd=bal)
    term = _clean_str(req.query.get("q"), 64).lstrip("@")
    q = select(db.Bot)
    if term:
        q = q.where((db.Bot.username.contains(term)) | (func.cast(db.Bot.owner_id, String).contains(term)))
    async with db.Session() as s:
        rows = (await s.execute(q.order_by(desc(db.Bot.created)).limit(80))).scalars().all()
        owners = list({r.owner_id for r in rows})
        bals = {r.user_id: float(r.balance_usd) for r in (await s.execute(select(db.UserBalance).where(db.UserBalance.bot_id == 0, db.UserBalance.user_id.in_(owners or [0])))).scalars().all()}
    out = []
    for r in rows:
        out.append({"bot_id": r.id, "username": r.username, "name": r.name, "tpl": r.template, "status": r.status, "owner_id": r.owner_id,
                    "owner_balance_usd": bals.get(r.owner_id, 0.0), "sales_30d": (await _sales(r.id, 30))["sales_usd"]})
    return _ok(bots=out)


async def a_hold(req: web.Request) -> web.Response:
    """الطلبات المعلّقة بانتظار موافقة المدير (تفاعل وأرقام) + تفعيل/إيقاف الموافقة اليدوية."""
    await _ctx(req, "admin")
    from ..modules import hold
    from ..runtime import manager
    res = {}
    if req.method == "POST":
        b = await _body(req)
        act = b.get("action")
        if act == "toggle" and b.get("sec") in hold.SECS:
            await hold.set_enabled(b["sec"], bool(b.get("on")))
        elif act in ("approve", "reject"):
            try:
                pk = int(b.get("id"))
            except (TypeError, ValueError):
                return _err("bad_id")
            if act == "approve":
                ok, msg = await hold.approve(pk, notify=manager._order_note)
            else:
                ok, msg = await hold.reject(pk, reason=_clean_str(b.get("reason"), 200) or "رُفض الطلب من الإدارة", notify=manager._order_note)
            res = {"done": ok, "message": msg}
        elif act == "approve_all":
            sm = await hold.summary()
            ids = [o["id"] for o in sm["orders"] if (not b.get("provider") or o["provider"] == b.get("provider")) and not o["busy"]]
            okn = 0
            for pk in ids:
                ok, _m = await hold.approve(pk, notify=manager._order_note)
                okn += ok
            res = {"done": True, "message": f"أُرسل {okn} من {len(ids)}"}
    return _ok(**(await hold.summary()), settings=await hold.settings(), **res)


async def a_orders(req: web.Request) -> web.Response:
    """طلبات تحتاج تنفيذاً يدوياً من المنصة (الرقمي والمنتجات العامة)، مع التسليم أو الاسترجاع."""
    ctx = await _ctx(req, "admin")
    if req.method == "POST":
        b = await _body(req)
        oid = _clean_str(b.get("order_id"), 64)
        async with db.Session() as s:
            o = (await s.execute(select(db.ServiceOrder).where(db.ServiceOrder.order_id == oid))).scalars().first()
            if o is None:
                return _err("not_found", status=404)
            if b.get("action") == "deliver":
                text = _clean_str(b.get("text"), 2000)
                if not text:
                    return _err("empty", "اكتب بيانات التسليم")
                if o.status in ("completed", "refunded", "canceled"):
                    return _err("done", "الطلب منتهٍ مسبقاً")
                o.status, o.delivery_text = "completed", text
                await s.commit()
                await _notify_user(o.bot_id, o.user_id, f"✅ تم تنفيذ طلبك #{oid[-8:]}\n{o.service_name}\n\n{text}")
                return _ok()
        if b.get("action") == "refund":
            ok, msg, _ = await ledger.atomic_dual_refund(oid, reason=_clean_str(b.get("reason"), 200) or "تعذّر التنفيذ", admin_id=ctx.uid)
            if ok:
                await _notify_user(o.bot_id, o.user_id, f"↩️ تعذّر تنفيذ طلبك #{oid[-8:]} وأُعيد المبلغ لرصيدك.")
            return _ok(message=msg) if ok else _err("failed", msg)
        return _err("bad_action")
    st = req.query.get("status", "queued,pending")
    async with db.Session() as s:
        rows = (await s.execute(select(db.ServiceOrder).where(db.ServiceOrder.status.in_(st.split(",")))
                                .order_by(desc(db.ServiceOrder.created)).limit(100))).scalars().all()
    return _ok(orders=[_order_dict(o) for o in rows])


async def a_catalog(req: web.Request) -> web.Response:
    """كتالوج المنصة: التكلفة الحقيقية، رقم الخدمة لدى المزود، الإظهار، والهوامش."""
    await _ctx(req, "admin")
    if req.method == "POST":
        b = await _body(req)
        sec = b.get("sec")
        if sec in pcat.TPLS and b.get("item_id"):
            kw = {}
            if "ps" in b:
                kw["ps"] = _clean_str(b["ps"], 64)
            if "cost" in b and b["cost"] not in (None, ""):
                try:
                    kw["cost"] = max(0.0, float(b["cost"]))
                except (TypeError, ValueError):
                    return _err("bad_cost")
            if "off" in b:
                kw["off"] = bool(b["off"])
            await pcat.set_entry(sec, _clean_str(b["item_id"], 64), **kw)
            _CAT_CACHE.clear()
        if "margin_key" in b:
            mk = _clean_str(b["margin_key"], 64)
            mt = "fixed" if b.get("margin_type") == "fixed" else "percent"
            try:
                await MarkupManager.set_margin_rule(mk, mt, max(0.0, float(b.get("margin_val") or 0)), admin_id=0, note="v2 panel")
                _CAT_CACHE.clear()
            except (TypeError, ValueError):
                return _err("bad_margin")
    out = {}
    for sec in pcat.TPLS:
        cmap = await pcat.get_map(sec)
        if sec == "smm":
            from ..modules.providers.smm import catalog_source
            base = [(x["id"], x["name_ar"], x["rate_per_1k"]) for x in catalog_source()]
        elif sec == "tgstars":
            base = [(x["id"], x["name_ar"], x["rate_usd"]) for x in TGSTARS_CATALOG]
        elif sec == "digital":
            base = [(x["id"], x["name_ar"], x["rate_usd"]) for x in DIGITAL_CATALOG]
        else:
            base = [(f"{c}_{a}", f"{ai['name_ar']} — {ci['name_ar']}", SMSManager.base_cost(c, a)) for c, ci in SMS_COUNTRIES.items() for a, ai in SMS_APPS.items()]
        out[sec] = [{"id": i, "name": n, "default_cost": float(d), "cost": pcat.effective_cost(cmap, i, d), "ps": (cmap.get(i) or {}).get("ps", ""),
                     "off": pcat.is_off(cmap, i)} for i, n, d in base]
    return _ok(catalog=out, margins=await MarkupManager.get_all_rules())


async def a_providers(req: web.Request) -> web.Response:
    await _ctx(req, "admin")
    keys = {"smm": "smm:providers", "sms": "sms:providers", "tgstars": "tgstars:providers"}
    if req.method == "POST":
        b = await _body(req)
        sec = b.get("sec")
        if sec not in keys:
            return _err("bad_sec")
        provs = await db.kv_get(0, keys[sec], []) or []
        if b.get("action") == "add":
            name, url, key = _clean_str(b.get("name"), 40), _clean_url(b.get("api_url")), _clean_str(b.get("api_key"), 200)
            if not (name and url.startswith("https://") and key):
                return _err("bad_values", "الاسم والرابط (https) والمفتاح مطلوبة")
            provs.append({"name": name, "api_url": url, "api_key": key, "on": True})
        elif b.get("action") == "delete":
            idx = int(b.get("index", -1))
            if 0 <= idx < len(provs):
                provs.pop(idx)
        elif b.get("action") == "toggle":
            idx = int(b.get("index", -1))
            if 0 <= idx < len(provs):
                provs[idx]["on"] = not provs[idx].get("on", True)
        await db.kv_set(0, keys[sec], provs)
    out = {}
    for sec, k in keys.items():
        out[sec] = [{"name": p.get("name"), "api_url": p.get("api_url"), "on": p.get("on", True), "key_hint": "…" + str(p.get("api_key", ""))[-4:]}
                    for p in (await db.kv_get(0, k, []) or [])]
    return _ok(providers=out)


async def a_provider_balance(req: web.Request) -> web.Response:
    await _ctx(req, "admin")
    sec = req.query.get("sec", "smm")
    mgr = {"smm": SMMManager, "sms": SMSManager, "tgstars": TGStarsManager}.get(sec)
    if mgr is None:
        return _err("bad_sec")
    async def one(p):
        try:
            return {"name": p.name, "balance": round(float(await p.get_balance()), 4)}
        except Exception as e:  # noqa: BLE001
            return {"name": p.name, "error": str(e)[:120]}
    res = await asyncio.gather(*(one(p) for p in await mgr.get_configured_providers(0)))
    return _ok(results=list(res))


async def a_smm_sync(req: web.Request) -> web.Response:
    """مقارنة أسعار مواقع التفاعل: الحالة، التحديث الآن، واستيراد مواقع بالجملة (لصق نص)."""
    await _ctx(req, "admin")
    from ..modules import smm_agg
    await smm_agg.load()
    msg = {}
    if req.method == "POST":
        b = await _body(req)
        if b.get("action") == "import":
            added, updated = await smm_agg.import_providers(str(b.get("text") or "")[:20000])
            msg = {"added": added, "updated": updated}
            if added or updated:
                smm_agg.start_refresh()
        elif b.get("action") == "refresh":
            msg = {"started": smm_agg.start_refresh()}
    st = smm_agg.status()
    top = [{"id": i["id"], "name": i["name_ar"], "rate": i["rate_per_1k"], "n": i.get("n", 1),
            "best": (i.get("offers") or [{}])[0].get("p", "")} for i in smm_agg.items_now()[:60]]
    return _ok(status=st, items=top, **msg)


async def a_topups(req: web.Request) -> web.Response:
    ctx = await _ctx(req, "admin")
    if req.method == "POST":
        b = await _body(req)
        rid = _clean_str(b.get("receipt_id"), 64)
        async with db.Session() as s:
            rc = (await s.execute(select(db.PaymentReceipt).where(db.PaymentReceipt.receipt_id == rid))).scalars().first()
        if rc is None or rc.bot_id != 0:
            return _err("not_found", status=404)
        if b.get("action") == "approve":
            from ..wallet import MIN_TOPUP_USD
            amt = b.get("amount_usd")
            amt = float(amt) if amt not in (None, "") else None
            if amt is not None and amt < MIN_TOPUP_USD:
                return _err("below_min", f"الحد الأدنى {MIN_TOPUP_USD:g}$")
            ok, msg, _ = await payments.approve_receipt(rid, f"by {ctx.uid}", bot_id=0, amount_usd=amt)
            if ok:
                await ledger.apply_first_deposit_bonus(rc.user_id, amt if amt is not None else float(rc.amount_usd))
        else:
            ok, msg = await payments.reject_receipt(rid, _clean_str(b.get("reason"), 200), bot_id=0)
        if not ok:
            return _err("failed", msg)
    async with db.Session() as s:
        rows = (await s.execute(select(db.PaymentReceipt).where(db.PaymentReceipt.bot_id == 0, db.PaymentReceipt.status == "pending")
                                .order_by(db.PaymentReceipt.id.desc()).limit(50))).scalars().all()
    return _ok(receipts=[{"id": r.receipt_id, "uid": r.user_id, "name": r.user_name, "method": r.method, "amount_usd": float(r.amount_usd),
                          "proof": r.proof_text} for r in rows])


async def a_settings(req: web.Request) -> web.Response:
    ctx = await _ctx(req, "admin")
    from .. import plat as platform
    p0 = await platform.get(0)
    if req.method == "POST":
        b = await _body(req)
        if "maintenance" in b:
            p0["maintenance"] = bool(b["maintenance"])
            await platform.save(0)
            await platform.audit(0, ctx.uid, "maintenance", info="v2 panel")
        if isinstance(b.get("seller_methods"), list):
            ms = [{"name": _clean_str(x.get("name"), 40), "account": _clean_str(x.get("account"), 200), "instructions": _clean_str(x.get("instructions"), 500)}
                  for x in b["seller_methods"][:10] if isinstance(x, dict) and _clean_str(x.get("name"), 40)]
            await db.kv_set(0, "sys:seller_pay_methods", ms)
    return _ok(maintenance=bool(p0.get("maintenance")), seller_methods=await db.kv_get(0, "sys:seller_pay_methods", []) or [])


# ───────────────────────── التسجيل ─────────────────────────
def setup_routes(app: web.Application) -> None:
    u = r"{bot_username:[A-Za-z0-9_]{3,40}}"
    P = f"/api/v2/{u}"
    r = app.router
    r.add_get(f"{P}/boot", boot)
    r.add_post(f"{P}/prefs", prefs)
    r.add_get(f"{P}/catalog", catalog_ep)
    r.add_post(f"{P}/quote", quote_ep)
    r.add_post(f"{P}/order", v1.create_store_order)
    r.add_post(f"{P}/cart", v1.checkout_cart_order)
    r.add_get(f"{P}/orders", v1.get_user_orders)
    r.add_post(f"{P}/sms/check", v1.sms_check_endpoint)
    r.add_post(f"{P}/sms/cancel", v1.sms_cancel_endpoint)
    r.add_get(f"{P}/wallet", wallet_ep)
    r.add_post(f"{P}/deposit/stars", deposit_stars)
    r.add_post(f"{P}/deposit/receipt", deposit_receipt)
    r.add_get(f"{P}/account", account_ep)
    for path, h in (("overview", s_overview), ("orders", s_orders), ("customers", s_customers)):
        r.add_get(f"{P}/seller/{path}", h)
    r.add_post(f"{P}/seller/orders", s_order_action)
    r.add_post(f"{P}/seller/customers", s_customer_action)
    for path, h in (("pricing", s_pricing), ("payments", s_payments), ("receipts", s_receipts), ("marketing", s_marketing), ("store", s_store)):
        r.add_get(f"{P}/seller/{path}", h)
        r.add_post(f"{P}/seller/{path}", h)
    r.add_post(f"{P}/seller/upload", upload_ep)
    r.add_get(f"{P}/admin/overview", a_overview)
    r.add_get(f"{P}/admin/provider_balance", a_provider_balance)
    r.add_get(f"{P}/admin/smm_sync", a_smm_sync)
    r.add_get(f"{P}/admin/hold", a_hold)
    r.add_post(f"{P}/admin/hold", a_hold)
    r.add_post(f"{P}/admin/smm_sync", a_smm_sync)
    for path, h in (("sellers", a_sellers), ("orders", a_orders), ("catalog", a_catalog), ("providers", a_providers),
                    ("topups", a_topups), ("settings", a_settings)):
        r.add_get(f"{P}/admin/{path}", h)
        r.add_post(f"{P}/admin/{path}", h)
