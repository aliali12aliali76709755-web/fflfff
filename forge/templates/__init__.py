"""سجل القوالب، الصنف الأساسي لكل قالب، ومساعد إدارة العناصر."""
from __future__ import annotations

import importlib
import logging

from .. import ui
from ..ctx import Ctx
from ..ui import B, esc, kb

CATEGORIES = [
    ("biz", "💼", "تجارة وخدمات", "Business & services"),
    ("aud", "📣", "قنوات وجمهور", "Channels & audience"),
    ("media", "🎬", "وسائط وملفات", "Media & files"),
    ("util", "🧰", "أدوات يومية", "Everyday tools"),
    ("learn", "🎓", "تعليم وإسلاميات", "Learning & Islamic"),
    ("fun", "🎮", "ألعاب ومسابقات", "Games & contests"),
    ("pro", "🏭", "منصات", "Platforms"),
]
CAT_OF = {
    "biz": ["store", "qrmenu", "booking", "vip", "tickets", "forms"],
    "aud": ["post", "channel", "joinreq", "contact", "buttons", "sarahah", "whisper"],
    "media": ["downloader", "compress", "convert", "mediaedit", "sticker", "img2pdf", "pdftools", "voice", "ocr", "shazam"],
    "util": ["translate", "shortener", "tempmail", "proxy", "wallets", "decor", "whatsapp", "getid"],
    "learn": ["quran", "english"],
    "fun": ["xo", "chess", "roulette"],
    "pro": ["maker"],
}
# قوالب مقترحة للمبتدئ حين لا توجد بيانات استخدام بعد
STARTERS = ["store", "contact", "buttons", "downloader", "joinreq", "vip", "quran", "booking"]
# ثلاث مزايا مختصرة تظهر في بطاقة كل قالب
FEATS = {
    "downloader": ["يوتيوب، إنستغرام، تيك توك، X، فيسبوك وريديت", "فيديو أو صوت فقط", "بدون علامة مائية حين يتيحها المصدر"],
    "quran": ["قراءة واستماع بستة قرّاء مع التفسير الميسّر", "ورد يومي بتذكير وتتبّع الحفظ", "مصحف على الويب يحفظ موضع القارئ مع البوت"],
    "buttons": ["قوائم وأزرار بلا حدود", "كل زر يعرض نصاً أو صورة أو ملفاً", "صفحة روابط على الويب بالأزرار نفسها"],
    "post": ["منشورات بأزرار شفافة", "نشر مباشر في قناتك", "يدعم الصور والفيديو والملفات"],
    "maker": ["صانع بوتات كامل باسمك", "مستخدموك ينشئون بوتاتهم من كل القوالب", "إشعارات وإحصائيات تصلك أنت"],
    "sarahah": ["رابط شخصي لكل مستخدم", "رسائل مجهولة بالنص والصور والصوت", "رد مجهول على كل رسالة"],
    "proxy": ["بروكسيات MTProto مجانية", "اختيار حسب الدولة", "اتصال بضغطة زر"],
    "store": ["منتجات بأقسام وصور وأسعار", "سلة وطلبات تصلك فوراً بقبول ورفض وتسليم", "متجر على الويب يطلب منه الزبون مباشرة"],
    "translate": ["22 لغة", "كشف تلقائي للغة النص", "تبديل سريع بين اللغات"],
    "joinreq": ["قبول تلقائي أو يدوي", "رسالة ترحيب في الخاص", "قبول كل المنتظرين دفعة واحدة"],
    "compress": ["ثلاث درجات ضغط", "يعرض الحجم قبل وبعد", "مناسب لواتساب وتيليجرام"],
    "convert": ["صور، صوت وفيديو", "استخراج الصوت من الفيديو", "تحويل الفيديو إلى GIF"],
    "roulette": ["سحوبات برابط مشاركة", "اختيار فائزين عشوائي عادل", "روليت سريع من قائمة أسماء"],
    "contact": ["رسائل الأعضاء تصلك مع أسمائهم", "رد بالنص والوسائط", "حظر المزعجين بضغطة"],
    "mediaedit": ["8 فلاتر وقص وتدوير", "غلاف بأي مقاس", "قص وكتم واستخراج صوت للفيديو"],
    "chess": ["مباريات حية بين لاعبين", "رقعة تفاعلية ومؤقت", "دعوة الخصم برابط"],
    "channel": ["نشر فوري ومجدول", "أزرار تحت المنشور", "إدارة عدة قنوات"],
    "english": ["اختبار تحديد مستوى ودروس قواعد بشرح عربي", "مراجعة متباعدة للمفردات", "دورة على الويب بتقدّم يتزامن مع البوت"],
    "pdftools": ["دمج عدة ملفات", "استخراج النص والصفحات", "معلومات الملف"],
    "sticker": ["أي صورة تصبح ملصقاً", "PNG شفاف 512×512", "جاهز لحزم الملصقات"],
    "xo": ["ضد البوت بثلاثة مستويات", "ضد صديق برابط دعوة", "رموز وإحصائيات لكل لاعب"],
    "img2pdf": ["حتى 40 صورة في ملف", "ترتيب حسب الإرسال", "جودة عالية وحجم معقول"],
    "voice": ["النص إلى صوت MP3", "البصمات والفيديو إلى نص", "عربي وإنجليزي"],
    "decor": ["عشرات الزخارف العربية واللاتينية", "نسخ بضغطة واحدة", "إطارات ورموز للأسماء"],
    "whisper": ["همسات سرية في المجموعات", "لا يقرؤها إلا المستلم", "تدعم الصور والملفات"],
    "wallets": ["TRON و TON و Ethereum", "إشعار فوري بكل معاملة", "رصيد وآخر المعاملات"],
    "shortener": ["اختصار فوري", "عدة روابط في رسالة واحدة", "سجل بآخر روابطك"],
    "tickets": ["تذاكر دعم منظمة", "سجل كامل لكل محادثة", "فتح وإغلاق وإعادة فتح"],
    "qrmenu": ["منيو رقمي بأقسام وصور وأسعار", "رمز QR يفتح المنيو على الويب دون تثبيت شيء", "الطلبات تصلك مباشرة في البوت"],
    "ocr": ["استخراج النص من الصور", "عربي وإنجليزي", "نص جاهز للنسخ"],
    "forms": ["أسئلة مفتوحة واختيار من متعدد", "إشعار بكل إجابة", "تصدير إلى Excel"],
    "booking": ["خدمات وأوقات عمل وأيام عطلة", "الوقت المحجوز يختفي تلقائياً", "صفحة حجز على الويب، والتأكيد بضغطة"],
    "vip": ["خطط بأسعار ومدد", "مراجعة إثبات الدفع", "دخول القناة وإخراج تلقائي عند الانتهاء"],
    "tempmail": ["بريد مؤقت بضغطة", "قراءة الرسائل داخل البوت", "استبدال العنوان متى شئت"],
    "shazam": ["تعرّف على الأغنية من صوت أو فيديو", "اسم الأغنية والمغني وسنة الإصدار والغلاف", "مقطع صوتي للأغنية — مجاني بلا حدود"],
    "whatsapp": ["رقم ← رابط محادثة واتساب", "يفتح المحادثة بدون حفظ الرقم", "رسالة جاهزة اختيارية"],
    "getid": ["آيديك واسمك ويوزرك بضغطة", "رقمك عند مشاركته بنفسك", "آيدي أي رسالة معاد توجيهها"],
}

