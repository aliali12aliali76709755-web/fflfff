"""اشتراكات VIP: خطط، طلبات وصول بإثبات دفع، رابط دعوة لمرة واحدة، وإخراج تلقائي عند الانتهاء."""
import datetime as dt
import logging
import time

from telegram.error import TelegramError

from .. import db, ui
from .. import plat
from ..ctx import Ctx
from ..ui import B, esc, kb
from . import Items, Tpl

log = logging.getLogger("forge.vip")


class Vip(Tpl):
    emoji, ar, en = "💎", "اشتراكات VIP", "VIP subscriptions"
    d_ar, d_en = "خطط VIP وطلبات وصول", "VIP plans and access requests"
    cats = ("top",)
    guide_ar = ("1. أضف خططك بصيغة <code>اسم الخطة | السعر | عدد الأيام</code>.\n"
                "2. من «📢 قناة VIP» اربط قناتك أو مجموعتك الخاصة (البوت يجب أن يكون مشرفاً بصلاحية دعوة وحظر الأعضاء).\n"
                "3. اكتب طريقة الدفع في «💳 تعليمات الدفع».\n4. المشترك يختار خطة ويرسل إثبات الدفع، فيصلك للمراجعة.\n"
                "5. عند القبول يرسل البوت للمشترك رابط دعوة يعمل لشخص واحد، وعند انتهاء المدة يُخرجه من القناة تلقائياً ويبلغه.\n\n"
                "الدفع يتم بينك وبين المشترك مباشرة؛ البوت لا يحصّل أموالاً.")

    def __init__(self) -> None:
        self.items = Items("vip", fields=("name", "price", "days"), ar="خطة", en="plan",
                           fmt_ar="اسم الخطة | السعر | عدد الأيام", fmt_en="Plan name | Price | Days",
                           sample=[{"name": "شهر", "price": "10$", "days": "30"}])

    def setup(self, app) -> None:
        if app.job_queue is not None:
            app.job_queue.run_repeating(self._expire, interval=1800, first=90, name="vip_expire")

    async def _expire(self, context) -> None:
        bot_id = context.bot_data["bot_id"]
        if plat.admin_lock(context.bot_data) is not None:      # البوت مغلق من الإدارة: لا مهام مجدولة
            return
        cfg = await db.kv_get(bot_id, "vip:cfg", {}) or {}
        now = time.time()
        for r in await db.rec_list(bot_id, "vip", status="active", limit=2000):
            if r.data.get("until", 0) > now:
                continue
            await db.rec_update(bot_id, r.id, status="expired")
            if cfg.get("chat"):
                try:
                    await context.bot.ban_chat_member(cfg["chat"], r.user_id)
                    await context.bot.unban_chat_member(cfg["chat"], r.user_id, only_if_banned=True)
                except TelegramError:
                    log.warning("vip: cannot remove %s from %s", r.user_id, cfg["chat"])
            try:
                await context.bot.send_message(r.user_id, "⌛️ انتهى اشتراكك VIP. يمكنك التجديد من /start")
            except TelegramError:
                pass

    async def active(self, c: Ctx, uid: int):
        recs = await c.rec_list("vip", user_id=uid, status="active", limit=1)
        return recs[0] if recs else None

    async def home(self, c: Ctx) -> None:
        sub = await self.active(c, c.uid)
        status = c.t("لا يوجد اشتراك فعّال.", "No active subscription.")
        if sub:
            until = dt.datetime.utcfromtimestamp(sub.data["until"])
            status = c.t(f"✅ اشتراكك فعّال حتى {until:%Y-%m-%d}", f"✅ Active until {until:%Y-%m-%d}")
        await c.edit(ui.head(c.brand) + "\n" + (await c.kv("vip:intro") or c.t(
            "اشترك للوصول إلى المحتوى الحصري.", "Subscribe to access exclusive content.")) + f"\n\n{status}",
            kb([[B(c.t("💎 الخطط", "💎 Plans"), "t:plans", style="success")], c.tail()]))

    async def owner(self, c: Ctx):
        cfg = await c.kv("vip:cfg", {}) or {}
        act, pen = await c.rec_count("vip", status="active"), await c.rec_count("vip", status="pending")
        return (c.t(f"📢 القناة: {esc(cfg.get('title') or 'غير مربوطة')}\n👥 مشتركون فعّالون: {act}\n🕒 طلبات تنتظر: {pen}",
                    f"📢 Channel: {esc(cfg.get('title') or 'not linked')}\n👥 Active subscribers: {act}\n🕒 Pending requests: {pen}"),
                [[B(c.t("➕ إضافة خطة", "➕ Add plan"), "t:ia:vip"), B(c.t("📋 الخطط", "📋 Plans"), "t:il:vip")],
                 [B(c.t("📢 قناة VIP", "📢 VIP channel"), "t:chan"), B(c.t("💳 تعليمات الدفع", "💳 Payment instructions"), "t:pay")],
                 [B(c.t(f"🕒 الطلبات ({pen})", f"🕒 Requests ({pen})"), "t:reqs"), B(c.t(f"👥 المشتركون ({act})", f"👥 Subscribers ({act})"), "t:subs")]])

    def req_kb(self, c: Ctx, rid: int):
        return kb([[B(c.t("✅ قبول", "✅ Approve"), f"t:ok:{rid}", style="success"), B(c.t("❌ رفض", "❌ Reject"), f"t:no:{rid}", style="danger")]])

    async def cb(self, c: Ctx, a: list[str]) -> None:  # noqa: C901
        if await self.items.handle_cb(c, a):
            return
        act, t = a[0], c.t
        if act == "plans":
            plans = await self.items.all(c)
            rows = [[B(f"{p['name']} — {p.get('price', '')} · {p.get('days', '')} {t('يوم', 'days')}"[:60], f"t:p:{p['id']}")] for p in plans]
            await c.edit(ui.head(t("💎 اختر الخطة", "💎 Choose a plan")), kb(rows + [c.home_row()]))
        elif act == "p":
            p = await self.items.get(c, int(a[1]))
            if p is None:
                return
            pay = await c.kv("vip:pay") or t("تواصل مع المالك لمعرفة طريقة الدفع.", "Contact the owner for payment details.")
            c.set_state("vip_proof", plan=p["name"], price=p.get("price", ""), days=int(p.get("days") or 30) if str(p.get("days") or "30").isdigit() else 30)
            await c.edit(t(f"💎 <b>{esc(p['name'])}</b> — {esc(p.get('price', ''))}\n\n💳 <b>طريقة الدفع</b>\n{pay}\n\n📸 بعد الدفع أرسل هنا إثبات الدفع (صورة أو رقم العملية).\n\n/cancel للإلغاء",
                           f"💎 <b>{esc(p['name'])}</b> — {esc(p.get('price', ''))}\n\n💳 <b>Payment</b>\n{pay}\n\n📸 After paying, send the proof here (screenshot or transaction ID).\n\n/cancel to abort"),
                         kb([[B(t("⬅️ رجوع", "⬅️ Back"), "t:plans")]]))
        elif not c.is_owner:
            return
        elif act in ("chan", "pay", "intro"):
            c.set_state("vip_set", field=act)
            await c.edit({"chan": t("📢 أضف البوت مشرفاً في القناة/المجموعة الخاصة، ثم أرسل معرّفها (@username) أو حوّل منشوراً منها.",
                                   "📢 Make the bot an admin of the private channel/group, then send its @username or forward a post from it."),
                          "pay": t("💳 أرسل تعليمات الدفع (مثلاً: شام كاش، USDT TRC20 مع العنوان).", "💳 Send the payment instructions."),
                          "intro": t("✍️ أرسل نص الترحيب.", "✍️ Send the intro text.")}[act] + t("\n\n/cancel للإلغاء", "\n\n/cancel to abort"),
                         kb([[B(t("❌ إلغاء", "❌ Cancel"), "o:home")]]))
        elif act == "reqs":
            recs = await c.rec_list("vip", status="pending", limit=10)
            rows = [[B(f"✅ #{r.id}", f"t:ok:{r.id}"), B(f"❌ #{r.id}", f"t:no:{r.id}")] for r in recs]
            text = "\n".join(f"#{r.id} · {esc(r.data['name'])} · {esc(r.data['plan'])}" for r in recs) or t("لا توجد طلبات.", "No requests.")
            await c.edit(ui.head(t("🕒 طلبات الاشتراك", "🕒 Subscription requests")) + "\n" + text, kb(rows + [[B(t("🎛 غرفة التحكم", "🎛 Control room"), "o:home")]]))
        elif act == "subs":
            recs = await c.rec_list("vip", status="active", limit=30)
            text = "\n".join(f"• {esc(r.data['name'])} (<code>{r.user_id}</code>) — {dt.datetime.utcfromtimestamp(r.data['until']):%Y-%m-%d}" for r in recs) \
                or t("لا يوجد مشتركون.", "No subscribers.")
            await c.edit(ui.head(t("👥 المشتركون", "👥 Subscribers")) + "\n" + text, kb([[B(t("🎛 غرفة التحكم", "🎛 Control room"), "o:home")]]))
        elif act in ("ok", "no"):
            r = await c.rec_get(int(a[1]))
            if r is None or r.status != "pending":
                await c.answer(t("عولج من قبل", "Already handled"), True)
                return
            if act == "no":
                await c.rec_update(r.id, status="rejected")
                try:
                    await c.send(t("❌ لم يُقبل طلب اشتراكك. تواصل مع المالك للتفاصيل.", "❌ Your subscription request was not approved."), chat_id=r.user_id)
                except TelegramError:
                    pass
                await c.edit(t(f"❌ رُفض الطلب #{r.id}.", f"❌ Request #{r.id} rejected."))
                return
            cfg = await c.kv("vip:cfg", {}) or {}
            if not cfg.get("chat"):
                await c.answer(t("اربط قناة VIP أولاً.", "Link the VIP channel first."), True)
                return
            try:
                inv = await c.bot.create_chat_invite_link(cfg["chat"], member_limit=1, expire_date=dt.datetime.utcnow() + dt.timedelta(days=2))
            except TelegramError:
                await c.answer(t("تعذّر إنشاء رابط الدعوة. تأكد من صلاحيات البوت في القناة.", "Couldn't create the invite link. Check the bot's rights."), True)
                return
            d = dict(r.data, until=time.time() + int(r.data["days"]) * 86400)
            await c.rec_update(r.id, data=d, status="active")
            try:
                await c.send(t(f"✅ تم تفعيل اشتراكك «{esc(d['plan'])}» لمدة {d['days']} يوماً.\n\n🔗 رابط الدخول (لك وحدك):\n{inv.invite_link}",
                               f"✅ Your “{esc(d['plan'])}” subscription is active for {d['days']} days.\n\n🔗 Your personal invite link:\n{inv.invite_link}"),
                             chat_id=r.user_id)
            except TelegramError:
                pass
            await c.edit(t(f"✅ قُبل الطلب #{r.id} وأُرسل الرابط للمشترك.", f"✅ Request #{r.id} approved; link sent."))

    async def msg(self, c: Ctx) -> bool:
        if c.is_owner and await self.items.handle_msg(c):
            return True
        st, t = c.st, c.t
        if st and st["k"] == "vip_set" and c.is_owner:
            if st["field"] == "chan":
                origin = getattr(c.msg, "forward_origin", None)
                ref = origin.chat.id if origin is not None and getattr(origin, "chat", None) else (
                    int(c.text) if c.text.lstrip("-").isdigit() else (c.text if c.text.startswith("@") else "@" + c.text.rsplit("/", 1)[-1]))
                try:
                    chat = await c.bot.get_chat(ref)
                    me = await c.bot.get_chat_member(chat.id, c.bot.id)
                    assert me.status in ("administrator", "creator")
                except Exception:
                    await c.send(t("⚠️ لم أستطع الوصول. تأكد أن البوت مشرف هناك.", "⚠️ Couldn't access it. Make sure the bot is an admin there."))
                    return True
                await c.kv_set("vip:cfg", {"chat": chat.id, "title": chat.title or str(ref)})
            else:
                await c.kv_set(f"vip:{st['field']}", c.msg.text_html or "")
            c.clear_state()
            await c.send(t("✅ تم الحفظ.", "✅ Saved."), kb([c.home_row()]))
            return True
        if st and st["k"] == "vip_proof":
            c.clear_state()
            d = {"plan": st["plan"], "price": st["price"], "days": st["days"], "name": c.user.full_name}
            rid = await c.rec_add("vip", d, status="pending")
            await c.send(t("✅ وصل إثبات الدفع. سيُفعَّل اشتراكك بعد المراجعة.", "✅ Proof received. Your subscription will be activated after review."), kb([c.home_row()]))
            await c.notify_owner(t(f"🔔 <b>طلب اشتراك #{rid}</b>\n💎 {esc(d['plan'])} — {esc(d['price'])} · {d['days']} يوم\n👤 {c.name} (<code>{c.uid}</code>)\n\n⬇️ إثبات الدفع:",
                                   f"🔔 <b>Subscription request #{rid}</b>\n💎 {esc(d['plan'])} — {esc(d['price'])} · {d['days']} days\n👤 {c.name} (<code>{c.uid}</code>)\n\n⬇️ Payment proof:"))
            try:
                await c.bot.copy_message(c.owner_id, c.chat.id, c.msg.message_id, reply_markup=self.req_kb(c, rid))
            except TelegramError:
                pass
            return True
        return False


TPL = Vip()
