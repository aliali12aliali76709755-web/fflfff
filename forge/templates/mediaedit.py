"""محرّر الوسائط: فلاتر وتعديلات وقص وتحويل للصور، وأدوات للفيديو، وصورة غلاف بأي حجم."""
import asyncio
import re
from pathlib import Path

from .. import ui
from ..ctx import Ctx
from ..ui import B, kb
from . import Tpl
from ._util import bump, cleanup, ffmpeg, fits_upload, too_big

FILTERS = {"bw": ("⚫ أبيض وأسود", "⚫ B&W"), "sepia": ("🟤 سيبيا", "🟤 Sepia"), "blur": ("🌫 ضبابي", "🌫 Blur"), "sharp": ("🔪 حدّة", "🔪 Sharpen"),
           "inv": ("🔁 عكس الألوان", "🔁 Invert"), "con": ("◐ تباين +", "◐ Contrast +"), "bri": ("☀️ سطوع +", "☀️ Brightness +"), "sat": ("🌈 تشبّع +", "🌈 Saturation +")}
CROPS = {"1x1": (1, 1), "16x9": (16, 9), "9x16": (9, 16), "4x5": (4, 5)}


def _apply(path: str, op: str, arg: str = "") -> None:
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
    im = Image.open(path).convert("RGB")
    if op == "bw":
        im = ImageOps.grayscale(im).convert("RGB")
    elif op == "sepia":
        g = ImageOps.grayscale(im)
        im = ImageOps.colorize(g, "#2e1f0f", "#f3e2c0")
    elif op == "blur":
        im = im.filter(ImageFilter.GaussianBlur(4))
    elif op == "sharp":
        im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=160))
    elif op == "inv":
        im = ImageOps.invert(im)
    elif op == "con":
        im = ImageEnhance.Contrast(im).enhance(1.35)
    elif op == "bri":
        im = ImageEnhance.Brightness(im).enhance(1.25)
    elif op == "sat":
        im = ImageEnhance.Color(im).enhance(1.4)
    elif op == "rot":
        im = im.rotate(-90, expand=True)
    elif op == "flip":
        im = ImageOps.mirror(im)
    elif op == "crop":
        rw, rh = CROPS[arg]
        w, h = im.size
        if w * rh > h * rw:
            nw = h * rw // rh
            im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
        else:
            nh = w * rh // rw
            im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    elif op == "cover":
        w, h = (int(x) for x in arg.split("x"))
        im = ImageOps.fit(im, (w, h), Image.LANCZOS)
    im.save(path, "PNG")


def _export(path: str, out: str, fmt: str) -> None:
    from PIL import Image
    im = Image.open(path).convert("RGB")
    im.save(out, {"jpg": "JPEG", "png": "PNG", "webp": "WEBP"}[fmt], **({"quality": 93} if fmt != "png" else {}))


