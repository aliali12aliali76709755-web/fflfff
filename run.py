"""نقطة التشغيل: python run.py"""
import asyncio
import json
import logging
import os
import signal
import sys
import traceback
import urllib.request
from aiohttp import web
from telegram import Update

for _s in (sys.stdout, sys.stderr):  # طرفية ويندوز قد لا تدعم العربية افتراضياً
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

LOGS = []


class MemoryHandler(logging.Handler):
    def emit(self, record):
        try:
            LOGS.append(self.format(record))
            if len(LOGS) > 500:
                LOGS.pop(0)
        except Exception:
            pass


mem_handler = MemoryHandler()
mem_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
mem_handler.setLevel(logging.INFO)
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(mem_handler)


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


async def handle_health(_req: web.Request) -> web.Response:
    return web.Response(text="BotForge is running OK", status=200)


async def handle_debug(_req: web.Request) -> web.Response:
    status_lines = ["=== BOT STATUS ==="]
    try:
        from forge.runtime import manager
        maker_stat = "Not initialized"
        if hasattr(manager, "maker") and manager.maker:
            up_run = manager.maker.updater.running if manager.maker.updater else False
            maker_stat = f"username=@{manager.maker.bot.username}, running={manager.maker.running}, polling={up_run}"
        status_lines.append(f"Maker: {maker_stat}")
        status_lines.append(f"Child bots: {len(manager.apps) if hasattr(manager, 'apps') else 0}")
    except Exception as e:
        status_lines.append(f"Manager error: {e}")
    status_lines.append("\n=== RECENT LOGS ===")
    return web.Response(text="\n".join(status_lines) + "\n" + ("\n".join(LOGS) or "No logs yet"), content_type="text/plain")


async def start_http_server(port: int):
    app = web.Application()
    app.router.add_get("/", handle_health)
    app.router.add_get("/healthz", handle_health)
    app.router.add_get("/debug", handle_debug)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info("Render health HTTP server listening on 0.0.0.0:%d", port)
    return runner


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for noisy in ("httpx", "httpcore", "apscheduler", "telegram.ext.Updater"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # 1. Start HTTP server first for Render health checks
    port = int(os.environ.get("PORT", os.environ.get("WEB_PORT", 0)) or 0)
    runner = None
    if port > 0:
        try:
            runner = await start_http_server(port)
        except Exception:
            logging.exception("Failed to start health HTTP server on port %s", port)

    # 2. Start BotForge
    notify("🚀 BotForge is initializing on server...")
    try:
        from forge.runtime import manager

        await manager.start_all()
        notify(f"✅ BotForge is LIVE on server!\nBot: @{manager.maker.bot.username}")
        print(f"\n✅ BotForge is running — maker bot: https://t.me/{manager.maker.bot.username}")
        print(f"   Child bots running: {len(manager.apps)}. Press Ctrl+C to stop.\n")
    except BaseException:
        err = traceback.format_exc()
        logging.error("FATAL in start_all: %s", err)
        notify(f"❌ Error in start_all:\n{err}")

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass

    async def _watchdog():
        while not stop.is_set():
            try:
                await asyncio.sleep(15)
                from forge.runtime import manager
                if hasattr(manager, "maker") and manager.maker:
                    up = manager.maker.updater
                    if up and not up.running:
                        logging.warning("⚠️ Watchdog: Polling was stopped! Automatically reviving polling...")
                        try:
                            await up.start_polling(allowed_updates=Update.ALL_TYPES)
                            logging.info("✅ Watchdog: Polling successfully revived!")
                        except Exception as poll_err:
                            logging.error("Watchdog failed to revive polling: %s", poll_err)
            except asyncio.CancelledError:
                break
            except Exception as w_err:
                logging.error("Watchdog exception: %s", w_err)

    watchdog_task = asyncio.create_task(_watchdog())
    try:
        await stop.wait()
    finally:
        watchdog_task.cancel()
        if runner:
            await runner.cleanup()
        try:
            from forge.runtime import manager

            await manager.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except BaseException:
        err = traceback.format_exc()
        notify(f"❌ Unhandled Exception in run.py:\n{err}")
        sys.exit(1)
