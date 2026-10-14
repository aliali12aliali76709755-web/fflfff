"""طبقة المصادقة والتحقق الصارم من الهوية والأدوار للتطبيقات المصغرة (Mini Apps Auth Layer)."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any
from aiohttp import web
from sqlalchemy import func, select

from .. import config, crypto, db
from . import sign

log = logging.getLogger("forge.miniapp_auth")


@dataclass
class AuthContext:
    """سياق هوية وصلاحيات المستخدم داخل التطبيق المصغر."""
    bot: db.Bot
    user: dict[str, Any]
    role: str               # "admin" | "seller" | "buyer"
    uid: int
    uname: str
    is_owner: bool
    is_admin: bool
    init_data_raw: str = ""
    is_guest: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid": self.uid,
            "name": self.uname,
            "role": self.role,
            "is_owner": self.is_owner,
            "is_admin": self.is_admin,
            "is_guest": self.is_guest,
        }


_RESOLVE_CACHE: dict[str, tuple[float, db.Bot | None]] = {}


def invalidate_resolve_cache(bot_identifier: str | int | None = None) -> None:
    if bot_identifier:
        clean = str(bot_identifier).lstrip("@").strip().lower()
        _RESOLVE_CACHE.pop(clean, None)
    else:
        _RESOLVE_CACHE.clear()


async def resolve_bot(bot_identifier: str | int | None = None) -> db.Bot | None:
    """يجلب سجل البوت إما عبر ID أو عبر username مع توفير بدائل ذكية وكاش 60 ثانية."""
    clean_u = str(bot_identifier or "").lstrip("@").strip().lower()
    hit = _RESOLVE_CACHE.get(clean_u)
    if hit and time.time() - hit[0] < 60:
        return hit[1]

    async with db.Session() as s:
        # إذا لم يتم تحديد بوت أو تم تمرير اسم عام افتراضي
        if not clean_u or clean_u in ("shop", "app", "default", "store", "admin_app", "store_default"):
            bot = (await s.execute(
                select(db.Bot).where(db.Bot.status == "active", db.Bot.template.in_(("digital", "sms", "smm", "tgstars", "store")))
            )).scalars().first()
            if bot is None:
                bot = (await s.execute(select(db.Bot).where(db.Bot.status == "active"))).scalars().first()
            _RESOLVE_CACHE[clean_u] = (time.time(), bot)
            return bot

        # إذا كان المعرف رقماً (Bot ID)
        if clean_u.isdigit():
            bot = await s.get(db.Bot, int(clean_u))
            if bot:
                _RESOLVE_CACHE[clean_u] = (time.time(), bot)
                return bot

        # البحث عبر اسم المستخدم username
        # الأحدث النشط أولاً (قد يبقى سجل قديم بنفس الاسم لبوت حُذف وأعيد تسجيله)
        bot = (await s.execute(
            select(db.Bot).where(func.lower(db.Bot.username) == clean_u)
            .order_by((db.Bot.status == "active").desc(), db.Bot.created.desc())
        )).scalars().first()
        _RESOLVE_CACHE[clean_u] = (time.time(), bot)
        return bot




async def authenticate_miniapp_request(
    req: web.Request,
    bot_identifier: str | int | None = None,
    *,
    require_role: str | None = None,
) -> AuthContext:
    """يتحقق من صحة توقيع initData بمفتاح توكن البوت المعني أو الصانع ويحدد دور المستخدم بدقة صارمة."""
    # استخراج store_id من الاستعلام أو الترويسة إن لم يُمرر
    if not bot_identifier:
        bot_identifier = (
            req.match_info.get("bot_username")
            or req.headers.get("x-store-id")
            or req.headers.get("X-Store-Id")
            or req.query.get("store_id")
            or req.query.get("start_param")
            or "default"
        )

    bot = await resolve_bot(bot_identifier)
    if bot is None:
        raise web.HTTPNotFound(
            text=json.dumps({"ok": False, "success": False, "error": "bot_not_found", "message": "البوت غير موجود"}),
            content_type="application/json",
        )

    # قراءة بيانات initData من كافة الترويسات والبارامترات الممكنة
    init_data = (
        req.headers.get("X-Telegram-Init-Data")
        or req.headers.get("x-telegram-init-data")
        or req.headers.get("X-Init-Data")
        or req.headers.get("x-init-data")
        or req.query.get("_init")
        or req.query.get("init_data")
        or req.query.get("initData")
        or ""
    )

    body_role = ""
    # فحص محتوى الـ body إن كان JSON ويحتوي على initData أو role
    try:
        body = await req.json()
        if isinstance(body, dict):
            if not init_data:
                init_data = body.get("initData") or body.get("init_data") or ""
            body_role = str(body.get("role") or body.get("requestedRole") or "").strip().lower()
    except Exception:
        pass


    user_data = None

    is_guest = False

    # مفتاح إدارة للوصول من المتصفح خارج تيليجرام: يعمل فقط إن ضُبط ADMIN_WEB_SECRET (24 حرفاً فأكثر).
    # لا قيمة افتراضية ولا اشتقاق من توكن الصانع، والمقارنة بزمن ثابت ضد هجمات التوقيت.
    admin_secret = os.environ.get("ADMIN_WEB_SECRET", "").strip()
    req_admin_key = (req.headers.get("x-admin-key") or req.headers.get("X-Admin-Key") or "").strip()
    is_key_authenticated_admin = bool(
        len(admin_secret) >= 24 and req_admin_key
        and hmac.compare_digest(req_admin_key.encode(), admin_secret.encode())
    )

    if not init_data:
        if is_key_authenticated_admin and config.ADMIN_ID:
            user_data = {"id": int(config.ADMIN_ID), "first_name": "مدير المنصة", "username": "super_admin"}
        else:
            # زائر من المتصفح: تصفّح فقط، بهوية سالبة فريدة لكل جهاز (لا تتصادم مع هويات تيليجرام ولا مع زوار آخرين)
            gid = (req.headers.get("x-guest-id") or req.cookies.get("guest_id") or "").strip()[:64]
            if not gid:
                peer = req.remote or ""
                ua = req.headers.get("User-Agent", "")
                gid = f"{peer}|{ua}"
            h = int.from_bytes(hashlib.sha256(gid.encode()).digest()[:6], "big")
            user_data = {"id": -(h or 1), "first_name": "زائر المتجر", "username": ""}
            is_guest = True
    else:
        init_data = str(init_data)
        # 1. التحقق بتوكن البوت نفسه (الحالة الطبيعية: فتح المتجر من داخل بوت البائع)
        if bot.token:
            try:
                user_data = sign.check_init_data(init_data, crypto.dec(bot.token), max_age=86400)
            except Exception:
                user_data = None

        # 2. التحقق بتوكن الصانع (فتح اللوحة من بوت الصانع) — هوية تيليجرام واحدة عالمياً فلا خلط بين المتاجر
        if not user_data and config.MAKER_TOKEN:
            try:
                user_data = sign.check_init_data(init_data, config.MAKER_TOKEN, max_age=86400)
            except Exception:
                user_data = None

        # 3. احتياطي محدود: بوتات يملكها نفس المستخدم فقط، وننقل السياق لذلك البوت نفسه.
        #    لا نجرّب توكنات كل البوتات أبداً (كان ذلك بطيئاً ويقبل توقيع بوت آخر داخل متجر غريب).
        if not user_data:
            parsed_uid = None
            try:
                u_obj = json.loads(urllib.parse.parse_qs(init_data).get("user", ["{}"])[0])
                if isinstance(u_obj, dict) and u_obj.get("id"):
                    parsed_uid = int(u_obj["id"])
            except Exception:
                parsed_uid = None
            if parsed_uid:
                async with db.Session() as s:
                    owned = (await s.execute(
                        select(db.Bot).where(db.Bot.owner_id == parsed_uid, db.Bot.status == "active").limit(20)
                    )).scalars().all()
                for b in owned:
                    if not b.token:
                        continue
                    try:
                        u_try = sign.check_init_data(init_data, crypto.dec(b.token), max_age=86400)
                    except Exception:
                        u_try = None
                    if u_try:
                        user_data, bot = u_try, b
                        break

    if not user_data or not user_data.get("id"):
        raise web.HTTPUnauthorized(
            text=json.dumps({"ok": False, "success": False, "error": "invalid_signature", "message": "توقيع الدخول غير صالح أو منتهي الصلاحية"}),
            content_type="application/json",
        )

    uid = int(user_data["id"])
    name_parts = [user_data.get("first_name", ""), user_data.get("last_name", "")]
    uname = " ".join(p for p in name_parts if p).strip() or user_data.get("username", "") or f"User {uid}"

    # تحديد الأدوار في السيرفر بدقة صارمة
    is_admin = (not is_guest) and bool(config.is_admin(uid) or (config.ADMIN_ID and uid == config.ADMIN_ID))
    is_owner = (not is_guest) and bool(uid == bot.owner_id)

    # الزائر من خارج تيليجرام يتصفح فقط: أي عملية كتابة (شراء/شحن/تعديل) تتطلب فتح المتجر من تيليجرام
    _guest_ok = req.path.endswith(("/auth", "/coupon/validate", "/user/language"))
    if is_guest and req.method not in ("GET", "HEAD", "OPTIONS") and not _guest_ok:
        raise web.HTTPUnauthorized(
            text=json.dumps({"ok": False, "success": False, "error": "telegram_required",
                             "message": "افتح المتجر من داخل تيليجرام لإتمام العملية"}),
            content_type="application/json",
        )


    # إذا كان المستخدم يملك بوتاً خاصاً به وفُتح التطبيق باسم افتراضي
    if not is_guest and not is_owner and not is_admin and str(bot_identifier).lower() in ("shop", "app", "default", "store", "admin_app", "store_default"):
        async with db.Session() as s:
            user_bot = (await s.execute(
                select(db.Bot).where(db.Bot.owner_id == uid, db.Bot.status == "active")
            )).scalars().first()
            if user_bot:
                bot = user_bot
                is_owner = True

    if is_admin:
        role = "admin"
    elif is_owner:
        role = "seller"
    else:
        role = "buyer"

    ctx = AuthContext(
        bot=bot,
        user=user_data,
        role=role,
        uid=uid,
        uname=uname,
        is_owner=is_owner,
        is_admin=is_admin,
        init_data_raw=str(init_data),
        is_guest=is_guest,
    )

    if require_role == "seller" and not (ctx.is_owner or ctx.is_admin):
        raise web.HTTPForbidden(
            text=json.dumps({"ok": False, "success": False, "error": "forbidden_role", "message": "هذه الصفحة مخصصة لمالك المتجر فقط"}),
            content_type="application/json",
        )

    if require_role == "admin" and not ctx.is_admin:
        raise web.HTTPForbidden(
            text=json.dumps({"ok": False, "success": False, "error": "forbidden_role", "message": "هذه الصفحة مخصصة لمدير المنصة فقط"}),
            content_type="application/json",
        )

    return ctx


async def authenticate_admin_request(req: web.Request) -> AuthContext:
    """يتحقق حصراً من هوية المدير العام للمنصة (ADMIN_ID)."""
    return await authenticate_miniapp_request(req, "admin_app", require_role="admin")
