"""صارحني: استقبل رسائل مجهولة عبر رابط شخصي."""
from urllib.parse import quote

from telegram.error import TelegramError

from .. import ui
from ..ctx import Ctx
from ..ui import B, kb
from . import Tpl
from ._util import bump


class Sarahah(Tpl):
    emoji, ar, en = "🎭", "صارحني", "Anonymous messages"
    d_ar, d_en = "استقبل رسائل مجهولة", "Receive anonymous messages"
    guide_ar = ("كل مستخدم يحصل على رابط خاص به. من يفتح الرابط يكتب رسالة تصل لصاحب الرابط دون كشف هوية المرسل، "
                "ويستطيع صاحب الرابط الرد عليها بشكل مجهول أيضاً. لا يحتاج القالب أي إعداد من المالك.")

    async def home(self, c: Ctx) -> None:
        link = c.link(f"u{c.uid}")
        n = await c.rec_count("sar", user_id=c.uid)
        share = f"https://t.me/share/url?url={quote(link)}&text={quote(c.t('صارحني برسالة مجهولة 🎭', 'Send me an anonymous message 🎭'))}"
        await c.edit(ui.head(c.t("🎭 صارحني", "🎭 Anonymous messages")) + "\n" + c.t(
            f"هذا رابطك الخاص. شاركه مع أصدقائك لتصلك رسائلهم دون أن تعرف من أرسلها:\n\n<code>{link}</code>\n\n📥 رسائل وصلتك: {n}",
            f"This is your personal link. Share it to receive messages without knowing the sender:\n\n<code>{link}</code>\n\n📥 Messages received: {n}"),
            kb([[B(c.t("📤 مشاركة الرابط", "📤 Share link"), url=share)], c.tail()]))

    async def owner(self, c: Ctx):
        n = await c.kv("sar:count", 0)
        return c.t(f"💌 إجمالي الرسائل المجهولة: {n}", f"💌 Anonymous messages: {n}"), []

    async def start_param(self, c: Ctx, param: str) -> bool:
        if not (param.startswith("u") and param[1:].isdigit()):
            return False
        target = int(param[1:])
        if target == c.uid:
            await self.home(c)
            return True
        c.set_state("sar", to=target)
        await c.send(c.t("✍️ اكتب الآن رسالتك المجهولة (نص أو صورة أو بصمة).\nلن يعرف المستلم من أنت.\n\n/cancel للإلغاء",
                         "✍️ Write your anonymous message now (text, photo or voice).\nThe recipient won't know who you are.\n\n/cancel to abort"))
        return True

    async def cb(self, c: Ctx, a: list[str]) -> None:
        if a[0] == "re":
            rec = await c.rec_get(int(a[1]))
            if rec is None or rec.user_id != c.uid:
                return await c.answer(c.t("غير متاح", "Unavailable"), True)
            c.set_state("sar_re", rid=rec.id)
            await c.send(c.t("↩️ اكتب ردّك، وسيصل للمرسل دون أن تعرف هويته.", "↩️ Write your reply; it reaches the sender anonymously."))
        elif a[0] == "again":
            c.set_state("sar", to=int(a[1]))
            await c.send(c.t("✍️ اكتب رسالتك.", "✍️ Write your message."))

    async def msg(self, c: Ctx) -> bool:
        st = c.st
        if not st or st["k"] not in ("sar", "sar_re"):
            await self.home(c)
            return True
        c.clear_state()
        try:
            if st["k"] == "sar":
                rid = await c.rec_add("sar", {"from": c.uid}, user_id=st["to"])
                await c.send(c.t("📩 <b>وصلتك رسالة مجهولة:</b>", "📩 <b>You got an anonymous message:</b>"), chat_id=st["to"])
                await c.copy_to(st["to"], c.chat.id, c.msg.message_id, kb([[B(c.t("↩️ رد", "↩️ Reply"), f"t:re:{rid}")]]))
                await bump(c, "sar:count")
                await c.send(c.t("✅ أُرسلت رسالتك بشكل مجهول.", "✅ Your message was sent anonymously."),
                             kb([[B(c.t("✍️ رسالة أخرى", "✍️ Another message"), f"t:again:{st['to']}")],
                                 [B(c.t("🔗 أريد رابطي الخاص", "🔗 Get my own link"), "t:home")]]))
            else:
                rec = await c.rec_get(st["rid"])
                await c.send(c.t("↩️ <b>وصلك رد على رسالتك المجهولة:</b>", "↩️ <b>You got a reply to your anonymous message:</b>"),
                             chat_id=rec.data["from"])
                await c.copy_to(rec.data["from"], c.chat.id, c.msg.message_id)
                await c.send(c.t("✅ أُرسل ردّك.", "✅ Reply sent."))
        except TelegramError:
            await c.send(c.t("⚠️ تعذّر الإرسال: المستلم لم يفتح البوت أو حظره.",
                             "⚠️ Couldn't deliver: the recipient hasn't started the bot or blocked it."))
        return True


TPL = Sarahah()
