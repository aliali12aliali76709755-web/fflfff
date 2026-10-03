"""ضغط الفيديو: تقليل حجم الفيديو ليناسب واتساب وتيليجرام عبر ffmpeg."""
from telegram.constants import ChatAction

from .. import config, ui
from ..ctx import Ctx
from ..ui import B, kb
from . import Tpl
from ._util import bump, cleanup, ffmpeg, fits_upload, mb, too_big

LEVELS = {"l": ("🟢 خفيف (720p)", "🟢 Light (720p)", 720, 26), "m": ("🟡 متوسط (480p)", "🟡 Medium (480p)", 480, 28),
          "h": ("🔴 قوي (360p)", "🔴 Strong (360p)", 360, 31)}


class Compress(Tpl):
    emoji, ar, en = "📉", "ضغط الفيديو", "Video compressor"
    d_ar, d_en = "قلّل حجم الفيديو ليناسب الواتساب وتيليجرام", "Shrink videos to fit WhatsApp and Telegram"
    cats = ("top", "tools")
    guide_ar = ("المستخدم يرسل فيديو ويختار قوة الضغط (خفيف 720p، متوسط 480p، قوي 360p)، ويستلم الفيديو مضغوطاً مع الحجم قبل وبعد.\n\n"
                f"• حد الاستقبال الحالي من تيليجرام: {config.MAX_DOWNLOAD_MB}MB (20MB مع Bot API العادي، وحتى 2GB مع خادم Bot API محلي).\n"
                "• الضغط يستهلك معالج السيرفر، فالفيديوهات الطويلة تأخذ وقتاً.")

    async def home(self, c: Ctx) -> None:
        await c.edit(ui.head(c.brand) + "\n" + c.t(f"🎬 أرسل الفيديو (حتى {config.MAX_DOWNLOAD_MB}MB) ثم اختر قوة الضغط.",
                                                             f"🎬 Send the video (up to {config.MAX_DOWNLOAD_MB}MB) then pick the strength."), kb([c.tail()]))

    async def owner(self, c: Ctx):
        n = await c.kv("cmp:count", 0)
        return c.t(f"📉 فيديوهات ضُغطت: {n}", f"📉 Videos compressed: {n}"), []

    async def cb(self, c: Ctx, a: list[str]) -> None:
        if a[0] != "q" or a[1] not in LEVELS:
            return
        fid = c.x.user_data.get("cmp_file")
        if not fid:
            await c.answer(c.t("أرسل الفيديو أولاً.", "Send the video first."), True)
            return
        _, _, h, crf = LEVELS[a[1]]
        await c.edit(c.t("⏳ جاري الضغط… انتظر قليلاً.", "⏳ Compressing… please wait."))
        src = out = None
        try:
            src = await c.download(fid, ".mp4")
            out = c.tmp(".mp4")
            ok, err = await ffmpeg(["-i", str(src), "-vf", f"scale=-2:'min({h},ih)'", "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
                                    "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(out)])
            if not ok or not out.exists():
                await c.send(c.t(f"⚠️ فشل الضغط. {err[:120]}", f"⚠️ Compression failed. {err[:120]}"))
                return
            if not fits_upload(out):
                await c.send(c.t("⚠️ الناتج ما زال أكبر من حد الإرسال. جرّب ضغطاً أقوى.", "⚠️ Output still exceeds the upload limit. Try a stronger level."))
                return
            await c.bot.send_chat_action(c.chat.id, ChatAction.UPLOAD_VIDEO)
            with open(out, "rb") as fh:
                await c.video(fh, caption=c.t(f"✅ قبل: {mb(src)} ← بعد: {mb(out)}", f"✅ Before: {mb(src)} → after: {mb(out)}"), supports_streaming=True, filename="compressed.mp4")
            await bump(c, "cmp:count")
        except Exception:
            await c.send(c.t("⚠️ تعذّرت معالجة الفيديو.", "⚠️ Couldn't process the video."))
        finally:
            cleanup(src, out)

    async def msg(self, c: Ctx) -> bool:
        f = c.file_of()
        if f is None or f[1] not in ("video", "document", "animation", "video_note"):
            await c.send(c.t("🎬 أرسل ملف فيديو.", "🎬 Please send a video file."))
            return True
        err = too_big(c, f[2])
        if err:
            await c.send(err)
            return True
        c.x.user_data["cmp_file"] = f[0]
        await c.send(c.t("اختر قوة الضغط:", "Pick the compression strength:"), kb([[B(c.t(v[0], v[1]), f"t:q:{k}")] for k, v in LEVELS.items()]))
        return True


TPL = Compress()
