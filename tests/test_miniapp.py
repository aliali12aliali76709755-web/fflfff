"""التطبيق المصغّر داخل تيليجرام: النفق التلقائي، زر القائمة في كل بوت وفي الصانع، والدخول إلى اللوحات بهوية تيليجرام."""
import asyncio
import hashlib
import hmac
import json
import time
from pathlib import Path
from urllib.parse import urlencode

import aiohttp

from harness import ADMIN, MAKER, MID, Check, boot, make_bot, tok

FAKE = str(Path(__file__).with_name("fake_cloudflared.py"))
NAME = Path(__file__).with_name("fake_tunnel_name.txt")
B_STORE, B_QURAN, B_CONTACT = 260000001, 260000002, 260000003


def init_data(token: str, user: dict, age: int = 0) -> str:
    pairs = {"auth_date": str(int(time.time()) - age), "query_id": "AAE", "user": json.dumps(user, separators=(",", ":"))}
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(pairs)


async def main():  # noqa: C901
    NAME.write_text("alpha-beta")
    tg, mgr = await boot(web=True, tunnel=FAKE)
    from forge import config, web
    from forge import plat as platform
    from forge.web import tunnel as tun
    ck = Check()
    base = f"http://127.0.0.1:{config.WEB_PORT}"
    url1 = "https://alpha-beta.trycloudflare.com"
    ali, sara, boss = tg.user(500, "Ali"), tg.user(600, "Sara"), tg.user(ADMIN, "Boss")
    (await platform.get(0))["promo"]["when"] = "idle"

    def menus(bot):
        return [c["p"]["menu_button"] for c in tg.calls if c["bot"] == bot and c["method"] == "setChatMenuButton"]

    print("— النفق التلقائي —")
    ck.ok(config.PUBLIC_URL == url1 and web.https() and mgr.tunnel is not None and mgr.tunnel.url == url1, "النفق يعطي المنصة رابط https عند الإقلاع")
    await tg.settle()
    ck.ok(bool(menus(MID)) and menus(MID)[-1].get("web_app", {}).get("url") == f"{url1}/app" and menus(MID)[-1]["text"] == "لوحتي", "زر القائمة في بوت الصانع يفتح «لوحتي» داخل تيليجرام")

    print("— زر القائمة والتطبيق المصغّر في البوتات —")
    for u in (boss, ali, sara):
        await tg.say(MAKER, u, "/start")
    T = await make_bot(tg, ali, B_STORE, "store")
    TQ = await make_bot(tg, ali, B_QURAN, "quran")
    TC = await make_bot(tg, ali, B_CONTACT, "contact")
    await asyncio.sleep(0.3)
    await tg.settle()
    ck.ok(menus(B_STORE)[-1].get("web_app", {}).get("url") == f"{url1}/b{B_STORE}_bot" and menus(B_STORE)[-1]["text"] == "المتجر", "زر القائمة في المتجر يفتح متجره")
    ck.ok(menus(B_QURAN)[-1]["text"] == "المصحف", "زر القائمة في بوت القرآن")
    ck.ok(not any("web_app" in m for m in menus(B_CONTACT)), "بوت بلا موقع خاص: زر القائمة يبقى للأوامر")
    await tg.say(T, sara, "/start")
    first = tg.buttons(B_STORE)[0]
    ck.ok(first["text"] == "🛍 افتح المتجر" and first["web_app"]["url"].startswith(f"{url1}/b{B_STORE}_bot?k=600-") and tg.buttons(B_STORE)[1]["text"] == "🛍 تصفّح المنتجات", "أول زر يفتح المتجر داخل تيليجرام والتصفح بالأزرار بديل")
    await tg.say(TQ, sara, "/start")
    ck.ok(tg.buttons(B_QURAN)[0]["text"] == "📖 افتح المصحف" and "web_app" in tg.buttons(B_QURAN)[0], "بوت القرآن: المصحف أول زر")
    t = await tg.click(T, ali, "o:site")
    ck.ok("يعمل داخل تيليجرام" in t and "زر القائمة" in t and "دون الخروج من البوت" in t, "غرفة التحكم تشرح أن الموقع داخل تيليجرام")

    http = aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True))
    print("— صفحات تتصرف كتطبيق مصغّر —")
    async with http.get(f"{base}/b{B_STORE}_bot") as r:
        page = await r.text()
    ck.ok("telegram-web-app.js" in page and "only-web" in page and "only-tg" in page and "data-tgclose" in page, "الصفحة تحمّل واجهة تيليجرام وتخفي عناصر الموقع الخارجي داخله")
    async with http.get(f"{base}/static/app.js") as r:
        js = await r.text()
    ck.ok(all(x in js for x in ("themeParams", "BackButton", "tg.close()", "openTelegramLink", "HapticFeedback")), "ألوان تيليجرام، زر الرجوع، الإغلاق، والاهتزاز")
    async with http.get(f"{base}/static/app.css") as r:
        ck.ok(".in-tg .only-web" in await r.text(), "تنسيق خاص بالعرض داخل تيليجرام")

    print("— الدخول إلى اللوحات بهوية تيليجرام —")
    async with http.get(f"{base}/app") as r:
        page = await r.text()
        ck.ok(r.status == 200 and "/auth" in page and "initData" in page, "صفحة دخول الصانع")
    async with http.post(f"{base}/auth", json={"initData": init_data(tok(B_STORE), {"id": 500, "first_name": "Ali"})}) as r:
        ck.ok(r.status == 403, "هوية موقّعة بتوكن بوت آخر تُرفض")
    async with http.post(f"{base}/auth", json={"initData": init_data(MAKER, {"id": 500, "first_name": "Ali"}, age=90000)}) as r:
        ck.ok(r.status == 403, "هوية قديمة تُرفض")
    async with http.post(f"{base}/auth", data="x") as r:
        ck.ok(r.status == 403, "جسم غير صالح يُرفض")
    async with http.post(f"{base}/auth", json={"initData": init_data(MAKER, {"id": 500, "first_name": "Ali"})}) as r:
        ck.ok(r.status == 200 and (await r.json())["to"] == "/me", "دخول صانع البوتات بهوية تيليجرام")
    async with http.get(f"{base}/me") as r:
        page = await r.text()
        ck.ok(r.status == 200 and f"b{B_STORE}_bot" in page and "👑" not in page and "telegram.org" in r.headers.get("Content-Security-Policy", ""), "لوحتي تفتح بلا روابط دخول، ومسموح عرضها داخل تيليجرام ويب فقط")
    async with http.get(f"{base}/admin") as r:
        ck.ok(r.status == 403, "صانع عادي لا يدخل لوحة الإدارة")
    await http.get(f"{base}/logout")
    async with http.post(f"{base}/auth", json={"initData": init_data(MAKER, {"id": ADMIN, "first_name": "Boss"})}) as r:
        ck.ok(r.status == 200, "دخول المدير")
    async with http.get(f"{base}/me") as r:
        ck.ok("👑 الإدارة" in await r.text(), "المدير يرى زر لوحة الإدارة في لوحته")
    async with http.get(f"{base}/admin") as r:
        ck.ok(r.status == 200 and "أكبر البوتات" in await r.text(), "ولوحة الإدارة تفتح له")
    await tg.click(MAKER, ali, "m:web")
    b = tg.find(MID, "افتح اللوحة")
    ck.ok(b["web_app"]["url"].startswith(f"{url1}/me?t="), "زر «لوحتي على الويب» يفتح داخل تيليجرام")

    print("— حالة الويب للمدير وتغيّر رابط النفق —")
    t = await tg.click(MAKER, boss, "m:adm:wb")
    ck.ok("تعمل داخل تيليجرام" in t and url1 in t and "نفق تلقائي" in t, "شاشة حالة الويب")
    ck.ok("أُعيد ضبط زر القائمة في 3 بوت" in await tg.click(MAKER, boss, "m:adm:wbr"), "إعادة ضبط أزرار القوائم")
    NAME.write_text("gamma-delta")
    tun.Tunnel.RESTART_DELAY = 0.2
    mgr.tunnel.RESTART_DELAY = 0.2
    mgr.tunnel.proc.kill()
    for _ in range(60):
        await asyncio.sleep(0.1)
        if config.PUBLIC_URL != url1:
            break
    await asyncio.sleep(0.4)
    await tg.settle()
    url2 = "https://gamma-delta.trycloudflare.com"
    ck.ok(config.PUBLIC_URL == url2, "النفق يعود تلقائياً برابطه الجديد بعد انقطاعه")
    ck.ok(menus(B_STORE)[-1]["web_app"]["url"] == f"{url2}/b{B_STORE}_bot" and menus(MID)[-1]["web_app"]["url"] == f"{url2}/app", "أزرار القوائم تتبع الرابط الجديد دون تدخل")
    await tg.say(T, sara, "/start")
    ck.ok(tg.buttons(B_STORE)[0]["web_app"]["url"].startswith(url2), "والأزرار الجديدة تحمل الرابط الجديد")

    print("— بلا برنامج النفق —")
    got = []

    async def cb(u):
        got.append(u)

    async def no_download():
        return None
    old_dl, old_bin = tun.download, config.CLOUDFLARED
    tun.download, config.CLOUDFLARED = no_download, "/nonexistent/cloudflared"
    t2 = tun.Tunnel(cb)
    ck.ok(await t2.start(wait=1) == "" and "cloudflared" in t2.error and not got, "غياب cloudflared لا يوقف شيئاً ويُسجَّل السبب")
    tun.download, config.CLOUDFLARED = old_dl, old_bin
    ck.ok(tun._asset() in ("cloudflared-linux-amd64", "cloudflared-linux-arm64", "cloudflared-linux-386", "cloudflared-linux-arm"), "اسم ملف التنزيل المناسب للنظام")

    await http.close()
    proc = mgr.tunnel.proc
    await mgr.shutdown()
    ck.ok(proc.returncode is not None and config.PUBLIC_URL == "" and mgr.tunnel is None, "الإيقاف ينهي النفق")
    NAME.unlink(missing_ok=True)
    ck.errors("كل السيناريوهات")
    ck.ok(not tg.problems, "كل الرسائل صالحة لتيليجرام" + "".join("\n      " + p for p in sorted(set(tg.problems))[:12]))
    await tg.stop()
    ck.done()


asyncio.run(main())
