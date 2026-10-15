"""ربط موقع الأرقام hero-sms من ملف seed_providers.txt + بروتوكول SMS-Activate (حجز/فحص/إلغاء/رصيد)."""
import os

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from forge import db
from forge.modules import smm_agg
from forge.modules.providers.sms import StandardSMSAdapter

KEY = "A03A61d78546c69fbfc5d8b9996A21fe"


@pytest.mark.anyio
async def test_seed_and_protocol():
    await db.init()
    await db.kv_set(0, "sms:providers", [])
    await db.kv_set(0, "sms:seeded", False)
    await db.kv_set(0, smm_agg.SEED_FLAG, True)          # لا نلمس مواقع التفاعل هنا
    os.environ["SEED_TEST"] = "1"
    try:
        await smm_agg.seed_once()
    finally:
        os.environ.pop("SEED_TEST", None)
    provs = await db.kv_get(0, "sms:providers", [])
    assert provs == [{"name": "hero-sms", "api_url": "https://hero-sms.com/stubs/handler_api.php", "api_key": KEY, "on": True}]
    assert await smm_agg.seed_once() == 0 and len(await db.kv_get(0, "sms:providers", [])) == 1, "مرة واحدة فقط"
    await db.kv_set(0, "sms:providers", [])

    seen = []

    async def h(req):
        q = req.query
        seen.append(dict(q))
        if q.get("api_key") != KEY:
            return web.Response(text="BAD_KEY")
        a = q.get("action")
        if a == "getBalance":
            return web.Response(text="ACCESS_BALANCE:12.34")
        if a == "getNumber":
            return web.Response(text="ACCESS_NUMBER:777:9647701234567" if q.get("country") == "47" else "NO_NUMBERS")
        if a == "getStatus":
            return web.Response(text="STATUS_OK:55821")
        if a == "setStatus":
            return web.Response(text="ACCESS_CANCEL")
        return web.Response(text="BAD_ACTION")
    app = web.Application()
    app.router.add_get("/stubs/handler_api.php", h)
    srv = TestServer(app)
    await srv.start_server()
    try:
        ad = StandardSMSAdapter("hero-sms", f"http://127.0.0.1:{srv.port}/stubs/handler_api.php", KEY)
        assert await ad.get_balance() == 12.34
        r = await ad.get_number("iq", "tg")
        assert r["activation_id"] == "777" and r["phone"] == "+9647701234567"
        assert seen[-1]["service"] == "tg" and seen[-1]["country"] == "47", "كود العراق الصحيح في SMS-Activate"
        with pytest.raises(RuntimeError):
            await ad.get_number("eg", "wa")
        assert (await ad.check_sms("777")) == {"status": "received", "code": "55821"}
        assert await ad.cancel_number("777")
    finally:
        await srv.close()
