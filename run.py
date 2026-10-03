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
            if len(LOGS) > 1000:
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


_bot_started = False


async def handle_health(_req: web.Request) -> web.Response:
    return web.Response(text="BotForge OK", status=200)


async def handle_debug(_req: web.Request) -> web.Response:
    status_lines = ["=== BOT STATUS ==="]
    status_lines.append(f"bot_started={_bot_started}")
    try:
        from forge.runtime import manager
        maker_stat = "Not initialized"
        if hasattr(manager, "maker") and manager.maker:
            try:
                up_run = manager.maker.updater.running if manager.maker.updater else False
                maker_stat = f"username=@{manager.maker.bot.username}, running={manager.maker.running}, polling={up_run}"
            except Exception as e:
                maker_stat = f"error accessing maker props: {e}"
        status_lines.append(f"Maker: {maker_stat}")
        status_lines.append(f"Child bots: {len(manager.apps) if hasattr(manager, 'apps') else 0}")
    except Exception as e:
        status_lines.append(f"Manager error: {e}")
    status_lines.append("\n=== RECENT LOGS (last 80) ===")
    return web.Response(
        text="\n".join(status_lines) + "\n" + ("\n".join(LOGS[-80:]) or "No logs yet"),
        content_type="text/plain",
    )


async def start_http_server(port: int):
    app = web.Application()
    app.router.add_get("/", handle_health)
    app.router.add_get("/healthz", handle_health)
    app.router.add_get("/debug", handle_debug)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info("Health HTTP server listening on 0.0.0.0:%d", port)
    return runner


async def _self_ping_loop(port: int) -> None:
    """Ping الخادم كل 10 دقائق لمنع Render Free Tier من النوم وإيقاف البوت."""
    await asyncio.sleep(60)  # انتظر دقيقة حتى يكتمل التشغيل
    # Render يوفر الرابط الخارجي في متغير RENDER_EXTERNAL_URL
    external = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
    ping_url = f"{external}/healthz" if external else ""
    while True:
        if ping_url:
            try:
                req = urllib.request.Request(ping_url, headers={"User-Agent": "BotForge-KeepAlive/1.0"})
                urllib.request.urlopen(req, timeout=15)
                logging.info("Keep-alive ping OK → %s", ping_url)
            except Exception as e:
                logging.warning("Keep-alive ping failed: %s", e)
        await asyncio.sleep(540)  # كل 9 دقائق (أقل من حد الـ 15 دقيقة)



async def _try_start_all() -> bool:
    """محاولة واحدة لتشغيل البوت. تعيد True عند النجاح."""
    global _bot_started
    try:
        from forge.runtime import manager
        await manager.start_all()
        _bot_started = True
        logging.info("✅ BotForge started successfully!")
        notify(f"✅ BotForge LIVE!\nBot: @{manager.maker.bot.username}")
        return True
    except SystemExit as e:
        logging.error("FATAL SystemExit in start_all: %s", e)
        notify(f"❌ Fatal: {e}")
        return False  # لا تعيد المحاولة - مشكلة إعداد
    except Exception:
        err = traceback.format_exc()
        logging.error("start_all failed: %s", err)
        return False


async def main() -> None:
    global _bot_started
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for noisy in ("httpx", "httpcore", "apscheduler", "telegram.ext.Updater", "telegram.ext._updater"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # 1. بدء خادم HTTP أولاً حتى يتعرف Render على الخدمة
    port = int(os.environ.get("PORT", os.environ.get("WEB_PORT", 0)) or 0)
    runner = None
    ping_task = None
    if port > 0:
        try:
            runner = await start_http_server(port)
            # ابدأ self-ping لمنع Render من إيقاف الخدمة تلقائياً (Free Tier)
            ping_task = asyncio.create_task(_self_ping_loop(port))
            logging.info("Self-ping keep-alive started (every 10 min)")
        except Exception:
            logging.exception("Failed to start health HTTP server on port %s", port)


    # 2. محاولة تشغيل البوت مع إعادة المحاولة التلقائية
    notify("🚀 BotForge initializing...")
    max_retries = 10
    for attempt in range(1, max_retries + 1):
        ok = await _try_start_all()
        if ok:
            break
        if attempt < max_retries:
            wait = min(attempt * 5, 30)
            logging.warning("Retry %d/%d in %ds...", attempt, max_retries, wait)
            await asyncio.sleep(wait)
        else:
            logging.error("All %d attempts failed. Bot will stay down.", max_retries)
            notify("❌ BotForge failed to start after all retries.")

    # 3. إعداد إشارات الإيقاف
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass

    # 4. Watchdog: يراقب البوت كل 10 ثوانٍ ويعيد تشغيله إذا توقف
    async def _watchdog():
        while not stop.is_set():
            try:
                await asyncio.sleep(10)
                from forge.runtime import manager

                # فحص حالة polling
                maker_ok = False
                if hasattr(manager, "maker") and manager.maker:
                    try:
                        up = manager.maker.updater
                        maker_ok = bool(up and up.running)
                    except Exception:
                        maker_ok = False

                if not maker_ok:
                    logging.warning("⚠️ Watchdog: polling is DOWN! Attempting recovery...")
                    # محاولة إعادة تشغيل polling فقط أولاً
                    recovered = False
                    if hasattr(manager, "maker") and manager.maker and manager.maker.updater:
                        try:
                            await manager.maker.updater.start_polling(
                                allowed_updates=Update.ALL_TYPES,
                                drop_pending_updates=False,
                            )
                            recovered = True
                            logging.info("✅ Watchdog: polling revived!")
                            notify("✅ Watchdog revived polling!")
                        except Exception as poll_err:
                            logging.error("Watchdog polling revival failed: %s", poll_err)

                    if not recovered:
                        # إعادة تشغيل كاملة
                        logging.warning("⚠️ Watchdog: full restart...")
                        try:
                            await manager.shutdown()
                        except Exception:
                            pass
                        for attempt in range(5):
                            ok = await _try_start_all()
                            if ok:
                                logging.info("✅ Watchdog: full restart succeeded!")
                                notify("✅ Watchdog: bot fully restarted!")
                                break
                            await asyncio.sleep(10)
                        else:
                            logging.error("Watchdog: full restart failed after 5 attempts")

            except asyncio.CancelledError:
                break
            except Exception as w_err:
                logging.error("Watchdog exception: %s", w_err)

    watchdog_task = asyncio.create_task(_watchdog())
    try:
        await stop.wait()
    finally:
        watchdog_task.cancel()
        if ping_task:
            ping_task.cancel()
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
        notify(f"❌ Unhandled Exception:\n{err}")
        sys.exit(1)
