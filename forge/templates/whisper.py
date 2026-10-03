"""همسة: رسائل سرية في المجموعات والقنوات لا يقرؤها إلا المستلم (نص عبر الوضع المضمّن، وملفات عبر رابط)."""
import hashlib
import re

from telegram import InlineQueryResultArticle, InputTextMessageContent
from telegram.error import TelegramError

from .. import ui
from ..ctx import Ctx
from ..ui import B, esc, kb
from . import Tpl
from ._util import bump

TARGET_RE = re.compile(r"^(.*?)\s+(@[A-Za-z0-9_]{4,32}|\d{5,12})\s*$", re.S)


class Whisper(Tpl):
    emoji, ar, en = "🤫", "همسة", "Whisper"
    d_ar, d_en = "نصوص وصور وملفات سرية للمجموعات والقنوات", "Secret texts, photos and files for groups and channels"
    guide_ar = ("<b>مهم:</b> فعّل الوضع المضمّن للبوت من @BotFather بالأمر <code>/setinline</code>.\n\n"
                "<b>همسة نصية:</b> في أي محادثة يكتب المستخدم:\n<code>@يوزر_البوت نص الهمسة @يوزر_المستلم</code>\n"
                "ثم يختار النتيجة. تظهر رسالة بزر «عرض الهمسة» لا يفتحها إلا المستلم والمرسل.\n\n"
                "<b>همسة بملف/صورة:</b> من داخل البوت يضغط «همسة بملف»، يحدد المستلم ويرسل الملف، فيحصل على زر يشاركه في المجموعة؛ "
                "المستلم فقط يستلم الملف في الخاص.")

    async def home(self, c: Ctx) -> None:
        u = c.bot.username
        await c.edit(ui.head(c.brand) + "\n" + c.t(
            f"🤫 أرسل همسة سرية في أي مجموعة لا يقرؤها إلا من تختاره.\n\nاكتب في المجموعة:\n<code>@{u} نص الهمسة @username</code>\n\nثم اختر النتيجة التي تظهر.",
            f"🤫 Send a secret whisper in any group that only your chosen person can read.\n\nType in the group:\n<code>@{u} your whisper @username</code>\n\nThen pick the result."),
            kb([[B(c.t("✍️ جرّب الآن", "✍️ Try now"), switch_inline_query="")], [B(c.t("📎 همسة بملف", "📎 Whisper a file"), "t:file")], c.tail()]))

    async def owner(self, c: Ctx):
        n = await c.kv("wh:count", 0)
        return c.t(f"🤫 همسات أُرسلت: {n}\n\n⚠️ فعّل /setinline للبوت من BotFather.", f"🤫 Whispers sent: {n}\n\n⚠️ Enable /setinline in BotFather."), []

    async def inline(self, c: Ctx) -> None:
        iq = c.u.inline_query
        q = (iq.query or "").strip()
        if q.startswith("#") and q[1:].isdigit():  # مشاركة همسة ملف
            r = await c.rec_get(int(q[1:]))
            if r is not None and r.kind == "whf" and r.user_id == c.uid:
                res = InlineQueryResultArticle(
                    id=f"f{r.id}", title=c.t("📎 إرسال همسة الملف", "📎 Send the file whisper"), description=f"→ {r.data['to']}",
                    input_message_content=InputTextMessageContent(c.t(f"📎 همسة سرية (ملف) إلى {esc(r.data['to'])}", f"📎 Secret file whisper for {esc(r.data['to'])}"), parse_mode="HTML"),
                    reply_markup=kb([[B(c.t("📥 استلام الملف", "📥 Get the file"), url=c.link(f"wh_{r.id}"))]]))
                await iq.answer([res], cache_time=0, is_personal=True)
            return
        m = TARGET_RE.match(q)
        if not m or not m.group(1).strip():
            res = InlineQueryResultArticle(
                id="help", title=c.t("اكتب: نص الهمسة ثم @يوزر المستلم", "Type: your whisper then @username"),
                description=c.t("مثال: أحبك يا صديقي @ali", "Example: hi there @ali"),
                input_message_content=InputTextMessageContent(c.t(f"🤫 لإرسال همسة اكتب:\n@{c.bot.username} نص الهمسة @username", f"🤫 To whisper type:\n@{c.bot.username} text @username")))
            await iq.answer([res], cache_time=0, is_personal=True)
            return
        text, to = m.group(1).strip()[:190], m.group(2).lower()
        key = hashlib.sha1(f"{c.uid}|{to}|{text}".encode()).hexdigest()[:16]
        seen = c.x.bot_data.setdefault("wh_seen", {})
        rid = seen.get(key)
        if rid is None:
            rid = await c.rec_add("wh", {"to": to, "text": text, "name": c.user.first_name})
            seen[key] = rid
            if len(seen) > 5000:
                for k in list(seen)[:2000]:
                    seen.pop(k, None)
        res = InlineQueryResultArticle(
            id=key, title=c.t(f"🤫 إرسال همسة إلى {to}", f"🤫 Whisper to {to}"), description=c.t("لن يقرأها أحد غيره", "Only they can read it"),
            input_message_content=InputTextMessageContent(c.t(f"🤫 همسة سرية من {c.name} إلى {esc(to)}", f"🤫 Secret whisper from {c.name} to {esc(to)}"), parse_mode="HTML"),
            reply_markup=kb([[B(c.t("👁 عرض الهمسة", "👁 Show whisper"), f"t:w:{rid}")]]))
        await iq.answer([res], cache_time=0, is_personal=True)

    def allowed(self, c: Ctx, r) -> bool:
        to = r.data["to"]
        return c.uid == r.user_id or to == str(c.uid) or (c.user.username and to == "@" + c.user.username.lower())

    async def start_param(self, c: Ctx, param: str) -> bool:
        if not (param.startswith("wh_") and param[3:].isdigit()):
            return False
        r = await c.rec_get(int(param[3:]))
        if r is None or r.kind != "whf" or not self.allowed(c, r):
            await c.send(c.t("🚫 هذه الهمسة ليست لك.", "🚫 This whisper isn't for you."))
            return True
        try:
            await c.send(c.t(f"📎 همسة من {esc(r.data['name'])}:", f"📎 Whisper from {esc(r.data['name'])}:"))
            await c.copy_to(c.chat.id, r.data["chat"], r.data["mid"])
        except TelegramError:
            await c.send(c.t("⚠️ لم يعد الملف متاحاً.", "⚠️ The file is no longer available."))
        return True

    async def cb(self, c: Ctx, a: list[str]) -> None:
        if a[0] == "w":
            r = await c.rec_get(int(a[1]))
            if r is None:
                await c.answer(c.t("انتهت صلاحية الهمسة.", "This whisper expired."), True)
            elif not self.allowed(c, r):
                await c.answer(c.t("🚫 هذه الهمسة ليست لك.", "🚫 This whisper isn't for you."), True)
            else:
                if c.uid != r.user_id and not r.data.get("read"):
                    await c.rec_update(r.id, data=dict(r.data, read=True))
                    await bump(c, "wh:count")
                await c.answer(r.data["text"][:200], True)
        elif a[0] == "file":
            c.set_state("wh_to")
            await c.edit(c.t("📎 أرسل يوزر المستلم (مثل @ali) أو رقمه (ID).\n\n/cancel للإلغاء", "📎 Send the recipient's @username or ID.\n\n/cancel to abort"), kb([c.home_row()]))

    async def msg(self, c: Ctx) -> bool:
        st = c.st
        if st and st["k"] == "wh_to":
            to = c.text.strip().lower()
            if not re.fullmatch(r"@[a-z0-9_]{4,32}|\d{5,12}", to):
                await c.send(c.t("⚠️ أرسل يوزراً صحيحاً مثل @ali.", "⚠️ Send a valid @username."))
                return True
            c.set_state("wh_file", to=to)
            await c.send(c.t("📤 الآن أرسل الصورة أو الملف أو النص السري.", "📤 Now send the secret photo, file or text."))
            return True
        if st and st["k"] == "wh_file":
            c.clear_state()
            rid = await c.rec_add("whf", {"to": st["to"], "chat": c.chat.id, "mid": c.msg.message_id, "name": c.user.first_name})
            await bump(c, "wh:count")
            await c.send(c.t("✅ الهمسة جاهزة. اضغط الزر واختر المجموعة لإرسالها، وسيستلم المستلم الملف في الخاص.",
                             "✅ Ready. Tap the button and choose the chat; the recipient gets the file in private."),
                         kb([[B(c.t("📤 إرسال إلى محادثة", "📤 Send to a chat"), switch_inline_query=f"#{rid}")]]))
            return True
        await self.home(c)
        return True


TPL = Whisper()
