"""مدير التشغيل: يشغّل بوت الصانع وكل البوتات المصنوعة داخل عملية واحدة (long polling)."""
from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy import select
from telegram import Update
from telegram.error import Conflict, Forbidden, InvalidToken, TelegramError
from telegram.ext import Application, ApplicationBuilder

from . import child, config, crypto, db, templates
from . import plat as platform

log = logging.getLogger("forge.runtime")


class Manager:
    def __init__(self) -> None:
        self.apps: dict[int, Application] = {}
        self.maker: Application | None = None
        self._busy: set[int] = set()
        self.conflicts: dict[int, dict] = {}
        self._ticker: asyncio.Task | None = None
        self.web = None
        self.tunnel = None

    # ── بناء التطبيق ──
    def build(self, token: str) -> Application:
        b = (ApplicationBuilder().token(token).base_url(config.BOT_API_BASE).base_file_url(config.BOT_API_FILE_BASE)
             .connect_timeout(20).read_timeout(40).write_timeout(120).pool_timeout(30)
             .get_updates_read_timeout(40)
             .concurrent_updates(128)
             .connection_pool_size(256))
        if config.LOCAL_API:
            b = b.local_mode(True)
        return b.build()

    async def probe(self, token: str, webhook: bool = False):
        """يتحقق من التوكن ويعيد بيانات البوت (User) أو يرفع استثناء. مع webhook=True يعيد (User, رابط الويب هوك الحالي)."""
        app = self.build(token)
        try:
            await app.bot.initialize()
            if webhook:
                try:
                    info = await app.bot.get_webhook_info()
                    return app.bot.bot, (info.url or "")
                except TelegramError:
                    return app.bot.bot, ""
            return app.bot.bot
        finally:
            try:
                await app.bot.shutdown()
            except Exception:
                pass

    # ── البوتات المصنوعة ──
    def running(self, bot_id: int) -> bool:
        return bot_id in self.apps

    async def _set_status(self, bot_id: int, status: str, error: str = "") -> None:
        async with db.Session() as s:
            row = await s.get(db.Bot, bot_id)
            if row is not None:
                row.status, row.error = status, error[:500]
                await s.commit()

    async def start_bot(self, row: db.Bot) -> tuple[bool, str]:
        if row.id in self.apps or row.id in self._busy:
            return True, ""
        self._busy.add(row.id)
        try:
            app = self.build(crypto.dec(row.token))
            tpl = templates.get(row.template)
            core = await child.load_core(row.id)
            app.bot_data["manager"] = self
            app.bot_data["adm"] = await platform.adm(row.id)
            child.register(app, row, tpl, core)
            await app.initialize()
            await app.start()
            bot_id = row.id

            def on_poll_error(err: TelegramError) -> None:
                loop = asyncio.get_running_loop()
                if isinstance(err, (InvalidToken, Forbidden)):
                    loop.create_task(self._fail(bot_id, "التوكن غير صالح أو تم إلغاؤه"))
                elif isinstance(err, Conflict):
                    loop.create_task(self._conflict(bot_id))

            await app.updater.start_polling(allowed_updates=Update.ALL_TYPES, error_callback=on_poll_error)
            self.apps[row.id] = app
            await self._set_status(row.id, "active")
            app.create_task(child.set_commands(app))
            return True, ""
        except (InvalidToken, Forbidden):
            await self._set_status(row.id, "error", "التوكن غير صالح أو تم إلغاؤه")
            return False, "token"
        except Exception as e:  # noqa: BLE001
            log.exception("start_bot %s failed", row.id)
            await self._set_status(row.id, "error", str(e))
            return False, str(e)
        finally:
            self._busy.discard(row.id)

    async def _fail(self, bot_id: int, reason: str) -> None:
        await self.stop_bot(bot_id)
        await self._set_status(bot_id, "error", reason)
        await self._tell_owner(bot_id, f"⚠️ توقف بوتك @{{u}}: {reason}.\nافتح «بوتاتي» ← البوت ← «🔑 التوكن» وأرسل التوكن الجديد من @BotFather.")

    async def _conflict(self, bot_id: int) -> None:
        """التوكن يُستخدم في مكان آخر. لا نوقف البوت (قد يكون تعارضاً عابراً)، لكن ننبه المالك إن استمر."""
        now = time.time()
        st = self.conflicts.setdefault(bot_id, {"first": now, "last": now, "told": False})
        if now - st["last"] > 120:      # انقطع التعارض ثم عاد: ابدأ العدّ من جديد
            st.update(first=now, told=False)
        st["last"] = now
        if now - st["first"] > 45 and not st["told"]:
            st["told"] = True
            await self._set_status(bot_id, "active", "تعارض: التوكن مستخدم في مكان آخر")
            await self._tell_owner(bot_id, "⚠️ بوتك @{u} يعمل في مكان آخر بنفس التوكن (منصة أو سيرفر آخر)، لذلك تضيع بعض رسائله.\n\n"
                                           "الحل: أرسل /revoke إلى @BotFather واختر البوت للحصول على توكن جديد، ثم من «بوتاتي» ← البوت ← «🔑 التوكن» أرسل التوكن الجديد.")

    def in_conflict(self, bot_id: int) -> bool:
        st = self.conflicts.get(bot_id)
        return bool(st and time.time() - st["last"] < 120)

    async def _tell_owner(self, bot_id: int, text: str) -> None:
        async with db.Session() as s:
            row = await s.get(db.Bot, bot_id)
        if row is None:
            return
        sender = self.maker if row.factory_id == 0 else self.apps.get(row.factory_id)
        if sender is None:
            return
        try:
            await sender.bot.send_message(row.owner_id, text.replace("{u}", row.username or str(bot_id)))
        except TelegramError:
            pass

    async def stop_bot(self, bot_id: int) -> None:
        app = self.apps.pop(bot_id, None)
        self.conflicts.pop(bot_id, None)
        if app is None:
            return
        for step in (app.updater.stop, app.stop, app.shutdown):
            try:
                await step()
            except Exception:  # noqa: BLE001
                pass

    async def restart_bot(self, bot_id: int) -> tuple[bool, str]:
        await self.stop_bot(bot_id)
        async with db.Session() as s:
            row = await s.get(db.Bot, bot_id)
        if row is None:
            return False, "missing"
        return await self.start_bot(row)

    def set_owner(self, bot_id: int, owner_id: int) -> None:
        app = self.apps.get(bot_id)
        if app is not None:
            app.bot_data["owner_id"] = owner_id

    # ── دورة الحياة ──
    async def start_all(self) -> None:
        from . import maker  # تأجيل الاستيراد لتفادي الحلقة
        templates.load()
        await db.init()
        await platform.preload()
        await self._start_web()
        if not config.ADMIN_ID:  # المدير يُحدَّد تلقائياً: أول من يفتح الصانع
            config.ADMIN_ID = int(await db.kv_get(0, "sys:admin", 0) or 0)
        if not config.MAKER_TOKEN:
            raise SystemExit("MAKER_TOKEN غير موجود. ضعه في ملف .env")
        self.maker = self.build(config.MAKER_TOKEN)
        self.maker.bot_data.update(manager=self, factory_id=0, maker_fid=0)
        maker.register(self.maker)
        await self.maker.initialize()
        await self.maker.start()
        await self.maker.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        log.info("maker @%s started", self.maker.bot.username)
        self.maker.create_task(maker.set_commands(self.maker))
        async with db.Session() as s:
            rows = (await s.execute(select(db.Bot).where(db.Bot.status == "active"))).scalars().all()
        sem = asyncio.Semaphore(8)

        async def boot(r: db.Bot):
            async with sem:
                ok, err = await self.start_bot(r)
                if not ok:
                    log.warning("bot @%s not started: %s", r.username, err)

        await asyncio.gather(*(boot(r) for r in rows))
        log.info("%d child bots running", len(self.apps))
        self._ticker = asyncio.create_task(self._tick_loop())

    async def _start_web(self) -> None:
        self.tunnel = None
        try:
            from .web import server as webserver
            self.web = await webserver.start(self)
        except Exception:
            self.web = None

    async def _on_tunnel_url(self, url: str) -> None:
        """رابط النفق يتغير مع كل تشغيل: نعتمده رابطاً عاماً ونعيد ضبط أزرار القوائم."""
        config.PUBLIC_URL = url
        await self.refresh_menus()

    async def refresh_menus(self) -> int:
        from . import maker
        if self.maker is not None:
            await maker.apply_menu(self.maker)
        n = 0
        for app in list(self.apps.values()):
            await child.apply_menu_button(app)
            n += 1
        return n

    async def _tick_loop(self) -> None:
        while True:
            await asyncio.sleep(30)
            try:
                await self.tick()
            except Exception:  # noqa: BLE001
                log.exception("tick failed")

    async def tick(self) -> None:
        """مهام دورية: إنهاء الإغلاقات المؤقتة، والتقرير اليومي للمدير."""
        from . import admin
        await admin.expire_locks(self)
        await admin.daily_report(self)
        await self._sweep()

    async def _sweep(self) -> None:
        """كل ساعة: حذف طلبات الويب وحجوزاته التي لم يؤكدها أصحابها خلال يومين."""
        import datetime as dt

        from sqlalchemy import delete
        if time.time() - getattr(self, "_swept", 0) < 3600:
            return
        self._swept = time.time()
        async with db.Session() as s:
            await s.execute(delete(db.Rec).where(db.Rec.kind.like("%:web"), db.Rec.created < db.now() - dt.timedelta(days=2)))
            await s.commit()
        cache = config.DATA_DIR / "webcache"
        if cache.is_dir():      # صور لم تُطلب منذ شهرين
            for f in cache.iterdir():
                try:
                    if time.time() - f.stat().st_mtime > 60 * 86400:
                        f.unlink()
                except OSError:
                    pass

    async def shutdown(self) -> None:
        if self._ticker is not None:
            self._ticker.cancel()
        if self.tunnel is not None:
            await self.tunnel.stop()
            self.tunnel = None
            config.PUBLIC_URL = ""
        if self.web is not None:
            from .web import server as webserver
            await webserver.stop(self.web)
            self.web = None
        for bot_id in list(self.apps):
            await self.stop_bot(bot_id)
        if self.maker is not None:
            for step in (self.maker.updater.stop, self.maker.stop, self.maker.shutdown):
                try:
                    await step()
                except Exception:  # noqa: BLE001
                    pass


manager = Manager()
