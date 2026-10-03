"""موقع المتجر والمنيو: كتالوج بأقسام وبحث، سلة، وإرسال الطلب إلى البوت."""
from __future__ import annotations

from ..templates._shop import price_num, price_unit, web_code
from . import kit
from .render import e


async def render(site):
    tpl, lite = site.tpl, site.lite()
    items = await tpl.visible(lite)
    cats = tpl.cat_names(items)
    unit = next((price_unit(x.get("price", "")) for x in items if price_unit(x.get("price", ""))), "")
    intro = await lite.kv(f"{tpl.ns}:intro") or ""
    info = await lite.kv(f"{tpl.ns}:info") or ""
    t = site.t
    is_menu = tpl.ns == "qrmenu"
    data = {
        "ns": tpl.ns, "unit": unit, "cats": cats, "emoji": tpl.emoji, "menu": is_menu,
        "items": [{"id": kit.as_int(x.get("id")), "name": str(x.get("name", "")), "price": str(x.get("price", "")), "num": price_num(x.get("price", "")),
                   "desc": str(x.get("desc", "")), "cat": str(x.get("cat") or "").strip(), "img": site.img(str(x.get("photo") or ""))} for x in items],
    }
    cart_btn = (f'<button class="icon-btn" id="cartBtn" aria-label="{e(t("السلة", "Cart"))}">🛒<span class="dot" id="cartDot" hidden>0</span></button>')
    tagline = site.cfg.get("tagline") or kit.plain(intro) or t(*tpl.w_intro)
    body = f'''
<section class="hero"><div class="avatar lg"><span>{tpl.emoji}</span><img src="{site.root}/avatar" alt="" onerror="this.remove()"></div>
<h1>{e(site.title)}</h1><p class="prose">{e(tagline)}</p></section>
<div class="search mt"><input class="input" id="q" type="search" placeholder="{e(t("ابحث عن " + tpl.w_item[0] + "…", "Search…"))}" autocomplete="off"></div>
<nav class="chips mt" id="chips" aria-label="{e(t("الأقسام", "Categories"))}"></nav>
<section class="grid" id="grid" aria-live="polite"></section>
<div class="empty" id="none" hidden><div class="big">🔍</div>{e(t("لا توجد نتائج مطابقة.", "No matching results."))}</div>
{f'<section class="card mt2"><h2>{e(t("📍 الدفع والاستلام", "📍 Payment & delivery"))}</h2><div class="prose rich mt">{kit.rich(info)}</div></section>' if info else ""}
<div class="mt2">{kit.open_bot_btn(site, t("تابع طلباتك في البوت", "Track your orders in the bot"), "btn soft block")}</div>

<div class="bar" id="bar" hidden><div class="in"><button class="btn primary block" id="barBtn"><span id="barTxt"></span></button></div></div>

<div class="scrim" id="prodSheet"><div class="sheet" role="dialog" aria-modal="true"><div class="grab"></div><div id="prodBody"></div></div></div>

<div class="scrim" id="cartSheet"><div class="sheet" role="dialog" aria-modal="true"><div class="grab"></div>
<div class="row between"><h2>{e(t("🛒 سلتك", "🛒 Your cart"))}</h2><button class="btn sm" data-close>{e(t("إغلاق", "Close"))}</button></div>
<div id="cartLines" class="mt"></div>
<div class="row between mt"><span class="muted">{e(t("الإجمالي", "Total"))}</span><b class="price" id="cartTotal" style="font-size:1.25rem"></b></div>
<form id="orderForm" class="stack mt2" novalidate>
<h3>{e(t("بيانات الطلب", "Order details"))}</h3>
<label>{e(t("الاسم", "Name"))}<input class="input" name="name" required maxlength="60" autocomplete="name"></label>
<label>{e(t("رقم الهاتف", "Phone number"))}<input class="input" name="phone" required maxlength="30" inputmode="tel" autocomplete="tel" dir="ltr"></label>
<label>{e(t("رقم الطاولة أو العنوان", "Table number or address") if is_menu else t("عنوان التوصيل", "Delivery address"))}<input class="input" name="where" required maxlength="160"></label>
<label>{e(t("ملاحظة (اختياري)", "Note (optional)"))}<textarea name="note" maxlength="300"></textarea></label>
<button class="btn primary block" type="submit" id="sendBtn">{e(t("إرسال الطلب", "Place order"))}</button>
<p class="small muted center" id="hint"></p>
</form></div></div>

<div class="scrim" id="doneSheet"><div class="sheet center" role="dialog" aria-modal="true"><div class="grab"></div><div id="doneBody" class="stack" style="padding:10px 0 6px"></div></div></div>
'''
    return await kit.shell(site, body, scripts=("shop.js",), data=data, actions=cart_btn)


