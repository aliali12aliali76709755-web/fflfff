"""الترجمة: ترجمة فورية إلى 22 لغة."""
import asyncio

from .. import ui
from ..ctx import Ctx
from ..ui import B, esc, kb
from . import Tpl
from ._util import bump

LANGS = [("ar", "🇸🇦 العربية"), ("en", "🇬🇧 English"), ("tr", "🇹🇷 Türkçe"), ("fr", "🇫🇷 Français"), ("de", "🇩🇪 Deutsch"),
         ("es", "🇪🇸 Español"), ("it", "🇮🇹 Italiano"), ("ru", "🇷🇺 Русский"), ("fa", "🇮🇷 فارسی"), ("ur", "🇵🇰 اردو"),
         ("hi", "🇮🇳 हिन्दी"), ("zh-CN", "🇨🇳 中文"), ("ja", "🇯🇵 日本語"), ("ko", "🇰🇷 한국어"), ("pt", "🇵🇹 Português"),
         ("nl", "🇳🇱 Nederlands"), ("sv", "🇸🇪 Svenska"), ("id", "🇮🇩 Indonesia"), ("ms", "🇲🇾 Melayu"), ("uk", "🇺🇦 Українська"),
         ("ku", "☀️ Kurdî"), ("el", "🇬🇷 Ελληνικά")]
NAMES = dict(LANGS)


def _translate(text: str, target: str) -> str:
    from deep_translator import GoogleTranslator
    return GoogleTranslator(source="auto", target=target).translate(text)


class Translate(Tpl):
    emoji, ar, en = "🌍", "الترجمة", "Translator"
    d_ar, d_en = "ترجمة فورية إلى 22 لغة", "Instant translation into 22 languages"
    cats = ("edu",)
    guide_ar = "المستخدم يختار لغة الترجمة مرة واحدة ثم يرسل أي نص فيُترجم فوراً، مع أزرار لإعادة الترجمة إلى لغة أخرى. لا يحتاج القالب أي إعداد."

    def target(self, c: Ctx) -> str:
        return c.x.user_data.get("tr_to") or ("en" if c.lang == "ar" else "ar")

    async def home(self, c: Ctx) -> None:
        cur = self.target(c)
        btns = [B(("✓ " if code == cur else "") + name, f"t:to:{code}") for code, name in LANGS]
        await c.edit(ui.head(c.brand) + "\n" + c.t(f"✍️ أرسل أي نص وسأترجمه إلى: <b>{NAMES[cur]}</b>\n\nلتغيير اللغة اختر من الأزرار:",
                                                             f"✍️ Send any text and I'll translate it into: <b>{NAMES[cur]}</b>\n\nPick another language:"),
                     kb(ui.grid(btns, 3) + [c.tail()]))

    async def owner(self, c: Ctx):
        n = await c.kv("tr:count", 0)
        return c.t(f"🌍 ترجمات منجزة: {n}", f"🌍 Translations done: {n}"), []

    async def cb(self, c: Ctx, a: list[str]) -> None:
        if a[0] == "to" and a[1] in NAMES:
            c.x.user_data["tr_to"] = a[1]
            last = c.x.user_data.get("tr_last")
            if len(a) > 2 and last:
                await self.do(c, last)
            else:
                await self.home(c)

    async def do(self, c: Ctx, text: str) -> None:
        to = self.target(c)
        try:
            out = await asyncio.wait_for(asyncio.to_thread(_translate, text[:4500], to), 30)
        except Exception:
            await c.send(c.t("⚠️ تعذّرت الترجمة الآن. حاول بعد قليل.", "⚠️ Translation failed. Try again shortly."))
            return
        await bump(c, "tr:count")
        quick = [B(NAMES[k], f"t:to:{k}:1") for k in ("ar", "en", "tr") if k != to]
        await c.send(f"<b>{NAMES[to]}</b>\n\n{esc(out or '')}", kb([quick, [B(c.t("🌍 لغة أخرى", "🌍 Other language"), "t:home")]]))

    async def msg(self, c: Ctx) -> bool:
        text = c.text
        if not text or text.startswith("/"):
            return False
        c.x.user_data["tr_last"] = text
        await self.do(c, text)
        return True


TPL = Translate()
