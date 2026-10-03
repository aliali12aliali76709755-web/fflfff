"""OCR صورة إلى نص: استخراج النص العربي والإنجليزي من الصور."""
import asyncio
import io
import shutil

import httpx

from .. import config, ui
from ..ctx import Ctx
from ..ui import B, esc, kb
from . import Tpl
from ._util import bump, chunks, cleanup, grab

LANGS = {"ara": "🇸🇦 العربية", "eng": "🇬🇧 English"}


def _prep(path: str):
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(path)).convert("L")
    return ImageOps.autocontrast(im)


def _tesseract(path: str, lang: str) -> str:
    import pytesseract
    from PIL import Image
    im = _prep(path)
    if max(im.size) < 1400:
        k = 1400 / max(im.size)
        im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    try:
        have = set(pytesseract.get_languages(config=""))
    except Exception:
        have = {"eng"}
    use = "+".join(x for x in dict.fromkeys([lang, "eng"]) if x in have) or "eng"
    return pytesseract.image_to_string(im, lang=use).strip()


def _jpeg_under_1mb(path: str) -> bytes:
    from PIL import Image
    im = _prep(path)
    if max(im.size) > 2000:
        im.thumbnail((2000, 2000), Image.LANCZOS)
    for q in (85, 70, 55, 40):
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=q)
        if buf.tell() < 1000_000:
            break
    return buf.getvalue()


async def _online(path: str, lang: str) -> str | None:
    """قراءة عبر خدمة ocr.space حين لا يكون Tesseract مثبتاً."""
    data = await asyncio.to_thread(_jpeg_under_1mb, path)
    async with httpx.AsyncClient(timeout=60) as cl:
        r = await cl.post("https://api.ocr.space/parse/image", data={"apikey": config.OCR_SPACE_KEY, "language": lang, "OCREngine": "1", "scale": "true"},
                          files={"file": ("image.jpg", data, "image/jpeg")})
        r.raise_for_status()
        j = r.json()
    if j.get("IsErroredOnProcessing"):
        return None
    return "\n".join(p.get("ParsedText", "") for p in j.get("ParsedResults") or []).strip()


class Ocr(Tpl):
    emoji, ar, en = "🔎", "OCR صورة إلى نص", "OCR image to text"
    d_ar, d_en = "استخراج النص من الصور", "Extract text from images"
    guide_ar = ("العضو يختار لغة النص ثم يرسل صورة فيها كتابة، فيستخرج البوت نصها جاهزاً للنسخ. الصور الواضحة والمستقيمة تعطي أفضل نتيجة.\n\n"
                "إن كان محرّك Tesseract مثبتاً على السيرفر (مضمّن في نسخة Docker) تتم القراءة محلياً. "
                "وإن لم يكن مثبتاً يستخدم البوت خدمة ocr.space المجانية عبر الإنترنت، وهي محدودة بعدد طلبات يومي؛ "
                "لرفع الحد سجّل مفتاحاً مجانياً من موقعها وضعه في <code>OCR_SPACE_KEY</code> داخل ملف .env.")

    def lang(self, c: Ctx) -> str:
        return c.x.user_data.get("ocr_lang") or ("ara" if c.lang == "ar" else "eng")

    async def home(self, c: Ctx) -> None:
        cur = self.lang(c)
        await c.edit(ui.head(c.brand) + "\n" + c.t("📷 أرسل صورة فيها نص وسأستخرجه لك.\n\nلغة النص في الصورة:", "📷 Send an image containing text and I'll extract it.\n\nLanguage of the text:"),
                     kb([[B(("✓ " if k == cur else "") + v, f"t:lang:{k}") for k, v in LANGS.items()], c.tail()]))

    async def owner(self, c: Ctx):
        n = await c.kv("ocr:count", 0)
        eng = c.t("محلي (Tesseract)", "local (Tesseract)") if shutil.which("tesseract") else c.t("عبر الإنترنت (ocr.space)", "online (ocr.space)")
        return c.t(f"🔎 محرّك القراءة: {eng}\n📝 صور عولجت: {n}", f"🔎 Engine: {eng}\n📝 Images processed: {n}"), []

    async def cb(self, c: Ctx, a: list[str]) -> None:
        if a[0] == "lang" and a[1] in LANGS:
            c.x.user_data["ocr_lang"] = a[1]
            await self.home(c)

    async def msg(self, c: Ctx) -> bool:
        f = c.file_of()
        mime = getattr(c.msg.document, "mime_type", "") or ""
        if f is None or not (f[1] == "photo" or mime.startswith("image/")):
            await c.send(c.t("📷 أرسل صورة.", "📷 Please send an image."))
            return True
        src = await grab(c, ".img")
        if src is None:
            return True
        lang, text = self.lang(c), None
        try:
            if shutil.which("tesseract"):
                try:
                    text = await asyncio.wait_for(asyncio.to_thread(_tesseract, str(src), lang), 90)
                except Exception:
                    text = None
            if text is None:
                try:
                    text = await _online(str(src), lang)
                except Exception:
                    text = None
        finally:
            cleanup(src)
        if text is None:
            await c.send(c.t("⚠️ خدمة قراءة الصور غير متاحة الآن. حاول بعد قليل.", "⚠️ The OCR service is unavailable right now. Try again shortly."))
            return True
        if not text:
            await c.send(c.t("🤷 لم أجد نصاً واضحاً في الصورة.", "🤷 No clear text found in the image."))
            return True
        await bump(c, "ocr:count")
        for part in chunks(text):
            await c.send(f"<code>{esc(part)}</code>")
        return True


TPL = Ocr()
