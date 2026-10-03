"""نقطة التشغيل: python run.py"""
import asyncio
import logging
import signal
import sys

for _s in (sys.stdout, sys.stderr):  # طرفية ويندوز قد لا تدعم العربية افتراضياً
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from forge.runtime import manager  # noqa: E402


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for noisy in ("httpx", "httpcore", "apscheduler", "telegram.ext.Updater"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    await manager.start_all()
    print(f"\n✅ BotForge is running — maker bot: https://t.me/{manager.maker.bot.username}")
    print(f"   Child bots running: {len(manager.apps)}.  Press Ctrl+C to stop.")
    from forge import config, web
    if manager.web is not None:
        print(f"   Website on this computer: {web.local_url()}")
        if manager.tunnel is not None and manager.tunnel.url:
            print(f"   Public https tunnel (changes every run): {config.PUBLIC_URL}")
            print("   Bots now open their sites INSIDE Telegram (menu button next to the message box).")
        elif config.PUBLIC_URL:
            print(f"   Public URL: {config.PUBLIC_URL}")
        elif manager.tunnel is not None:
            print(f"   Auto https tunnel is still starting ({manager.tunnel.error or 'first run downloads cloudflared, ~40MB'}).")
            print("   Website buttons appear in the bots by themselves once it is ready; watch this window for 'tunnel url'.")
        else:
            print("   No PUBLIC_URL and AUTO_TUNNEL=0: sites stay local; Telegram cannot open them inside bots (see README).")
    print()
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
