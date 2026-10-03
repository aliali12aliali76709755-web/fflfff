"""تهيئة بيئة الاختبار: خادم تيليجرام وهمي + قاعدة بيانات مؤقتة."""
import logging
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.mock_tg import MockTG  # noqa: E402

MID = 100000100
MAKER = f"{MID}:" + "A" * 35
ADMIN = 1


def tok(bot_id: int) -> str:
    return f"{bot_id}:" + "B" * 35


def free_port() -> int:
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def boot(caps: dict | None = None, admin: int = ADMIN, web: bool = False, public_url: str = "", tunnel: str = ""):
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("forge.templates").setLevel(logging.ERROR)
    tg = MockTG()
    if caps:
        tg.caps[MID] = caps
    await tg.start()
    tmp = tempfile.mkdtemp(prefix="forge_")
    os.environ.update(BOT_API_BASE=tg.base, BOT_API_FILE_BASE=tg.file_base, MAKER_TOKEN=MAKER, ADMIN_ID=str(admin),
                      DATA_DIR=tmp, DATABASE_URL=f"sqlite+aiosqlite:///{tmp}/t.db", DEFAULT_LANG="ar",
                      WEB_PORT=str(free_port()) if web else "0", WEB_HOST="127.0.0.1", PUBLIC_URL=public_url,
                      AUTO_TUNNEL="1" if tunnel else "0", CLOUDFLARED=tunnel)
    from telegram.ext import Application
    orig = Application.process_update

    async def counted(self, update):
        try:
            await orig(self, update)
        finally:
            tg.processed += 1

    Application.process_update = counted
    from forge.runtime import manager
    await manager.start_all()
    return tg, manager


async def make_bot(tg, user, bot_id: int, tpl_key: str) -> str:
    """ينشئ بوتاً عبر الصانع بالقالب المطلوب ويعيد التوكن."""
    token = tok(bot_id)
    await tg.click(MAKER, user, f"m:tpl:{tpl_key}")
    await tg.say(MAKER, user, token)
    outs = [c["p"].get("text", "") for c in tg.out(MID)[-2:]]
    assert any("بوتك أصبح حياً" in o for o in outs), outs
    return token


ERRORS: list[str] = []


class _Collect(logging.Handler):
    def emit(self, record):
        if record.levelno >= logging.ERROR:
            ERRORS.append(self.format(record)[:1500])


class Check:
    def __init__(self):
        self.n = 0
        self.failed = []
        h = _Collect()
        h.setFormatter(logging.Formatter("%(name)s: %(message)s\n%(exc_text)s"))
        logging.getLogger().addHandler(h)

    def errors(self, label: str):
        """يفشل إن سُجّل أي استثناء منذ آخر فحص."""
        got = list(ERRORS)
        ERRORS.clear()
        self.ok(not got, f"{label}: بلا أخطاء" + ("" if not got else "\n      " + got[0].replace("\n", "\n      ")[-900:]))

    def ok(self, cond, label: str):
        self.n += 1
        if not cond:
            self.failed.append(label)
            print(f"  ✗ {label}")
        else:
            print(f"  ✓ {label}")

    def done(self):
        print(f"\n{self.n - len(self.failed)}/{self.n} passed")
        if self.failed:
            raise SystemExit(1)