class MediaEdit(Tpl):
    emoji, ar, en = "🎬", "محرّر الوسائط", "Media editor"
    d_ar = "حرّر الصور والفيديو: فلاتر، تعديلات، قص، تحويل صيغ، أدوات فيديو، وصورة غلاف بأي حجم"
    d_en = "Edit photos and videos: filters, adjustments, crop, format conversion, video tools and covers of any size"
    cats = ("tools",)
    guide_ar = ("<b>الصور:</b> أرسل صورة ثم طبّق عليها ما تشاء بالتتابع: 8 فلاتر، تدوير، قلب، قص بنسب جاهزة، صورة غلاف بأي مقاس (مثل 1280x720)، "
                "ثم حمّلها JPG أو PNG أو WEBP. زر «↩️ الأصل» يعيد الصورة كما كانت.\n\n"
                "<b>الفيديو:</b> كتم الصوت، استخراج الصوت MP3، تحويل إلى GIF، قص مقطع بالثواني، واستخراج صورة غلاف.")

    async def home(self, c: Ctx) -> None:
        await c.edit(ui.head(c.brand) + "\n" + c.t("🖼 أرسل صورة أو فيديو لبدء التعديل.", "🖼 Send a photo or a video to start editing."), kb([c.tail()]))

    async def owner(self, c: Ctx):
        n = await c.kv("me:count", 0)
        return c.t(f"🎬 عمليات تعديل: {n}", f"🎬 Edits performed: {n}"), []

    def photo_kb(self, c: Ctx):
        t = c.t
        return kb(ui.grid([B(t(*v), f"t:f:{k}") for k, v in FILTERS.items()], 2) + [
            [B(t("↻ تدوير", "↻ Rotate"), "t:f:rot"), B(t("⇋ قلب", "⇋ Flip"), "t:f:flip")],
            [B(f"✂️ {k.replace('x', ':')}", f"t:cr:{k}") for k in CROPS],
            [B(t("🖼 غلاف بمقاس مخصص", "🖼 Cover (custom size)"), "t:cover")],
            [B("⬇️ JPG", "t:ex:jpg"), B("⬇️ PNG", "t:ex:png"), B("⬇️ WEBP", "t:ex:webp")],
            [B(t("↩️ الأصل", "↩️ Original"), "t:reset")]])

    def video_kb(self, c: Ctx):
        t = c.t
        return kb([[B(t("🔇 كتم الصوت", "🔇 Mute"), "t:v:mute"), B(t("🎵 استخراج الصوت", "🎵 Extract audio"), "t:v:mp3")],
                   [B(t("🎞 إلى GIF", "🎞 To GIF"), "t:v:gif"), B(t("🖼 صورة غلاف", "🖼 Thumbnail"), "t:v:thumb")],
                   [B(t("✂️ قص مقطع", "✂️ Trim"), "t:v:trim")]])

    def work(self, c: Ctx) -> Path | None:
        p = c.x.user_data.get("me_path")
        return Path(p) if p and Path(p).exists() else None

    async def show(self, c: Ctx, note: str = "") -> None:
        p = self.work(c)
        if p is None:
            return
        with open(p, "rb") as fh:
            await c.photo(fh, caption=note or c.t("اختر التعديل التالي:", "Pick the next edit:"), kb=self.photo_kb(c))

    async def load_photo(self, c: Ctx, fid: str) -> None:
        cleanup(self.work(c))
        src = await c.download(fid, ".img")
        await asyncio.to_thread(_apply, str(src), "noop")
        c.x.user_data.update(me_path=str(src), me_fid=fid)

    async def cb(self, c: Ctx, a: list[str]) -> None:  # noqa: C901
        act, t = a[0], c.t
        if act == "v":
            await self.video_op(c, a[1])
            return
        if act == "cover":
            c.set_state("me_cover")
            await c.send(t("🖼 أرسل المقاس بالبكسل مثل <code>1280x720</code>.", "🖼 Send the size in pixels, e.g. <code>1280x720</code>."))
            return
        p = self.work(c)
        if p is None:
            if c.x.user_data.get("me_fid") and act != "ex":
                await self.load_photo(c, c.x.user_data["me_fid"])
                p = self.work(c)
            if p is None:
                await c.answer(t("أرسل الصورة من جديد.", "Send the photo again."), True)
                return
        try:
            if act == "f":
                await asyncio.to_thread(_apply, str(p), a[1])
            elif act == "cr" and a[1] in CROPS:
                await asyncio.to_thread(_apply, str(p), "crop", a[1])
            elif act == "reset":
                await self.load_photo(c, c.x.user_data["me_fid"])
            elif act == "ex" and a[1] in ("jpg", "png", "webp"):
                out = c.tmp("." + a[1])
                await asyncio.to_thread(_export, str(p), str(out), a[1])
                with open(out, "rb") as fh:
                    await c.doc(fh, filename=f"edited.{a[1]}")
                cleanup(out)
                return
            else:
                return
            await bump(c, "me:count")
            await self.show(c)
        except Exception:
            await c.send(t("⚠️ تعذّر تطبيق التعديل.", "⚠️ Couldn't apply the edit."))

    async def video_op(self, c: Ctx, op: str, trim: tuple[float, float] | None = None) -> None:
        t, fid = c.t, c.x.user_data.get("me_vid")
        if not fid:
            await c.answer(t("أرسل الفيديو أولاً.", "Send the video first."), True)
            return
        if op == "trim" and trim is None:
            c.set_state("me_trim")
            await c.send(t("✂️ أرسل بداية ونهاية المقطع بالثواني مثل <code>5-20</code>.", "✂️ Send start and end in seconds, e.g. <code>5-20</code>."))
            return
        await c.send(t("⏳ جاري المعالجة…", "⏳ Processing…"))
        ext = {"mute": ".mp4", "mp3": ".mp3", "gif": ".gif", "thumb": ".jpg", "trim": ".mp4"}[op]
        src = out = None
        try:
            src, out = await c.download(fid, ".mp4"), c.tmp(ext)
            args = {"mute": ["-i", str(src), "-c:v", "copy", "-an"], "mp3": ["-i", str(src), "-vn", "-c:a", "libmp3lame", "-b:a", "192k"],
                    "gif": ["-i", str(src), "-t", "12", "-vf", "fps=12,scale=480:-1:flags=lanczos", "-an"],
                    "thumb": ["-ss", "1", "-i", str(src), "-frames:v", "1", "-q:v", "2"],
                    "trim": ["-ss", str(trim[0]), "-to", str(trim[1]), "-i", str(src), "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac"] if trim else []}[op]
            ok, _ = await ffmpeg([*args, str(out)])
            if not ok or not fits_upload(out):
                await c.send(t("⚠️ فشلت المعالجة.", "⚠️ Processing failed."))
                return
            with open(out, "rb") as fh:
                if op in ("mute", "trim"):
                    await c.video(fh, filename="edited.mp4", supports_streaming=True, kb=self.video_kb(c))
                elif op == "mp3":
                    await c.audio(fh, filename="audio.mp3")
                elif op == "thumb":
                    await c.photo(fh)
                else:
                    await c.doc(fh, filename="clip.gif")
            await bump(c, "me:count")
        except Exception:
            await c.send(t("⚠️ تعذّرت معالجة الفيديو.", "⚠️ Couldn't process the video."))
        finally:
            cleanup(src, out)

    async def msg(self, c: Ctx) -> bool:
        st, t = c.st, c.t
        if st and st["k"] == "me_cover":
            m = re.fullmatch(r"\s*(\d{2,4})\s*[x×*]\s*(\d{2,4})\s*", c.text)
            p = self.work(c)
            if not m or p is None or not (16 <= int(m.group(1)) <= 4096 and 16 <= int(m.group(2)) <= 4096):
                await c.send(t("⚠️ مثال صحيح: <code>1280x720</code> (وأرسل الصورة أولاً).", "⚠️ Valid example: <code>1280x720</code> (send the photo first)."))
                return True
            c.clear_state()
            await asyncio.to_thread(_apply, str(p), "cover", f"{m.group(1)}x{m.group(2)}")
            await self.show(c, f"🖼 {m.group(1)}×{m.group(2)}")
            return True
        if st and st["k"] == "me_trim":
            m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*", c.text)
            if not m or float(m.group(1)) >= float(m.group(2)):
                await c.send(t("⚠️ مثال صحيح: <code>5-20</code>", "⚠️ Valid example: <code>5-20</code>"))
                return True
            c.clear_state()
            await self.video_op(c, "trim", (float(m.group(1)), float(m.group(2))))
            return True
        f = c.file_of()
        if f is None:
            await self.home(c)
            return True
        err = too_big(c, f[2])
        if err:
            await c.send(err)
            return True
        mime = getattr(c.msg.document, "mime_type", "") or ""
        if f[1] == "photo" or mime.startswith("image/"):
            try:
                await self.load_photo(c, f[0])
            except Exception:
                await c.send(t("⚠️ لم أستطع قراءة الصورة.", "⚠️ Couldn't read the image."))
                return True
            await self.show(c, t("🖼 الصورة جاهزة. اختر التعديل:", "🖼 Photo loaded. Pick an edit:"))
        elif f[1] in ("video", "animation", "video_note") or mime.startswith("video/"):
            c.x.user_data["me_vid"] = f[0]
            await c.send(t("🎬 الفيديو جاهز. اختر الأداة:", "🎬 Video loaded. Pick a tool:"), self.video_kb(c))
        else:
            await c.send(t("⚠️ أرسل صورة أو فيديو.", "⚠️ Send a photo or a video."))
        return True


TPL = MediaEdit()
