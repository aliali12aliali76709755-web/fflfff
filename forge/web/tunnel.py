"""نفق https تلقائي (Cloudflare quick tunnel) ليعمل التطبيق المصغّر داخل تيليجرام من جهاز بلا نطاق.

تيليجرام لا يفتح صفحة داخل التطبيق إلا من رابط https عام. حين لا يُضبط PUBLIC_URL ويكون AUTO_TUNNEL=1
نشغّل cloudflared فيعطينا رابطاً مؤقتاً من نوع https://xxxx.trycloudflare.com يوصل إلى خادم الويب المحلي.
الرابط يتغير مع كل تشغيل، فنعيد ضبط أزرار القوائم في البوتات كلما تغيّر.
"""
from __future__ import annotations

import asyncio
import logging
import platform as _platform
import re
import shutil
import stat
import sys
import tarfile
import time
from pathlib import Path

import httpx

from .. import config

log = logging.getLogger("forge.tunnel")
URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
RELEASE = "https://github.com/cloudflare/cloudflared/releases/latest/download/"
TOOLS = config.DATA_DIR / "tools"


def _asset() -> str | None:
    """اسم ملف cloudflared المناسب لهذا الجهاز في صفحة الإصدارات الرسمية."""
    machine = _platform.machine().lower()
    arm = machine in ("arm64", "aarch64")
    if sys.platform.startswith("win"):
        return "cloudflared-windows-amd64.exe" if "64" in machine or machine == "amd64" else "cloudflared-windows-386.exe"
    if sys.platform == "darwin":
        return "cloudflared-darwin-arm64.tgz" if arm else "cloudflared-darwin-amd64.tgz"
    if sys.platform.startswith("linux"):
        if arm:
            return "cloudflared-linux-arm64"
        return "cloudflared-linux-amd64" if machine in ("x86_64", "amd64") else ("cloudflared-linux-arm" if machine.startswith("arm") else "cloudflared-linux-386")
    return None


def _local() -> Path:
    return TOOLS / ("cloudflared.exe" if sys.platform.startswith("win") else "cloudflared")


def find() -> str | None:
    if config.CLOUDFLARED:
        return config.CLOUDFLARED if Path(config.CLOUDFLARED).exists() else None
    return shutil.which("cloudflared") or (str(_local()) if _local().exists() else None)


async def download() -> str | None:
    """ينزّل cloudflared من إصدارات Cloudflare الرسمية إلى data/tools. يعيد المسار أو None."""
    asset = _asset()
    if asset is None:
        return None
    TOOLS.mkdir(parents=True, exist_ok=True)
    target, tmp = _local(), TOOLS / (asset + ".part")
    log.info("downloading %s from Cloudflare releases (one time)…", asset)
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(30, read=120)) as cl:
            async with cl.stream("GET", RELEASE + asset) as r:
                r.raise_for_status()
                with open(tmp, "wb") as fh:
                    async for chunk in r.aiter_bytes(1 << 16):
                        fh.write(chunk)
        if asset.endswith(".tgz"):
            with tarfile.open(tmp) as tf:
                member = next(m for m in tf.getmembers() if m.isfile() and Path(m.name).name == "cloudflared")
                with tf.extractfile(member) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
            tmp.unlink(missing_ok=True)
        else:
            tmp.replace(target)
        target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return str(target)
    except Exception as err:  # noqa: BLE001
        log.warning("could not download cloudflared: %s", err)
        tmp.unlink(missing_ok=True)
        return None


class Tunnel:
    """يدير عملية cloudflared: تشغيل، قراءة الرابط، وإعادة التشغيل إن توقفت."""

    RESTART_DELAY = 10.0

    def __init__(self, on_url) -> None:
        self.on_url = on_url          # دالة تُستدعى مع كل رابط جديد
        self.proc: asyncio.subprocess.Process | None = None
        self.url = ""
        self.error = ""
        self._task: asyncio.Task | None = None
        self._stopping = False
        self._got = asyncio.Event()
        self._starts: list[float] = []
        self.last = ""

    async def start(self, wait: float = 40.0) -> str:
        """يشغّل النفق وينتظر رابطه. يعيد الرابط، أو نصاً فارغاً إن تعذّر (والبوتات تكمل بلا مواقع داخلية)."""
        binary = find()
        if binary is None:
            binary = await download()
        if binary is None:
            self.error = "cloudflared غير موجود وتعذّر تنزيله"
            log.warning("auto tunnel unavailable: cloudflared not found and could not be downloaded")
            return ""
        self._binary = binary
        self._task = asyncio.create_task(self._run())
        try:
            await asyncio.wait_for(self._got.wait(), wait)
        except asyncio.TimeoutError:
            self.error = "لم يصل رابط النفق في الوقت المتوقع"
            log.warning("tunnel url not received within %ss; will keep trying in the background", wait)
        return self.url

    async def _spawn(self) -> None:
        self.proc = await asyncio.create_subprocess_exec(
            self._binary, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{config.WEB_PORT}",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, stdin=asyncio.subprocess.DEVNULL)

    async def _run(self) -> None:
        while not self._stopping:
            now = time.time()
            self._starts = [t for t in self._starts if now - t < 3600] + [now]
            if len(self._starts) > 12:      # يتعطل باستمرار: نهدأ نصف ساعة ثم نحاول من جديد
                self.error = "النفق يتوقف مراراً" + (f" ({self.last})" if self.last else "")
                log.warning("tunnel keeps failing (%s); retrying in 30 minutes", self.last)
                await asyncio.sleep(1800)
                self._starts = []
                continue
            try:
                await self._spawn()
            except OSError as err:
                self.error = f"تعذّر تشغيل cloudflared: {err}"
                log.warning("cannot run cloudflared: %s", err)
                return
            assert self.proc is not None and self.proc.stdout is not None
            while True:
                line = await self.proc.stdout.readline()
                if not line:
                    break
                text = line.decode("utf-8", "replace").strip()
                if text:
                    self.last = text[-160:]
                m = URL_RE.search(text)
                if m and m.group(0) != self.url:
                    self.url, self.error = m.group(0), ""
                    log.info("tunnel url: %s", self.url)
                    self._got.set()
                    try:
                        await self.on_url(self.url)
                    except Exception:  # noqa: BLE001
                        log.exception("on_url failed")
            await self.proc.wait()
            if self._stopping:
                return
            if not self.url:
                self.error = f"توقف cloudflared قبل أن يعطي رابطاً: {self.last}" if self.last else "توقف cloudflared قبل أن يعطي رابطاً"
            log.warning("tunnel process exited (code %s); restarting in %ss", self.proc.returncode, self.RESTART_DELAY)
            await asyncio.sleep(self.RESTART_DELAY)

    async def stop(self) -> None:
        self._stopping = True
        if self.proc is not None and self.proc.returncode is None:
            try:
                self.proc.terminate()
                await asyncio.wait_for(self.proc.wait(), 5)
            except (ProcessLookupError, asyncio.TimeoutError):
                try:
                    self.proc.kill()
                except ProcessLookupError:
                    pass
        if self._task is not None:
            self._task.cancel()