async def order(site, body: dict) -> dict:
    tpl, lite = site.tpl, site.lite()
    cart = body.get("cart")
    if not isinstance(cart, dict) or not cart or len(cart) > 60:
        raise kit.ApiError("empty", site.t("السلة فارغة.", "The cart is empty."))
    cart = {str(k): v for k, v in cart.items() if str(k).isascii() and str(k).isdecimal() and type(v) is int and 0 < v <= 99}
    if not cart:
        raise kit.ApiError("empty", site.t("السلة فارغة.", "The cart is empty."))
    name, phone = kit.clean(body.get("name"), 60), kit.clean(body.get("phone"), 30)
    where, note = kit.clean(body.get("where"), 160), kit.clean(body.get("note"), 300)
    if len(name) < 2 or len(phone) < 5 or len(where) < 1:
        raise kit.ApiError("details", site.t("أكمل الاسم ورقم الهاتف والعنوان.", "Please fill in name, phone and address."))
    lines, total, unit = await tpl.lines_of(lite, cart)
    if not lines or len(lines) != len(cart):
        raise kit.ApiError("changed", site.t("بعض أصناف سلتك لم يعد متاحاً. حدّث الصفحة وراجع السلة.", "Some items in your cart are no longer available. Refresh the page and review it."), 409)
    if len(lines) > 40:
        raise kit.ApiError("too_many", site.t("الطلب كبير جداً. قسّمه إلى طلبين.", "The order is too large. Split it in two."))
    details = f"{name} · {phone}\n{where}" + (f"\n{note}" if note else "")
    if site.uid:
        kit.throttle(("order", site.bot.id, site.uid), 5, 600)
        rid, d = await tpl.place_order(lite, lines, total, unit, details, name, src="web")
        await lite.kv_set(f"{tpl.ns}:cust:{site.uid}", details[:300])
        await lite.send(site.t("✅ <b>وصل طلبك من الموقع</b>\nيراجعه البائع الآن، وسيصلك هنا إشعار بقبوله.\n\n", "✅ <b>Your website order was received</b>\nYou'll be notified here once accepted.\n\n")
                        + tpl.order_text(lite, rid, d, "new"))
        return {"placed": True, "id": rid}
    # زائر بلا هوية تيليجرام: نحفظ الطلب مؤقتاً ويؤكده من البوت ليعرف البائع من يخاطب
    kit.throttle(("weborder", site.bot.id, kit.client_ip(site.req)), 30, 600)
    if await lite.rec_count(f"{tpl.ns}:web", status="wait") >= 300:      # طلبات معلّقة كثيرة بلا تأكيد: نوقف القبول مؤقتاً
        raise kit.ApiError("busy", site.t("الطلبات كثيرة الآن. اطلب من داخل البوت مباشرة.", "Too many pending orders right now. Please order inside the bot."), 429)
    rid = await lite.rec_add(f"{tpl.ns}:web", {"cart": cart, "note": details, "name": name}, status="wait", user_id=0)
    return {"placed": False, "link": f"{site.tg_link}?start={web_code(site.bot.id, rid)}"}


API = {"order": order}