# جملة موجّهة لعضو البوت (لا لصانعه): تُستخدم وصفاً افتراضياً للبوت في تيليجرام وفي صفحته على الويب
PITCH = {
    "store": ("تصفّح منتجاتنا، أضف ما يعجبك إلى السلة، واطلب بسهولة.", "Browse our products, add what you like to the cart and order easily."),
    "qrmenu": ("تصفّح المنيو واطلب مباشرة من هنا.", "Browse the menu and order right here."),
    "booking": ("احجز موعدك في أقل من دقيقة: اختر الخدمة، اليوم، ثم الوقت.", "Book your appointment in under a minute: pick the service, the day and the time."),
    "vip": ("اشترك للوصول إلى المحتوى الحصري، وتابع اشتراكك من هنا.", "Subscribe to access exclusive content and manage your subscription here."),
    "tickets": ("افتح تذكرة دعم وتابع الرد عليها من هنا.", "Open a support ticket and follow the replies here."),
    "forms": ("أجب عن أسئلة النموذج في دقائق.", "Answer the form in a few minutes."),
    "post": ("أنشئ منشوراً بأزرار شفافة وانشره في قناتك.", "Create a post with inline buttons and publish it to your channel."),
    "channel": ("بوت إدارة ونشر خاص بمالك القناة.", "A management and publishing bot for the channel owner."),
    "joinreq": ("يستقبل طلبات الانضمام إلى القناة ويرد عليها.", "Handles join requests for the channel."),
    "contact": ("راسلنا هنا وسيصلك الرد في أقرب وقت.", "Message us here and we'll reply as soon as possible."),
    "buttons": ("كل ما تحتاجه في قوائم وأزرار واضحة.", "Everything you need in clear menus and buttons."),
    "sarahah": ("استقبل رسائل صريحة من أصدقائك دون أن تعرف من أرسلها.", "Receive honest messages from friends without knowing who sent them."),
    "whisper": ("أرسل همسة سرية في أي مجموعة، لا يقرؤها إلا من تختاره.", "Send a secret whisper in any group that only the person you choose can read."),
    "downloader": ("أرسل رابط الفيديو وأحمّله لك من يوتيوب، إنستغرام، تيك توك وغيرها.", "Send a video link and I'll download it from YouTube, Instagram, TikTok and more."),
    "compress": ("أرسل الفيديو وأصغّر حجمه مع الحفاظ على وضوحه.", "Send a video and I'll shrink it while keeping it clear."),
    "convert": ("أحوّل الصور والصوت والفيديو بين الصيغ.", "I convert images, audio and video between formats."),
    "mediaedit": ("عدّل صورك ومقاطعك: فلاتر، قص، تدوير وأكثر.", "Edit your photos and clips: filters, crop, rotate and more."),
    "sticker": ("أرسل صورة وأحوّلها إلى ملصق جاهز.", "Send a picture and I'll turn it into a sticker."),
    "img2pdf": ("أرسل صورك وأجمعها في ملف PDF واحد.", "Send your images and I'll combine them into one PDF."),
    "pdftools": ("ادمج ملفات PDF واستخرج صفحاتها ونصوصها.", "Merge PDFs and extract their pages and text."),
    "voice": ("أحوّل الصوت إلى نص، والنص إلى صوت.", "I turn speech into text and text into speech."),
    "ocr": ("أرسل صورة فيها كتابة وأستخرج نصها.", "Send an image with writing and I'll extract the text."),
    "translate": ("أرسل أي نص وأترجمه إلى اللغة التي تختارها.", "Send any text and I'll translate it into the language you choose."),
    "shortener": ("أرسل رابطاً طويلاً وأختصره لك فوراً.", "Send a long link and I'll shorten it instantly."),
    "tempmail": ("بريد مؤقت لاستقبال رموز التفعيل دون كشف بريدك الحقيقي.", "A temporary inbox for activation codes without exposing your real email."),
    "proxy": ("بروكسيات تيليجرام مجانية تتصل بها بضغطة واحدة.", "Free Telegram proxies you connect to with one tap."),
    "wallets": ("راقب محافظك الرقمية واستلم إشعاراً بكل معاملة.", "Watch your crypto wallets and get notified of every transaction."),
    "decor": ("أرسل اسمك وأزخرفه لك بعشرات الأشكال.", "Send your name and I'll style it in dozens of ways."),
    "quran": ("القرآن الكريم: قراءة، استماع، تفسير، وورد يومي.", "The Holy Quran: reading, listening, tafsir and a daily reminder."),
    "english": ("تعلّم الإنجليزية خطوة بخطوة: دروس قصيرة، كلمات جديدة، ومراجعة ذكية.", "Learn English step by step: short lessons, new words and smart review."),
    "xo": ("العب XO ضد البوت أو ضد أصدقائك.", "Play tic-tac-toe against the bot or your friends."),
    "chess": ("العب الشطرنج مباشرة مع صديقك.", "Play live chess with a friend."),
    "roulette": ("أنشئ سحباً واختر الفائزين عشوائياً.", "Create a giveaway and pick winners at random."),
    "maker": ("اصنع بوت تيليجرام خاصاً بك مجاناً وبدون برمجة.", "Build your own Telegram bot for free, no code."),
    "shazam": ("أرسل مقطعاً صوتياً أو فيديو وسأتعرف على الأغنية لك.", "Send audio or a video and I'll identify the song for you."),
    "whatsapp": ("أرسل رقماً مع رمز الدولة وأحوّله إلى رابط محادثة واتساب.", "Send a number with its country code and I'll turn it into a WhatsApp chat link."),
    "getid": ("اعرف آيديك واسمك ويوزرك بضغطة واحدة.", "Get your ID, name and username in one tap."),
}


