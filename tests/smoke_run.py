"""يشغّل run.py كعملية مستقلة أمام الخادم الوهمي ويتأكد أنه يقلع ويرد ثم يتوقف بنظافة."""
import asyncio
import os
import signal
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.mock_tg import MockTG  # noqa: E402

MAKER = "100000100:" + "A" * 35


async def main():
    tg = MockTG()
    await tg.start()
    tmp = tempfile.mkdtemp()
    env = dict(os.environ, BOT_API_BASE=tg.base, BOT_API_FILE_BASE=tg.file_base, MAKER_TOKEN=MAKER, ADMIN_ID="", DATA_DIR=tmp, DATABASE_URL="")
    p = await asyncio.create_subprocess_exec(sys.executable, "run.py", cwd=str(Path(__file__).resolve().parent.parent), env=env,
                                             stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    out = b""
    for _ in range(200):
        out += await p.stdout.read(200)
        if b"is running" in out:
            break
    tg.message(MAKER, tg.user(5, "Ali"), "/start")
    await asyncio.sleep(2)
    replied = any("أهلاً Ali" in c["p"].get("text", "") for c in tg.calls)
    p.send_signal(signal.SIGINT)
    code = await asyncio.wait_for(p.wait(), 20)
    print("started:", b"is running" in out, "| replied:", replied, "| exit code:", code, "| db:", (Path(tmp) / "forge.db").exists(), "| key:", (Path(tmp) / "secret.key").exists())
    await tg.stop()


asyncio.run(main())
