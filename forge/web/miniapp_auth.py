"""طبقة المصادقة والتحقق الصارم من الهوية والأدوار للتطبيقات المصغرة (Mini Apps Auth Layer)."""
from __future__ import annotations

import json
import logging
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid": self.uid,
            "name": self.uname,
            "role": self.role,
            "is_owner": self.is_owner,
            "is_admin": self.is_admin,
        }


async def resolve_bot(bot_identifier: str | int) -> db.Bot | None:
    """يجلب سجل البوت إما عبر ID أو عبر username."""
    async with db.Session() as s:
        if isinstance(bot_identifier, int) or (isinstance(bot_identifier, str) and bot_identifier.isdigit()):
            return await s.get(db.Bot, int(bot_identifier))
        clean_u = str(bot_identifier).lstrip("@").lower()
        bot = (await s.execute(select(db.Bot).where(func.lower(db.Bot.username) == clean_u))).scalars().first()
        if bot is None and clean_u in ("shop", "app", "default", "store", "admin_app", ""):
            bot = (await s.execute(
                select(db.Bot).where(db.Bot.status == "active", db.Bot.template.in_(("digital", "sms", "smm", "tgstars", "store")))
            )).scalars().first()
            if bot is None:
                bot = (await s.execute(select(db.Bot).where(db.Bot.status == "active"))).scalars().first()
        return bot


async def authenticate_miniapp_request(
    req: web.Request,
    bot_identifier: str | int,
    *,
    require_role: str | None = None,
) -> AuthContext:
    """يتحقق من صحة توقيع initData بمفتاح توكن البوت المعني أو الصانع ويحدد دور المستخدم بدقة صارمة."""
    bot = await resolve_bot(bot_identifier)
    if bot is None:
        raise web.HTTPNotFound(
            text=json.dumps({"ok": False, "error": "bot_not_found", "message": "البوت غير موجود"}),
            content_type="application/json",
        )

    init_data = (
        req.headers.get("X-Telegram-Init-Data")
        or req.headers.get("X-Init-Data")
        or req.query.get("_init")
        or req.query.get("init_data")
        or ""
    )

    if not init_data:
        raise web.HTTPUnauthorized(
            text=json.dumps({"ok": False, "error": "missing_init_data", "message": "بيانات الدخول مفقودة"}),
            content_type="application/json",
        )

    user_data = None
    # 1. التحقق عبر توكن البوت المطلوب
    if bot.token:
        try:
            raw_token = crypto.dec(bot.token)
            user_data = sign.check_init_data(init_data, raw_token, max_age=86400)
        except Exception:
            pass

    # 2. التحقق عبر توكن الصانع الرئيسي (في حال فُتح التطبيق من بوت الصانع أو الأدمن)
    if not user_data and config.MAKER_TOKEN:
        try:
            user_data = sign.check_init_data(init_data, config.MAKER_TOKEN, max_age=86400)
        except Exception:
            pass

    # 3. التحقق الاحتياطي عبر توكنات البوتات النشطة للمالك
    if not user_data:
        async with db.Session() as s:
            bots_list = (await s.execute(select(db.Bot).where(db.Bot.status == "active"))).scalars().all()
            for b in bots_list[:10]:
                if b.token:
                    try:
                        u_try = sign.check_init_data(init_data, crypto.dec(b.token), max_age=86400)
                        if u_try:
                            user_data = u_try
                            break
                    except Exception:
                        pass

    if not user_data or not user_data.get("id"):
        raise web.HTTPUnauthorized(
            text=json.dumps({"ok": False, "error": "invalid_signature", "message": "توقيع الدخول غير صالح أو منتهي الصلاحية"}),
            content_type="application/json",
        )

    uid = int(user_data["id"])
    name_parts = [user_data.get("first_name", ""), user_data.get("last_name", "")]
    uname = " ".join(p for p in name_parts if p).strip() or user_data.get("username", "") or f"User {uid}"

    # تحديد الأدوار في السيرفر بشكل صارم
    is_admin = bool(config.ADMIN_ID and uid == config.ADMIN_ID)
    is_owner = bool(uid == bot.owner_id)

    # إذا فُتح التطبيق العام وكان المستخدم يملك بوتاً خاصاً به، نربطه ببوته المخصص
    if not is_owner and not is_admin and str(bot_identifier).lower() in ("shop", "app", "default", "store", "admin_app"):
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
        init_data_raw=init_data,
    )

    if require_role == "seller" and not (ctx.is_owner or ctx.is_admin):
        raise web.HTTPForbidden(
            text=json.dumps({"ok": False, "error": "forbidden_role", "message": "هذه الصفحة مخصصة لمالك المتجر فقط"}),
            content_type="application/json",
        )

    if require_role == "admin" and not ctx.is_admin:
        raise web.HTTPForbidden(
            text=json.dumps({"ok": False, "error": "forbidden_role", "message": "هذه الصفحة مخصصة لمدير المنصة فقط"}),
            content_type="application/json",
        )

    return ctx


async def authenticate_admin_request(req: web.Request) -> AuthContext:
    """يتحقق من طلبات لوحة الأدمن المركزية (ADMIN_ID) المشتقة من توكن الصانع الرئيسي أو أي بوت للمنصة."""
    init_data = (
        req.headers.get("X-Telegram-Init-Data")
        or req.headers.get("X-Init-Data")
        or req.query.get("_init")
        or req.query.get("init_data")
        or ""
    )

    if not init_data:
        raise web.HTTPUnauthorized(
            text=json.dumps({"ok": False, "error": "missing_init_data", "message": "بيانات الدخول مفقودة"}),
            content_type="application/json",
        )

    user_data = None
    if config.MAKER_TOKEN:
        try:
            user_data = sign.check_init_data(init_data, config.MAKER_TOKEN, max_age=86400)
        except Exception:
            pass

    if not user_data:
        async with db.Session() as s:
            bots_list = (await s.execute(select(db.Bot).where(db.Bot.status == "active"))).scalars().all()
            for b in bots_list[:10]:
                if b.token:
                    try:
                        u_try = sign.check_init_data(init_data, crypto.dec(b.token), max_age=86400)
                        if u_try:
                            user_data = u_try
                            break
                    except Exception:
                        pass

    if not user_data or not user_data.get("id"):
        raise web.HTTPUnauthorized(
            text=json.dumps({"ok": False, "error": "invalid_signature", "message": "توقيع الدخول غير صالح"}),
            content_type="application/json",
        )

    uid = int(user_data["id"])
    if not (config.ADMIN_ID and uid == config.ADMIN_ID):
        raise web.HTTPForbidden(
            text=json.dumps({"ok": False, "error": "admin_only", "message": "هذه اللوحة مخصصة للأدمن فقط"}),
            content_type="application/json",
        )

    maker_bot = db.Bot(id=0, owner_id=config.ADMIN_ID, username="MakerBot", name="Maker", token="", template="maker")
    name_parts = [user_data.get("first_name", ""), user_data.get("last_name", "")]
    uname = " ".join(p for p in name_parts if p).strip() or user_data.get("username", "") or "Admin"

    return AuthContext(
        bot=maker_bot,
        user=user_data,
        role="admin",
        uid=uid,
        uname=uname,
        is_owner=True,
        is_admin=True,
        init_data_raw=init_data,
    )
