"""محول صيغ الملفات: تحويل الصور والصوت والفيديو إلى الصيغ الشائعة."""
import asyncio

from .. import ui
from ..ctx import Ctx
from ..ui import B, kb
from . import Tpl
from ._util import bump, cleanup, ffmpeg, fits_upload, media_ext, too_big

IMG = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff", ".heic"}
AUD = {".mp3", ".ogg", ".oga", ".wav", ".m4a", ".flac", ".aac", ".opus", ".wma"}
VID = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".3gp", ".m4v", ".flv"}
TARGETS = {"img": ["jpg", "png", "webp", "pdf"], "aud": ["mp3", "ogg", "wav", "m4a"], "vid": ["mp4", "mp3", "gif", "webm"]}


def kind_of(ext: str, tg_kind: str) -> str | None:
    if ext in IMG or tg_kind == "photo":
        return "img"
    if ext in AUD or tg_kind in ("audio", "voice"):
        return "aud"
    if ext in VID or tg_kind in ("video", "animation", "video_note"):
        return "vid"
    return None


def _img(src: str, out: str, fmt: str) -> None:
    from PIL import Image
    im = Image.open(src)
    if fmt in ("jpg", "pdf") and im.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", im.size, (255, 255, 255))
        im = im.convert("RGBA")
        bg.paste(im, mask=im.split()[-1])
        im = bg
    elif fmt in ("jpg", "pdf"):
        im = im.convert("RGB")
    im.save(out, {"jpg": "JPEG", "png": "PNG", "webp": "WEBP", "pdf": "PDF"}[fmt], **({"quality": 92} if fmt in ("jpg", "webp") else {}))


FF = {"mp3": ["-vn", "-c:a", "libmp3lame", "-b:a", "192k"], "ogg": ["-vn", "-c:a", "libopus", "-b:a", "64k"], "wav": ["-vn"],
      "m4a": ["-vn", "-c:a", "aac", "-b:a", "160k"], "mp4": ["-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-c:a", "aac", "-movflags", "+faststart"],
      "webm": ["-c:v", "libvpx-vp9", "-crf", "34", "-b:v", "0", "-c:a", "libopus"],
      "gif": ["-t", "15", "-vf", "fps=12,scale=480:-1:flags=lanczos", "-an"]}


class Convert(Tpl):
    emoji, ar, en = "🔄", "محول صيغ الملفات", "File converter"
    d_ar, d_en = "تحويل صور وصوت وفيديو إلى صيغ شائعة", "Convert images, audio and video to common formats"
    guide_ar = ("المستخدم يرسل ملفاً فيتعرف البوت على نوعه ويعرض الصيغ المتاحة:\n• الصور ← JPG / PNG / WEBP / PDF\n• الصوت ← MP3 / OGG / WAV / M4A\n"
                "• الفيديو ← MP4 / MP3 (استخراج الصوت) / GIF (أول 15 ثانية) / WEBM\n\nللحفاظ على صيغة الصورة أرسلها «كملف» لا كصورة مضغوطة.")

    async def home(self, c: Ctx) -> None:
        await c.edit(ui.head(c.brand) + "\n" + c.t("📎 أرسل صورة أو ملف صوت أو فيديو، ثم اختر الصيغة المطلوبة.",
                                                             "📎 Send an image, audio or video file, then pick the target format."), kb([c.tail()]))

    async def owner(self, c: Ctx):
        n = await c.kv("cv:count", 0)
        return c.t(f"🔄 ملفات حُوّلت: {n}", f"🔄 Files converted: {n}"), []

    async def cb(self, c: Ctx, a: list[str]) -> None:
        job = c.x.user_data.get("cv")
        if a[0] != "to" or not job or a[1] not in TARGETS[job["kind"]]:
            return
        fmt = a[1]
        await c.edit(c.t("⏳ جاري التحويل…", "⏳ Converting…"))
        src = out = None
        try:
            src = await c.download(job["fid"], job["ext"] or "")
            out = c.tmp("." + fmt)
            if job["kind"] == "img":
                await asyncio.to_thread(_img, str(src), str(out), fmt)
                ok = out.exists()
            else:
                ok, _ = await ffmpeg(["-i", str(src), *FF[fmt], str(out)])
            if not ok or not fits_upload(out):
                await c.send(c.t("⚠️ فشل التحويل أو الناتج أكبر من الحد.", "⚠️ Conversion failed or the output is too large."))
                return
            with open(out, "rb") as fh:
                name = f"converted.{fmt}"
                if fmt in ("mp3", "m4a", "wav"):
                    await c.audio(fh, filename=name)
                elif fmt == "ogg":
                    await c.voice(fh)
                elif fmt == "mp4":
                    await c.video(fh, filename=name, supports_streaming=True)
                else:
                    await c.doc(fh, filename=name)
            await bump(c, "cv:count")
        except Exception:
            await c.send(c.t("⚠️ تعذّرت معالجة الملف.", "⚠️ Couldn't process the file."))
        finally:
            cleanup(src, out)

    async def msg(self, c: Ctx) -> bool:
        f = c.file_of()
        if f is None:
            await c.send(c.t("📎 أرسل ملفاً (صورة، صوت أو فيديو).", "📎 Send a file (image, audio or video)."))
            return True
        ext = media_ext(c)
        kind = kind_of(ext, f[1])
        if kind is None:
            await c.send(c.t("⚠️ نوع الملف غير مدعوم.", "⚠️ Unsupported file type."))
            return True
        err = too_big(c, f[2])
        if err:
            await c.send(err)
            return True
        c.x.user_data["cv"] = {"fid": f[0], "ext": ext, "kind": kind}
        btns = [B(t.upper(), f"t:to:{t}") for t in TARGETS[kind] if "." + t != ext and not (t == "jpg" and ext == ".jpeg")]
        await c.send(c.t("اختر الصيغة المطلوبة:", "Pick the target format:"), kb(ui.grid(btns, 4)))
        return True


TPL = Convert()
