"""اختبار مواقع البوتات ولوحات الويب: الصفحات، واجهات الطلب والحجز والتقدّم، الهوية، الصور، والربط مع البوت."""
import asyncio
import hashlib
import hmac
import io
import json
import time
from urllib.parse import urlencode

import aiohttp

from harness import ADMIN, MAKER, MID, Check, boot, make_bot, tok

B = {"store": 230000001, "qrmenu": 230000002, "booking": 230000003, "english": 230000004, "quran": 230000005, "buttons": 230000006, "contact": 230000007}
PUBLIC = "https://bots.example.com"


def jpeg() -> bytes:
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (64, 64), (120, 80, 200)).save(b, "JPEG")
    return b.getvalue()


def init_data(token: str, user: dict) -> str:
    pairs = {"auth_date": str(int(time.time())), "query_id": "AAE", "user": json.dumps(user, separators=(",", ":"))}
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(pairs)


async def main():  # noqa: C901
    tg, mgr = await boot(web=True, public_url=PUBLIC)
    from forge import config, db, web
    from forge import plat as platform
    from forge.web import sign
    ck = Check()
    base = f"http://127.0.0.1:{config.WEB_PORT}"
    ali, sara, omar, boss = tg.user(500, "Ali", username="ali_k"), tg.user(600, "Sara"), tg.user(700, "Omar"), tg.user(ADMIN, "Boss")
    for u in (boss, ali, sara):
        await tg.say(MAKER, u, "/start")
    T, U = {}, {}
    for k, bid in B.items():
        T[k] = await make_bot(tg, ali, bid, k)
        U[k] = f"b{bid}_bot"
    http = aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True))
    (await platform.get(0))["promo"]["when"] = "idle"      # رسالة الترويج لا تلي رسالة البداية في هذا الاختبار

    async def get(path, **kw):
        async with http.get(base + path, allow_redirects=kw.pop("redirects", True), **kw) as r:
            return r.status, await r.text()

    async def api(k, name, body=None, **headers):
        async with http.request("POST" if body is not None else "GET", f"{base}/{U[k]}/api/{name}", json=body, headers=headers) as r:
            return r.status, await r.json()

    def texts(n0, bot, to=None):
        return [str(c["p"].get("text", "")) for c in tg.calls[n0:] if c["bot"] == bot and c["method"] in ("sendMessage", "editMessageText") and (to is None or str(c["p"].get("chat_id")) == str(to))]

    print("— الخادم والصفحة الرئيسية —")
    st, t = await get("/")
    ck.ok(st == 200 and "ابنِ بوت تيليجرام" in t and ">34<" in t and f"t.me/b{MID}_bot" in t, "صفحة المنصة")
    ck.ok((await get("/healthz"))[0] == 200 and (await get("/static/app.css"))[0] == 200 and (await get("/static/shop.js"))[0] == 200, "الملفات الثابتة")
    st, t = await get("/nosuch_bot")
    ck.ok(st == 404 and "غير موجودة" in t, "بوت غير موجود ← صفحة 404")
    ck.ok(web.public() and web.https() and web.site_url("X_bot") == f"{PUBLIC}/X_bot", "الرابط العام مضبوط")

    print("— المتجر: البوت —")
    k = "store"
    await tg.click(T[k], ali, "t:ia:store")
    await tg.say(T[k], ali, None, caption="سماعة | 25$ | صوت نقي | إلكترونيات", **tg.photo("PH1", jpeg()))
    for row in ("شاحن | 12$ | سريع | إلكترونيات", "حقيبة | 30$ | جلد | حقائب"):
        await tg.click(T[k], ali, "t:ia:store")
        await tg.say(T[k], ali, row)
    t = await tg.say(T[k], sara, "/start")
    btn = tg.buttons(B[k])[0]
    url = btn.get("web_app", {}).get("url", "")
    ck.ok(btn["text"] == "🛍 افتح المتجر" and btn.get("style") == "primary", "التطبيق المصغّر أول زر في الشاشة الرئيسية")
    ck.ok(url.startswith(f"{PUBLIC}/{U[k]}?k=600-") and sign.check_user(B[k], url.split("k=")[1]) == 600, "زر الموقع يفتح داخل تيليجرام برمز العضو")
    key_sara = url.split("k=")[1]
    t = await tg.click(T[k], sara, "t:menu")
    ck.ok("اختر القسم" in t and tg.find(B[k], "إلكترونيات · 2") and tg.find(B[k], "كل المنتجات · 4"), "الأقسام في البوت")
    await tg.click(T[k], sara, "t:cat:0")
    ck.ok(tg.find(B[k], "سماعة") and tg.find(B[k], "شاحن") and not any("حقيبة" in b["text"] for b in tg.buttons(B[k])), "أصناف القسم فقط")
    await tg.click(T[k], sara, "t:add:3")
    await tg.click(T[k], sara, "t:add:3")
    t = await tg.click(T[k], sara, "t:cart")
    ck.ok("24$" in t and tg.find(B[k], "إتمام الطلب"), "السلة والإجمالي")
    await tg.click(T[k], sara, "t:order")
    n0 = len(tg.calls)
    t = await tg.say(T[k], sara, "سارة 0999 دمشق")
    ck.ok("وصل طلبك" in t and any("طلب جديد" in x for x in texts(n0, B[k], 500)), "طلب من البوت يصل المالك")
    await tg.click(T[k], sara, "t:add:4")
    t = await tg.click(T[k], sara, "t:order")
    ck.ok("بياناتك السابقة" in t and "سارة 0999 دمشق" in t, "تذكّر بيانات الزبون")
    n0 = len(tg.calls)
    await tg.press(T[k], sara, "استخدم بياناتي السابقة")
    ck.ok(sum("طلب جديد" in x for x in texts(n0, B[k], 500)) == 1, "إعادة الطلب بالبيانات السابقة")
    await tg.click(T[k], ali, "t:io:store:4")
    await tg.click(T[k], sara, "t:menu")
    await tg.click(T[k], sara, "t:cat:all")
    ck.ok(not any("حقيبة" in b["text"] for b in tg.buttons(B[k])), "إخفاء صنف مؤقتاً")
    t = await tg.click(T[k], ali, "t:ords:all")
    ck.ok(tg.find(B[k], "Sara") and tg.find(B[k], "جديدة"), "قائمة الطلبات بفلاتر")

    print("— المتجر: الموقع —")
    st, page = await get(f"/{U[k]}")
    ck.ok(st == 200 and "سماعة" in page and "شاحن" in page and "حقيبة" not in page and "shop.js" in page and "إلكترونيات" in page, "صفحة المتجر تعرض المنتجات الظاهرة")
    img = page.split('"img":"/img/')[1].split('"')[0]
    img = "/img/" + img
    async with http.get(base + img) as r:
        ck.ok(r.status == 200 and (await r.read())[:2] == b"\xff\xd8" and "max-age" in r.headers.get("Cache-Control", ""), "صورة المنتج عبر وكيل الصور")
    ck.ok((await get(img.replace(img.split("/")[3], "0" * 24)))[0] == 404, "رابط صورة بتوقيع خاطئ يُرفض")
    ck.ok(tok(B[k]) not in page and "600-" not in page, "الصفحة لا تحتوي توكناً ولا رمز عضو")
    st, r = await api(k, "order", {"cart": {}, "name": "x", "phone": "1", "where": ""})
    ck.ok(st == 400 and r["error"] == "empty", "سلة فارغة تُرفض")
    st, r = await api(k, "order", {"cart": {"2": 1}, "name": "ع", "phone": "1", "where": ""})
    ck.ok(st == 400 and r["error"] == "details", "بيانات ناقصة تُرفض")
    st, r = await api(k, "order", {"cart": {"4": 1, "2": 1}, "name": "Omar", "phone": "0999111", "where": "حلب"})
    ck.ok(st == 409 and r["error"] == "changed", "سلة فيها صنف أُخفي تُرفض كاملة ليراجعها الزبون")
    ck.ok((await api(k, "order", {"cart": {"2": "5", "²": 1}, "name": "Omar", "phone": "0999111", "where": "حلب"}))[0] == 400, "كميات وأرقام غير صالحة تُرفض بلا خطأ في الخادم")
    async with http.post(f"{base}/{U[k]}/api/order", data="[1,2]", headers={"Content-Type": "application/json"}) as rr:
        ck.ok(rr.status == 400, "جسم طلب ليس كائناً يُرفض")
    ck.ok((await get(f"/{U[k]}?k=1-é"))[0] == 200 and (await get("/admin?t=a.é"))[0] == 403, "رموز بحروف غير لاتينية لا تُسقط الخادم")
    n0 = len(tg.calls)
    st, r = await api(k, "order", {"cart": {"2": 2, "3": 1}, "name": "عمر", "phone": "0999111", "where": "حلب", "note": "اتصل قبل التوصيل"})
    ck.ok(st == 200 and r["placed"] is False and f"t.me/{U[k]}?start=w" in r["link"] and not texts(n0, B[k], 500), "زائر مجهول: يُحفظ الطلب ولا يُزعج المالك قبل التأكيد")
    param = r["link"].split("start=")[1]
    n0 = len(tg.calls)
    t = await tg.say(T[k], omar, f"/start {param}")
    own = [x for x in texts(n0, B[k], 500) if "طلب جديد" in x]
    ck.ok("تم تأكيد طلبك من الموقع" in t and len(own) == 1 and "من الموقع" in own[0] and "62$" in own[0] and "حلب" in own[0] and "700" in own[0], "تأكيد الطلب من البوت يوصله للمالك باسم العضو")
    ck.ok("أُرسل من قبل" in await tg.say(T[k], sara, f"/start {param}"), "رابط الطلب لمرة واحدة")
    ck.ok("غير صالح" in await tg.say(T[k], omar, "/start w999_0123456789"), "رابط طلب مزوّر يُرفض")
    n0 = len(tg.calls)
    st, r = await api(k, "order", {"cart": {"3": 3}, "name": "سارة", "phone": "0999222", "where": "دمشق"}, **{"X-User-Key": key_sara})
    ck.ok(st == 200 and r["placed"] is True and any("طلب جديد" in x and "36$" in x for x in texts(n0, B[k], 500)) and any("وصل طلبك من الموقع" in x for x in texts(n0, B[k], 600)),
          "عضو معروف: الطلب يصل فوراً ويُبلَّغ الطرفان")
    n0 = len(tg.calls)
    st, r = await api(k, "order", {"cart": {"3": 1}, "name": "Omar", "phone": "0999333", "where": "حمص"}, **{"X-Init-Data": init_data(T[k], {"id": 700, "first_name": "Omar"})})
    ck.ok(st == 200 and r["placed"] is True and any("700" in x for x in texts(n0, B[k], 500)), "الدخول ببيانات تيليجرام (initData)")
    st, r = await api(k, "order", {"cart": {"3": 1}, "name": "Omar", "phone": "0999333", "where": "حمص"}, **{"X-Init-Data": init_data(tok(999), {"id": 700, "first_name": "Omar"})})
    ck.ok(r.get("placed") is False, "initData بتوكن آخر لا تُقبل")
    st, r = await api(k, "order", {"cart": {"3": 1}, "name": "Omar", "phone": "0999333", "where": "حمص"}, **{"X-User-Key": "600-" + "0" * 24})
    ck.ok(r.get("placed") is False, "رمز عضو مزوّر لا يُقبل")
    for _ in range(5):
        st, r = await api(k, "order", {"cart": {"3": 1}, "name": "سارة", "phone": "0999222", "where": "دمشق"}, **{"X-User-Key": key_sara})
    ck.ok(st == 429, "حد للطلبات المتكررة")
    ck.ok((await api(k, "nothing", {}))[0] == 404, "واجهة غير موجودة")
    day = await db.daily([B[k]], db.today())
    ck.ok(day.get("web", 0) == 2, "عدّاد زيارات الموقع")

    print("— غرفة التحكم: الموقع والهوية والتجهيز —")
    t = await tg.say(T[k], ali, "/admin")
    ck.ok(tg.find(B[k], "موقع البوت") and tg.find(B[k], "هوية البوت") and "جاهزية بوتك" in t and tg.find(B[k], "أكمل التجهيز"), "أزرار الموقع والهوية ونسبة الجاهزية")
    t = await tg.click(T[k], ali, "o:todo")
    ck.ok("✅ أضف أول منتج حقيقي" in t and "⬜️ اكتب طرق الدفع" in t and tg.find(B[k], "اكتب طرق الدفع"), "قائمة التجهيز تميّز المنجز من المتبقي")
    await tg.click(T[k], ali, "t:set:info")
    await tg.say(T[k], ali, "الدفع عند الاستلام <b>فقط</b>")
    ck.ok("✅ اكتب طرق الدفع" in await tg.click(T[k], ali, "o:todo"), "الخطوة تكتمل بعد تنفيذها")
    t = await tg.click(T[k], ali, "o:site")
    ck.ok(f"{PUBLIC}/{U[k]}" in t and "يعمل داخل تيليجرام" in t and "زيارات اليوم" in t and tg.find(B[k], "افتحه داخل تيليجرام")["web_app"]["url"].startswith(f"{PUBLIC}/{U[k]}?k=500-") and "زر القائمة" in t, "شاشة موقع البوت")
    await tg.click(T[k], ali, "o:sitec:2")
    await tg.click(T[k], ali, "o:sitetag")
    await tg.say(T[k], ali, "أفضل الإلكترونيات بأفضل سعر")
    st, page = await get(f"/{U[k]}")
    ck.ok("--accent:#0f766e" in page and "أفضل الإلكترونيات بأفضل سعر" in page and "الدفع عند الاستلام" in page, "اللون والعبارة ونص الدفع تظهر في الموقع")
    n0 = len(tg.calls)
    await tg.click(T[k], ali, "o:siteqr")
    ck.ok(any(c["method"] == "sendPhoto" for c in tg.calls[n0:]), "رمز QR للموقع")
    menus = [c for c in tg.calls if c["bot"] == B[k] and c["method"] == "setChatMenuButton"]
    ck.ok(bool(menus) and menus[-1]["p"]["menu_button"]["web_app"]["url"] == f"{PUBLIC}/{U[k]}", "زر القائمة يفتح الموقع")
    await tg.click(T[k], ali, "o:siteon")
    st, page = await get(f"/{U[k]}")
    await tg.say(T[k], sara, "/start")
    ck.ok(st == 404 and "غير مفعّل" in page and not any("web_app" in b for b in tg.buttons(B[k])), "إيقاف الموقع يغلق الرابط ويخفي الزر")
    ck.ok([c for c in tg.calls if c["bot"] == B[k] and c["method"] == "setChatMenuButton"][-1]["p"]["menu_button"]["type"] == "commands", "وزر القائمة يعود للأوامر")
    await tg.click(T[k], ali, "o:siteon")
    descs = [c for c in tg.calls if c["bot"] == B[k] and c["method"] == "setMyDescription"]
    ck.ok(any("منتجاتنا" in c["p"]["description"] and "بدء" in c["p"]["description"] for c in descs) and any(c["bot"] == B[k] and c["method"] == "setMyShortDescription" for c in tg.calls), "وصف افتراضي للبوت عند إنشائه")
    t = await tg.click(T[k], ali, "o:idn")
    ck.ok("هوية البوت" in t and "افتراضية" in t, "شاشة هوية البوت")
    await tg.click(T[k], ali, "o:iddesc")
    n0 = len(tg.calls)
    t = await tg.say(T[k], ali, "متجر الياسمين للإلكترونيات")
    ck.ok(any(c["method"] == "setMyDescription" and c["p"]["description"] == "متجر الياسمين للإلكترونيات" for c in tg.calls[n0:]) and "متجر الياسمين" in t, "تعديل وصف البوت")
    await tg.click(T[k], ali, "o:idname")
    n0 = len(tg.calls)
    await tg.say(T[k], ali, "متجر الياسمين")
    ck.ok(any(c["method"] == "setMyName" for c in tg.calls[n0:]), "تعديل اسم البوت")

    print("— الإغلاق يغلق الموقع —")
    await tg.click(MAKER, boss, f"m:adm:lk:{B[k]}:c")
    await tg.click(MAKER, boss, f"m:adm:lkr:{B[k]}:0")
    await tg.click(MAKER, boss, f"m:adm:lkgo:{B[k]}:0")
    st, page = await get(f"/{U[k]}")
    st2, r = await api(k, "order", {"cart": {"3": 1}, "name": "Omar", "phone": "0999333", "where": "حمص"})
    ck.ok(st == 403 and "مغلق" in page and "سماعة" not in page and st2 == 403 and r["ok"] is False, "البوت المغلق: موقعه وواجهاته مغلقة")
    await tg.click(MAKER, boss, f"m:adm:ulgo:{B[k]}:0")
    ck.ok((await get(f"/{U[k]}"))[0] == 200, "وإعادة الفتح تعيد الموقع")

    print("— المنيو —")
    k = "qrmenu"
    await tg.click(T[k], ali, "t:ia:qrmenu")
    await tg.say(T[k], ali, "شاورما | 15000 ل.س | مع ثومية | وجبات")
    st, page = await get(f"/{U[k]}")
    ck.ok(st == 200 and "شاورما" in page and "رقم الطاولة" in page, "صفحة المنيو")
    n0 = len(tg.calls)
    await tg.click(T[k], ali, "t:qr")
    cap = [c["p"].get("caption", "") for c in tg.calls[n0:] if c["method"] == "sendPhoto"]
    ck.ok(bool(cap) and f"{PUBLIC}/{U[k]}" in cap[0], "رمز QR يفتح المنيو على الويب")
    st, r = await api(k, "order", {"cart": {"2": 2}, "name": "زائر", "phone": "0999000", "where": "طاولة 4"})
    await tg.say(T[k], omar, f"/start {r['link'].split('start=')[1]}")
    ck.ok(any("30,000 ل.س" in x and "طاولة 4" in x for x in texts(0, B[k], 500)), "طلب المنيو بعملة نصية")

    print("— بيانات مستوردة خبيثة لا تصل الصفحة كوسوم —")
    items = await db.kv_get(B["store"], "store:items")
    await db.kv_set(B["store"], "store:items", items + [{"id": '"><img src=x onerror=alert(1)>', "name": "<script>alert(2)</script>", "price": "1$", "desc": "", "cat": ""}])
    core = mgr.apps[B["store"]].bot_data["core"]
    core["site"]["color"] = 'red;}</style><script>alert(3)</script>'
    st, page = await get(f"/{U['store']}")
    ck.ok(st == 200 and "<img src=x" not in page and "<script>alert" not in page and "alert(3)" not in page and '"id":0' in page, "معرّف ولون واسم مزروعة عبر الاستيراد تُحيَّد")
    await db.kv_set(B["store"], "store:items", items)
    core["site"]["color"] = ""

    print("— الحجز —")
    k = "booking"
    st, page = await get(f"/{U[k]}")
    ck.ok(st == 200 and "استشارة" in page and "booking.js" in page, "صفحة الحجز")
    date = json.loads(page.split("window.SITE=")[1].split(";</script>")[0])["days"][1]["date"]
    st, r = await api(k, "slots", {"date": date})
    ck.ok(st == 200 and "09:00" in r["slots"] and "16:30" in r["slots"], "الأوقات المتاحة")
    ck.ok((await api(k, "slots", {"date": "2020-01-01"}))[1]["slots"] == [] and (await api(k, "slots", {"date": date.replace("-", "")}))[1]["slots"] == [], "تاريخ ماضٍ أو بصيغة أخرى بلا أوقات")
    k2 = sign.user_token(B[k], 600)
    both = await asyncio.gather(*[api(k, "book", {"svc": 1, "date": date, "time": "15:00", "name": f"زبون {i}", "phone": "0999000"}, **{"X-User-Key": k2}) for i in range(3)])
    ck.ok(sorted(x[0] for x in both) == [200, 409, 409], "ثلاثة طلبات متزامنة على الوقت نفسه: واحد فقط ينجح")
    await tg.click(T[k], ali, "t:hours")
    ck.ok("صيغة غير صحيحة" in await tg.say(T[k], ali, "00:00-999999:00 | 5 | 3 | 5"), "أوقات عمل غير معقولة تُرفض")
    await tg.say(T[k], ali, "/cancel")
    n0 = len(tg.calls)
    st, r = await api(k, "book", {"svc": 1, "date": date, "time": "10:00", "name": "سارة", "phone": "0999222"}, **{"X-User-Key": sign.user_token(B[k], 600)})
    ck.ok(st == 200 and r["placed"] and any("حجز جديد" in x and "10:00" in x and "من صفحة الويب" in x for x in texts(n0, B[k], 500)) and any("وصل طلب الحجز" in x for x in texts(n0, B[k], 600)), "حجز عضو معروف")
    ck.ok("10:00" not in (await api(k, "slots", {"date": date}))[1]["slots"], "الوقت المحجوز يختفي")
    st, r = await api(k, "book", {"svc": 1, "date": date, "time": "10:00", "name": "عمر", "phone": "0999111"})
    ck.ok(st == 409 and r["error"] == "taken", "وقت محجوز يُرفض")
    st, r = await api(k, "book", {"svc": 1, "date": date, "time": "11:00", "name": "عمر", "phone": "0999111"})
    n0 = len(tg.calls)
    t = await tg.say(T[k], omar, f"/start {r['link'].split('start=')[1]}")
    ck.ok("وصل طلب الحجز" in t and any("حجز جديد" in x and "11:00" in x for x in texts(n0, B[k], 500)), "حجز زائر يتأكد من البوت")
    t = await tg.click(T[k], omar, "t:mine")
    ck.ok("11:00" in t, "الحجز يظهر في «حجوزاتي»")

    print("— الإنجليزية —")
    k = "english"
    st, page = await get(f"/{U[k]}")
    ck.ok(st == 200 and "english.js" in page and "Present Simple" in page and '"state":null' in page, "صفحة الدورة")
    key = sign.user_token(B[k], 600)
    today = json.loads(page.split("window.SITE=")[1].split(";</script>")[0])["today"]
    st, r = await api(k, "sync", {"u": {"lvl": 2, "xp": 44, "done": [0, 1], "box": {"3": [1, today + 1], "999": [0, today]}}}, **{"X-User-Key": key})
    ck.ok(st == 200 and r["saved"], "حفظ التقدّم من الويب")
    t = await tg.say(T[k], sara, "/start")
    ck.ok("A2" in t and "44" in t, "التقدّم يظهر في البوت")
    st, page = await get(f"/{U[k]}?k={key}")
    ck.ok('"xp":44' in page and '"999"' not in page, "والموقع يحمّل تقدّم العضو (مع تجاهل القيم غير الصالحة)")
    ck.ok((await api(k, "sync", {"u": {"lvl": 9, "xp": -1}}, **{"X-User-Key": key}))[0] == 400 and (await api(k, "sync", {"u": {"lvl": 1, "xp": 1, "done": 5, "box": []}}, **{"X-User-Key": key}))[0] == 400, "حالة غير صالحة تُرفض")
    st, r = await api(k, "state", None, **{"X-Init-Data": init_data(T[k], {"id": 600, "first_name": "Sara"})})
    ck.ok(st == 200 and r["user"] and r["state"]["xp"] == 44, "الصفحة المفتوحة من زر القائمة تجلب تقدّم العضو قبل أي حفظ")
    ck.ok((await api(k, "state", None))[1] == {"ok": True, "state": None, "user": False}, "زائر بلا هوية: لا حالة")
    ck.ok((await api(k, "sync", {"u": {"lvl": 1, "xp": 1, "done": [], "box": {}}}))[1]["saved"] is False, "زائر بلا هوية: لا حفظ على الخادم")

    print("— القرآن —")
    k = "quran"
    import forge.templates.quran as q
    q._cache[112] = ["بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ قُلْ هُوَ ٱللَّهُ أَحَدٌ", "ٱللَّهُ ٱلصَّمَدُ", "لَمْ يَلِدْ وَلَمْ يُولَدْ", "وَلَمْ يَكُن لَّهُۥ كُفُوًا أَحَدٌۢ"]
    st, page = await get(f"/{U[k]}")
    ck.ok(st == 200 and "الإخلاص" in page and "quran.js" in page and "Amiri" in page, "صفحة المصحف")
    st, r = await api(k, "surah", {"n": 112})
    ck.ok(st == 200 and len(r["ayahs"]) == 4, "نص السورة")
    ck.ok((await api(k, "surah", {"n": 500}))[0] == 400, "رقم سورة غير صالح")
    key = sign.user_token(B[k], 600)
    st, r = await api(k, "save", {"s": 112, "off": 2, "hifz": [112, 114, 999], "rec": 1}, **{"X-User-Key": key})
    ck.ok(r["saved"], "حفظ موضع القراءة")
    await tg.say(T[k], sara, "/start")
    t = await tg.click(T[k], sara, "t:cont")
    ck.ok("سورة الإخلاص" in t, "البوت يتابع من موضع الويب")
    t = await tg.click(T[k], sara, "t:hz")
    ck.ok("2 من 114" in t, "المحفوظات تتزامن")
    st, page = await get(f"/{U[k]}?k={key}")
    ck.ok('"s":112' in page, "والموقع يحمّل الموضع المحفوظ")
    st, r = await api(k, "state", None, **{"X-Init-Data": init_data(T[k], {"id": 600, "first_name": "Sara"})})
    ck.ok(r["state"]["s"] == 112 and r["state"]["hifz"] == [112, 114] and r["state"]["rec"] == 1, "وزر القائمة يجلب الموضع نفسه")

    print("— صفحة الروابط والصفحة العامة —")
    k = "buttons"
    for name, content in (("واتساب", "https://wa.me/963999"), ("الأسعار", "الباقة الأساسية <10$>")):
        await tg.click(T[k], ali, "t:add:0")
        await tg.say(T[k], ali, name)
        nid = max(n["id"] for n in await db.kv_get(B[k], "buttons:tree"))
        await tg.click(T[k], ali, f"t:con:{nid}")
        await tg.say(T[k], ali, content)
    st, page = await get(f"/{U[k]}")
    ck.ok(st == 200 and '"url":"https://wa.me/963999"' in page and "الأسعار" in page and "links.js" in page and "<10$>" not in page, "صفحة الروابط (والمحتوى مهرَّب)")
    ck.ok("الباقة الأساسية" in await tg.say(T[k], sara, "/start v2"), "رابط يفتح زراً بعينه في البوت")
    st, page = await get(f"/{U['contact']}")
    ck.ok(st == 200 and "بوت التواصل" in page and f"https://t.me/{U['contact']}" in page and "اصنعه مجاناً" in page and f"start=ref_500" in page, "صفحة تعريفية عامة مع دعوة الصانع")
    await tg.say(T["contact"], sara, "/start")
    ck.ok(not any("web_app" in b or "الموقع" in b["text"] for b in tg.buttons(B["contact"])), "لا زر موقع في بوت بلا موقع خاص")

    print("— لوحات الويب —")
    st, page = await get("/admin")
    ck.ok(st == 403, "لوحة الإدارة مغلقة بلا دخول")
    ck.ok((await get("/admin?t=" + sign.session("me", ADMIN, 60)))[0] == 403 and (await get("/admin?t=abc.def"))[0] == 403, "رمز من نوع آخر أو مزوّر يُرفض")
    await tg.click(MAKER, boss, "m:adm:home")
    ck.ok(tg.find(MID, "لوحة الويب"), "زر لوحة الويب في لوحة الإدارة")
    await tg.click(MAKER, boss, "m:adm:web")
    link = tg.find(MID, "افتح اللوحة")["web_app"]["url"]
    ck.ok(link.startswith(f"{PUBLIC}/admin?t="), "رابط دخول موقّع")
    st, page = await get(link.replace(PUBLIC, ""))
    ck.ok(st == 200 and "لوحة الإدارة" in page and "أكبر البوتات" in page and f"@{U['store']}" in page and "<svg" in page and "Ali" in page, "لوحة الإدارة بالأرقام والرسوم")
    ck.ok(not any(tok(b) in page for b in B.values()) and "?t=" not in page, "لا توكنات في اللوحة")
    ck.ok((await get("/admin"))[0] == 200, "الجلسة تبقى في ملف الارتباط")
    await tg.click(MAKER, sara, "m:adm:web")
    ck.ok(not any("admin?t=" in str(c["p"]) for c in tg.calls if str(c["p"].get("chat_id")) == "600"), "غير المدير لا يحصل على رابط الإدارة")
    t = await tg.say(MAKER, boss, f"/start adm_{B['store']}")
    ck.ok("صانع البوت" in t and f"@{U['store']}" in t, "زر «إدارة» في اللوحة يفتح بطاقة البوت")
    await http.get(base + "/logout")
    ck.ok((await get("/admin"))[0] == 403, "تسجيل الخروج")
    t = await tg.click(MAKER, ali, "m:home")
    ck.ok(tg.find(MID, "لوحتي على الويب"), "زر لوحتي على الويب لصانع البوتات")
    await tg.click(MAKER, ali, "m:web")
    st, page = await get(tg.find(MID, "افتح اللوحة")["web_app"]["url"].replace(PUBLIC, ""))
    ck.ok(st == 200 and "بوتاتك" in page and f"@{U['booking']}" in page and "بانتظارك الآن" in page and "طلبات جديدة" in page, "لوحة صانع البوتات مع ما ينتظره")
    await http.get(base + "/logout")
    await make_bot(tg, sara, 230000050, "xo")
    await tg.click(MAKER, sara, "m:web")
    st, page = await get(tg.find(MID, "افتح اللوحة")["web_app"]["url"].replace(PUBLIC, ""))
    ck.ok(st == 200 and "b230000050_bot" in page and U["store"] not in page, "كل صانع يرى بوتاته فقط")
    t = await tg.say(MAKER, ali, f"/start bot_{B['store']}")
    ck.ok("غرفة التحكم" in str(tg.buttons(MID)) and tg.find(MID, "موقع البوت")["url"] == f"{PUBLIC}/{U['store']}", "بطاقة البوت فيها زر موقعه")
    t = await tg.say(MAKER, sara, f"/start bot_{B['store']}")
    ck.ok("أهلاً Sara" in t, "رابط بوت لا تملكه يفتح الرئيسية فقط")

    print("— بلا رابط عام —")
    config.PUBLIC_URL = ""
    await tg.say(T["store"], sara, "/start")
    ck.ok(not any("web_app" in b or "الويب" in b["text"] for b in tg.buttons(B["store"])), "بلا رابط عام: لا يظهر زر الموقع للأعضاء")
    t = await tg.click(T["store"], ali, "o:site")
    ck.ok("PUBLIC_URL" in t and f"http://localhost:{config.WEB_PORT}/{U['store']}" in t, "المالك يرى السبب والرابط المحلي")
    await tg.click(MAKER, ali, "m:web")
    ck.ok(f"http://localhost:{config.WEB_PORT}/me?t=" in tg.text(MID) and not any("افتح اللوحة" in b["text"] for b in tg.buttons(MID)[:1]), "رابط اللوحة المحلي كنص")
    ck.ok((await get(f"/{U['store']}"))[0] == 200, "والموقع يبقى متاحاً محلياً")
    config.PUBLIC_URL = PUBLIC

    await http.close()
    ck.errors("كل السيناريوهات")
    ck.ok(not tg.problems, "كل الرسائل صالحة لتيليجرام (HTML، الطول، الأزرار)" + "".join("\n      " + p for p in sorted(set(tg.problems))[:12]))
    await mgr.shutdown()
    await tg.stop()
    ck.done()


asyncio.run(main())
