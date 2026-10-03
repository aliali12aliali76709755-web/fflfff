"""اختبار كل القوالب: إنشاء بوت لكل قالب، فتح لوحة المالك والدليل وواجهة المستخدم، ثم سيناريوهات فعلية لكل قالب."""
import asyncio
import io
import subprocess
import tempfile

from harness import MAKER, Check, boot, make_bot, tok


def png(color=(200, 30, 30), size=(320, 240), text=None) -> bytes:
    from PIL import Image, ImageDraw
    im = Image.new("RGB", size, color)
    if text:
        ImageDraw.Draw(im).text((10, 10), text, fill=(255, 255, 255))
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


def mp4() -> bytes:
    out = tempfile.mktemp(suffix=".mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=10", "-f", "lavfi", "-i",
                    "sine=frequency=440:duration=2", "-shortest", "-pix_fmt", "yuv420p", out], check=True)
    return open(out, "rb").read()


def pdf(pages: int) -> bytes:
    from pypdf import PdfWriter
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(width=200, height=200)
    b = io.BytesIO()
    w.write(b)
    return b.getvalue()


async def main():  # noqa: C901
    tg, mgr = await boot()
    from forge import templates
    ck = Check()
    ali, sara, omar = tg.user(500, "Ali", username="ali_k"), tg.user(600, "Sara", username="sara_s"), tg.user(700, "Omar")
    await tg.say(MAKER, ali, "/start")
    keys = list(templates.load())
    ck.ok(len(keys) == 34, "34 قالباً محمّلة")
    T, B = {}, {}
    print("— فحص عام لكل قالب —")
    for i, k in enumerate(keys):
        B[k] = 300000000 + i
        T[k] = await make_bot(tg, ali, B[k], k)
        t1 = await tg.say(T[k], ali, "/start")
        t2 = await tg.click(T[k], ali, "o:tguide")
        await tg.click(T[k], ali, "o:preview")
        await tg.say(T[k], sara, "/start")
        n = len(tg.out(B[k]))
        await tg.say(T[k], sara, "مرحبا")
        ck.ok("غرفة التحكم" in t1 and len(t2) > 60 and len(tg.out(B[k])) > n, f"{templates.get(k).ar}: لوحة المالك + الدليل + واجهة المستخدم + رد على نص")
    ck.errors("الفحص العام")
    ck.ok(len(mgr.apps) == 34, "34 بوتاً تعمل معاً")

    def last(k):
        return tg.text(B[k])

    def sent(k, method):
        return [c for c in tg.calls if c["bot"] == B[k] and c["method"] == method]

    print("— بوت التواصل —")
    k = "contact"
    await tg.say(T[k], sara, "عندي سؤال")
    ck.ok("وصلت رسالتك" in last(k) and len(sent(k, "copyMessage")) >= 1, "الرسالة تصل للمالك")
    await tg.click(T[k], ali, "t:rp:600")
    await tg.say(T[k], ali, "أهلاً سارة")
    ck.ok(any(str(c["p"]["chat_id"]) == "600" for c in sent(k, "copyMessage")), "رد المالك يصل للمستخدم")

    print("— صارحني —")
    k = "sarahah"
    await tg.say(T[k], omar, "/start u600")
    await tg.say(T[k], omar, "رسالة مجهولة")
    ck.ok("مجهول" in last(k) and any(str(c["p"]["chat_id"]) == "600" for c in sent(k, "copyMessage")), "رسالة مجهولة تصل لصاحب الرابط")

    print("— بوت الأزرار —")
    k = "buttons"
    await tg.click(T[k], ali, "t:add:0")
    await tg.say(T[k], ali, "الأسعار")
    await tg.click(T[k], ali, "t:con:1")
    await tg.say(T[k], ali, "السعر 10$")
    await tg.say(T[k], sara, "/start")
    ck.ok(tg.find(B[k], "الأسعار"), "الزر يظهر للمستخدم")
    ck.ok("السعر 10$" in await tg.press(T[k], sara, "الأسعار"), "محتوى الزر")

    print("— إنشاء منشور —")
    k = "post"
    await tg.say(T[k], sara, "/start")
    await tg.say(T[k], sara, "عرض اليوم")
    await tg.say(T[k], sara, "اطلب - https://t.me/x")
    cp = sent(k, "copyMessage")[-1]["p"]
    ck.ok(cp.get("reply_markup", {}).get("inline_keyboard", [[{}]])[0][0].get("url") == "https://t.me/x", "منشور بأزرار")

    print("— منيو QR والمتجر —")
    for k in ("qrmenu", "store"):
        await tg.click(T[k], ali, f"t:ia:{k}")
        await tg.say(T[k], ali, "بيتزا | 12$ | حجم وسط")
        await tg.say(T[k], sara, "/start")
        await tg.click(T[k], sara, "t:menu")
        ck.ok(tg.find(B[k], "بيتزا"), f"{k}: الصنف في القائمة")
        await tg.click(T[k], sara, "t:add:2")
        await tg.click(T[k], sara, "t:add:2")
        t = await tg.click(T[k], sara, "t:cart")
        ck.ok("24$" in t, f"{k}: إجمالي السلة")
        await tg.click(T[k], sara, "t:order")
        await tg.say(T[k], sara, "سارة 0999 طاولة 4")
        ck.ok(any("طلب جديد" in c["p"]["text"] and str(c["p"]["chat_id"]) == "500" for c in tg.out(B[k])), f"{k}: إشعار المالك بالطلب")
        accept = [b["callback_data"] for c in tg.out(B[k]) if "طلب جديد" in c["p"]["text"] for row in c["p"]["reply_markup"]["inline_keyboard"] for b in row if "قبول" in b["text"]][-1]
        await tg.click(T[k], ali, accept)
        ck.ok(any("مقبول" in c["p"]["text"] and str(c["p"]["chat_id"]) == "600" for c in tg.out(B[k])), f"{k}: إشعار الزبون بالقبول")
    await tg.click(T["qrmenu"], ali, "t:qr")
    ck.ok(len(sent("qrmenu", "sendPhoto")) == 1, "qrmenu: صورة QR")

    print("— التذاكر —")
    k = "tickets"
    await tg.click(T[k], sara, "t:new")
    await tg.say(T[k], sara, "مشكلة دفع")
    await tg.say(T[k], sara, "دفعت ولم يصل")
    ck.ok("فُتحت التذكرة #" in last(k) or any("تذكرة جديدة" in c["p"]["text"] for c in tg.out(B[k])), "فتح تذكرة")
    rid = [c["p"]["text"] for c in tg.out(B[k]) if "تذكرة جديدة" in c["p"]["text"]][-1].split("#")[1].split("<")[0]
    await tg.click(T[k], ali, f"t:re:{rid}")
    await tg.say(T[k], ali, "سنراجع الأمر")
    ck.ok(any("رد الدعم" in c["p"]["text"] and str(c["p"]["chat_id"]) == "600" for c in tg.out(B[k])), "رد الدعم يصل")
    ck.ok("سنراجع الأمر" in await tg.click(T[k], sara, f"t:v:{rid}"), "سجل التذكرة")

    print("— النماذج —")
    k = "forms"
    await tg.click(T[k], sara, "t:go")
    await tg.say(T[k], sara, "سارة أحمد")
    await tg.click(T[k], sara, "t:opt:0")
    ck.ok(any("إجابة جديدة" in c["p"]["text"] and "ممتازة" in c["p"]["text"] for c in tg.out(B[k])), "إجابات النموذج تصل للمالك")
    await tg.click(T[k], ali, "t:csv")
    ck.ok(len(sent(k, "sendDocument")) == 1, "تصدير CSV")

    print("— الحجز —")
    k = "booking"
    await tg.click(T[k], ali, "t:hours")
    await tg.say(T[k], ali, "00:00-23:59 | 60 | 3 | 0")
    await tg.click(T[k], sara, "t:svc")
    await tg.click(T[k], sara, "t:s:1")
    d = tg.buttons(B[k])[1]["callback_data"]
    await tg.click(T[k], sara, d)
    slots = [b for b in tg.buttons(B[k]) if b.get("callback_data", "").startswith("t:h:")]
    ck.ok(len(slots) > 3, "أوقات متاحة")
    await tg.click(T[k], sara, slots[0]["callback_data"])
    await tg.say(T[k], sara, "سارة 0999")
    ck.ok(any("حجز جديد" in c["p"]["text"] for c in tg.out(B[k])), "إشعار المالك بالحجز")
    await tg.click(T[k], omar, d)
    slots2 = [b["callback_data"] for b in tg.buttons(B[k]) if b.get("callback_data", "").startswith("t:h:")]
    ck.ok(slots[0]["callback_data"] not in slots2, "الوقت المحجوز لا يظهر لغيره")

    print("— VIP —")
    k = "vip"
    tg.chats["@vipchan"] = {"id": -1009, "type": "channel", "title": "VIP", "username": "vipchan"}
    tg.members[(-1009, B[k])] = "administrator"
    await tg.click(T[k], ali, "t:chan")
    await tg.say(T[k], ali, "@vipchan")
    await tg.click(T[k], sara, "t:p:1")
    await tg.say(T[k], sara, "رقم العملية 123")
    ck.ok(any("طلب اشتراك" in c["p"]["text"] for c in tg.out(B[k])), "طلب الاشتراك يصل للمالك")
    approve = [b["callback_data"] for c in sent(k, "copyMessage") if c["p"].get("reply_markup") for row in c["p"]["reply_markup"]["inline_keyboard"] for b in row if "قبول" in b["text"]][-1]
    await tg.click(T[k], ali, approve)
    ck.ok(any("t.me/+inv" in c["p"]["text"] and str(c["p"]["chat_id"]) == "600" for c in tg.out(B[k])), "رابط الدعوة يصل للمشترك")

    print("— طلبات الانضمام —")
    k = "joinreq"
    jr = {"chat_join_request": {"chat": {"id": -1007, "type": "channel", "title": "قناتي"}, "from": omar, "user_chat_id": 700, "date": 1}}
    tg.raw(T[k], jr)
    await tg.settle()
    ck.ok(len(sent(k, "approveChatJoinRequest")) == 1, "قبول تلقائي")
    await tg.click(T[k], ali, "t:mode")
    tg.raw(T[k], jr)
    await tg.settle()
    ck.ok(any("طلب انضمام" in c["p"]["text"] for c in tg.out(B[k])) and len(sent(k, "approveChatJoinRequest")) == 1, "الوضع اليدوي يسأل المالك")

    print("— XO —")
    k = "xo"
    await tg.click(T[k], sara, "t:go:hard")
    for _ in range(5):
        free = [b["callback_data"] for b in tg.buttons(B[k]) if b.get("callback_data", "").startswith("t:m:")]
        if not free:
            break
        await tg.click(T[k], sara, free[0])
    ck.ok(any(w in last(k) for w in ("فاز البوت", "تعادل")), "البوت الصعب لا يخسر")
    await tg.click(T[k], sara, "t:fr")
    gid = last(k).split("start=xo_")[1].split("<")[0]
    await tg.say(T[k], omar, f"/start xo_{gid}")
    ck.ok(any(str(c["p"].get("chat_id")) == "700" and "vs" in c["p"]["text"] for c in tg.out(B[k])), "لعبة مع صديق تبدأ")

    print("— الروليت —")
    k = "roulette"
    await tg.click(T[k], sara, "t:new")
    await tg.say(T[k], sara, "سحب تجريبي")
    await tg.say(T[k], sara, "1")
    gw = last(k).split("start=gw_")[1].split("<")[0]
    await tg.say(T[k], omar, f"/start gw_{gw}")
    await tg.say(T[k], ali, f"/start gw_{gw}")
    await tg.click(T[k], sara, f"t:draw:{gw}")
    ck.ok("الفائزون" in last(k) and any("انتهى السحب" in c["p"]["text"] or "مبروك" in c["p"]["text"] for c in tg.out(B[k])), "السحب يختار فائزاً ويبلغ المشاركين")
    await tg.click(T[k], sara, "t:quick")
    ck.ok("🏆" in await tg.say(T[k], sara, "أحمد\nسعيد\nليلى"), "روليت سريع")

    print("— همسة —")
    k = "whisper"
    tg.raw(T[k], {"inline_query": {"id": "q1", "from": ali, "query": "سر صغير @sara_s", "offset": ""}})
    await tg.settle()
    ans = sent(k, "answerInlineQuery")[-1]["p"]["results"][0]
    data = ans["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
    tg.raw(T[k], {"callback_query": {"id": "c1", "from": omar, "chat_instance": "x", "data": data, "inline_message_id": "im1"}})
    await tg.settle()
    ck.ok("ليست لك" in str(sent(k, "answerCallbackQuery")[-2:]), "الهمسة مرفوضة لغير المستلم")
    tg.raw(T[k], {"callback_query": {"id": "c2", "from": sara, "chat_instance": "x", "data": data, "inline_message_id": "im1"}})
    await tg.settle()
    ck.ok("سر صغير" in str(sent(k, "answerCallbackQuery")[-2:]), "المستلم يقرأ الهمسة")

    print("— الشطرنج —")
    k = "chess"
    await tg.click(T[k], sara, "t:new:5")
    gid = last(k).split("start=ch_")[1].split("<")[0]
    await tg.say(T[k], omar, f"/start ch_{gid}")
    import chess as ch
    for uci, who in (("f2f3", sara), ("e7e5", omar), ("g2g4", sara), ("d8h4", omar)):
        mv = ch.Move.from_uci(uci)
        await tg.click(T[k], who, f"t:q:{gid}:{mv.from_square}")
        await tg.click(T[k], who, f"t:q:{gid}:{mv.to_square}")
    ck.ok(any("كش مات" in c["p"]["text"] and "Omar" in c["p"]["text"] for c in tg.out(B[k])), "كش مات (مات الأحمق) والفائز صحيح")

    print("— إدارة قناة —")
    k = "channel"
    tg.chats["@news"] = {"id": -1011, "type": "channel", "title": "أخبار", "username": "news"}
    tg.members[(-1011, B[k])] = "administrator"
    await tg.click(T[k], ali, "t:add")
    await tg.say(T[k], ali, "@news")
    await tg.click(T[k], ali, "t:new")
    await tg.say(T[k], ali, "خبر عاجل")
    await tg.say(T[k], ali, "0")
    await tg.click(T[k], ali, "t:to:0")
    await tg.click(T[k], ali, "t:now")
    ck.ok(any(str(c["p"]["chat_id"]) == "-1011" for c in sent(k, "copyMessage")), "نشر فوري في القناة")
    await tg.click(T[k], ali, "t:new")
    await tg.say(T[k], ali, "خبر مجدول")
    await tg.say(T[k], ali, "0")
    await tg.click(T[k], ali, "t:to:0")
    await tg.click(T[k], ali, "t:when")
    ck.ok("جُدول المنشور" in await tg.say(T[k], ali, "+30"), "جدولة منشور")
    ck.ok("#1" in await tg.click(T[k], ali, "t:sch"), "قائمة المجدولة")

    print("— تعليم الإنجليزية —")
    k = "english"
    await tg.click(T[k], sara, "t:pt:0:0")
    from forge.templates._english_data import PLACEMENT
    for i, q in enumerate(PLACEMENT):
        await tg.click(T[k], sara, f"t:pa:{i}:{q[2]}")
    ck.ok("12/12" in last(k) and "B1" in last(k), "اختبار المستوى")
    await tg.click(T[k], sara, "t:nw")
    ck.ok("—" in last(k), "كلمات جديدة")
    await tg.click(T[k], sara, "t:rv")
    ck.ok("ما معنى" in last(k), "مراجعة")
    await tg.click(T[k], sara, "t:le:0")
    await tg.click(T[k], sara, "t:lq:0:0:0")
    await tg.click(T[k], sara, "t:lx:0:0:0:2")
    await tg.click(T[k], sara, "t:lx:0:1:1:0")
    ck.ok("أتممت الدرس" in last(k), "اختبار الدرس")

    print("— الوسائط —")
    img, vid = png(), mp4()
    k = "sticker"
    await tg.say(T[k], sara, **tg.photo("P1", img))
    ck.ok(len(sent(k, "sendSticker")) == 1 and len(sent(k, "sendDocument")) == 1, "ملصق + PNG")
    k = "img2pdf"
    await tg.say(T[k], sara, **tg.photo("P2", img))
    await tg.say(T[k], sara, **tg.photo("P3", png((0, 90, 200))))
    await tg.click(T[k], sara, "t:go")
    d = sent(k, "sendDocument")
    ck.ok(len(d) == 1 and tg.files["up/images.pdf"][:4] == b"%PDF", "صور ← PDF")
    k = "pdftools"
    await tg.say(T[k], sara, **tg.document("D1", pdf(2), "a.pdf", "application/pdf"))
    await tg.say(T[k], sara, **tg.document("D2", pdf(3), "b.pdf", "application/pdf"))
    await tg.click(T[k], sara, "t:merge")
    ck.ok("5 صفحة" in str(sent(k, "sendDocument")[-1]["p"].get("caption")), "دمج PDF")
    await tg.say(T[k], sara, **tg.document("D3", pdf(4), "c.pdf", "application/pdf"))
    ck.ok("الصفحات" in await tg.click(T[k], sara, "t:info") and "4" in last(k), "معلومات PDF")
    k = "mediaedit"
    await tg.say(T[k], sara, **tg.photo("P4", img))
    await tg.click(T[k], sara, "t:f:bw")
    await tg.click(T[k], sara, "t:cr:1x1")
    await tg.click(T[k], sara, "t:ex:jpg")
    from PIL import Image
    out = Image.open(io.BytesIO(tg.files["up/edited.jpg"]))
    ck.ok(out.size[0] == out.size[1] and len(set(out.convert("RGB").getpixel((5, 5)))) == 1, "فلتر + قص + تصدير")
    await tg.say(T[k], sara, **tg.video("V1", vid))
    await tg.click(T[k], sara, "t:v:mp3")
    ck.ok(len(sent(k, "sendAudio")) == 1, "استخراج صوت من فيديو")
    k = "compress"
    await tg.say(T[k], sara, **tg.video("V2", vid))
    await tg.click(T[k], sara, "t:q:h")
    ck.ok(len(sent(k, "sendVideo")) == 1, "ضغط الفيديو")
    k = "convert"
    await tg.say(T[k], sara, **tg.video("V3", vid))
    await tg.click(T[k], sara, "t:to:gif")
    ck.ok(tg.files.get("up/converted.gif", b"")[:3] == b"GIF", "فيديو ← GIF")
    await tg.say(T[k], sara, **tg.photo("P5", img))
    await tg.click(T[k], sara, "t:to:webp")
    ck.ok(tg.files.get("up/converted.webp", b"")[:4] == b"RIFF", "صورة ← WEBP")
    k = "ocr"
    await tg.say(T[k], sara, **tg.photo("P6", png((255, 255, 255), (900, 200))))
    ck.ok(any(w in last(k) for w in ("لم أجد نصاً", "غير متاحة")), "OCR يعالج الصورة")
    await tg.say(T[k], sara, "/start")
    ck.ok(tg.find(B[k], "العربية"), "OCR: اختيار لغة النص")

    print("— قوالب تعتمد على الإنترنت (يجب أن تفشل بلطف هنا) —")
    await tg.say(T["shortener"], sara, "https://example.com/very/long/link")
    ck.ok("example.com" in last("shortener"), "اختصار الروابط: رد مفهوم")
    await tg.say(T["translate"], sara, "مرحبا بالعالم")
    ck.ok(len(last("translate")) > 5, "الترجمة: رد مفهوم")
    await tg.click(T["tempmail"], sara, "t:new")
    await tg.click(T["proxy"], sara, "t:rnd")
    await tg.click(T["quran"], sara, "t:l:0")
    ck.ok(tg.find(B["quran"], "الفاتحة"), "قائمة السور")
    await tg.click(T["quran"], sara, "t:s:1")
    await tg.say(T["wallets"], sara, "TXYZopYRdj2D9XRtbG411XZZ3kM5VkAeBf")
    ck.ok(any(w in last("wallets") for w in ("بدأت مراقبة",)), "إضافة محفظة TRON")
    await tg.say(T["wallets"], sara, "0x52908400098527886E0F7030069857D2E4169EE7")
    ck.ok(len(tg.buttons(B["wallets"])) == 3, "عنوان EVM يطلب اختيار الشبكة")
    await tg.say(T["downloader"], sara, "https://example.com/video")
    ck.ok(tg.find(B["downloader"], "فيديو"), "التحميل يعرض الصيغ")
    await tg.say(T["voice"], sara, "hello")
    ck.ok(len(last("voice")) > 3 or sent("voice", "sendAudio"), "نص ← صوت: رد مفهوم")
    n0 = len(tg.out(B["voice"]))
    await tg.say(T["voice"], sara, **tg.video("V9", vid))
    ck.ok(any(w in x for x in [c["p"]["text"] for c in tg.out(B["voice"])[n0:]] for w in ("غير متاحة", "📝", "لم أتعرف")), "صوت ← نص: يعالج المقطع ويرد")

    print("— صانع بوتات فرعي —")
    k = "maker"
    await tg.click(T[k], sara, "m:new")
    ck.ok("الخطوة 1 من 3" in last(k), "الصانع الفرعي يعرض المجالات")
    await tg.click(T[k], sara, "m:tpl:decor")
    await tg.say(T[k], sara, tok(390000001))
    ck.ok(mgr.running(390000001) and any("بوتك أصبح حياً" in c["p"]["text"] for c in tg.out(B[k])[-3:]), "الصانع الفرعي ينشئ ويشغّل بوتاً")
    ck.ok(any("بوت جديد" in c["p"]["text"] and str(c["p"]["chat_id"]) == "500" for c in tg.out(B[k])), "إشعار مالك الصانع الفرعي")
    await tg.say(tok(390000001), sara, "/start")
    ck.ok("غرفة التحكم" in tg.text(390000001), "بوت الصانع الفرعي يعمل")
    await tg.say(T[k], ali, "/admin")
    await tg.click(T[k], ali, "m:home")
    ck.ok(tg.find(B[k], "لوحة الإدارة"), "مالك الصانع الفرعي يرى لوحة الإدارة")
    ck.ok(f"@b390000001_bot" in str(tg.buttons(B[k])) or "البوتات" in await tg.click(T[k], ali, "m:adm:home"), "لوحة إدارة الصانع الفرعي")
    await tg.click(T[k], ali, "m:adm:b:0")
    ck.ok(tg.find(B[k], "@b390000001_bot"), "مدير الصانع الفرعي يرى بوتات مستخدميه")
    t = await tg.click(MAKER, sara, "m:bots")
    ck.ok("(0)" in t, "بوتات الصانع الفرعي معزولة عن الرئيسي")

    ck.errors("السيناريوهات")
    ck.ok(not tg.problems, "كل الرسائل صالحة لتيليجرام (HTML، الطول، الأزرار)" + "".join("\n      " + p for p in sorted(set(tg.problems))[:12]))
    await mgr.shutdown()
    await tg.stop()
    ck.done()


asyncio.run(main())
