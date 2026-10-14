"""واجهة موحّدة ومرتبة لكل قوالب التجارة (الرقمي، التفاعل، الأرقام، النجوم، والمدمجة):
- الرئيسية للزبون: المتجر المصغّر أولاً، ثم الأقسام، ثم المحفظة والطلبات وحسابي — بلا زحمة.
- الدعم يظهر فقط إن ضبطه البائع، والأسئلة الشائعة فقط إن فعّلها، والمساعدة/الشروط في أسفل المتجر المصغّر لا في الأزرار.
- غرفة تحكم مختصرة للبائع: أرقام اليوم + اختصارات إلى لوحة التحكم الكاملة في التطبيق المصغّر + أدوات متقدمة.
"""
from __future__ import annotations

import datetime as dt
from urllib.parse import urlencode

from sqlalchemy import func, select

from .. import config, db, ui
from ..ctx import Ctx
from ..modules import ledger
from ..ui import B, esc, kb

COMMERCE = {"digital", "smm", "sms", "tgstars", "smmsms", "megastore"}
BROWSE = {
    "digital": [("🎮 الألعاب", "🎮 Games", "t:cat:games"), ("🎬 الاشتراكات", "🎬 Subscriptions", "t:cat:apps"), ("🎟 البطاقات", "🎟 Gift cards", "t:cat:cards")],
    "smm": [("🚀 تصفّح الخدمات", "🚀 Browse services", "t:cats")],
    "sms": [("📱 اختر الدولة", "📱 Pick a country", "t:countries")],
    "tgstars": [("⭐ النجوم", "⭐ Stars", "t:cat:stars"), ("💎 بريميوم", "💎 Premium", "t:cat:premium"), ("🎁 الهدايا", "🎁 Gifts", "t:cat:gifts")],
}
INTRO = {
    "digital": ("اشحن ألعابك واشترك في تطبيقاتك المفضلة بسرعة وأمان.", "Top up your games and subscribe to your favorite apps, fast and safe."),
    "smm": ("متابعين وتفاعل لكل المنصات بتنفيذ سريع.", "Followers and engagement for every platform, delivered fast."),
    "sms": ("أرقام تفعيل فورية، ويُسترجع المبلغ إن لم يصل الكود.", "Instant activation numbers, refunded if no code arrives."),
    "tgstars": ("نجوم وبريميوم وهدايا تيليجرام لحسابك أو لأصدقائك.", "Telegram Stars, Premium and gifts for you or your friends."),
}


def app_url(c: Ctx, **params) -> str:
    if not config.PUBLIC_URL or not c.bot.username:
        return ""
    q = ("?" + urlencode(params)) if params else ""
    return f"{config.PUBLIC_URL.rstrip('/')}/app/{c.bot.username}{q}"


async def store_cfg(c: Ctx) -> dict:
    from ..web.store_api import store_cfg as _cfg
    return await _cfg(c.bot_id)


def _grid(btns: list, n: int = 2) -> list:
    return [btns[i:i + n] for i in range(0, len(btns), n)]


# ───────────────────────── الزبون ─────────────────────────
async def customer_home(c: Ctx, key: str, browse: list | None = None, intro_key: str = "", default_intro: str = "") -> None:
    t = c.t
    cfg = await store_cfg(c)
    bal = await ledger.get_user_balance_display(c.bot_id, c.uid)
    intro = await c.kv(intro_key or f"{key}:intro") or cfg.get("desc") or default_intro or t(*INTRO.get(key, ("", "")))
    ann = cfg.get("announcement") or ""
    url = app_url(c)
    browse = browse if browse is not None else [B(t(a, e), d) for a, e, d in BROWSE.get(key, [])]
    sup = cfg.get("support") or {}
    has_sup = any(sup.get(k) for k in ("username", "whatsapp", "email", "channel")) or bool(sup.get("links"))
    rows = [
        [B(t("🛍 افتح المتجر", "🛍 Open the store"), web_app=url, style="primary")] if url else None,
        *_grid(browse, 2),
        [B(t("💳 شحن الرصيد", "💳 Top up"), "t:wallet", style="success"), B(t("📦 طلباتي", "📦 My orders"), "t:orders")],
        [B(t("👤 حسابي", "👤 My account"), "t:acct")] + ([B(t("🎧 الدعم", "🎧 Support"), "t:support")] if has_sup else []),
        [B(t("❓ الأسئلة الشائعة", "❓ FAQ"), "t:faq")] if (cfg.get("faq_enabled") and cfg.get("faq")) else None,
        c.tail(),
    ]
    text = (ui.head(esc(cfg.get("name") or c.brand)) + (f"📣 {esc(ann)}\n\n" if ann else "") + f"{esc(intro)}\n\n"
            + f"💰 <b>{t('رصيدك', 'Balance')}:</b> <code>{bal}</code>")
    await c.edit(text, kb(rows))


