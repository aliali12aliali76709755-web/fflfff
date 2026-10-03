"""إنشاء منشور: منشورات بوسائط وأزرار شفافة للنشر السريع في القنوات."""
from telegram.error import TelegramError

from .. import ui
from ..child import buttons_kb, parse_buttons
from ..ctx import Ctx
from ..ui import B, esc, kb
from . import Tpl
from ._util import bump


class Post(Tpl):
    emoji, ar, en = "📨", "إنشاء منشور", "Post creator"
    d_ar, d_en = "أنشئ منشورات بوسائط وأزرار شفافة للنشر السريع", "Create posts with media and inline buttons for quick publishing"
    cats = ("top", "community")
    guide_ar = ("يرسل المستخدم محتوى المنشور ثم الأزرار بصيغة <code>نص - رابط</code>، فيحصل على منشور جاهز يستطيع تحويله "
                "أو نشره مباشرة في قناته.\n\nللنشر المباشر يجب أن يكون هذا البوت مشرفاً في القناة، وأن يكون المستخدم نفسه مشرفاً فيها.")

    async def home(self, c: Ctx) -> None:
        c.set_state("post_content")
        await c.edit(ui.head(c.t("📨 إنشاء منشور", "📨 Post creator")) + "\n" + c.t(
            "1️⃣ أرسل الآن محتوى المنشور: نص، صورة، فيديو أو ملف مع تعليق.",
            "1️⃣ Send the post content now: text, photo, video or file with caption."), kb([c.tail()]))

    async def owner(self, c: Ctx):
        n = await c.kv("post:count", 0)
        return c.t(f"📨 منشورات أُنشئت: {n}", f"📨 Posts created: {n}"), []

    async def cb(self, c: Ctx, a: list[str]) -> None:
        if a[0] == "pub":
            if "post" not in c.x.user_data:
                await c.answer(c.t("أنشئ منشوراً أولاً.", "Create a post first."), True)
                return
            c.set_state("post_chan")
            await c.send(c.t("📢 أرسل معرّف القناة مثل <code>@mychannel</code>.\nيجب أن أكون مشرفاً فيها وأن تكون أنت مشرفاً أيضاً.",
                             "📢 Send the channel username like <code>@mychannel</code>.\nBoth the bot and you must be admins there."))

    async def msg(self, c: Ctx) -> bool:
        st = c.st
        k = st["k"] if st else "post_content"
        if k == "post_content":
            c.x.user_data["post"] = {"chat": c.chat.id, "mid": c.msg.message_id, "btn": []}
            c.set_state("post_buttons")
            await c.send(c.t(
                "2️⃣ أرسل الأزرار، كل سطر صف:\n<code>نص الزر - https://example.com</code>\nزرّان في صف: افصل بينهما بـ <code>&amp;&amp;</code>\n\n"
                "أو أرسل <code>0</code> لمنشور بلا أزرار.",
                "2️⃣ Send the buttons, one row per line:\n<code>Button text - https://example.com</code>\nTwo in a row: separate with <code>&amp;&amp;</code>\n\n"
                "Or send <code>0</code> for no buttons."))
        elif k == "post_buttons":
            post = c.x.user_data.get("post")
            if not post:
                return False
            post["btn"] = [] if c.text.strip() == "0" else parse_buttons(c.text)
            if c.text.strip() != "0" and not post["btn"]:
                await c.send(c.t("⚠️ لم أفهم الأزرار. الصيغة: <code>نص - رابط</code>", "⚠️ Couldn't parse. Format: <code>text - link</code>"))
                return True
            c.clear_state()
            await c.copy_to(c.chat.id, post["chat"], post["mid"], buttons_kb(post["btn"]))
            await bump(c, "post:count")
            await c.send(c.t("☝️ منشورك جاهز. حوّله لأي مكان، أو انشره مباشرة في قناتك.",
                             "☝️ Your post is ready. Forward it anywhere, or publish it to your channel."),
                         kb([[B(c.t("📢 نشر في قناة", "📢 Publish to channel"), "t:pub")], [B(c.t("🔁 منشور جديد", "🔁 New post"), "t:home")]]))
        elif k == "post_chan":
            post = c.x.user_data.get("post")
            ref = c.text.strip()
            ref = ref if ref.startswith("@") or ref.lstrip("-").isdigit() else "@" + ref.rsplit("/", 1)[-1]
            try:
                chat = await c.bot.get_chat(int(ref) if ref.lstrip("-").isdigit() else ref)
                who = await c.bot.get_chat_member(chat.id, c.uid)
                if who.status not in ("administrator", "creator"):
                    await c.send(c.t("⚠️ يجب أن تكون مشرفاً في هذه القناة.", "⚠️ You must be an admin of that channel."))
                    return True
                await c.bot.copy_message(chat.id, post["chat"], post["mid"], reply_markup=buttons_kb(post["btn"]))
            except TelegramError:
                await c.send(c.t("⚠️ تعذّر النشر. تأكد أن البوت مشرف في القناة وله صلاحية النشر.",
                                 "⚠️ Publishing failed. Make sure the bot is an admin with posting rights."))
                return True
            c.clear_state()
            await c.send(c.t(f"✅ نُشر في {esc(chat.title)}.", f"✅ Published to {esc(chat.title)}."),
                         kb([[B(c.t("🔁 منشور جديد", "🔁 New post"), "t:home")]]))
        else:
            return False
        return True


TPL = Post()