class Tpl:
    key = ""
    emoji = "🤖"
    ar = ""
    en = ""
    d_ar = ""
    d_en = ""
    cats: tuple[str, ...] = ()
    guide_ar = ""
    guide_en = ""
    feats: list = []
    site = False          # للقالب موقع ويب غني مرتبط بالبوت

    def name(self, lang: str) -> str:
        return self.ar if lang == "ar" else self.en

    def desc(self, lang: str) -> str:
        return self.d_ar if lang == "ar" else self.d_en

    def title(self, lang: str) -> str:
        return f"{self.emoji} {self.name(lang)}"

    def pitch(self, lang: str) -> str:
        ar, en = PITCH.get(self.key, (self.d_ar, self.d_en))
        return ar if lang == "ar" else en

    # ── واجهة المستخدم ──
    async def home(self, c: Ctx) -> None:
        await c.edit(f"{self.title(c.lang)}\n{ui.LINE}\n\n{esc(self.desc(c.lang))}", kb([c.tail()]))

    # ── لوحة المالك: (نص إضافي، صفوف أزرار) ──
    async def owner(self, c: Ctx) -> tuple[str, list]:
        return "", []

    async def cb(self, c: Ctx, a: list[str]) -> None:
        return None

    async def msg(self, c: Ctx) -> bool:
        return False

    async def start_param(self, c: Ctx, param: str) -> bool:
        return False

    async def inline(self, c: Ctx) -> None:
        return None

    async def join_request(self, c: Ctx) -> None:
        return None

    async def group_msg(self, c: Ctx) -> bool:
        return False

    def setup(self, app) -> None:
        return None

    async def checklist(self, c: Ctx) -> list:
        """خطوات تجهيز خاصة بالقالب: [(تم؟، الوصف، زر يفتح الخطوة)]."""
        return []


