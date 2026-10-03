"""توزيع الصفحات على مواقع القوالب، مع صفحة المنصة والصفحة العامة لأي بوت."""
from __future__ import annotations

from sqlalchemy import func, select

from .. import config, db, templates
from . import kit, render, s_booking, s_english, s_links, s_quran, s_shop
from .kit import ApiError
from .render import e

MODULES = {"store": s_shop, "qrmenu": s_shop, "quran": s_quran, "english": s_english, "booking": s_booking, "buttons": s_links}
__all__ = ["ApiError", "render_site", "api", "landing", "MODULES"]


async def render_site(site):
    mod = MODULES.get(site.tpl.key)
    return await (mod.render(site) if mod is not None else generic(site))


async def api(site, name: str, body: dict) -> dict:
    mod = MODULES.get(site.tpl.key)
    fn = getattr(mod, "API", {}).get(name) if mod is not None else None
    if fn is None:
        raise ApiError("not_found", status=404)
    return await fn(site, body)


async def generic(site):
    """صفحة تعريفية لأي بوت لا يملك قالبه موقعاً خاصاً."""
    tpl = site.tpl
    body = f'''
<section class="hero" style="padding-top:44px"><div class="avatar lg"><span>{tpl.emoji}</span><img src="{site.root}/avatar" alt="" onerror="this.remove()"></div>
<h1>{e(site.title)}</h1><p class="prose">{e(site.cfg.get("tagline") or tpl.pitch(site.lang))}</p>
<span class="badge">{tpl.emoji} {e(tpl.name(site.lang))}</span></section>
<div class="mt2">{kit.open_bot_btn(site)}</div>
<p class="center muted small mt only-web">{e(site.t("يفتح البوت في تطبيق تيليجرام.", "Opens the bot in the Telegram app."))}</p>
'''
    return await kit.shell(site, body)


async def landing(req, mgr):
    lang = "en" if req.query.get("lang") == "en" else "ar"

    def t(ar: str, en: str) -> str:
        return ar if lang == "ar" else en

    async with db.Session() as s:
        bots = int((await s.execute(select(func.count()).select_from(db.Bot).where(db.Bot.status == "active"))).scalar() or 0)
        members = int((await s.execute(select(func.count()).select_from(db.BUser))).scalar() or 0)
    tpls = templates.load()
    maker = f"https://t.me/{mgr.maker.bot.username}" if mgr.maker is not None else "#"
    brand = render.brand(lang)
    cats = ""
    for key, emoji, ar, en in templates.CATEGORIES:
        names = [x for x in tpls.values() if key in x.cats]
        if not names:
            continue
        chips = "".join(f'<span class="chip">{x.emoji} {e(x.name(lang))}{" 🌐" if x.site else ""}</span>' for x in names)
        cats += f'<section class="card"><h3>{emoji} {e(t(ar, en))}</h3><div class="pill-nav mt" style="justify-content:flex-start">{chips}</div></section>'
    steps = [(t("اختر نوع البوت", "Pick a bot type"), t("متجر، منيو، حجز مواعيد، قرآن، تعليم، تحميل… عشرات الأنواع الجاهزة.", "Store, menu, bookings, Quran, learning, downloads… dozens of ready types.")),
             (t("اربطه بتوكن من BotFather", "Link a token from BotFather"), t("يعمل بوتك خلال ثوانٍ، دون أي برمجة أو سيرفر.", "Your bot runs within seconds. No code, no server.")),
             (t("جهّزه وانشر رابطه", "Set it up and share it"), t("غرفة تحكم كاملة داخل البوت، وموقع ويب جاهز للأنواع التي تحمل علامة 🌐.", "A full control room inside the bot, plus a ready website for types marked 🌐."))]
    how = "".join(f'<div class="step"><div class="n">{i}</div><div><h3>{e(a)}</h3><p class="muted small">{e(b)}</p></div></div>' for i, (a, b) in enumerate(steps, 1))
    body = f'''
<header class="top"><div class="in wide"><div class="avatar"><span>⚡</span></div><div class="grow brand">{e(brand)}</div>
<a class="btn sm primary" href="{e(maker)}" target="_blank" rel="noopener">{e(t("ابدأ الآن", "Start now"))}</a></div></header>
<main class="wrap wide">
<section class="hero" style="padding:54px 0 20px"><span class="badge">{e(t("مجاني · بدون برمجة", "Free · No code"))}</span>
<h1 style="font-size:clamp(1.8rem,5vw,2.7rem);max-width:18ch">{e(t("ابنِ بوت تيليجرام يعمل فعلاً، ومعه موقعه", "Build a Telegram bot that really works, with its own website"))}</h1>
<p>{e(t("اختر النوع، اربط التوكن، وابدأ. كل بوت له غرفة تحكم وإحصائيات، وكثير منها له موقع ويب مرتبط به مباشرة.",
        "Pick a type, link the token and go. Every bot gets a control room and statistics, and many get a linked website."))}</p>
<div class="pill-nav mt"><a class="btn primary" href="{e(maker)}" target="_blank" rel="noopener">{e(t("اصنع بوتك مجاناً", "Build your bot for free"))}</a>
<a class="btn" href="#types">{e(t("شاهد الأنواع", "See the types"))}</a></div></section>
<section class="kpis mt2" style="grid-template-columns:repeat(3,minmax(0,1fr))">
<div class="kpi center"><div class="v center">{len(tpls)}</div><div class="l">{e(t("نوعاً جاهزاً", "ready types"))}</div></div>
<div class="kpi center"><div class="v center">{bots:,}</div><div class="l">{e(t("بوتاً يعمل الآن", "bots running"))}</div></div>
<div class="kpi center"><div class="v center">{members:,}</div><div class="l">{e(t("عضواً في البوتات", "members"))}</div></div></section>
<div class="sec-title"><h2>{e(t("كيف يعمل؟", "How it works"))}</h2></div><section class="card stack">{how}</section>
<div class="sec-title" id="types"><h2>{e(t("الأنواع المتاحة", "Available types"))}</h2><span class="small muted">🌐 = {e(t("له موقع ويب", "has a website"))}</span></div>
<section class="stack">{cats}</section>
<div class="mt2 center"><a class="btn primary" href="{e(maker)}" target="_blank" rel="noopener">{e(t("اصنع بوتك الآن", "Build your bot now"))}</a></div>
</main><footer class="footer">{e(brand)}{' · <a href="' + e(config.PRIVACY_URL) + '">' + e(t("الخصوصية", "Privacy")) + "</a>" if config.PRIVACY_URL else ""}</footer>'''
    return render.page(brand, body, lang=lang, tg=False, desc=t("اصنع بوت تيليجرام وموقعه مجاناً وبدون برمجة.", "Build a Telegram bot and its website for free, no code."))
