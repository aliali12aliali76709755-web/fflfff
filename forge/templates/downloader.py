"""تحميل الفيديوهات: تنزيل الوسائط العامة من يوتيوب وإنستغرام وتيك توك وX وفيسبوك وريديت عبر yt-dlp."""
import asyncio
import logging
import re
from pathlib import Path

from telegram.constants import ChatAction

from .. import config, ui
from ..ctx import Ctx
from ..ui import B, esc, kb
from . import Tpl
from ._util import FFMPEG, bump, cleanup, fits_upload, mb

log = logging.getLogger("forge.downloader")
URL_RE = re.compile(r"https?://[^\s<>\"]+", re.I)
_sem = asyncio.Semaphore(3)  # حد التنزيلات المتزامنة على السيرفر كله


def _download(url: str, base: Path, audio: bool, max_mb: int) -> tuple[Path, str]:
    from yt_dlp import YoutubeDL
    limit = max_mb * 1024 * 1024
    fmt = ("bestaudio[ext=m4a]/bestaudio/best" if audio else
           f"b[ext=mp4][filesize<{max_mb}M]/bv*[ext=mp4][height<=720]+ba[ext=m4a]/b[height<=720]/b[filesize<{max_mb}M]/b")
    opts = {"outtmpl": f"{base}.%(ext)s", "format": fmt, "noplaylist": True, "quiet": True, "no_warnings": True,
            "max_filesize": limit, "merge_output_format": "mp4", "socket_timeout": 30, "retries": 2,
            "restrictfilenames": True, "concurrent_fragment_downloads": 4}
    if FFMPEG:
        opts["ffmpeg_location"] = FFMPEG
    with YoutubeDL(opts) as y:
        info = y.extract_info(url, download=True)
        if "entries" in info:
            info = info["entries"][0]
    files = sorted(base.parent.glob(base.name + ".*"), key=lambda p: p.stat().st_size, reverse=True)
    if not files:
        raise RuntimeError("too_big")
    return files[0], (info.get("title") or "")[:200]


class Downloader(Tpl):
    emoji, ar, en = "📥", "تحميل الفيديوهات", "Video downloader"
    d_ar = "حمّل الوسائط العامة من يوتيوب وإنستغرام وتيك توك وX وفيسبوك وريديت"
    d_en = "Download public media from YouTube, Instagram, TikTok, X, Facebook and Reddit"
    guide_ar = ("المستخدم يرسل رابط فيديو عام ويختار «فيديو» أو «صوت»، فينزّله البوت ويرسله له.\n\n"
                f"• حد الحجم الحالي: {config.MAX_UPLOAD_MB}MB للملف (حدّ Bot API العادي 50MB؛ للوصول إلى 2GB شغّل خادم Bot API محلياً واضبط LOCAL_API في .env).\n"
                "• يعمل مع المحتوى العام فقط؛ الحسابات الخاصة والمحتوى المحمي لا يُنزَّل.\n"
                "• المواقع تغيّر أنظمتها باستمرار، فحدّث مكتبة yt-dlp دورياً: <code>pip install -U yt-dlp</code>.\n"
                "• دمج الصوت مع الفيديو يتم عبر ffmpeg المضمّن مع المشروع.")

    async def home(self, c: Ctx) -> None:
        await c.edit(ui.head(c.brand) + "\n" + c.t(
            "🔗 أرسل رابط الفيديو من يوتيوب، إنستغرام، تيك توك، X، فيسبوك أو ريديت وسأحمّله لك.",
            "🔗 Send a video link from YouTube, Instagram, TikTok, X, Facebook or Reddit and I'll download it."), kb([c.tail()]))

    async def owner(self, c: Ctx):
        n = await c.kv("dl:count", 0)
        return c.t(f"📥 تنزيلات ناجحة: {n}\n📦 حد الحجم: {config.MAX_UPLOAD_MB}MB", f"📥 Successful downloads: {n}\n📦 Size limit: {config.MAX_UPLOAD_MB}MB"), []

    async def cb(self, c: Ctx, a: list[str]) -> None:
        if a[0] not in ("v", "a"):
            return
        url = c.x.user_data.get("dl_url")
        if not url:
            await c.answer(c.t("أرسل الرابط أولاً.", "Send the link first."), True)
            return
        if c.x.user_data.get("dl_busy"):
            await c.answer(c.t("⏳ لديك تنزيل جارٍ.", "⏳ You already have a download running."), True)
            return
        c.x.user_data["dl_busy"] = True
        await c.edit(c.t("⏳ جاري التنزيل… قد يستغرق دقيقة.", "⏳ Downloading… this may take a minute."))
        base, path, audio = c.tmp(), None, a[0] == "a"
        try:
            async with _sem:
                path, title = await asyncio.wait_for(asyncio.to_thread(_download, url, base, audio, config.MAX_UPLOAD_MB), 600)
            if not fits_upload(path):
                await c.send(c.t(f"⚠️ الملف ({mb(path)}) أكبر من الحد المسموح ({config.MAX_UPLOAD_MB}MB).", f"⚠️ File ({mb(path)}) exceeds the limit ({config.MAX_UPLOAD_MB}MB)."))
                return
            await c.bot.send_chat_action(c.chat.id, ChatAction.UPLOAD_DOCUMENT)
            cap = esc(title)[:900]
            with open(path, "rb") as fh:
                if audio:
                    await c.audio(fh, caption=cap, title=title[:60] or None, filename=path.name)
                elif path.suffix.lower() in (".mp4", ".mov", ".m4v"):
                    await c.video(fh, caption=cap, supports_streaming=True, filename=path.name)
                else:
                    await c.doc(fh, caption=cap, filename=path.name)
            await bump(c, "dl:count")
        except asyncio.TimeoutError:
            await c.send(c.t("⚠️ انتهت مهلة التنزيل.", "⚠️ Download timed out."))
        except Exception as e:  # noqa: BLE001
            log.info("download failed: %s", str(e)[:200])
            msg = str(e).lower()
            if "too_big" in msg or "larger than max-filesize" in msg:
                await c.send(c.t(f"⚠️ الفيديو أكبر من الحد المسموح ({config.MAX_UPLOAD_MB}MB).", f"⚠️ The video exceeds the limit ({config.MAX_UPLOAD_MB}MB)."))
            else:
                await c.send(c.t("⚠️ تعذّر التنزيل. تأكد أن الرابط صحيح وأن المحتوى عام.", "⚠️ Download failed. Make sure the link is correct and public."))
        finally:
            c.x.user_data.pop("dl_busy", None)
            for p in base.parent.glob(base.name + ".*"):
                cleanup(p)

    async def msg(self, c: Ctx) -> bool:
        m = URL_RE.search(c.text)
        if not m:
            await c.send(c.t("🔗 أرسل رابطاً يبدأ بـ https://", "🔗 Send a link starting with https://"))
            return True
        c.x.user_data["dl_url"] = m.group(0)
        await c.send(c.t("اختر الصيغة:", "Pick a format:"), kb([[B(c.t("🎬 فيديو", "🎬 Video"), "t:v"), B(c.t("🎵 صوت فقط", "🎵 Audio only"), "t:a")]]))
        return True


TPL = Downloader()
