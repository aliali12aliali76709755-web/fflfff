"""خادم الويب: صفحة المنصة، موقع لكل بوت، واجهات JSON للمواقع، وكيل الصور، ولوحات الويب."""
from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from aiohttp import web
from sqlalchemy import func, select
from telegram.error import TelegramError

from .. import child, config, crypto, db, templates
from .. import plat as platform
from ..ctx import Lite
from ..i18n import norm
from . import dash, render, sign, sites
from . import site_url
from .render import e

log = logging.getLogger("forge.web")
STATIC = Path(__file__).parent / "static"
CACHE = config.DATA_DIR / "webcache"
SITE_DEF = {"on": True, "color": "", "tagline": "", "menu": True}
COLORS = {"store": "#7c3aed", "qrmenu": "#c2410c", "quran": "#0f766e", "english": "#2563eb", "booking": "#0e7490", "buttons": "#334155", "vip": "#b45309"}
PALETTE = [("#2563eb", "أزرق"), ("#7c3aed", "بنفسجي"), ("#0f766e", "أخضر"), ("#c2410c", "برتقالي"), ("#be123c", "وردي"), ("#b45309", "ذهبي"), ("#334155", "رمادي")]
MGR = web.AppKey("mgr", object)


@dataclass
class Site:
    """كل ما تحتاجه صفحة أو واجهة تخص بوتاً واحداً."""
    req: web.Request
    bot: db.Bot
    tpl: object
    core: dict
    adm: dict
    app: object                      # تطبيق البوت العامل أو None
    lang: str = "ar"
    uid: int = 0
    uname: str = ""
    cfg: dict = field(default_factory=dict)
    mgr: object = None

    def t(self, ar: str, en: str) -> str:
        return ar if self.lang == "ar" else en

    @property
    def root(self) -> str:
        return f"/{self.bot.username}"

    @property
    def accent(self) -> str:
        color = str(self.cfg.get("color") or "")
        return color if re.fullmatch(r"#[0-9a-fA-F]{6}", color) else COLORS.get(self.tpl.key, "#2563eb")

    @property
    def title(self) -> str:
        return self.bot.name or self.bot.username

    @property
    def tg_link(self) -> str:
        return f"https://t.me/{self.bot.username}"

    def img(self, file_id: str) -> str:
        return f"/img/{self.bot.id}/{sign.img(self.bot.id, file_id)}/{file_id}" if file_id else ""

    def lite(self) -> Lite:
        return Lite(self.bot.id, self.bot.owner_id, uid=self.uid, lang=self.lang, name=self.uname,
                    bot=self.app.bot if self.app is not None else None, core=self.core)

    def js(self, **data) -> dict:
        return {"bot": self.bot.username, "root": self.root, "lang": self.lang, "tg": self.tg_link, "user": bool(self.uid), **data}


def site_cfg(core: dict) -> dict:
    return {**SITE_DEF, **(core.get("site") or {})}


def _lang(req: web.Request, core: dict) -> str:
    forced = core.get("lang") or "auto"
    if forced != "auto":
        return "ar" if norm(forced) == "ar" else "en"
    q = req.query.get("lang", "")
    if q in ("ar", "en"):
        return q
    accept = req.headers.get("Accept-Language", "").lower()
    if not accept or "ar" in [x.split(";")[0].strip()[:2] for x in accept.split(",")]:
        return "ar"
    return "en"


async def _bot(username: str) -> db.Bot | None:
    async with db.Session() as s:
        return (await s.execute(select(db.Bot).where(func.lower(db.Bot.username) == username.lower()))).scalars().first()


def _identity(req: web.Request, bot: db.Bot) -> tuple[int, str]:
    key = req.headers.get("X-User-Key") or req.query.get("k") or ""
    uid = sign.check_user(bot.id, key)
    if uid:
        return uid, ""
    init = req.headers.get("X-Init-Data") or ""
    if init:
        try:
            user = sign.check_init_data(init, crypto.dec(bot.token))
        except Exception:  # noqa: BLE001
            user = None
        if user:
            return int(user["id"]), " ".join(x for x in (user.get("first_name"), user.get("last_name")) if x)
    return 0, ""


