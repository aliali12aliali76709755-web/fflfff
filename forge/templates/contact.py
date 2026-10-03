"""بوت التواصل: استقبل رسائل المستخدمين وردّ عليهم مباشرة."""
from telegram.error import TelegramError

from .. import db
from ..ctx import Ctx
from ..ui import B, kb
from . import Tpl
from ._util import bump


class Contact(Tpl):
    emoji, ar, en = "📞", "بوت التواصل", "Contact bot"
    d_ar, d_en = "استقبل رسائل المستخدمين وردّ عليهم مباشرة.", "Receive users' messages and reply to them directly."
    cats = ("top",)
    guide_ar = ("كل رسالة يرسلها المستخدم تصلك هنا مع اسمه ورقمه.\n\n"
                "<b>للرد:</b> اضغط مطوّلاً على رسالة العضو واختر «رد»، ثم اكتب ردّك، أو اضغط زر «↩️ رد».\n"
                "يدعم النص والصور والفيديو والملفات والبصمات.\nمن «رسالة الاستلام» تغيّر النص الذي يراه المستخدم بعد إرسال رسالته.")

    async def home(self, c: Ctx) -> None:
        txt = await c.kv("contact:intro") or c.t("👋 أهلاً بك!\n\n✍️ أرسل رسالتك هنا وسيصلك الرد في أقرب وقت.",
                                                 "👋 Welcome!\n\n✍️ Send your message here and you'll get a reply soon.")
        await c.edit(txt, kb([c.tail()]))

    async def owner(self, c: Ctx):
        n = await c.kv("contact:count", 0)
        return (c.t(f"📩 الرسائل المستلمة: {n}\n\nللرد على عضو: اضغط مطوّلاً على رسالته واختر «رد»، أو استخدم زر الرد تحت رسالة المستخدم.",
                    f"📩 Messages received: {n}\n\nTo answer: reply to the user's message."),
                [[B(c.t("✏️ رسالة البداية", "✏️ Intro text"), "t:set:intro"), B(c.t("✅ رسالة الاستلام", "✅ Receipt text"), "t:set:ack")]])

    async def cb(self, c: Ctx, a: list[str]) -> None:
        if not c.is_owner:
            return
        if a[0] == "set":
            c.set_state("contact_set", field=a[1])
            await c.edit(c.t("✍️ أرسل النص الجديد.\n\n/cancel للإلغاء", "✍️ Send the new text.\n\n/cancel to abort"),
                         kb([[B(c.t("❌ إلغاء", "❌ Cancel"), "o:home")]]))
        elif a[0] == "rp":
            c.set_state("contact_reply", uid=int(a[1]))
            await c.send(c.t("✍️ اكتب ردّك الآن (أي نوع رسالة).", "✍️ Write your reply now (any message type)."))
        elif a[0] == "bn":
            async with db.Session() as s:
                row = await s.get(db.BUser, (c.bot_id, int(a[1])))
                if row is not None:
                    row.banned = not row.banned
                    await s.commit()
                    await c.answer(c.t("🚫 تم الحظر" if row.banned else "✅ أُلغي الحظر",
                                       "🚫 Banned" if row.banned else "✅ Unbanned"), True)

    async def _deliver(self, c: Ctx, uid: int) -> None:
        try:
            await c.copy_to(uid, c.chat.id, c.msg.message_id)
            await c.send(c.t("✅ أُرسل الرد.", "✅ Reply sent."))
        except TelegramError:
            await c.send(c.t("⚠️ تعذّر الإرسال (ربما حظر المستخدم البوت).", "⚠️ Couldn't deliver (the user may have blocked the bot)."))

    async def msg(self, c: Ctx) -> bool:
        st = c.st
        if c.is_owner:
            if st and st["k"] == "contact_set":
                await c.kv_set(f"contact:{st['field']}", c.msg.text_html or "")
                c.clear_state()
                await c.send(c.t("✅ تم الحفظ.", "✅ Saved."), kb([c.home_row()]))
                return True
            if st and st["k"] == "contact_reply":
                c.clear_state()
                await self._deliver(c, st["uid"])
                return True
            rt = c.msg.reply_to_message
            if rt is not None:
                uid = c.x.bot_data.setdefault("contact_map", {}).get(rt.message_id)
                if uid:
                    await self._deliver(c, uid)
                    return True
            return False
        head = c.t(f"📩 رسالة من {c.name}", f"📩 Message from {c.name}") + f" (<code>{c.uid}</code>)" + (
            f" @{c.user.username}" if c.user.username else "")
        btns = kb([[B(c.t("↩️ رد", "↩️ Reply"), f"t:rp:{c.uid}"), B(c.t("🚫 حظر/إلغاء", "🚫 Ban/unban"), f"t:bn:{c.uid}")]])
        try:
            await c.bot.send_message(c.owner_id, head, parse_mode="HTML")
            m = await c.bot.copy_message(c.owner_id, c.chat.id, c.msg.message_id, reply_markup=btns)
        except TelegramError:
            await c.send(c.t("⚠️ تعذّر إيصال رسالتك حالياً.", "⚠️ Your message couldn't be delivered right now."))
            return True
        cmap = c.x.bot_data.setdefault("contact_map", {})
        cmap[m.message_id] = c.uid
        if len(cmap) > 3000:
            for k in list(cmap)[:1000]:
                cmap.pop(k, None)
        await bump(c, "contact:count")
        await c.send(await c.kv("contact:ack") or c.t("✅ وصلت رسالتك، سنرد عليك قريباً.", "✅ Message received, we'll reply soon."))
        return True


TPL = Contact()
