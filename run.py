"""نقطة التشغيل: python run.py"""
import asyncio
import json
import logging
import os
import signal
import sys
import traceback
import urllib.request


def notify(text: str) -> None:
    token = os.environ.get("MAKER_TOKEN", "")
    admin = os.environ.get("ADMIN_ID", "")
    if token and admin:
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            req = urllib.request.Request(
                url,
                data=json.dumps({"chat_id": int(admin), "text": text[:4000]}).encode(),
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=8)
        except Exception:
            pass


for _s in (sys.stdout, sys.stderr):  # طرفية ويندوز قد لا تدعم العربية افتراضياً
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    from forge.runtime import manager  # noqa: E402
except Exception as e:
    notify(f"❌ Failed to import forge.runtime:\n{traceback.format_exc()}")
    raise


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for noisy in ("httpx", "httpcore", "apscheduler", "telegram.ext.Updater"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    notify("🚀 BotForge is initializing on server...")
    try:
        await manager.start_all()
    except Exception as e:
        notify(f"❌ Error in manager.start_all():\n{traceback.format_exc()}")
        raise
    notify(f"✅ BotForge is LIVE on server!\nBot: @{manager.maker.bot.username}")
    print(f"\n✅ BotForge is running — maker bot: https://t.me/{manager.maker.bot.username}")
    print(f"   Child bots running: {len(manager.apps)}.  Press Ctrl+C to stop.\n")
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # Windows
            pass
    try:
        await stop.wait()
    finally:
        await manager.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        notify(f"❌ Unhandled Exception in run.py:\n{traceback.format_exc()}")
        raise