class Items:
    """قائمة عناصر يديرها المالك (أصناف، منتجات، خدمات، خطط...) محفوظة في KV."""

    def __init__(self, ns: str, fields=("name", "price", "desc"), ar="عنصر", en="item",
                 fmt_ar="الاسم | السعر | الوصف", fmt_en="Name | Price | Description", sample: list | None = None,
                 photo: bool = False, toggle: bool = False, hint_ar: str = "", hint_en: str = ""):
        self.ns, self.fields, self.ar, self.en = ns, fields, ar, en
        self.fmt_ar, self.fmt_en, self.sample, self.photo = fmt_ar, fmt_en, sample or [], photo
        self.toggle, self.hint_ar, self.hint_en = toggle, hint_ar, hint_en

    def labels(self, lang: str) -> list[str]:
        return [x.strip() for x in (self.fmt_ar if lang == "ar" else self.fmt_en).split("|")]

    @property
    def key(self) -> str:
        return f"{self.ns}:items"

    async def all(self, c: Ctx) -> list[dict]:
        items = await c.kv(self.key)
        if items is None:
            items = [dict(x, id=i + 1) for i, x in enumerate(self.sample)]
            await c.kv_set(self.key, items)
        return items

    async def get(self, c: Ctx, iid: int) -> dict | None:
        return next((x for x in await self.all(c) if x["id"] == iid), None)

    async def save(self, c: Ctx, items: list[dict]) -> None:
        await c.kv_set(self.key, items)

    def line(self, it: dict) -> str:
        s = ("🚫 " if it.get("off") else "") + f"<b>{esc(it.get(self.fields[0], ''))}</b>"
        if len(self.fields) > 1 and it.get(self.fields[1]):
            s += f" — {esc(it[self.fields[1]])}"
        return s

    def parse(self, text: str) -> dict | None:
        parts = [p.strip() for p in text.split("|")]
        if not parts or not parts[0]:
            return None
        return {f: (parts[i] if i < len(parts) else "") for i, f in enumerate(self.fields)}

    def _prompt(self, c: Ctx) -> str:
        t = c.t(f"✍️ أرسل بيانات ال{self.ar} بهذه الصيغة:\n<code>{self.fmt_ar}</code>",
                f"✍️ Send the {self.en} in this format:\n<code>{self.fmt_en}</code>")
        if self.hint_ar:
            t += "\n\n" + c.t(self.hint_ar, self.hint_en or self.hint_ar)
        if self.photo:
            t += c.t("\n\n🖼 لإضافة صورة: أرسل الصورة واكتب هذه البيانات في خانة التعليق تحتها.", "\n\n🖼 To add a photo: send the photo with this data as its caption.")
        return t + c.t("\n\n/cancel للإلغاء", "\n\n/cancel to abort")

    async def ui_list(self, c: Ctx) -> None:
        items = await self.all(c)
        body = "\n".join(f"{i}. {self.line(x)}" + (f"\n   {esc(x.get('desc', ''))}" if x.get("desc") else "")
                         for i, x in enumerate(items[:25], 1)) or c.t("القائمة فارغة. أضف أول عنصر من الزر بالأسفل.", "The list is empty. Add the first one below.")
        if len(items) > 25:
            body += c.t(f"\n… و{len(items) - 25} أخرى في الأزرار", f"\n… and {len(items) - 25} more in the buttons")
        text = ui.head(c.t(f"📋 القائمة ({len(items)})", f"📋 List ({len(items)})")) + body[:3300] + ("\n\n" + c.t(
            "اضغط أي عنصر لتعديله أو حذفه.", "Tap any item to edit or delete it.") if items else "")
        rows = ui.grid([B(("🚫 " if x.get("off") else "✏️ ") + str(x.get(self.fields[0], ""))[:26], f"t:ii:{self.ns}:{x['id']}") for x in items[:60]], 2)
        rows.append([B(c.t(f"➕ إضافة {self.ar}", f"➕ Add {self.en}"), f"t:ia:{self.ns}", style="success")])
        rows.append([B(c.t("🎛 غرفة التحكم", "🎛 Control room"), "o:home")])
        await c.edit(text, kb(rows))

    async def handle_cb(self, c: Ctx, a: list[str]) -> bool:
        if len(a) < 2 or a[1] != self.ns or a[0] not in ("il", "ii", "ia", "ie", "id", "io"):
            return False
        if not c.is_owner:
            await c.answer(c.t("للمالك فقط", "Owner only"), True)
            return True
        act = a[0]
        if act == "il":
            await self.ui_list(c)
        elif act == "ia":
            c.set_state("item", ns=self.ns, id=0)
            await c.edit(self._prompt(c), kb([[B(c.t("❌ إلغاء", "❌ Cancel"), f"t:il:{self.ns}")]]))
        elif act in ("ii", "ie", "id", "io"):
            iid = int(a[2])
            it = await self.get(c, iid)
            if it is None:
                await c.answer(c.t("غير موجود", "Not found"), True)
                await self.ui_list(c)
            elif act in ("ii", "io"):
                if act == "io":
                    items = await self.all(c)
                    for x in items:
                        if x["id"] == iid:
                            x["off"] = not x.get("off")
                            it = x
                    await self.save(c, items)
                labels = self.labels(c.lang)
                det = "\n".join(f"▫️ {esc(labels[i] if i < len(labels) else f)}: <b>{esc(it.get(f, '') or '—')}</b>" for i, f in enumerate(self.fields))
                extra = (c.t("\n🖼 الصورة: ", "\n🖼 Photo: ") + ("✅" if it.get("photo") else "—")) if self.photo else ""
                state = (c.t("\n\n🚫 <b>مخفي</b>: لا يراه الزبائن الآن.", "\n\n🚫 <b>Hidden</b>: customers can't see it now.") if it.get("off") else "") if self.toggle else ""
                await c.edit(f"{det}{extra}{state}", kb([
                    [B(c.t("✏️ تعديل", "✏️ Edit"), f"t:ie:{self.ns}:{iid}"),
                     B(c.t("🗑 حذف", "🗑 Delete"), f"t:id:{self.ns}:{iid}", style="danger")],
                    [B(c.t("👁 إظهار للزبائن", "👁 Show to customers") if it.get("off") else c.t("🚫 إخفاء مؤقتاً", "🚫 Hide for now"), f"t:io:{self.ns}:{iid}")] if self.toggle else None,
                    [B(c.t("⬅️ القائمة", "⬅️ List"), f"t:il:{self.ns}")]]))
            elif act == "ie":
                c.set_state("item", ns=self.ns, id=iid)
                await c.edit(self._prompt(c), kb([[B(c.t("❌ إلغاء", "❌ Cancel"), f"t:il:{self.ns}")]]))
            else:
                await self.save(c, [x for x in await self.all(c) if x["id"] != iid])
                await c.answer(c.t("تم الحذف", "Deleted"))
                await self.ui_list(c)
        return True

    async def handle_msg(self, c: Ctx) -> bool:
        st = c.st
        if not st or st.get("k") != "item" or st.get("ns") != self.ns:
            return False
        it = self.parse(c.text)
        if it is None:
            await c.send(self._prompt(c))
            return True
        if self.photo and c.msg.photo:
            it["photo"] = c.msg.photo[-1].file_id
        items = await self.all(c)
        if st.get("id"):
            for x in items:
                if x["id"] == st["id"]:
                    if "photo" not in it and x.get("photo"):
                        it["photo"] = x["photo"]
                    if x.get("off"):
                        it["off"] = True
                    x.update(it)
        else:
            it["id"] = max([x["id"] for x in items], default=0) + 1
            items.append(it)
        await self.save(c, items)
        c.clear_state()
        await c.send(c.t("✅ تم الحفظ.", "✅ Saved."))
        await self.ui_list(c)
        return True


