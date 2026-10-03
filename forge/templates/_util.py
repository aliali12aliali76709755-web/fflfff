"""أدوات مشتركة بين القوالب: تشغيل ffmpeg، طلبات HTTP، نداء نماذج الذكاء، وحدود الأحجام."""
from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import httpx

from .. import config
from ..ctx import Ctx

def _find_ffmpeg() -> str | None:
    """ffmpeg من النظام إن وُجد، وإلا النسخة المضمّنة مع مكتبة imageio-ffmpeg (تعمل على ويندوز دون تثبيت)."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


FFMPEG = _find_ffmpeg()
UA = {"User-Agent": "Mozilla/5.0 (BotForge)"}


async def run(cmd: list[str], timeout: int = 600) -> tuple[int, str]:
    """يشغّل أمراً خارجياً دون حجب الحلقة. يعيد (كود الخروج، آخر مخرجات الخطأ)."""
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
    try:
        _, err = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return -1, "timeout"
    return proc.returncode or 0, (err or b"").decode(errors="ignore")[-600:]


async def ffmpeg(args: list[str], timeout: int = 900) -> tuple[bool, str]:
    if not FFMPEG:
        return False, "ffmpeg غير مثبت على السيرفر"
    code, err = await run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", *args], timeout)
    return code == 0, err


async def get_json(url: str, *, params: dict | None = None, headers: dict | None = None, timeout: float = 20):
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers={**UA, **(headers or {})}) as cl:
        r = await cl.get(url, params=params)
        r.raise_for_status()
        return r.json()


async def get_text(url: str, *, params: dict | None = None, timeout: float = 20) -> str:
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=UA) as cl:
        r = await cl.get(url, params=params)
        r.raise_for_status()
        return r.text


async def post_json(url: str, payload: dict, *, headers: dict | None = None, timeout: float = 60):
    async with httpx.AsyncClient(timeout=timeout, headers={**UA, **(headers or {})}) as cl:
        r = await cl.post(url, json=payload)
        r.raise_for_status()
        return r.json()


def too_big(c: Ctx, size: int) -> str | None:
    """رسالة خطأ إن تجاوز الملف حد التنزيل من تيليجرام، وإلا None."""
    if size and size > config.MAX_DOWNLOAD_MB * 1024 * 1024:
        return c.t(f"⚠️ الملف أكبر من الحد المسموح ({config.MAX_DOWNLOAD_MB}MB).",
                   f"⚠️ File exceeds the allowed limit ({config.MAX_DOWNLOAD_MB}MB).")
    return None


def fits_upload(path: Path) -> bool:
    return path.exists() and path.stat().st_size <= config.MAX_UPLOAD_MB * 1024 * 1024


def cleanup(*paths: Path | None) -> None:
    for p in paths:
        try:
            if p is not None:
                Path(p).unlink(missing_ok=True)
        except OSError:
            pass


async def bump(c: Ctx, key: str, n: int = 1) -> int:
    v = int(await c.kv(key, 0)) + n
    await c.kv_set(key, v)
    return v


def chunks(text: str, size: int = 3800) -> list[str]:
    return [text[i:i + size] for i in range(0, len(text), size)] or [""]


async def grab(c: Ctx, suffix: str = "") -> Path | None:
    """ينزّل وسائط الرسالة الحالية إلى ملف مؤقت، أو يرسل رسالة الخطأ ويعيد None."""
    f = c.file_of()
    if f is None:
        return None
    err = too_big(c, f[2])
    if err:
        await c.send(err)
        return None
    try:
        return await c.download(f[0], suffix)
    except Exception:
        await c.send(c.t("⚠️ تعذّر تنزيل الملف من تيليجرام.", "⚠️ Couldn't download the file from Telegram."))
        return None


def mb(path: Path) -> str:
    return f"{path.stat().st_size / 1048576:.1f}MB"


def media_ext(c: Ctx) -> str:
    """امتداد الملف المرسل بحروف صغيرة (مثل .mp4) أو سلسلة فارغة."""
    m = c.msg
    for kind in ("document", "video", "audio", "animation"):
        obj = getattr(m, kind, None)
        name = getattr(obj, "file_name", None) if obj else None
        if name and "." in name:
            return "." + name.rsplit(".", 1)[-1].lower()
    if m.photo:
        return ".jpg"
    if m.voice:
        return ".ogg"
    if m.video or m.video_note:
        return ".mp4"
    if m.audio:
        return ".mp3"
    return ""
