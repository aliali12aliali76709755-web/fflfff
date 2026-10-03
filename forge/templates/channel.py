"""إدارة قناة: ربط القنوات، نشر فوري أو مجدول بأزرار، وعرض المنشورات المجدولة."""
import datetime as dt
import logging
import re

from telegram.error import TelegramError

from .. import db, ui
from .. import plat
from ..child import buttons_kb, parse_buttons
from ..ctx import Ctx
from ..ui import B, esc, kb
from . import Tpl

log = logging.getLogger("forge.channel")


async def _publish(context) -> None:
    bot_id, rid = context.bot_data["bot_id"], context.job.data
    if plat.admin_lock(context.bot_data) is not None:      # البوت مغلق من الإدارة: لا مهام مجدولة
        return
    r = await db.rec_get(bot_id, rid)
    if r is None or r.status != "wait":
        return
    d = r.data
    try:
        await context.bot.copy_message(d["to"], d["chat"], d["mid"], reply_markup=buttons_kb(d.get("btn") or []))
        await db.rec_update(bot_id, rid, status="sent")
    except TelegramError as e:
        await db.rec_update(bot_id, rid, status="fail")
        try:
            await context.bot.send_message(context.bot_data["owner_id"], f"⚠️ فشل نشر المنشور المجدول #{rid}: {e}")
        except TelegramError:
            pass