# ترتيب العرض مطابق لترتيب القائمة (14 في الصفحة)
ORDER = [
    "store", "qrmenu", "booking", "vip", "tickets", "forms",
    "post", "channel", "joinreq", "contact", "buttons", "sarahah", "whisper",
    "downloader", "compress", "convert", "mediaedit", "sticker", "img2pdf", "pdftools", "voice", "ocr", "shazam",
    "translate", "shortener", "tempmail", "proxy", "wallets", "decor", "whatsapp", "getid",
    "quran", "english", "xo", "chess", "roulette", "maker",
]
REG: dict[str, Tpl] = {}


def load() -> dict[str, Tpl]:
    if REG:
        return REG
    for key in ORDER:
        try:
            mod = importlib.import_module(f"{__name__}.{key}")
        except ModuleNotFoundError as e:
            if e.name != f"{__name__}.{key}":
                raise
            logging.getLogger("forge.templates").warning("template %s is missing, skipped", key)
            continue
        tpl: Tpl = mod.TPL
        tpl.key = key
        tpl.cats = tuple(k for k, keys in CAT_OF.items() if key in keys)
        tpl.feats = FEATS.get(key, [])
        REG[key] = tpl
    return REG


class Gone(Tpl):
    """بديل لنوع حُذف من المنصة: البوت يبقى مسجلاً ويطلب من مالكه اختيار نوع آخر."""
    emoji, ar, en = "🧩", "نوع لم يعد متاحاً", "Type no longer available"
    d_ar, d_en = "هذا النوع أزيل من المنصة.", "This type was removed from the platform."
    guide_ar = "هذا النوع أزيل من المنصة. افتح بطاقة البوت في الصانع واضغط «🔄 تغيير النوع» لاختيار نوع آخر؛ أعضاء بوتك وإحصائياته محفوظة."

    async def home(self, c: Ctx) -> None:
        await c.edit(c.t("🛠 هذا البوت قيد التحديث وسيعود قريباً.", "🛠 This bot is being updated and will be back soon."), kb([c.tail()]))

    async def owner(self, c: Ctx):
        return c.t("⚠️ نوع هذا البوت لم يعد متاحاً. من الصانع: «بوتاتي» ← البوت ← «🔄 تغيير النوع».",
                   "⚠️ This bot's type is no longer available. In the maker: My bots → the bot → Change type."), []

    async def msg(self, c: Ctx) -> bool:
        await self.home(c)
        return True


_gone: dict[str, Tpl] = {}


def get(key: str) -> Tpl:
    reg = load()
    if key in reg:
        return reg[key]
    if key not in _gone:
        g = Gone()
        g.key = key
        _gone[key] = g
    return _gone[key]


def by_cat(cat: str) -> list[Tpl]:
    return [t for t in load().values() if cat in t.cats]
