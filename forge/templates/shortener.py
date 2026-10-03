"""اختصار الروابط: يختصر الروابط الطويلة عبر خدمات اختصار عامة ومجانية."""
import re

from .. import ui
from ..ctx import Ctx
from ..ui import B, esc, kb
from . import Tpl
from ._util import bump, get_text

URL_RE = re.compile(r"https?://[^\s<>\"]+", re.I)


async def shorten(url: str) -> str | None:
    for api, params in (("https://is.gd/create.php", {"format": "simple", "url": url}),
                        ("https://tinyurl.com/api-create.php", {"url": url}),
                        ("https://v.gd/create.php", {"format": "simple", "url": url})):
        try:
            out = (await get_text(api, params=params, timeout=12)).strip()
            if out.startswith("http") and len(out) < 80:
                return out
        except Exception:
            continue
    return None


class Shortener(Tpl):
    emoji, ar, en = "🔗", "اختصار الروابط", "URL shortener"
    d_ar, d_en = "اختصر الروابط الطويلة", "Shorten long links"
    cats = ("top", "tools")
    guide_ar = "المستخدم يرسل رابطاً طويلاً (أو عدة روابط في رسالة واحدة) فيحصل على روابط مختصرة جاهزة للنسخ، مع سجل لآخر روابطه. لا يحتاج القالب أي إعداد."

    async def home(self, c: Ctx) -> None:
        await c.edit(ui.head(c.brand) + "\n" + c.t("🔗 أرسل الرابط الطويل وسأختصره لك فوراً.", "🔗 Send a long link and I'll shorten it."),
                     kb([[B(c.t("🕘 روابطي الأخيرة", "🕘 My recent links"), "t:hist")], c.tail()]))

    async def owner(self, c: Ctx):
        n = await c.kv("short:count", 0)
        return c.t(f"🔗 روابط اختُصرت: {n}", f"🔗 Links shortened: {n}"), []

    async def cb(self, c: Ctx, a: list[str]) -> None:
        if a[0] == "hist":
            recs = await c.rec_list("short", user_id=c.uid, limit=10)
            text = "\n\n".join(f"<code>{esc(r.data['s'])}</code>\n↳ {esc(r.data['u'][:70])}" for r in recs) or c.t("لا توجد روابط بعد.", "No links yet.")
            await c.edit(ui.head(c.t("🕘 روابطي الأخيرة", "🕘 My recent links")) + "\n" + text, kb([c.home_row()]))

    async def msg(self, c: Ctx) -> bool:
        urls = URL_RE.findall(c.text)
        if not urls:
            await c.send(c.t("⚠️ أرسل رابطاً يبدأ بـ http:// أو https://", "⚠️ Send a link starting with http:// or https://"))
            return True
        out = []
        for u in urls[:5]:
            s = await shorten(u)
            if s:
                await c.rec_add("short", {"u": u, "s": s})
                await bump(c, "short:count")
                out.append(f"✅ <code>{esc(s)}</code>\n↳ {esc(u[:70])}")
            else:
                out.append(c.t(f"⚠️ تعذّر اختصار: {esc(u[:60])}", f"⚠️ Couldn't shorten: {esc(u[:60])}"))
        await c.send("\n\n".join(out), kb([c.home_row()]))
        return True


TPL = Shortener()
