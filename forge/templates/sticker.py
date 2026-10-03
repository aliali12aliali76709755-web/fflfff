"""صانع ملصقات: تحويل أي صورة إلى ملصق تيليجرام (PNG 512×512)."""
import asyncio
import io

from .. import ui
from ..ctx import Ctx
from ..ui import kb
from . import Tpl
from ._util import bump, cleanup, grab


def _make(path: str) -> tuple[bytes, bytes]:
    from PIL import Image
    im = Image.open(path).convert("RGBA")
    scale = 512 / max(im.size)
    im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.LANCZOS)
    canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    canvas.paste(im, ((512 - im.width) // 2, (512 - im.height) // 2), im)
    png, webp = io.BytesIO(), io.BytesIO()
    canvas.save(png, "PNG", optimize=True)
    im.save(webp, "WEBP", quality=95)
    return png.getvalue(), webp.getvalue()


class Sticker(Tpl):
    emoji, ar, en = "🎟", "صانع ملصقات", "Sticker maker"
    d_ar, d_en = "حوّل أي صورة إلى ملصق تيليجرام (PNG 512×512)", "Turn any image into a Telegram sticker (PNG 512×512)"
    cats = ("top", "tools")
    guide_ar = ("المستخدم يرسل صورة فيستلم:\n• الملصق نفسه جاهزاً للإرسال.\n• ملف PNG بمقاس 512×512 وخلفية شفافة، جاهز لرفعه إلى @Stickers لصنع حزمة.\n\n"
                "للحفاظ على الشفافية أرسل الصورة «كملف» بصيغة PNG. لا يحتاج القالب أي إعداد.")

    async def home(self, c: Ctx) -> None:
        await c.edit(ui.head(c.brand) + "\n" + c.t("🖼 أرسل صورة وسأحوّلها إلى ملصق. للخلفية الشفافة أرسلها كملف PNG.",
                                                             "🖼 Send an image and I'll turn it into a sticker. For transparency send it as a PNG file."), kb([c.tail()]))

    async def owner(self, c: Ctx):
        n = await c.kv("stk:count", 0)
        return c.t(f"🎟 ملصقات صُنعت: {n}", f"🎟 Stickers made: {n}"), []

    async def msg(self, c: Ctx) -> bool:
        f = c.file_of()
        mime = getattr(c.msg.document, "mime_type", "") or ""
        if f is None or not (f[1] == "photo" or mime.startswith("image/") or f[1] == "sticker"):
            await c.send(c.t("🖼 أرسل صورة.", "🖼 Please send an image."))
            return True
        src = await grab(c, ".img")
        if src is None:
            return True
        try:
            png, webp = await asyncio.to_thread(_make, str(src))
            await c.sticker(io.BytesIO(webp))
            await c.doc(io.BytesIO(png), filename="sticker.png", caption=c.t("✅ ملف PNG 512×512 جاهز لـ @Stickers", "✅ 512×512 PNG ready for @Stickers"))
            await bump(c, "stk:count")
        except Exception:
            await c.send(c.t("⚠️ لم أستطع معالجة الصورة.", "⚠️ Couldn't process the image."))
        finally:
            cleanup(src)
        return True


TPL = Sticker()
