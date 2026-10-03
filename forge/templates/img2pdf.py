"""تحويل الصور إلى PDF: صورة أو عدة صور في ملف PDF مرتب."""
import asyncio
import io

from .. import ui
from ..ctx import Ctx
from ..ui import B, kb
from . import Tpl
from ._util import bump, cleanup, too_big


def _build(paths: list[str]) -> bytes:
    import img2pdf
    from PIL import Image, ImageOps
    jpgs = []
    for p in paths:
        im = ImageOps.exif_transpose(Image.open(p))
        if im.mode != "RGB":
            bg = Image.new("RGB", im.size, (255, 255, 255))
            rgba = im.convert("RGBA")
            bg.paste(rgba, mask=rgba.split()[-1])
            im = bg
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=90)
        jpgs.append(buf.getvalue())
    return img2pdf.convert(jpgs)


class Img2Pdf(Tpl):
    emoji, ar, en = "🖼", "تحويل الصور إلى PDF", "Images to PDF"
    d_ar, d_en = "حوّل صورة أو عدة صور إلى ملف PDF مرتب بسرعة وسهولة.", "Turn one or several images into a tidy PDF quickly."
    cats = ("tools",)
    guide_ar = "المستخدم يرسل الصور واحدة تلو الأخرى (حتى 40 صورة) ثم يضغط «إنشاء PDF» فيستلم ملفاً واحداً بترتيب الإرسال، كل صورة في صفحة. لا يحتاج القالب أي إعداد."

    def imgs(self, c: Ctx) -> list[str]:
        return c.x.user_data.setdefault("i2p", [])

    async def home(self, c: Ctx) -> None:
        self.imgs(c).clear()
        await c.edit(ui.head(c.brand) + "\n" + c.t("🖼 أرسل الصور بالترتيب الذي تريده، ثم اضغط «إنشاء PDF».",
                                                             "🖼 Send the images in the order you want, then tap “Create PDF”."), kb([c.tail()]))

    async def owner(self, c: Ctx):
        n = await c.kv("i2p:count", 0)
        return c.t(f"📄 ملفات PDF أُنشئت: {n}", f"📄 PDFs created: {n}"), []

    async def cb(self, c: Ctx, a: list[str]) -> None:
        t, imgs = c.t, self.imgs(c)
        if a[0] == "clr":
            await self.home(c)
        elif a[0] == "go":
            if not imgs:
                await c.answer(t("أرسل صورة أولاً.", "Send an image first."), True)
                return
            await c.edit(t("⏳ جاري إنشاء الملف…", "⏳ Building the PDF…"))
            paths = []
            try:
                for fid in imgs:
                    paths.append(await c.download(fid, ".img"))
                pdf = await asyncio.to_thread(_build, [str(p) for p in paths])
                await c.doc(io.BytesIO(pdf), filename="images.pdf", caption=t(f"✅ {len(imgs)} صفحة.", f"✅ {len(imgs)} pages."))
                await bump(c, "i2p:count")
                imgs.clear()
            except Exception:
                await c.send(t("⚠️ تعذّر إنشاء الملف.", "⚠️ Couldn't build the PDF."))
            finally:
                cleanup(*paths)

    async def msg(self, c: Ctx) -> bool:
        f = c.file_of()
        mime = getattr(c.msg.document, "mime_type", "") or ""
        if f is None or not (f[1] == "photo" or mime.startswith("image/")):
            await c.send(c.t("🖼 أرسل صورة.", "🖼 Please send an image."))
            return True
        err = too_big(c, f[2])
        if err:
            await c.send(err)
            return True
        imgs = self.imgs(c)
        if len(imgs) >= 40:
            await c.send(c.t("⚠️ الحد 40 صورة للملف الواحد.", "⚠️ The limit is 40 images per file."))
            return True
        imgs.append(f[0])
        await c.send(c.t(f"📥 الصور المستلمة: {len(imgs)}", f"📥 Images received: {len(imgs)}"),
                     kb([[B(c.t(f"✅ إنشاء PDF ({len(imgs)})", f"✅ Create PDF ({len(imgs)})"), "t:go", style="success")], [B(c.t("🗑 مسح", "🗑 Clear"), "t:clr")]]))
        return True


TPL = Img2Pdf()
