"""دعم فني وتذاكر: نظام مبسط لاستقبال تذاكر الدعم والرد عليها."""
from telegram.error import TelegramError

from .. import db, ui
from ..ctx import Ctx
from ..ui import B, esc, kb
from . import Tpl


class Tickets(Tpl):
    emoji, ar, en = "🎫", "دعم فني وتذاكر", "Support tickets"
    d_ar, d_en = "نظام مبسط لاستقبال تذاكر الدعم", "A simple system for support tickets"
    cats = ("biz",)
    guide_ar = ("المستخدم يفتح تذكرة بعنوان ووصف، فتصلك مع زر «رد». كل الردود تُحفظ داخل التذكرة ويستطيع الطرفان متابعتها، "
                "وتستطيع إغلاق التذكرة عند انتهاء المشكلة. من «🎫 التذاكر المفتوحة» ترى كل ما ينتظر ردّك.")

    async def home(self, c: Ctx) -> None:
        n = await c.rec_count("ticket", user_id=c.uid, status="open")
        await c.edit(ui.head(c.t("🎫 الدعم الفني", "🎫 Support")) + "\n" + c.t(
            "افتح تذكرة جديدة واشرح مشكلتك، وسيرد عليك فريق الدعم هنا.", "Open a new ticket and describe your issue; support will reply here."),
            kb([[B(c.t("➕ تذكرة جديدة", "➕ New ticket"), "t:new", style="success")],
                [B(c.t(f"📂 تذاكري ({n} مفتوحة)", f"📂 My tickets ({n} open)"), "t:mine")], c.tail()]))

    async def owner(self, c: Ctx):
        o, cl = await c.rec_count("ticket", status="open"), await c.rec_count("ticket", status="closed")
        return (c.t(f"🎫 تذاكر مفتوحة: {o}\n✅ مغلقة: {cl}", f"🎫 Open tickets: {o}\n✅ Closed: {cl}"),
                [[B(c.t(f"🎫 التذاكر المفتوحة ({o})", f"🎫 Open tickets ({o})"), "t:all:open")],
                 [B(c.t("🗂 التذاكر المغلقة", "🗂 Closed tickets"), "t:all:closed")]])

    def render(self, c: Ctx, r: db.Rec) -> str:
        d = r.data
        st = c.t("🟢 مفتوحة", "🟢 Open") if r.status == "open" else c.t("⚪ مغلقة", "⚪ Closed")
        msgs = d["msgs"][-8:]
        cut = 3000 // max(1, len(msgs))
        thread = "\n\n".join(("👤 " if m["by"] == "u" else "🛟 ") + esc(m["text"][:cut]) for m in msgs)
        return f"🎫 <b>#{r.id} — {esc(d['subject'])}</b>\n{st} · {esc(d.get('name', ''))}\n{ui.LINE}\n{thread}"

    def view_kb(self, c: Ctx, r: db.Rec):
        rows = []
        if r.status == "open":
            rows.append([B(c.t("↩️ رد", "↩️ Reply"), f"t:re:{r.id}"), B(c.t("✅ إغلاق", "✅ Close"), f"t:cl:{r.id}")])
        elif c.is_owner:
            rows.append([B(c.t("🔓 إعادة فتح", "🔓 Reopen"), f"t:op:{r.id}")])
        rows.append([B(c.t("⬅️ رجوع", "⬅️ Back"), "t:all:open" if c.is_owner else "t:mine")])
        return kb(rows)

    async def cb(self, c: Ctx, a: list[str]) -> None:
        act, t = a[0], c.t
        if act == "new":
            c.set_state("tk_subject")
            await c.edit(t("✍️ أرسل عنواناً قصيراً للمشكلة.\n\n/cancel للإلغاء", "✍️ Send a short subject.\n\n/cancel to abort"), kb([c.home_row()]))
        elif act == "mine":
            recs = await c.rec_list("ticket", user_id=c.uid, limit=15)
            rows = [[B(f"{'🟢' if r.status == 'open' else '⚪'} #{r.id} {r.data['subject']}"[:60], f"t:v:{r.id}")] for r in recs]
            await c.edit(ui.head(t("📂 تذاكري", "📂 My tickets")) + ("" if recs else "\n" + t("لا توجد تذاكر.", "No tickets.")), kb(rows + [c.home_row()]))
        elif act == "all" and c.is_owner:
            recs = await c.rec_list("ticket", status=a[1], limit=20)
            rows = [[B(f"#{r.id} {r.data['subject']} · {r.data.get('name', '')}"[:60], f"t:v:{r.id}")] for r in recs]
            await c.edit(ui.head(t("🎫 التذاكر", "🎫 Tickets")) + ("" if recs else "\n" + t("لا توجد تذاكر.", "No tickets.")),
                         kb(rows + [[B(t("🎛 غرفة التحكم", "🎛 Control room"), "o:home")]]))
        elif act in ("v", "re", "cl", "op"):
            r = await c.rec_get(int(a[1]))
            if r is None or r.kind != "ticket" or not (c.is_owner or r.user_id == c.uid):
                await c.answer(t("غير متاح", "Unavailable"), True)
                return
            if act == "re":
                c.set_state("tk_reply", rid=r.id)
                await c.send(t(f"✍️ اكتب ردّك على التذكرة #{r.id}.", f"✍️ Write your reply to ticket #{r.id}."))
                return
            if act in ("cl", "op"):
                r.status = "closed" if act == "cl" else "open"
                await c.rec_update(r.id, status=r.status)
                other = r.user_id if c.is_owner else c.owner_id
                try:
                    await c.send(t(f"ℹ️ التذكرة #{r.id} أصبحت: {'مغلقة' if act == 'cl' else 'مفتوحة'}",
                                   f"ℹ️ Ticket #{r.id} is now {'closed' if act == 'cl' else 'open'}"), chat_id=other)
                except TelegramError:
                    pass
            await c.edit(self.render(c, r), self.view_kb(c, r))

    async def msg(self, c: Ctx) -> bool:
        st, t = c.st, c.t
        if not st:
            return False
        if st["k"] == "tk_subject":
            c.set_state("tk_body", subject=c.text[:80] or "—")
            await c.send(t("📝 الآن اشرح المشكلة بالتفصيل في رسالة واحدة.", "📝 Now describe the issue in one message."))
        elif st["k"] == "tk_body":
            c.clear_state()
            d = {"subject": st["subject"], "name": c.user.full_name, "msgs": [{"by": "u", "text": c.text[:1500]}]}
            rid = await c.rec_add("ticket", d, status="open")
            await c.send(t(f"✅ فُتحت التذكرة #{rid}. سنرد عليك هنا.", f"✅ Ticket #{rid} opened. We'll reply here."), kb([c.home_row()]))
            await c.notify_owner(t(f"🔔 <b>تذكرة جديدة #{rid}</b>\n👤 {c.name} (<code>{c.uid}</code>)\n📌 {esc(st['subject'])}\n\n{esc(c.text[:1500])}",
                                   f"🔔 <b>New ticket #{rid}</b>\n👤 {c.name} (<code>{c.uid}</code>)\n📌 {esc(st['subject'])}\n\n{esc(c.text[:1500])}"),
                                 kb([[B(t("↩️ رد", "↩️ Reply"), f"t:re:{rid}"), B(t("👁 عرض", "👁 View"), f"t:v:{rid}")]]))
        elif st["k"] == "tk_reply":
            c.clear_state()
            r = await c.rec_get(st["rid"])
            if r is None or not (c.is_owner or r.user_id == c.uid):
                return True
            staff = c.is_owner and r.user_id != c.uid
            d = dict(r.data)
            d["msgs"] = list(d["msgs"]) + [{"by": "s" if staff else "u", "text": c.text[:1500]}]
            await c.rec_update(r.id, data=d, status="open")
            await c.send(t("✅ أُرسل ردّك.", "✅ Reply sent."), kb([[B(t("👁 عرض التذكرة", "👁 View ticket"), f"t:v:{r.id}")]]))
            try:
                await c.send((t(f"🛟 <b>رد الدعم على تذكرتك #{r.id}</b>", f"🛟 <b>Support replied to ticket #{r.id}</b>") if staff else
                              t(f"👤 <b>رد جديد على التذكرة #{r.id}</b>", f"👤 <b>New reply on ticket #{r.id}</b>")) + f"\n\n{esc(c.text[:1500])}",
                             kb([[B(t("↩️ رد", "↩️ Reply"), f"t:re:{r.id}"), B(t("👁 عرض", "👁 View"), f"t:v:{r.id}")]]),
                             chat_id=r.user_id if staff else c.owner_id)
            except TelegramError:
                pass
        else:
            return False
        return True


TPL = Tickets()
