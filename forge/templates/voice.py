"""الصوت ⇌ النص: تحويل الصوت والفيديو إلى نص، والنص إلى صوت MP3."""
import asyncio
import io
import re

from .. import ui
from ..ctx import Ctx
from ..ui import B, esc, kb
from . import Tpl
from ._util import bump, chunks, cleanup, ffmpeg, grab

_local = {"model": None, "tried": False}
LANGS = {"ar": ("🇸🇦 العربية", "ar-SA"), "en": ("🇬🇧 English", "en-US"), "tr": ("🇹🇷 Türkçe", "tr-TR")}
MAX_MIN = 5       # أقصى مدة تُفرَّغ من المقطع
PIECE = 50        # ثوانٍ لكل طلب تعرّف


def _tts(text: str, lang: str) -> bytes:
    from gtts import gTTS
    buf = io.BytesIO()
    gTTS(text=text, lang=lang).write_to_fp(buf)
    return buf.getvalue()


def _whisper(path: str) -> str | None:
    """تفريغ محلي عبر faster-whisper إن كانت المكتبة مثبتة (اختياري، أدق وأبطأ)."""
    if not _local["tried"]:
        _local["tried"] = True
        try:
            from faster_whisper import WhisperModel
            _local["model"] = WhisperModel("base", device="cpu", compute_type="int8")
        except Exception:
            _local["model"] = None
    if _local["model"] is None:
        return None
    segs, _ = _local["model"].transcribe(path, vad_filter=True)
    return " ".join(s.text.strip() for s in segs).strip()


def _google(wav: str, lang: str) -> str | None:
    """تعرّف مجاني على الكلام عبر خدمة Google العامة، على مقاطع قصيرة متتالية."""
    import speech_recognition as sr
    r = sr.Recognizer()
    out, failed = [], 0
    with sr.AudioFile(wav) as src:
        total = min(src.DURATION, MAX_MIN * 60)
        done = 0.0
        while done < total:
            audio = r.record(src, duration=PIECE)
            done += PIECE
            try:
                out.append(r.recognize_google(audio, language=lang))
            except sr.UnknownValueError:
                continue
            except Exception:
                failed += 1
                if failed >= 2:
                    break
    if not out and failed:
        return None
    return " ".join(out).strip()


class Voice(Tpl):
    emoji, ar, en = "🎙", "الصوت ⇌ النص", "Voice ⇌ text"
    d_ar, d_en = "حوّل الصوت والفيديو إلى نص، والنص إلى صوت MP3", "Turn audio and video into text, and text into MP3 speech"
    guide_ar = ("<b>نص ← صوت:</b> العضو يرسل نصاً فيستلمه ملف MP3 منطوقاً.\n\n"
                "<b>صوت/فيديو ← نص:</b> العضو يختار لغة الكلام ثم يرسل بصمة أو ملفاً صوتياً أو فيديو (حتى 5 دقائق) فيستلم النص.\n\n"
                "يعمل دون أي مفاتيح عبر خدمة التعرّف العامة من Google، فتتفاوت الدقة مع الضجيج واللهجات. "
                "لدقة أعلى يمكن تثبيت <code>faster-whisper</code> على السيرفر فيستخدمه البوت تلقائياً.")

    def lang(self, c: Ctx) -> str:
        return c.x.user_data.get("vt_lang") or ("ar" if c.lang == "ar" else "en")

    async def home(self, c: Ctx) -> None:
        cur = self.lang(c)
        await c.edit(ui.head(c.brand) + "\n" + c.t(
            "🎙 أرسل بصمة أو ملف صوت أو فيديو لتحويله إلى نص.\n✍️ أو أرسل نصاً لتحويله إلى صوت MP3.\n\nلغة الكلام في المقاطع الصوتية:",
            "🎙 Send a voice note, audio or video to get its text.\n✍️ Or send text to get MP3 speech.\n\nSpoken language of your audio:"),
            kb([[B(("✓ " if k == cur else "") + v[0], f"t:lang:{k}") for k, v in LANGS.items()], c.tail()]))

    async def owner(self, c: Ctx):
        n = await c.kv("vt:count", 0)
        return c.t(f"🔁 عمليات تحويل: {n}", f"🔁 Conversions: {n}"), []

    async def cb(self, c: Ctx, a: list[str]) -> None:
        if a[0] == "lang" and a[1] in LANGS:
            c.x.user_data["vt_lang"] = a[1]
            await self.home(c)

    async def msg(self, c: Ctx) -> bool:
        t, f = c.t, c.file_of()
        if f is not None and f[1] in ("voice", "audio", "video", "video_note", "document"):
            src = await grab(c, ".media")
            if src is None:
                return True
            wav = c.tmp(".wav")
            await c.send(t("⏳ جاري تحويل الصوت إلى نص…", "⏳ Transcribing…"))
            try:
                ok, _ = await ffmpeg(["-i", str(src), "-vn", "-ac", "1", "-ar", "16000", "-t", str(MAX_MIN * 60), str(wav)])
                if not ok:
                    await c.send(t("⚠️ لم أستطع قراءة الملف الصوتي.", "⚠️ Couldn't read the audio."))
                    return True
                text = await asyncio.to_thread(_whisper, str(wav))
                if text is None:
                    try:
                        text = await asyncio.wait_for(asyncio.to_thread(_google, str(wav), LANGS[self.lang(c)][1]), 240)
                    except Exception:
                        text = None
                if text is None:
                    await c.send(t("⚠️ خدمة التعرّف على الكلام غير متاحة الآن. حاول بعد قليل.", "⚠️ Speech recognition is unavailable right now. Try again shortly."))
                elif not text:
                    await c.send(t("🤷 لم أتعرف على كلام واضح. تأكد من اختيار لغة الكلام الصحيحة.", "🤷 No clear speech detected. Check the selected language."),
                                 kb([[B(v[0], f"t:lang:{k}") for k, v in LANGS.items()]]))
                else:
                    await bump(c, "vt:count")
                    for part in chunks(text):
                        await c.send("📝 " + esc(part))
            finally:
                cleanup(src, wav)
            return True
        text = c.text
        if not text:
            return False
        lang = "ar" if re.search(r"[؀-ۿ]", text) else "en"
        try:
            audio = await asyncio.wait_for(asyncio.to_thread(_tts, text[:1500], lang), 60)
        except Exception:
            await c.send(t("⚠️ تعذّر تحويل النص إلى صوت الآن. حاول بعد قليل.", "⚠️ Text-to-speech failed right now. Try again shortly."))
            return True
        await c.audio(io.BytesIO(audio), filename="speech.mp3", title=text[:40])
        await bump(c, "vt:count")
        return True


TPL = Voice()
