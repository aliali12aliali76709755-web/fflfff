"""أدوات مشتركة بين مواقع البوتات: الهيكل العام للصفحة، التذييل، تنقية النص، وأخطاء الواجهات."""
from __future__ import annotations

import ipaddress
import re
import time

from .. import plat as platform
from . import render
from .render import e


class ApiError(Exception):
    def __init__(self, code: str, message: str = "", status: int = 400):
        super().__init__(code)
        self.code, self.message, self.status = code, message, status


_TAG = re.compile(r"<(/?)([a-zA-Z-]+)([^>]*)>")
_KEEP = {"b", "strong", "i", "em", "u", "s", "code", "pre", "blockquote"}
_HREF = re.compile(r'href="((?:https?://|tg://)[^"<>\s]+)"')


def rich(html: str) -> str:
    """يبقي وسوم التنسيق التي يحفظها تيليجرام (غامق، مائل، روابط...) بلا خصائص، ويحذف أي وسم آخر.

    ما بين الوسوم يُهرَّب منه كل < و > متبقٍّ، فلا يمرّ وسم غير مكتمل مهما كان مصدر النص.
    """
    def tag_out(m: re.Match) -> str:
        close, tag, attrs = m.group(1), m.group(2).lower(), m.group(3)
        if tag in _KEEP:
            return f"<{close}{tag}>"
        if tag == "a":
            if close:
                return "</a>"
            h = _HREF.search(attrs)
            return f'<a href="{h.group(1)}" target="_blank" rel="noopener nofollow">' if h else "<a>"
        return ""

    out, pos = [], 0
    for m in _TAG.finditer(html or ""):
        out.append((html[pos:m.start()]).replace("<", "&lt;").replace(">", "&gt;"))
        out.append(tag_out(m))
        pos = m.end()
    out.append((html or "")[pos:].replace("<", "&lt;").replace(">", "&gt;"))
    return "".join(out)


def plain(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html or "").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").replace("&quot;", '"').strip()


async def footer(site) -> str:
    from ..child import maker_app
    p = await platform.get(site.bot.factory_id)
    maker = maker_app({"manager": site.mgr, "factory_id": site.bot.factory_id})
    brand = render.brand(site.lang)
    if maker is not None and platform.promo_for(p, site.adm) is not None and site.tpl.key != "maker":
        link = f"https://t.me/{maker.bot.username}?start=ref_{site.bot.owner_id}"
        return (f'<footer class="footer">{e(site.t("تريد بوتاً وموقعاً مثل هذا؟", "Want a bot and a site like this?"))} '
                f'<a href="{e(link)}" target="_blank" rel="noopener">{e(site.t("اصنعه مجاناً", "Build yours for free"))}</a>'
                f'<div class="small" style="margin-top:6px">{e(brand)}</div></footer>')
    return f'<footer class="footer">{e(brand)}</footer>'


def header(site, actions: str = "") -> str:
    v = '<span class="verified" title="verified">✔</span>' if site.adm.get("verified") else ""
    return (f'<header class="top"><div class="in"><div class="avatar"><span>{site.tpl.emoji}</span>'
            f'<img src="{site.root}/avatar" alt="" loading="lazy" onerror="this.remove()"></div>'
            f'<div class="grow"><div class="brand">{e(site.title)}{v}</div><div class="small muted" dir="ltr" style="text-align:start">@{e(site.bot.username)}</div></div>'
            f"{actions}</div></header>")


async def shell(site, body: str, *, scripts: tuple = (), data: dict | None = None, actions: str = "", quran: bool = False, desc: str = ""):
    """صفحة موقع بوت كاملة: رأس + محتوى + تذييل."""
    html = header(site, actions) + f'<main class="wrap">{body}</main>' + await footer(site)
    return render.page(site.title, html, lang=site.lang, accent=site.accent, site=site.js(**(data or {})), scripts=scripts, quran=quran,
                       desc=desc or site.cfg.get("tagline") or site.tpl.pitch(site.lang))


def open_bot_btn(site, label: str = "", cls: str = "btn primary block") -> str:
    """في المتصفح: زر يفتح البوت. داخل تيليجرام (العضو في البوت أصلاً): زر يعيده إلى المحادثة."""
    label = label or site.t("افتح البوت في تيليجرام", "Open the bot in Telegram")
    return (f'<a class="{cls} only-web" href="{e(site.tg_link)}" target="_blank" rel="noopener">{e(label)}</a>'
            f'<button class="btn soft block only-tg" data-tgclose>{e(site.t("العودة إلى المحادثة", "Back to the chat"))}</button>')


# ── حد بسيط للطلبات المتكررة ──
_hits: dict[tuple, list[float]] = {}


def throttle(key: tuple, limit: int, window: int) -> None:
    now = time.time()
    hits = [t for t in _hits.get(key, []) if now - t < window]
    if len(hits) >= limit:
        raise ApiError("slow_down", "طلبات كثيرة. حاول بعد قليل.", 429)
    hits.append(now)
    _hits[key] = hits
    if len(_hits) > 5000:
        for k in [k for k, v in _hits.items() if not v or now - v[-1] > 3600]:
            _hits.pop(k, None)
        if len(_hits) > 20000:
            _hits.clear()


def client_ip(req) -> str:
    """عنوان الزائر. ترويسات الوسيط تُصدَّق فقط حين يصل الطلب من وسيط محلي (nginx، نفق Cloudflare...)."""
    remote = req.remote or "?"
    try:
        local = ipaddress.ip_address(remote).is_private or ipaddress.ip_address(remote).is_loopback
    except ValueError:
        local = False
    if local:
        fwd = req.headers.get("CF-Connecting-IP") or req.headers.get("X-Real-IP") or req.headers.get("X-Forwarded-For", "").split(",")[-1]
        if fwd.strip():
            return fwd.strip()[:64]
    return remote[:64]


def as_int(value, default: int = 0) -> int:
    """يحوّل قيمة مخزّنة إلى عدد صحيح مهما كان نوعها (القيم قد تأتي من ملف نسخة احتياطية مستورد)."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def clean(value, limit: int) -> str:
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value if value is not None else "")).strip()[:limit]