async def account_screen(c: Ctx) -> None:
    t = c.t
    bal = await ledger.get_user_balance_display(c.bot_id, c.uid)
    async with db.Session() as s:
        n = (await s.execute(select(func.count(db.ServiceOrder.id)).where(db.ServiceOrder.bot_id == c.bot_id, db.ServiceOrder.user_id == c.uid))).scalar() or 0
    text = (ui.head(t("👤 حسابي", "👤 My account")) + f"🆔 <code>{c.uid}</code>\n💰 {t('الرصيد', 'Balance')}: <code>{bal}</code>\n📦 {t('الطلبات', 'Orders')}: <b>{n}</b>")
    await c.edit(text, kb([
        [B(t("🎁 كود خصم", "🎁 Promo code"), "t:promo"), B(t("👥 اربح رصيداً", "👥 Earn credit"), "t:ref")],
        [B(t("🌐 اللغة", "🌐 Language"), "u:lang")],
        [B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")],
    ]))


async def support_screen(c: Ctx) -> bool:
    """يعرض وسائل الدعم التي ضبطها البائع. يعيد False إن لم يضبط شيئاً (فيستخدم البوت التذاكر)."""
    t = c.t
    sup = (await store_cfg(c)).get("support") or {}
    rows = []
    if sup.get("username"):
        rows.append([B(f"💬 @{sup['username']}", url=f"https://t.me/{sup['username']}")])
    if sup.get("channel"):
        rows.append([B(f"📢 @{sup['channel']}", url=f"https://t.me/{sup['channel']}")])
    if sup.get("whatsapp"):
        num = "".join(ch for ch in sup["whatsapp"] if ch.isdigit())
        if num:
            rows.append([B("🟢 WhatsApp", url=f"https://wa.me/{num}")])
    for lk in (sup.get("links") or [])[:6]:
        if lk.get("url", "").startswith("https://"):
            rows.append([B(f"🔗 {lk.get('label') or lk['url']}"[:40], url=lk["url"])])
    if not rows and not sup.get("email"):
        return False
    text = ui.head(t("🎧 الدعم الفني", "🎧 Support")) + t("تواصل معنا عبر:", "Reach us via:") + (f"\n✉️ <code>{esc(sup['email'])}</code>" if sup.get("email") else "")
    rows.append([B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")])
    await c.edit(text, kb(rows))
    return True


async def faq_screen(c: Ctx, idx: int | None = None) -> bool:
    t = c.t
    cfg = await store_cfg(c)
    faq = cfg.get("faq") or []
    if not (cfg.get("faq_enabled") and faq):
        return False
    if idx is not None and 0 <= idx < len(faq):
        f = faq[idx]
        await c.edit(f"❓ <b>{esc(f['q'])}</b>\n{ui.LINE}\n{esc(f['a'])}", kb([[B(t("⬅️ الأسئلة", "⬅️ FAQ"), "t:faq")], [B(t("🏠 الرئيسية", "🏠 Home"), "t:home")]]))
        return True
    rows = [[B(f"❓ {f['q']}"[:60], f"t:faqv:{i}")] for i, f in enumerate(faq[:20])]
    rows.append([B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")])
    await c.edit(ui.head(t("❓ الأسئلة الشائعة", "❓ FAQ")), kb(rows))
    return True


# ───────────────────────── البائع ─────────────────────────
async def owner_panel(c: Ctx, rcpt_cb: str = "t:adm:rcpts") -> tuple[str, list]:
    """غرفة تحكم مختصرة: أرقام اليوم، ما ينتظر البائع، ورصيده في الصانع + اختصارات منظمة."""
    t = c.t
    since = db.now() - dt.timedelta(days=1)
    async with db.Session() as s:
        n, sales, cost = (await s.execute(select(func.count(db.ServiceOrder.id), func.coalesce(func.sum(db.ServiceOrder.price_user_usd), 0),
                                                 func.coalesce(func.sum(db.ServiceOrder.cost_platform_usd), 0)).where(
            db.ServiceOrder.bot_id == c.bot_id, db.ServiceOrder.created >= since, db.ServiceOrder.status.notin_(("refunded", "canceled", "failed"))))).one()
        pend_rc = (await s.execute(select(func.count(db.PaymentReceipt.id)).where(db.PaymentReceipt.bot_id == c.bot_id, db.PaymentReceipt.status == "pending"))).scalar() or 0
        pend_o = (await s.execute(select(func.count(db.ServiceOrder.id)).where(db.ServiceOrder.bot_id == c.bot_id, db.ServiceOrder.status.in_(("queued", "pending"))))).scalar() or 0
    mbal = await ledger.get_seller_balance_usd(c.owner_id)
    info = (f"🛒 <b>{t('اليوم', 'Today')}</b>: {int(n)} {t('طلب', 'orders')} · ${float(sales):.2f} · "
            f"{t('ربحك', 'profit')} <b>${float(sales) - float(cost):.2f}</b>\n"
            f"💼 {t('رصيدك في الصانع', 'Maker balance')}: <b>${mbal:.2f}</b>" + (" ⚠️" if mbal < 5 else "")
            + (f"\n🧾 {t('إيصالات بانتظارك', 'Pending receipts')}: <b>{pend_rc}</b>" if pend_rc else "")
            + (f"\n⏳ {t('طلبات قيد الانتظار', 'Pending orders')}: <b>{pend_o}</b>" if pend_o else ""))
    if mbal < 5:
        info += "\n<i>" + t("اشحن رصيدك من بوت الصانع ← «💰 رصيدي» حتى لا يتوقف البيع.", "Top up from the maker bot → “💰 Balance” so sales don't stop.") + "</i>"

    if not app_url(c):
        # بلا رابط عام لا يعمل التطبيق المصغّر: نعرض أدوات القالب المفصّلة مباشرة
        legacy = getattr(c.tpl, "owner_legacy", None)
        if legacy is not None:
            _i, lrows = await legacy(c)
            return info, list(lrows)

    def dash(sec: str, ar: str, en: str, **kw):
        u = app_url(c, tab="dash", sec=sec)
        return B(t(ar, en), web_app=u, **kw) if u else None

    rows = [
        [dash("ov", "📊 لوحة التحكم الكاملة", "📊 Full dashboard", style="primary")],
        [B(t(f"🧾 الإيصالات ({pend_rc})", f"🧾 Receipts ({pend_rc})"), rcpt_cb, style="success" if pend_rc else None), dash("orders", "📦 الطلبات", "📦 Orders")],
        [dash("pricing", "🏷 الأسعار والهوامش", "🏷 Pricing"), dash("pay", "💳 طرق الدفع", "💳 Payments")],
        [dash("store", "🎨 المتجر والدعم", "🎨 Store & support"), dash("mkt", "📣 التسويق", "📣 Marketing")],
        [B(t("⚙️ أدوات متقدمة", "⚙️ Advanced tools"), "t:adv")],
    ]
    rows = [[b for b in r if b is not None] for r in rows]
    return info, [r for r in rows if r]


async def advanced(c: Ctx) -> None:
    """الأدوات القديمة المفصّلة للقالب (مخزون الأكواد، العروض المؤقتة، القنوات…) في شاشة مستقلة."""
    t = c.t
    legacy = getattr(c.tpl, "owner_legacy", None)
    if legacy is None:
        return
    info, rows = await legacy(c)
    rows = list(rows) + [[B(t("🎛 غرفة التحكم", "🎛 Control room"), "o:home")]]
    await c.edit(ui.head(t("⚙️ أدوات متقدمة", "⚙️ Advanced tools")) + (info or ""), kb(rows))
