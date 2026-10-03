"""أساس مشترك لقالبي «متجر مصغر» و«منيو QR»: أقسام، منتجات، سلة، طلبات، وموقع ويب مرتبط."""
from __future__ import annotations

import io
import re

from telegram.error import TelegramError

from .. import ui
from ..ctx import Ctx
from ..ui import B, esc, kb
from . import Items, Tpl

STATUS = {"new": ("🕒 قيد المراجعة", "🕒 Pending"), "ok": ("✅ مقبول", "✅ Accepted"),
          "no": ("❌ مرفوض", "❌ Rejected"), "done": ("📦 مكتمل", "📦 Completed")}
PER = 8


def price_num(p: str) -> float:
    """الرقم داخل نص السعر، مع فهم فواصل الآلاف: 15,000 و 1,250.5 و 12.5 و 9,5."""
    m = re.search(r"\d[\d.,]*", str(p or "").replace("٫", ".").replace("٬", ","))
    if not m:
        return 0.0
    num = m.group(0).rstrip(".,")
    if "," in num and "." in num:
        num = num.replace(".", "").replace(",", ".") if num.rfind(",") > num.rfind(".") else num.replace(",", "")
    elif "," in num:
        parts = num.split(",")
        num = "".join(parts) if all(len(x) == 3 for x in parts[1:]) else num.replace(",", ".", 1).replace(",", "")
    elif "." in num:
        parts = num.split(".")
        # 15.000 ل.س = خمسة عشر ألفاً، لكن 1.500 د.ك = دينار ونصف (عملات بثلاث خانات عشرية)
        if len(parts) > 2 or (len(parts[1]) == 3 and not _three_decimals(str(p))):
            num = "".join(parts) if all(len(x) == 3 for x in parts[1:]) else num
    try:
        return float(num)
    except ValueError:
        return 0.0


def _three_decimals(p: str) -> bool:
    low = p.lower()
    return any(k in low for k in ("kwd", "bhd", "omr", "jod", "tnd", "lyd", "د.ك", "د.ب", "ر.ع", "د.أ", "د.ا", "د.ت", "د.ل"))


def price_unit(p: str) -> str:
    """العملة كما كتبها المالك: ما يبقى من السعر بعد حذف الرقم ($، ل.س، USD...)."""
    return re.sub(r"\d+(?:[.,٫٬]\d+)*", "", str(p or ""), count=1).strip()[:8]


def money(v: float, unit: str) -> str:
    s = f"{v:,.2f}".rstrip("0").rstrip(".")
    return f"{s}{unit}" if len(unit) <= 1 else f"{s} {unit}"


def web_code(bot_id: int, rid: int) -> str:
    from ..web import sign
    return f"w{rid}_{sign.sig('weborder', bot_id, rid)[:10]}"