class Channel(Tpl):
    emoji, ar, en = "📢", "إدارة قناة", "Channel manager"
    d_ar, d_en = "أدوات خفيفة لإدارة القنوات", "Light tools for managing channels"
    cats = ("biz",)
    guide_ar = ("1. أضف البوت مشرفاً في قناتك بصلاحية النشر، ثم «➕ ربط قناة» وأرسل معرّفها.\n"
                "2. «📝 منشور جديد»: أرسل المحتوى، ثم الأزرار (أو 0)، ثم اختر القناة.\n"
                "3. انشر فوراً أو جدوِل: أرسل الوقت مثل <code>2026-01-31 18:30</code> أو <code>+90</code> (بعد 90 دقيقة). التوقيت حسب فرق التوقيت الذي تضبطه.\n"
                "4. من «🗓 المجدولة» ترى المنشورات المنتظرة وتلغيها.\n\nاللوحة للمالك والمشرفين فقط.")

    def setup(self, app) -> None:
        if app.job_queue is not None:
            app.job_queue.run_once(self._reload, 5, name="chan_reload")

    async def _reload(self, context) -> None:
        bot_id = context.bot_data["bot_id"]
        now = dt.datetime.utcnow()
        for r in await db.rec_list(bot_id, "sched", status="wait", limit=500):
            at = dt.datetime.fromisoformat(r.data["at"])
            context.job_queue.run_once(_publish, max(1.0, (at - now).total_seconds()), data=r.id, name=f"sched{r.id}")

    async def chans(self, c: Ctx) -> list[dict]:
        return await c.kv("chan:list", [])

    async def home(self, c: Ctx) -> None:
        if not c.is_owner:
            await c.edit(c.t("📢 هذا بوت إدارة خاص بمالك القناة.", "📢 This is a private management bot for the channel owner."))
            return
        from ..child import owner_home
        await owner_home(c)

    async def owner(self, c: Ctx):
        ch, n = await self.chans(c), await c.rec_count("sched", status="wait")
        tz = await c.kv("chan:tz", 3)
        names = "، ".join(esc(x["title"]) for x in ch) or c.t("لا توجد", "none")
        return (c.t(f"📢 القنوات: {names}\n🗓 منشورات مجدولة: {n}\n🕒 التوقيت: UTC{tz:+g}", f"📢 Channels: {names}\n🗓 Scheduled posts: {n}\n🕒 Timezone: UTC{tz:+g}"),
                [[B(c.t("📝 منشور جديد", "📝 New post"), "t:new", style="success")],
                 [B(c.t("➕ ربط قناة", "➕ Link channel"), "t:add"), B(c.t("📋 القنوات", "📋 Channels"), "t:list")],
                 [B(c.t(f"🗓 المجدولة ({n})", f"🗓 Scheduled ({n})"), "t:sch"), B(c.t("🕒 فرق التوقيت", "🕒 Timezone"), "t:tz")]])

    async def cb(self, c: Ctx, a: list[str]) -> None:  # noqa: C901
        if not c.is_owner:
            return
        act, t = a[0], c.t
        cancel = kb([[B(t("❌ إلغاء", "❌ Cancel"), "o:home")]])
        if act == "add":
            c.set_state("chan_add")
            await c.edit(t("➕ أضف البوت مشرفاً في القناة ثم أرسل معرّفها (@channel) أو حوّل منشوراً منها.\n\n/cancel للإلغاء",
                           "➕ Make the bot an admin of the channel, then send its @username or forward a post.\n\n/cancel to abort"), cancel)
        elif act == "list":
            ch = await self.chans(c)
            lines = []
            for x in ch:
                try:
                    n = await c.bot.get_chat_member_count(x["id"])
                except TelegramError:
                    n = "?"
                lines.append(f"• <b>{esc(x['title'])}</b> — 👥 {n}")
            rows = [[B(f"🗑 {x['title']}"[:40], f"t:rm:{i}")] for i, x in enumerate(ch)]
            await c.edit(ui.head(t("📋 القنوات المربوطة", "📋 Linked channels")) + "\n" + ("\n".join(lines) or t("لا توجد قنوات.", "No channels.")),
                         kb(rows + [[B(t("🎛 غرفة التحكم", "🎛 Control room"), "o:home")]]))
        elif act == "rm":
            ch = await self.chans(c)
            if int(a[1]) < len(ch):
                ch.pop(int(a[1]))
                await c.kv_set("chan:list", ch)
            await self.cb(c, ["list"])
        elif act == "tz":
            c.set_state("chan_tz")
            await c.edit(t("🕒 أرسل فرق التوقيت عن UTC (مثلاً 3 لسوريا وتركيا).", "🕒 Send your UTC offset (e.g. 3)."), cancel)
        elif act == "new":
            if not await self.chans(c):
                await c.answer(t("اربط قناة أولاً.", "Link a channel first."), True)
                return
            c.set_state("chan_content")
            await c.edit(t("📝 أرسل محتوى المنشور (نص، صورة، فيديو أو ملف).\n\n/cancel للإلغاء", "📝 Send the post content (text, photo, video or file).\n\n/cancel to abort"), cancel)
        elif act == "to":
            post = c.x.user_data.get("chan_post")
            ch = await self.chans(c)
            if not post or int(a[1]) >= len(ch):
                return
            post["to"], post["title"] = ch[int(a[1])]["id"], ch[int(a[1])]["title"]
            await c.edit(t(f"📢 القناة: <b>{esc(post['title'])}</b>\n\nمتى تريد النشر؟", f"📢 Channel: <b>{esc(post['title'])}</b>\n\nWhen should it go out?"),
                         kb([[B(t("🚀 انشر الآن", "🚀 Publish now"), "t:now", style="success")], [B(t("🗓 جدولة", "🗓 Schedule"), "t:when")], [B(t("❌ إلغاء", "❌ Cancel"), "o:home")]]))
        elif act == "now":
            post = c.x.user_data.pop("chan_post", None)
            if not post:
                return
            try:
                await c.bot.copy_message(post["to"], post["chat"], post["mid"], reply_markup=buttons_kb(post["btn"]))
                await c.edit(t(f"✅ نُشر في {esc(post['title'])}.", f"✅ Published to {esc(post['title'])}."), kb([[B(t("🎛 غرفة التحكم", "🎛 Control room"), "o:home")]]))
            except TelegramError as e:
                await c.edit(t(f"⚠️ تعذّر النشر: {esc(e)}", f"⚠️ Publishing failed: {esc(e)}"), kb([[B(t("🎛 غرفة التحكم", "🎛 Control room"), "o:home")]]))
        elif act == "when":
            c.set_state("chan_when")
            await c.edit(t("🗓 أرسل وقت النشر:\n<code>2026-01-31 18:30</code>\nأو <code>+90</code> للنشر بعد 90 دقيقة.", "🗓 Send the publish time:\n<code>2026-01-31 18:30</code>\nor <code>+90</code> for 90 minutes from now."), cancel)
        elif act == "sch":
            recs = await c.rec_list("sched", status="wait", limit=15, newest=False)
            tz = float(await c.kv("chan:tz", 3))
            lines = [f"#{r.id} · {(dt.datetime.fromisoformat(r.data['at']) + dt.timedelta(hours=tz)):%Y-%m-%d %H:%M} → {esc(r.data['title'])}" for r in recs]
            rows = [[B(t(f"🗑 إلغاء #{r.id}", f"🗑 Cancel #{r.id}"), f"t:del:{r.id}")] for r in recs]
            await c.edit(ui.head(t("🗓 المنشورات المجدولة", "🗓 Scheduled posts")) + "\n" + ("\n".join(lines) or t("لا توجد منشورات مجدولة.", "Nothing scheduled.")),
                         kb(rows + [[B(t("🎛 غرفة التحكم", "🎛 Control room"), "o:home")]]))
        elif act == "del":
            await c.rec_update(int(a[1]), status="cancel")
            for j in c.x.job_queue.get_jobs_by_name(f"sched{a[1]}") if c.x.job_queue else []:
                j.schedule_removal()
            await self.cb(c, ["sch"])

    async def msg(self, c: Ctx) -> bool:
        st, t = c.st, c.t
        if not (st and c.is_owner):
            if not c.is_owner:
                await self.home(c)
                return True
            return False
        k = st["k"]
        if k == "chan_add":
            origin = getattr(c.msg, "forward_origin", None)
            ref = origin.chat.id if origin is not None and getattr(origin, "chat", None) else (
                int(c.text) if c.text.lstrip("-").isdigit() else (c.text if c.text.startswith("@") else "@" + c.text.rsplit("/", 1)[-1]))
            try:
                chat = await c.bot.get_chat(ref)
                me = await c.bot.get_chat_member(chat.id, c.bot.id)
                assert me.status in ("administrator", "creator")
            except Exception:
                await c.send(t("⚠️ لم أستطع الوصول. تأكد أن البوت مشرف في القناة.", "⚠️ Couldn't access it. Make sure the bot is an admin there."))
                return True
            ch = [x for x in await self.chans(c) if x["id"] != chat.id] + [{"id": chat.id, "title": chat.title or str(ref)}]
            await c.kv_set("chan:list", ch)
            c.clear_state()
            await c.send(t(f"✅ رُبطت القناة: {esc(chat.title)}", f"✅ Linked: {esc(chat.title)}"), kb([c.home_row()]))
        elif k == "chan_tz":
            try:
                await c.kv_set("chan:tz", float(c.text.replace("+", "")))
            except ValueError:
                await c.send(t("أرسل رقماً مثل 3.", "Send a number like 3."))
                return True
            c.clear_state()
            await c.send(t("✅ تم الحفظ.", "✅ Saved."), kb([c.home_row()]))
        elif k == "chan_content":
            c.x.user_data["chan_post"] = {"chat": c.chat.id, "mid": c.msg.message_id, "btn": []}
            c.set_state("chan_btn")
            await c.send(t("🔗 أرسل الأزرار (<code>نص - رابط</code>، كل سطر صف) أو <code>0</code> بلا أزرار.", "🔗 Send buttons (<code>text - link</code>, one row per line) or <code>0</code> for none."))
        elif k == "chan_btn":
            post = c.x.user_data.get("chan_post")
            if not post:
                c.clear_state()
                return True
            post["btn"] = [] if c.text.strip() == "0" else parse_buttons(c.text)
            c.clear_state()
            ch = await self.chans(c)
            await c.copy_to(c.chat.id, post["chat"], post["mid"], buttons_kb(post["btn"]))
            await c.send(t("☝️ المعاينة. اختر القناة:", "☝️ Preview. Choose the channel:"), kb([[B(x["title"][:40], f"t:to:{i}")] for i, x in enumerate(ch)]))
        elif k == "chan_when":
            post = c.x.user_data.get("chan_post")
            tz = float(await c.kv("chan:tz", 3))
            now = dt.datetime.utcnow()
            txt = c.text.strip()
            try:
                if re.fullmatch(r"\+\d{1,5}", txt):
                    at = now + dt.timedelta(minutes=int(txt[1:]))
                else:
                    at = dt.datetime.strptime(txt, "%Y-%m-%d %H:%M") - dt.timedelta(hours=tz)
                assert at > now and post
            except Exception:
                await c.send(t("⚠️ وقت غير صالح أو في الماضي. مثال: <code>2026-01-31 18:30</code> أو <code>+90</code>", "⚠️ Invalid or past time. Example: <code>2026-01-31 18:30</code> or <code>+90</code>"))
                return True
            c.clear_state()
            c.x.user_data.pop("chan_post", None)
            rid = await c.rec_add("sched", dict(post, at=at.isoformat()), status="wait")
            if c.x.job_queue is not None:
                c.x.job_queue.run_once(_publish, (at - now).total_seconds(), data=rid, name=f"sched{rid}")
            await c.send(t(f"🗓 جُدول المنشور #{rid} في {(at + dt.timedelta(hours=tz)):%Y-%m-%d %H:%M} على {esc(post['title'])}.",
                           f"🗓 Post #{rid} scheduled for {(at + dt.timedelta(hours=tz)):%Y-%m-%d %H:%M} on {esc(post['title'])}."), kb([c.home_row()]))
        else:
            return False
        return True


TPL = Channel()