async def load_site(req: web.Request, *, page: bool) -> Site | web.Response:
    """يجهّز سياق الموقع، أو يعيد صفحة حالة (غير موجود، مغلق، صيانة...)."""
    mgr = req.app[MGR]
    bot = await _bot(req.match_info["username"])

    def fail(icon, ar, ar_text, en, en_text, status, lang="ar"):
        if not page:
            return web.json_response({"ok": False, "error": "unavailable"}, status=status)
        return render.status_page(icon, ar if lang == "ar" else en, ar_text if lang == "ar" else en_text, lang=lang, status=status)

    if bot is None:
        return fail("🔎", "الصفحة غير موجودة", "لا يوجد بوت بهذا الاسم على المنصة.", "Page not found", "There is no bot with that name here.", 404)
    app = mgr.apps.get(bot.id)
    core = app.bot_data["core"] if app is not None else await child.load_core(bot.id)
    adm = await platform.adm(bot.id)
    lang = _lang(req, core)
    cfg = site_cfg(core)
    bot_data = {"adm": adm, "core": core, "factory_id": bot.factory_id}
    lk = child.current_lock(bot_data)
    if lk is not None and lk["mode"] in ("closed", "temp"):
        return fail("🔒", "هذا البوت مغلق", "أغلقته إدارة المنصة.", "This bot is closed", "It was closed by the platform.", 403, lang)
    if lk is not None:
        return fail("🛠", "في صيانة", "نعود قريباً، شكراً لصبرك.", "Under maintenance", "We'll be back soon.", 503, lang)
    if bot.status != "active" or app is None:
        return fail("⏸", "البوت متوقف حالياً", "أوقفه صاحبه مؤقتاً. عد لاحقاً.", "This bot is paused", "Its owner paused it. Come back later.", 503, lang)
    if not cfg["on"]:
        return fail("🌙", "الموقع غير مفعّل", "صاحب هذا البوت لم يفعّل موقعه.", "Site is off", "The owner has not enabled this site.", 404, lang)
    uid, uname = _identity(req, bot)
    if uid:
        async with db.Session() as s:
            row = await s.get(db.BUser, (bot.id, uid))
        if row is not None and row.banned:
            uid = 0
        elif row is not None and not uname:
            uname = row.name
    return Site(req, bot, templates.get(bot.template), core, adm, app, lang, uid, uname, cfg, mgr)


# ───────────────────────── الصفحات ─────────────────────────
async def landing(req: web.Request) -> web.Response:
    return await sites.landing(req, req.app[MGR])


async def bot_page(req: web.Request) -> web.Response:
    site = await load_site(req, page=True)
    if isinstance(site, web.Response):
        return site
    await db.bump(site.bot.id, web=1)
    return await sites.render_site(site)


async def bot_api(req: web.Request) -> web.Response:
    site = await load_site(req, page=False)
    if isinstance(site, web.Response):
        return site
    body = {}
    if req.method == "POST":
        if req.content_length and req.content_length > 64 * 1024:
            return web.json_response({"ok": False, "error": "too_large"}, status=413)
        try:
            body = await req.json()
        except Exception:  # noqa: BLE001
            return web.json_response({"ok": False, "error": "bad_json"}, status=400)
        if not isinstance(body, dict):
            return web.json_response({"ok": False, "error": "bad_json"}, status=400)
    try:
        out = await sites.api(site, req.match_info["name"], body)
    except sites.ApiError as err:
        return web.json_response({"ok": False, "error": err.code, "message": err.message}, status=err.status)
    except Exception:  # noqa: BLE001
        log.exception("site api %s/%s failed", site.bot.username, req.match_info["name"])
        return web.json_response({"ok": False, "error": "server"}, status=500)
    return web.json_response({"ok": True, **(out or {})}, headers={"Cache-Control": "no-store"})


def _cached(name: str, max_age: int) -> Path | None:
    f = CACHE / name
    return f if f.exists() and time.time() - f.stat().st_mtime < max_age else None


async def image(req: web.Request) -> web.StreamResponse:
    """صور المنتجات: تُجلب من تيليجرام مرة واحدة ثم تُخدَّم من القرص. الرابط موقّع فلا يُطلب به ملف آخر."""
    bot_id, s, fid = req.match_info["bot_id"], req.match_info["sig"], req.match_info["fid"]
    if not (bot_id.isascii() and bot_id.isdecimal()) or not sign.same(s, sign.img(int(bot_id), fid)):
        raise web.HTTPNotFound()
    name = hashlib.sha1(f"{bot_id}:{fid}".encode()).hexdigest() + ".jpg"
    f = _cached(name, 30 * 86400)
    if f is None:
        app = req.app[MGR].apps.get(int(bot_id))
        if app is None:
            raise web.HTTPNotFound()
        try:
            tf = await app.bot.get_file(fid)
            if (tf.file_size or 0) > 8 * 1024 * 1024:
                raise web.HTTPNotFound()
            CACHE.mkdir(exist_ok=True)
            await tf.download_to_drive(CACHE / name)
        except TelegramError:
            raise web.HTTPNotFound() from None
        f = CACHE / name
    return web.FileResponse(f, headers={"Cache-Control": "public, max-age=2592000, immutable", "Content-Type": "image/jpeg"})