class Shop(Tpl):
    ns = "shop"
    w_item = ("صنف", "item")
    w_items = ("الأصناف", "Items")
    w_menu = ("🍽 تصفّح المنيو", "🍽 Browse the menu")
    w_site = ("🌐 افتح المنيو على الويب", "🌐 Open the web menu")
    w_app = ("🍽 افتح المنيو", "🍽 Open the menu")
    w_intro = ("أهلاً بك 👋\nتصفّح الأصناف، أضف ما يعجبك إلى السلة، ثم أرسل طلبك.", "Welcome 👋\nBrowse the items, add what you like to the cart, then place your order.")
    w_details = ("اسمك، رقم هاتفك، ورقم الطاولة أو العنوان", "your name, phone number and table number or address")
    with_qr = False
    photo = False
    site = True
    sample: list = []

    def __init__(self) -> None:
        self.items = Items(self.ns, fields=("name", "price", "desc", "cat"), ar=self.w_item[0], en=self.w_item[1], sample=self.sample, photo=self.photo,
                           fmt_ar="الاسم | السعر | الوصف | القسم", fmt_en="Name | Price | Description | Category", toggle=True,
                           hint_ar="الوصف والقسم اختياريان. الأصناف التي تحمل اسم القسم نفسه تُجمع معاً.",
                           hint_en="Description and category are optional. Items sharing a category name are grouped together.")

    # ── بيانات ──
    async def visible(self, c) -> list[dict]:
        return [x for x in await self.items.all(c) if not x.get("off")]

    @staticmethod
    def cat_names(items: list[dict]) -> list[str]:
        out: list[str] = []
        for x in items:
            k = (x.get("cat") or "").strip()
            if k and k not in out:
                out.append(k)
        return out

    def cart(self, c: Ctx) -> dict:
        return c.x.user_data.setdefault(f"cart_{self.ns}", {})

    async def lines_of(self, c, cart: dict) -> tuple[list[dict], float, str]:
        """يحوّل سلة {رقم الصنف: الكمية} إلى سطور مع الإجمالي. يتجاهل ما حُذف أو أُخفي."""
        items = {x["id"]: x for x in await self.visible(c)}
        lines, total, unit = [], 0.0, ""
        for sid, q in list(cart.items())[:60]:
            sid, q = str(sid), str(q)
            it = items.get(int(sid)) if sid.isascii() and sid.isdecimal() else None
            q = int(q) if q.isascii() and q.isdecimal() and len(q) < 4 else 0
            if it is None or q <= 0:
                continue
            q = min(q, 99)
            unit = unit or price_unit(it.get("price", ""))
            total += price_num(it.get("price", "")) * q
            lines.append({"id": it["id"], "name": it["name"], "price": it.get("price", ""), "qty": q})
        return lines, total, unit

    async def place_order(self, c, lines: list[dict], total: float, unit: str, note: str, name: str, src: str = "bot") -> tuple[int, dict]:
        """ينشئ الطلب ويبلغ المالك. يعمل من البوت ومن موقع الويب."""
        d = {"items": [{k: x[k] for k in ("name", "price", "qty")} for x in lines], "total": money(total, unit), "note": note[:600], "name": name[:80], "src": src}
        rid = await c.rec_add(f"{self.ns}:order", d, status="new")
        via = c.t(" · 🌐 من الموقع", " · 🌐 via website") if src == "web" else ""
        await c.notify_owner(c.t("🔔 <b>طلب جديد</b>", "🔔 <b>New order</b>") + via + "\n" + self.order_text(c, rid, d, "new")
                             + f"\n👤 {esc(name)} (<code>{c.uid}</code>)", self.order_kb(c, rid, "new"))
        return rid, d

    # ── واجهة العضو ──
    async def home(self, c: Ctx) -> None:
        t = c.t
        n = sum(self.cart(c).values())
        intro = await c.kv(f"{self.ns}:intro") or t(*self.w_intro)
        app = c.mini_app()      # داخل تيليجرام: التطبيق المصغّر هو الواجهة الأولى، والتصفح بالأزرار بديل
        site = [c.site_btn(*self.w_site, *self.w_app)]
        rows = [site if app else None,
                [B(t(*self.w_menu), "t:menu", style=None if app else "success")],
                None if app else site,
                [B(t(f"🛒 سلتي ({n})", f"🛒 My cart ({n})"), "t:cart"), B(t("🧾 طلباتي", "🧾 My orders"), "t:mine")],
                [B(t("📍 الدفع والاستلام", "📍 Payment & delivery"), "t:info")],
                c.tail()]
        await c.edit(ui.head(c.brand) + intro, kb(rows))

    async def menu(self, c: Ctx, cat: str | None = None, page: int = 0) -> None:
        t = c.t
        items = await self.visible(c)
        if not items:
            await c.edit(t("🕊 لا توجد أصناف معروضة الآن. عد قريباً.", "🕊 Nothing is listed right now. Check back soon."), kb([c.home_row()]))
            return
        cats = self.cat_names(items)
        if cat is None and len(cats) > 1:
            rows = [[B(f"{k} · {sum(1 for x in items if (x.get('cat') or '').strip() == k)}"[:60], f"t:cat:{i}")] for i, k in enumerate(cats)]
            other = sum(1 for x in items if not (x.get("cat") or "").strip())
            rows.append([B(t(f"📚 كل {self.w_items[0]} · {len(items)}", f"📚 All {self.w_items[1].lower()} · {len(items)}"), "t:cat:all")])
            if other:
                rows.insert(len(cats), [B(t(f"أخرى · {other}", f"Other · {other}"), "t:cat:none")])
            await c.edit(ui.head(t(*self.w_menu)) + t("اختر القسم:", "Pick a category:"), kb(rows + [c.home_row()]))
            return
        key = "all"
        if cat == "none":
            shown, key = [x for x in items if not (x.get("cat") or "").strip()], "none"
        elif cat is not None and cat != "all" and cat.isdigit() and int(cat) < len(cats):
            shown, key = [x for x in items if (x.get("cat") or "").strip() == cats[int(cat)]], cat
        else:
            shown = items
        pages = max(1, (len(shown) + PER - 1) // PER)
        page = max(0, min(page, pages - 1))
        cart = self.cart(c)
        rows = []
        for x in shown[page * PER:(page + 1) * PER]:
            q = cart.get(str(x["id"]), 0)
            rows.append([B((f"🛒{q} · " if q else "") + f"{x['name']} — {x.get('price', '')}"[:58], f"t:it:{x['id']}")])
        if pages > 1:
            rows.append([B("‹", f"t:pg:{key}:{page - 1}") if page else None, B(f"{page + 1} / {pages}", "noop"), B("›", f"t:pg:{key}:{page + 1}") if page < pages - 1 else None])
        n = sum(cart.values())
        rows.append([B(t(f"🛒 السلة ({n})", f"🛒 Cart ({n})"), "t:cart") if n else None,
                     B(t("⬅️ الأقسام", "⬅️ Categories"), "t:menu") if len(cats) > 1 else None])
        title = cats[int(key)] if key.isdigit() else t(*self.w_menu)
        c.x.user_data[f"back_{self.ns}"] = f"t:pg:{key}:{page}"
        await c.edit(ui.head(esc(title)) + t("اضغط الصنف لعرض تفاصيله وإضافته إلى السلة.", "Tap an item to see its details and add it to the cart."), kb(rows + [c.home_row()]))

    async def item(self, c: Ctx, iid: int) -> None:
        t = c.t
        it = await self.items.get(c, iid)
        if it is None or it.get("off"):
            await self.menu(c)
            return
        q = self.cart(c).get(str(iid), 0)
        text = (f"<b>{esc(it['name'])}</b>" + (f"\n🏷 {esc(it['cat'])}" if it.get("cat") else "") + f"\n💵 <b>{esc(it.get('price', ''))}</b>"
                + (f"\n\n{esc(it['desc'])}" if it.get("desc") else "") + (t(f"\n\n🛒 في سلتك: <b>{q}</b>", f"\n\n🛒 In your cart: <b>{q}</b>") if q else ""))
        back = c.x.user_data.get(f"back_{self.ns}", "t:menu")
        qty_row = ([B("➖", f"t:sub:{iid}"), B(f"× {q}", "noop"), B("➕", f"t:add:{iid}")] if q
                   else [B(t("➕ أضف إلى السلة", "➕ Add to cart"), f"t:add:{iid}", style="success")])
        markup = kb([qty_row, [B(t("🛒 السلة", "🛒 Cart"), "t:cart"), B(t("⬅️ رجوع", "⬅️ Back"), back)]])
        on_photo = bool(c.q and c.q.message and c.q.message.photo)
        if it.get("photo") and not on_photo:
            try:
                await c.photo(it["photo"], caption=text, kb=markup)
                return
            except TelegramError:
                pass
        if on_photo:
            try:
                await c.q.edit_message_caption(caption=text, reply_markup=markup, parse_mode="HTML")
                return
            except TelegramError:
                pass
        await c.edit(text, markup)

    async def cart_lines(self, c: Ctx) -> tuple[list[dict], float, str]:
        cart = self.cart(c)
        lines, total, unit = await self.lines_of(c, cart)
        keep = {str(x["id"]) for x in lines}
        for k in [k for k in cart if k not in keep]:
            cart.pop(k, None)
        return lines, total, unit

    async def cart_view(self, c: Ctx) -> None:
        t = c.t
        lines, total, unit = await self.cart_lines(c)
        if not lines:
            await c.edit(t("🛒 سلتك فارغة.\nتصفّح الأصناف وأضف ما يعجبك.", "🛒 Your cart is empty.\nBrowse the items and add what you like."),
                         kb([[B(t(*self.w_menu), "t:menu", style="success")], c.home_row()]))
            return
        body = "\n".join(f"{i}. {esc(x['name'])}\n    {x['qty']} × {esc(x['price'])}" for i, x in enumerate(lines, 1))
        rows = [[B(t("✅ إتمام الطلب", "✅ Checkout"), "t:order", style="success")]]
        rows += ui.grid([B(f"✏️ {x['name']}"[:28], f"t:it:{x['id']}") for x in lines[:8]], 2)
        rows += [[B(t("🗑 تفريغ السلة", "🗑 Empty cart"), "t:clr"), B(t("➕ أضف المزيد", "➕ Add more"), "t:menu")], c.home_row()]
        c.x.user_data[f"back_{self.ns}"] = "t:cart"
        await c.edit(ui.head(t("🛒 سلتك", "🛒 Your cart")) + f"{body}\n{ui.LINE}\n" + t(f"💰 الإجمالي: <b>{money(total, unit)}</b>", f"💰 Total: <b>{money(total, unit)}</b>")
                     + t("\n\nلتعديل كمية صنف اضغط اسمه.", "\n\nTap an item to change its quantity."), kb(rows))

    def order_text(self, c, rid: int, d: dict, status: str) -> str:
        shown = d["items"][:25]
        body = "\n".join(f"• {esc(str(x['name'])[:60])} × {x['qty']} — {esc(str(x['price'])[:24])}" for x in shown)
        if len(d["items"]) > len(shown):
            body += c.t(f"\n… و{len(d['items']) - len(shown)} صنفاً آخر", f"\n… and {len(d['items']) - len(shown)} more")
        st = c.t(*STATUS.get(status, STATUS["new"]))
        return (c.t(f"🧾 <b>طلب #{rid}</b> — {st}", f"🧾 <b>Order #{rid}</b> — {st}") + f"\n{body}\n💰 <b>{esc(d.get('total', ''))}</b>"
                + (f"\n📝 {esc(d['note'])}" if d.get("note") else ""))

    async def checkout(self, c: Ctx) -> None:
        t = c.t
        lines, total, unit = await self.cart_lines(c)
        if not lines:
            await self.cart_view(c)
            return
        c.set_state(f"{self.ns}_note")
        last = await c.kv(f"{self.ns}:cust:{c.uid}")
        rows = [[B(t("↩️ استخدم بياناتي السابقة", "↩️ Use my previous details"), "t:same")]] if last else []
        await c.edit(ui.head(t("✅ إتمام الطلب", "✅ Checkout")) + t(f"💰 الإجمالي: <b>{money(total, unit)}</b>\n\n📝 أرسل في رسالة واحدة: {self.w_details[0]}، وأي ملاحظة على الطلب.",
                                                                 f"💰 Total: <b>{money(total, unit)}</b>\n\n📝 Send in one message: {self.w_details[1]}, plus any note.")
                     + (t(f"\n\nبياناتك السابقة:\n<i>{esc(last)}</i>", f"\n\nYour previous details:\n<i>{esc(last)}</i>") if last else "")
                     + t("\n\n/cancel للإلغاء", "\n\n/cancel to abort"), kb(rows + [[B(t("⬅️ السلة", "⬅️ Cart"), "t:cart")]]))

    async def finish(self, c: Ctx, note: str) -> None:
        t = c.t
        lines, total, unit = await self.cart_lines(c)
        c.clear_state()
        if not lines:
            await self.home(c)
            return
        await c.kv_set(f"{self.ns}:cust:{c.uid}", note[:300])
        rid, d = await self.place_order(c, lines, total, unit, note, c.user.full_name)
        self.cart(c).clear()
        await c.send(t("✅ <b>وصل طلبك</b>\nيراجعه البائع الآن، وسيصلك هنا إشعار بقبوله.\n\n", "✅ <b>Order received</b>\nThe seller is reviewing it; you'll be notified here once accepted.\n\n")
                     + self.order_text(c, rid, d, "new"), kb([[B(t("🧾 طلباتي", "🧾 My orders"), "t:mine")], c.home_row()]))

    async def start_param(self, c: Ctx, param: str) -> bool:
        """روابط الموقع: w<رقم>_<توقيع> لتأكيد طلب أُرسل من الموقع، و i<رقم> لفتح صنف."""
        if param.startswith("i") and param[1:].isascii() and param[1:].isdecimal():
            await self.item(c, int(param[1:]))
            return True
        m = re.fullmatch(r"w(\d+)_([0-9a-f]{10})", param)
        if not m:
            return False
        rid = int(m.group(1))
        r = await c.rec_get(rid)
        if r is None or r.kind != f"{self.ns}:web" or param != web_code(c.bot_id, rid):
            await c.send(c.t("⚠️ رابط الطلب غير صالح.", "⚠️ This order link is not valid."), kb([c.home_row()]))
            return True
        if r.status != "wait":
            await c.send(c.t("ℹ️ هذا الطلب أُرسل من قبل. تجده في «طلباتي».", "ℹ️ This order was already placed. See “My orders”."), kb([[B(c.t("🧾 طلباتي", "🧾 My orders"), "t:mine")], c.home_row()]))
            return True
        lines, total, unit = await self.lines_of(c, r.data.get("cart") or {})
        await c.rec_update(rid, status="done")
        if not lines:
            await self.home(c)
            return True
        rid2, d = await self.place_order(c, lines, total, unit, r.data.get("note", ""), r.data.get("name") or c.user.full_name, src="web")
        await c.send(c.t("✅ <b>تم تأكيد طلبك من الموقع</b>\nيراجعه البائع الآن، وسيصلك هنا إشعار بقبوله.\n\n", "✅ <b>Your website order is confirmed</b>\nYou'll be notified here once accepted.\n\n")
                     + self.order_text(c, rid2, d, "new"), kb([[B(c.t("🧾 طلباتي", "🧾 My orders"), "t:mine")], c.home_row()]))
        return True

    # ── المالك ──
    async def owner(self, c: Ctx):
        t = c.t
        items = await self.items.all(c)
        hidden = sum(1 for x in items if x.get("off"))
        n_new, n_ok = await c.rec_count(f"{self.ns}:order", status="new"), await c.rec_count(f"{self.ns}:order", status="ok")
        n_done = await c.rec_count(f"{self.ns}:order", status="done")
        text = t(f"📦 {self.w_items[0]}: <b>{len(items)}</b>" + (f" (مخفي: {hidden})" if hidden else "") + f"  ·  🏷 الأقسام: <b>{len(self.cat_names(items))}</b>\n"
                 f"🧾 طلبات جديدة: <b>{n_new}</b>  ·  قيد التجهيز: <b>{n_ok}</b>  ·  مكتملة: <b>{n_done}</b>",
                 f"📦 {self.w_items[1]}: <b>{len(items)}</b>" + (f" (hidden: {hidden})" if hidden else "") + f"  ·  🏷 Categories: <b>{len(self.cat_names(items))}</b>\n"
                 f"🧾 New orders: <b>{n_new}</b>  ·  In progress: <b>{n_ok}</b>  ·  Completed: <b>{n_done}</b>")
        rows = [[B(t(f"🧾 الطلبات ({n_new})", f"🧾 Orders ({n_new})"), "t:ords:new", style="success" if n_new else None)],
                [B(t(f"➕ إضافة {self.w_item[0]}", f"➕ Add {self.w_item[1]}"), f"t:ia:{self.ns}"), B(t(f"📋 {self.w_items[0]}", f"📋 {self.w_items[1]}"), f"t:il:{self.ns}")],
                [B(t("✏️ نص الترحيب", "✏️ Welcome text"), "t:set:intro"), B(t("📍 نص الدفع والاستلام", "📍 Payment & delivery text"), "t:set:info")],
                [B(t("🔳 رمز QR للطباعة", "🔳 Printable QR code"), "t:qr")] if self.with_qr else None]
        return text, rows

    async def orders(self, c: Ctx, flt: str = "new") -> None:
        t = c.t
        flt = flt if flt in ("new", "ok", "done", "all") else "new"
        recs = await c.rec_list(f"{self.ns}:order", status=None if flt == "all" else flt, limit=12)
        tabs = [B(("• " if flt == k else "") + t(ar, en), f"t:ords:{k}") for k, ar, en in
                (("new", "جديدة", "New"), ("ok", "قيد التجهيز", "In progress"), ("done", "مكتملة", "Completed"), ("all", "الكل", "All"))]
        rows = [[B(f"#{r.id} · {r.data.get('name', '')} · {r.data.get('total', '')}"[:58], f"t:ord:{r.id}")] for r in recs]
        c.x.user_data[f"oflt_{self.ns}"] = flt
        await c.edit(ui.head(t("🧾 الطلبات", "🧾 Orders")) + (t("اضغط الطلب لعرضه وتحديث حالته.", "Tap an order to view it and update its status.") if recs
                                                             else t("لا توجد طلبات في هذه القائمة.", "No orders in this list.")),
                     kb([tabs[:2], tabs[2:]] + rows + [[B(t("🎛 غرفة التحكم", "🎛 Control room"), "o:home")]]))

    def order_kb(self, c, rid: int, status: str):
        rows = []
        if status == "new":
            rows.append([B(c.t("✅ قبول", "✅ Accept"), f"t:os:{rid}:ok", style="success"), B(c.t("❌ رفض", "❌ Reject"), f"t:os:{rid}:no", style="danger")])
        elif status == "ok":
            rows.append([B(c.t("📦 تم التسليم", "📦 Mark as delivered"), f"t:os:{rid}:done", style="success")])
        rows.append([B(c.t("🧾 كل الطلبات", "🧾 All orders"), "t:ords")])
        return kb(rows)

    def owner_order(self, c: Ctx, r) -> str:
        return (self.order_text(c, r.id, r.data, r.status) + f"\n{ui.LINE}\n👤 {esc(r.data.get('name', ''))} (<code>{r.user_id}</code>)\n🕒 {ui.when(r.created)}"
                + (c.t("\n🌐 أُرسل من الموقع", "\n🌐 Placed on the website") if r.data.get("src") == "web" else ""))

    # ── التوجيه ──
    async def cb(self, c: Ctx, a: list[str]) -> None:  # noqa: C901
        if await self.items.handle_cb(c, a):
            return
        act, t = a[0], c.t
        arg = a[1] if len(a) > 1 else ""
        if act == "menu":
            await self.menu(c)
        elif act == "cat":
            await self.menu(c, arg or "all", 0)
        elif act == "pg":
            await self.menu(c, arg or "all", int(a[2]) if len(a) > 2 and a[2].lstrip("-").isdigit() else 0)
        elif act == "it" and arg.isdigit():
            await self.item(c, int(arg))
        elif act in ("add", "sub") and arg.isdigit():
            cart = self.cart(c)
            it = await self.items.get(c, int(arg))
            if it is None or it.get("off"):
                await c.answer(t("هذا الصنف لم يعد متاحاً.", "This item is no longer available."), True)
                return await self.menu(c)
            q = max(0, min(99, cart.get(arg, 0) + (1 if act == "add" else -1)))
            if q:
                cart[arg] = q
            else:
                cart.pop(arg, None)
            await c.answer(t(f"🛒 في السلة: {q}", f"🛒 In cart: {q}") if q else t("أزيل من السلة", "Removed from cart"))
            await self.item(c, int(arg))
        elif act == "cart":
            await self.cart_view(c)
        elif act == "clr":
            self.cart(c).clear()
            await self.cart_view(c)
        elif act == "order":
            await self.checkout(c)
        elif act == "same":
            last = await c.kv(f"{self.ns}:cust:{c.uid}")
            if last:
                await self.finish(c, last)
            else:
                await self.checkout(c)
        elif act == "info":
            await c.edit(ui.head(t("📍 الدفع والاستلام", "📍 Payment & delivery")) + (await c.kv(f"{self.ns}:info") or t(
                "اختر ما تريد وأرسل طلبك، وسيتواصل معك البائع لتأكيد الدفع وطريقة الاستلام.",
                "Pick what you want and place your order; the seller will contact you to confirm payment and delivery.")), kb([c.home_row()]))
        elif act == "mine":
            recs = await c.rec_list(f"{self.ns}:order", user_id=c.uid, limit=6)
            text = "\n\n".join(self.order_text(c, r.id, r.data, r.status) for r in recs) or t("لم ترسل أي طلب بعد.", "You haven't placed an order yet.")
            await c.edit(ui.head(t("🧾 طلباتي", "🧾 My orders")) + text, kb([[B(t(*self.w_menu), "t:menu")], c.home_row()]))
        elif not c.is_owner:
            return
        elif act == "qr" and self.with_qr:
            await self.send_qr(c)
        elif act == "ords":
            await self.orders(c, arg or c.x.user_data.get(f"oflt_{self.ns}", "new"))
        elif act == "ord" and arg.isdigit():
            r = await c.rec_get(int(arg))
            if r is not None and r.kind == f"{self.ns}:order":
                await c.edit(self.owner_order(c, r), self.order_kb(c, r.id, r.status))
        elif act == "os" and arg.isdigit() and len(a) > 2 and a[2] in STATUS:
            r = await c.rec_get(int(arg))
            if r is None or r.kind != f"{self.ns}:order":
                return
            await c.rec_update(r.id, status=a[2])
            r.status = a[2]
            await c.edit(self.owner_order(c, r), self.order_kb(c, r.id, a[2]))
            head = {"ok": t("✅ <b>قُبل طلبك</b> وهو قيد التجهيز.", "✅ <b>Your order was accepted</b> and is being prepared."),
                    "no": t("❌ <b>نعتذر، لم يُقبل طلبك.</b>", "❌ <b>Sorry, your order was not accepted.</b>"),
                    "done": t("📦 <b>اكتمل طلبك.</b> شكراً لك!", "📦 <b>Your order is complete.</b> Thank you!")}.get(a[2], "")
            try:
                await c.send(head + "\n\n" + self.order_text(c, r.id, r.data, a[2]), chat_id=r.user_id)
            except TelegramError:
                pass
        elif act == "set" and arg in ("intro", "info"):
            c.set_state(f"{self.ns}_set", field=arg)
            what = t("نص الترحيب الذي يراه الزبون أول ما يفتح البوت", "the welcome text customers see first") if arg == "intro" else t(
                "طرق الدفع، التوصيل أو الاستلام، وأوقات العمل", "payment methods, delivery or pickup, and working hours")
            await c.edit(t(f"✍️ أرسل {what} (يدعم التنسيق).\n\n/cancel للإلغاء", f"✍️ Send {what} (formatting supported).\n\n/cancel to abort"),
                         kb([[B(t("❌ إلغاء", "❌ Cancel"), "o:home")]]))

    async def send_qr(self, c: Ctx) -> None:
        import qrcode

        from .. import web
        site_on = web.public() and (c.core.get("site") or {}).get("on", True)
        target = web.site_url(c.bot.username) if site_on else c.link()
        buf = io.BytesIO()
        qrcode.make(target).save(buf, format="PNG")
        buf.seek(0)
        await c.photo(buf, caption=c.t("🔳 <b>رمز QR جاهز للطباعة</b>\nضعه على الطاولات أو عند الكاشير؛ من يمسحه يفتح " + ("المنيو على الويب مباشرة دون تثبيت شيء" if site_on else "البوت")
                                       + f".\n\n{target}", "🔳 <b>Printable QR code</b>\nPlace it on tables; scanning opens " + ("the web menu directly" if site_on else "the bot") + f".\n\n{target}"),
                      filename="menu_qr.png")

    async def msg(self, c: Ctx) -> bool:
        if c.is_owner and await self.items.handle_msg(c):
            return True
        st = c.st
        if st and st["k"] == f"{self.ns}_set" and c.is_owner:
            await c.kv_set(f"{self.ns}:{st['field']}", ui.html_of(c.msg))
            c.clear_state()
            await c.send(c.t("✅ حُفظ النص.", "✅ Text saved."), kb([c.home_row()]))
            return True
        if st and st["k"] == f"{self.ns}_note":
            if not c.text:
                await c.send(c.t("📝 أرسل بياناتك نصاً.", "📝 Please send your details as text."))
                return True
            await self.finish(c, c.text)
            return True
        return False

    async def checklist(self, c: Ctx) -> list:
        items = await self.items.all(c)
        real = [x for x in items if x.get("name") != (self.sample[0]["name"] if self.sample else None)]
        return [(bool(real), c.t(f"أضف أول {self.w_item[0]} حقيقي", f"Add your first real {self.w_item[1]}"), f"t:ia:{self.ns}"),
                (any(x.get("photo") for x in items), c.t("أضف صورة لصنف واحد على الأقل", "Add a photo to at least one item"), f"t:il:{self.ns}"),
                (bool(await c.kv(f"{self.ns}:info")), c.t("اكتب طرق الدفع والاستلام", "Write payment & delivery info"), "t:set:info")]
