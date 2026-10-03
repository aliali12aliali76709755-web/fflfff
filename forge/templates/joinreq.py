"""طلبات الانضمام: قبول تلقائي أو يدوي لطلبات القنوات والمجموعات مع رسالة ترحيب مخصصة."""
from telegram.error import TelegramError

from .. import ui
from ..ctx import Ctx
from ..ui import B, esc, kb
from . import Tpl
from ._util import bump


class JoinReq(Tpl):
    emoji, ar, en = "📨", "طلبات الانضمام", "Join requests"
    d_ar, d_en = "قبول تلقائي/يدوي + رسالة ترحيب مخصّصة", "Auto/manual approval + custom welcome message"
    cats = ("top", "community")
    guide_ar = ("1. في قناتك أو مجموعتك أنشئ رابط دعوة مع تفعيل «طلب الموافقة على الانضمام».\n"
                "2. أضف هذا البوت مشرفاً بصلاحية «إضافة أعضاء/الموافقة على الطلبات».\n"
                "3. اختر الوضع: <b>تلقائي</b> يقبل كل طلب فوراً، أو <b>يدوي</b> يرسل لك كل طلب بزرّي قبول ورفض.\n"
                "4. اكتب رسالة الترحيب التي تصل للعضو في الخاص عند قبوله. استخدم {name} لاسم العضو و{chat} لاسم القناة.")

    async def cfg(self, c: Ctx) -> dict:
        return {"mode": "auto", "welcome": "", **(await c.kv("joinreq:cfg", {}) or {})}

    async def home(self, c: Ctx) -> None:
        await c.edit(ui.head(c.brand) + "\n" + c.t(
            "هذا البوت يدير طلبات الانضمام للقناة. إذا أرسلت طلب انضمام فسيصلك الرد هنا.",
            "This bot manages join requests. If you requested to join, you'll get the answer here."), kb([c.tail()]))

    async def owner(self, c: Ctx):
        cfg = await self.cfg(c)
        ok, pen = await c.kv("joinreq:ok", 0), await c.rec_count("jr", status="pending")
        mode = c.t("🟢 تلقائي", "🟢 Automatic") if cfg["mode"] == "auto" else c.t("✋ يدوي", "✋ Manual")
        return (c.t(f"⚙️ الوضع: {mode}\n✅ طلبات قُبلت: {ok}\n🕒 تنتظر: {pen}\n\nأضف البوت مشرفاً في القناة بصلاحية الموافقة على الطلبات.",
                    f"⚙️ Mode: {mode}\n✅ Approved: {ok}\n🕒 Pending: {pen}\n\nMake the bot an admin with rights to approve requests."),
                [[B(c.t("🔁 تبديل الوضع (تلقائي/يدوي)", "🔁 Toggle mode (auto/manual)"), "t:mode")],
                 [B(c.t("✏️ رسالة الترحيب", "✏️ Welcome message"), "t:wel"), B(c.t(f"🕒 الطلبات ({pen})", f"🕒 Requests ({pen})"), "t:list")],
                 [B(c.t("✅ قبول كل المنتظرين", "✅ Approve all pending"), "t:all")]])

    async def _approve(self, c: Ctx, chat_id: int, uid: int, title: str, name: str) -> bool:
        try:
            await c.bot.approve_chat_join_request(chat_id, uid)
        except TelegramError:
            return False
        await bump(c, "joinreq:ok")
        cfg = await self.cfg(c)
        text = (cfg["welcome"] or c.t("🎉 أهلاً {name}! تم قبول طلب انضمامك إلى {chat}.", "🎉 Welcome {name}! Your request to join {chat} was approved."))
        try:
            await c.send(text.replace("{name}", esc(name)).replace("{chat}", esc(title)), chat_id=uid)
        except TelegramError:
            pass
        return True

    async def join_request(self, c: Ctx) -> None:
        jr = c.u.chat_join_request
        cfg = await self.cfg(c)
        name, title = jr.from_user.full_name, jr.chat.title or ""
        if cfg["mode"] == "auto":
            await self._approve(c, jr.chat.id, jr.from_user.id, title, name)
            return
        rid = await c.rec_add("jr", {"chat": jr.chat.id, "title": title, "name": name}, status="pending", user_id=jr.from_user.id)
        await c.notify_owner(c.t(f"📨 <b>طلب انضمام</b>\n👤 {esc(name)} (<code>{jr.from_user.id}</code>)\n📢 {esc(title)}",
                                 f"📨 <b>Join request</b>\n👤 {esc(name)} (<code>{jr.from_user.id}</code>)\n📢 {esc(title)}"),
                             kb([[B(c.t("✅ قبول", "✅ Approve"), f"t:ok:{rid}", style="success"), B(c.t("❌ رفض", "❌ Decline"), f"t:no:{rid}", style="danger")]]))

    async def cb(self, c: Ctx, a: list[str]) -> None:
        if not c.is_owner:
            return
        act, t = a[0], c.t
        if act == "mode":
            cfg = await self.cfg(c)
            cfg["mode"] = "manual" if cfg["mode"] == "auto" else "auto"
            await c.kv_set("joinreq:cfg", cfg)
            from ..child import owner_home
            await owner_home(c)
        elif act == "wel":
            c.set_state("jr_wel")
            await c.edit(t("✏️ أرسل رسالة الترحيب. يمكنك استخدام {name} و {chat}.\n\n/cancel للإلغاء",
                           "✏️ Send the welcome message. You may use {name} and {chat}.\n\n/cancel to abort"), kb([[B(t("❌ إلغاء", "❌ Cancel"), "o:home")]]))
        elif act == "list":
            recs = await c.rec_list("jr", status="pending", limit=10)
            rows = [[B(f"✅ {r.data['name']}"[:30], f"t:ok:{r.id}"), B("❌", f"t:no:{r.id}")] for r in recs]
            await c.edit(ui.head(t("🕒 طلبات تنتظر", "🕒 Pending requests")) + ("" if recs else "\n" + t("لا توجد طلبات.", "No requests.")),
                         kb(rows + [[B(t("🎛 غرفة التحكم", "🎛 Control room"), "o:home")]]))
        elif act == "all":
            n = 0
            for r in await c.rec_list("jr", status="pending", limit=500):
                if await self._approve(c, r.data["chat"], r.user_id, r.data["title"], r.data["name"]):
                    n += 1
                await c.rec_update(r.id, status="ok")
            await c.answer(t(f"✅ قُبل {n} طلب.", f"✅ Approved {n}."), True)
        elif act in ("ok", "no"):
            r = await c.rec_get(int(a[1]))
            if r is None or r.status != "pending":
                await c.answer(t("عولج من قبل", "Already handled"), True)
                return
            if act == "ok":
                done = await self._approve(c, r.data["chat"], r.user_id, r.data["title"], r.data["name"])
            else:
                try:
                    await c.bot.decline_chat_join_request(r.data["chat"], r.user_id)
                    done = True
                except TelegramError:
                    done = False
            await c.rec_update(r.id, status=act)
            await c.edit((t("✅ قُبل", "✅ Approved") if act == "ok" else t("❌ رُفض", "❌ Declined")) + f": {esc(r.data['name'])}"
                         + ("" if done else t("\n⚠️ تعذّر التنفيذ (ربما سُحب الطلب).", "\n⚠️ Couldn't apply (request may be gone).")))

    async def msg(self, c: Ctx) -> bool:
        st = c.st
        if st and st["k"] == "jr_wel" and c.is_owner:
            cfg = await self.cfg(c)
            cfg["welcome"] = c.msg.text_html or ""
            await c.kv_set("joinreq:cfg", cfg)
            c.clear_state()
            await c.send(c.t("✅ تم الحفظ.", "✅ Saved."), kb([c.home_row()]))
            return True
        return False


TPL = JoinReq()