async def avatar(req: web.Request) -> web.StreamResponse:
    bot = await _bot(req.match_info["username"])
    if bot is None:
        raise web.HTTPNotFound()
    name = f"avatar_{bot.id}.jpg"
    f = _cached(name, 86400)
    miss = _cached(name + ".none", 3600)
    if f is None and miss is None:
        app = req.app[MGR].apps.get(bot.id)
        try:
            photos = await app.bot.get_user_profile_photos(bot.id, limit=1) if app is not None else None
            CACHE.mkdir(exist_ok=True)
            if photos is not None and photos.photos:
                tf = await app.bot.get_file(photos.photos[0][min(1, len(photos.photos[0]) - 1)].file_id)
                await tf.download_to_drive(CACHE / name)
                f = CACHE / name
            else:
                (CACHE / (name + ".none")).write_text("")
        except Exception:  # noqa: BLE001
            f = None
            try:
                CACHE.mkdir(exist_ok=True)
                (CACHE / (name + ".none")).write_text("")
            except OSError:
                pass
    if f is None:
        raise web.HTTPNotFound()
    return web.FileResponse(f, headers={"Cache-Control": "public, max-age=3600", "Content-Type": "image/jpeg"})


async def health(_req: web.Request) -> web.Response:
    return web.json_response({"ok": True})


@web.middleware
async def errors_mw(req: web.Request, handler):
    try:
        return await handler(req)
    except web.HTTPNotFound:
        if req.path.startswith(("/img/", "/static/")) or req.path.endswith("/avatar") or "/api/" in req.path:
            raise
        return render.status_page("🔎", "الصفحة غير موجودة", "تأكد من الرابط وحاول مرة أخرى.", status=404)
    except web.HTTPException:
        raise
    except Exception:  # noqa: BLE001
        log.exception("web error on %s", req.path)
        return render.status_page("⚠️", "حدث خطأ غير متوقع", "حاول مرة أخرى بعد قليل.", status=500)


def build(mgr) -> web.Application:
    app = web.Application(middlewares=[errors_mw], client_max_size=256 * 1024)
    app[MGR] = mgr
    u = r"{username:[A-Za-z][A-Za-z0-9_]{3,39}}"
    app.router.add_get("/", landing)
    app.router.add_get("/healthz", health)
    app.router.add_static("/static/", STATIC, append_version=False)
    app.router.add_get("/img/{bot_id}/{sig}/{fid}", image)
    dash.routes(app)
    app.router.add_get(f"/{u}", bot_page)
    app.router.add_get(f"/{u}/", bot_page)
    app.router.add_get(f"/{u}/avatar", avatar)
    app.router.add_route("*", f"/{u}/api/{{name:[a-z_]+}}", bot_api)
    return app


async def start(mgr):
    """يشغّل الخادم على WEB_PORT. فشل التشغيل (منفذ مشغول مثلاً) لا يوقف البوتات."""
    if config.WEB_PORT <= 0:
        return None
    try:
        runner = web.AppRunner(build(mgr), access_log=None)
        await runner.setup()
        await web.TCPSite(runner, config.WEB_HOST, config.WEB_PORT).start()
    except OSError as err:
        log.warning("web server not started on port %s: %s", config.WEB_PORT, err)
        return None
    log.info("web server on port %s (public url: %s)", config.WEB_PORT, config.PUBLIC_URL or "not set")
    if config.PUBLIC_URL and urlparse(config.PUBLIC_URL).path not in ("", "/"):
        log.warning("PUBLIC_URL must not contain a path (%s): pages use root-relative links", config.PUBLIC_URL)
    return runner


async def stop(runner) -> None:
    if runner is not None:
        try:
            await runner.cleanup()
        except Exception:  # noqa: BLE001
            pass


__all__ = ["start", "stop", "build", "Site", "site_cfg", "site_url", "PALETTE", "COLORS", "e"]
