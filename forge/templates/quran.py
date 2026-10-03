"""القرآن الكريم — كامل: قراءة، استماع، تفسير، بحث، متابعة ورد يومي وتتبّع الحفظ."""
import datetime as dt
import logging

from telegram.error import TelegramError

from .. import db, ui
from .. import plat
from ..ctx import Ctx
from ..ui import B, esc, kb
from . import Tpl
from ._util import get_json

log = logging.getLogger("forge.quran")
API = "https://api.alquran.cloud/v1"
SURAHS = [s.replace(" ", " ") for s in ("الفاتحة|البقرة|آل عمران|النساء|المائدة|الأنعام|الأعراف|الأنفال|التوبة|يونس|هود|يوسف|الرعد|إبراهيم|الحجر|النحل|الإسراء|الكهف|مريم|طه|"
          "الأنبياء|الحج|المؤمنون|النور|الفرقان|الشعراء|النمل|القصص|العنكبوت|الروم|لقمان|السجدة|الأحزاب|سبأ|فاطر|يس|الصافات|ص|الزمر|غافر|"
          "فصلت|الشورى|الزخرف|الدخان|الجاثية|الأحقاف|محمد|الفتح|الحجرات|ق|الذاريات|الطور|النجم|القمر|الرحمن|الواقعة|الحديد|المجادلة|الحشر|"
          "الممتحنة|الصف|الجمعة|المنافقون|التغابن|الطلاق|التحريم|الملك|القلم|الحاقة|المعارج|نوح|الجن|المزمل|المدثر|القيامة|الإنسان|المرسلات|"
          "النبأ|النازعات|عبس|التكوير|الانفطار|المطففين|الانشقاق|البروج|الطارق|الأعلى|الغاشية|الفجر|البلد|الشمس|الليل|الضحى|الشرح|التين|"
          "العلق|القدر|البينة|الزلزلة|العاديات|القارعة|التكاثر|العصر|الهمزة|الفيل|قريش|الماعون|الكوثر|الكافرون|النصر|المسد|الإخلاص|الفلق|الناس").split("|")]
assert len(SURAHS) == 114
RECITERS = [("ar.alafasy", "مشاري العفاسي"), ("ar.abdulbasitmurattal", "عبد الباسط"), ("ar.husary", "الحصري"),
            ("ar.minshawi", "المنشاوي"), ("ar.abdurrahmaansudais", "السديس"), ("ar.mahermuaiqly", "ماهر المعيقلي")]
PAGE = 8
_cache: dict[int, list[str]] = {}


async def tafsir(s: int, n: int) -> str:
    d = await get_json(f"{API}/ayah/{s}:{n}/ar.muyassar", timeout=20)
    return d["data"]["text"]


async def ayahs(n: int) -> list[str]:
    if n not in _cache:
        d = await get_json(f"{API}/surah/{n}/quran-uthmani", timeout=25)
        _cache[n] = [a["text"] for a in d["data"]["ayahs"]]
        if len(_cache) > 40:
            _cache.pop(next(iter(_cache)))
    return _cache[n]


class Quran(Tpl):
    emoji, ar, en = "☪", "القرآن الكريم — كامل", "Holy Quran — complete"
    d_ar = "مصحف متكامل للقراءة والاستماع والتفسير والتعلم والحفظ، مع ميزات متابعة يومية."
    d_en = "A complete Quran for reading, listening, tafsir and memorization, with daily follow-up."
    cats = ("top",)
    site = True
    guide_ar = ("مصحف كامل داخل تيليجرام، ومعه موقع ويب للقراءة والاستماع يحفظ موضع القارئ مع البوت:\n• 📖 قراءة كل السور مع حفظ موضع القراءة والمتابعة منه.\n• 🎧 استماع بأصوات عدة قرّاء.\n"
                "• 📚 التفسير الميسّر لأي آية.\n• 🔎 بحث في نص القرآن.\n• ⏰ تذكير يومي بالورد في الساعة التي يختارها المستخدم.\n• ❤️ تتبّع السور المحفوظة.\n\n"
                "النصوص والتلاوات تُجلب من خدمة alquran.cloud العامة، فيحتاج السيرفر اتصالاً بالإنترنت. لا يحتاج القالب أي إعداد من المالك.")

    def setup(self, app) -> None:
        if app.job_queue is not None:
            app.job_queue.run_repeating(self._remind, interval=3600, first=120, name="quran_remind")

    async def _remind(self, context) -> None:
        bot_id = context.bot_data["bot_id"]
        if plat.admin_lock(context.bot_data) is not None:      # البوت مغلق من الإدارة: لا مهام مجدولة
            return
        hour = (dt.datetime.utcnow() + dt.timedelta(hours=3)).hour
        for r in await db.rec_list(bot_id, "qu", limit=5000):
            if r.data.get("remind") != hour:
                continue
            s = r.data.get("s", 1)
            try:
                await context.bot.send_message(r.user_id, f"⏰ <b>وردك اليومي</b>\n\nتوقفت عند سورة {SURAHS[s - 1]}، الآية {r.data.get('off', 0) + 1}.",
                                               parse_mode="HTML", reply_markup=kb([[B("📖 تابع القراءة", "t:cont")]]))
            except TelegramError:
                pass

    async def user(self, c: Ctx):
        recs = await c.rec_list("qu", user_id=c.uid, limit=1)
        if recs:
            return recs[0]
        rid = await c.rec_add("qu", {"s": 1, "off": 0, "remind": None, "hifz": [], "rec": 0})
        return await c.rec_get(rid)

    async def home(self, c: Ctx) -> None:
        t = c.t
        site = [c.site_btn("🌐 المصحف على الويب", "🌐 Read on the web", "📖 افتح المصحف", "📖 Open the Mushaf")]
        await c.edit(ui.head(c.brand) + "\n" + t("﴿ وَرَتِّلِ الْقُرْآنَ تَرْتِيلًا ﴾\n\nاختر من القائمة:", "Choose from the menu:"), kb([
            site if c.mini_app() else None,
            [B(t("📖 السور", "📖 Surahs"), "t:l:0"), B(t("▶️ تابع القراءة", "▶️ Continue reading"), "t:cont")],
            [B(t("🎧 الاستماع", "🎧 Listen"), "t:al:0"), B(t("🔎 بحث", "🔎 Search"), "t:find")],
            [B(t("⏰ الورد اليومي", "⏰ Daily reminder"), "t:rem"), B(t("❤️ حفظي", "❤️ My memorization"), "t:hz")],
            None if c.mini_app() else site,
            c.tail()]))

    async def owner(self, c: Ctx):
        n = await c.rec_count("qu")
        return c.t(f"📖 قرّاء مسجّلون: {n}", f"📖 Readers: {n}"), []

    def surah_list(self, c: Ctx, page: int, pfx: str):
        per = 18
        pages = (114 + per - 1) // per
        page = max(0, min(page, pages - 1))
        btns = [B(f"{i + 1}. {SURAHS[i]}", f"{pfx}:{i + 1}") for i in range(page * per, min(114, (page + 1) * per))]
        back = "t:l" if pfx == "t:s" else "t:al"
        nav = [B("‹", f"{back}:{page - 1}") if page else None, B(f"• {page + 1}/{pages} •", "noop"), B("›", f"{back}:{page + 1}") if page < pages - 1 else None]
        return kb(ui.grid(btns, 3) + [nav, c.home_row()])

    async def read(self, c: Ctx, s: int, off: int) -> None:
        ay = await ayahs(s)
        off = max(0, min(off, max(0, len(ay) - 1)))
        off -= off % PAGE
        chunk = ay[off:off + PAGE]
        body = " ".join(f"{a} ﴿{off + i + 1}﴾" for i, a in enumerate(chunk))
        u = await self.user(c)
        await c.rec_update(u.id, data=dict(u.data, s=s, off=off))
        nav = [B("‹", f"t:r:{s}:{off - PAGE}") if off else None, B(f"{off + 1}-{off + len(chunk)}/{len(ay)}", "noop"),
               B("›", f"t:r:{s}:{off + PAGE}") if off + PAGE < len(ay) else (B(c.t("السورة التالية ›", "Next surah ›"), f"t:r:{s + 1}:0") if s < 114 else None)]
        await c.edit(f"<b>سورة {SURAHS[s - 1]}</b>\n{ui.LINE}\n{esc(body)}"[:4000], kb([
            nav, [B(c.t("📚 تفسير", "📚 Tafsir"), f"t:tf:{s}:{off}"), B(c.t("🎧 استماع", "🎧 Listen"), f"t:a:{s}")],
            [B(c.t("❤️ حفظتها", "❤️ Memorized"), f"t:hzt:{s}"), B(c.t("📖 السور", "📖 Surahs"), "t:l:0")], c.home_row()]))

    async def cb(self, c: Ctx, a: list[str]) -> None:  # noqa: C901
        act, t = a[0], c.t
        try:
            if act == "l":
                await c.edit(t("📖 اختر السورة:", "📖 Pick a surah:"), self.surah_list(c, int(a[1]), "t:s"))
            elif act == "s":
                await self.read(c, int(a[1]), 0)
            elif act == "r":
                await self.read(c, int(a[1]), int(a[2]))
            elif act == "cont":
                u = await self.user(c)
                await self.read(c, u.data.get("s", 1), u.data.get("off", 0))
            elif act == "tf":
                s, off = int(a[1]), int(a[2])
                ay = await ayahs(s)
                rows = ui.grid([B(str(i + 1), f"t:tfa:{s}:{i + 1}") for i in range(off, min(off + PAGE, len(ay)))], 4)
                await c.edit(t("📚 اختر رقم الآية لعرض تفسيرها:", "📚 Pick the ayah number for its tafsir:"), kb(rows + [[B(t("⬅️ رجوع", "⬅️ Back"), f"t:r:{s}:{off}")]]))
            elif act == "tfa":
                s, n = int(a[1]), int(a[2])
                tf = await tafsir(s, n)
                ay = await ayahs(s)
                await c.edit(f"<b>سورة {SURAHS[s - 1]} — الآية {n}</b>\n\n{esc(ay[n - 1])}\n\n<b>📚 التفسير الميسّر</b>\n{esc(tf)}"[:4000],
                             kb([[B(t("⬅️ رجوع", "⬅️ Back"), f"t:r:{s}:{n - 1}")]]))
            elif act == "al":
                await c.edit(t("🎧 اختر السورة للاستماع:", "🎧 Pick a surah to listen:"), self.surah_list(c, int(a[1]), "t:a"))
            elif act == "a":
                u = await self.user(c)
                cur = u.data.get("rec", 0)
                rows = ui.grid([B(("✓ " if i == cur else "") + name, f"t:ap:{a[1]}:{i}") for i, (_, name) in enumerate(RECITERS)], 2)
                await c.edit(t(f"🎧 سورة {SURAHS[int(a[1]) - 1]} — اختر القارئ:", f"🎧 Surah {SURAHS[int(a[1]) - 1]} — pick a reciter:"), kb(rows + [c.home_row()]))
            elif act == "ap":
                s, i = int(a[1]), int(a[2])
                u = await self.user(c)
                await c.rec_update(u.id, data=dict(u.data, rec=i))
                url = f"https://cdn.islamic.network/quran/audio-surah/128/{RECITERS[i][0]}/{s}.mp3"
                await c.answer(t("⏳ جاري إرسال التلاوة…", "⏳ Sending the recitation…"))
                try:
                    await c.audio(url, title=f"سورة {SURAHS[s - 1]}", performer=RECITERS[i][1])
                except TelegramError:
                    await c.send(t(f"🎧 التلاوة كبيرة الحجم، استمع من الرابط:\n{url}", f"🎧 The file is large; listen here:\n{url}"), disable_web_page_preview=False)
            elif act == "find":
                c.set_state("qu_find")
                await c.edit(t("🔎 أرسل كلمة أو عبارة للبحث عنها في القرآن.\n\n/cancel للإلغاء", "🔎 Send a word or phrase to search the Quran.\n\n/cancel to abort"), kb([c.home_row()]))
            elif act == "rem":
                u = await self.user(c)
                cur = u.data.get("remind")
                btns = [B(("✓ " if cur == h else "") + f"{h:02d}:00", f"t:rs:{h}") for h in (5, 6, 7, 8, 12, 16, 18, 20, 21, 22)]
                await c.edit(ui.head(t("⏰ الورد اليومي", "⏰ Daily reminder")) + "\n" + t(
                    f"الحالة: {'🟢 ' + f'{cur:02d}:00' if cur is not None else '🔴 متوقف'}\nاختر ساعة التذكير (توقيت مكة/دمشق):",
                    f"Status: {'🟢 ' + f'{cur:02d}:00' if cur is not None else '🔴 off'}\nPick the reminder hour (UTC+3):"),
                    kb(ui.grid(btns, 5) + [[B(t("🔕 إيقاف التذكير", "🔕 Turn off"), "t:rs:x")], c.home_row()]))
            elif act == "rs":
                u = await self.user(c)
                await c.rec_update(u.id, data=dict(u.data, remind=None if a[1] == "x" else int(a[1])))
                await self.cb(c, ["rem"])
            elif act == "hzt":
                u = await self.user(c)
                hz = list(u.data.get("hifz", []))
                s = int(a[1])
                hz.remove(s) if s in hz else hz.append(s)
                await c.rec_update(u.id, data=dict(u.data, hifz=hz))
                await c.answer(t("❤️ أُضيفت للمحفوظات" if s in hz else "أزيلت من المحفوظات", "❤️ Marked as memorized" if s in hz else "Removed"), True)
            elif act == "hz":
                u = await self.user(c)
                hz = sorted(u.data.get("hifz", []))
                names = "، ".join(SURAHS[s - 1] for s in hz) or t("لم تحدد سوراً بعد. افتح أي سورة واضغط «❤️ حفظتها».", "Nothing yet. Open a surah and tap “❤️ Memorized”.")
                await c.edit(ui.head(t("❤️ حفظي", "❤️ My memorization")) + "\n" + t(f"📊 {len(hz)} من 114 سورة\n\n{names}", f"📊 {len(hz)} of 114 surahs\n\n{names}"), kb([c.home_row()]))
        except TelegramError:
            raise
        except Exception:
            log.info("quran api unavailable")
            await c.answer(t("⚠️ تعذّر الاتصال بمصدر المصحف الآن. حاول بعد قليل.", "⚠️ Couldn't reach the Quran source. Try again shortly."), True)

    async def msg(self, c: Ctx) -> bool:
        st = c.st
        if st and st["k"] == "qu_find":
            c.clear_state()
            try:
                d = await get_json(f"{API}/search/{c.text[:60]}/all/quran-simple-clean", timeout=25)
                ms = d["data"]["matches"][:8]
            except Exception:
                ms = []
            if not ms:
                await c.send(c.t("لم أجد نتائج.", "No results."), kb([c.home_row()]))
                return True
            body = "\n\n".join(f"• {esc(m['text'])}\n  <i>{SURAHS[m['surah']['number'] - 1]} ﴿{m['numberInSurah']}﴾</i>" for m in ms)
            rows = [[B(f"{SURAHS[m['surah']['number'] - 1]} {m['numberInSurah']}", f"t:r:{m['surah']['number']}:{m['numberInSurah'] - 1}")] for m in ms[:5]]
            await c.send(c.t(f"🔎 نتائج «{esc(c.text[:60])}»:\n\n", f"🔎 Results for “{esc(c.text[:60])}”:\n\n") + body[:3600], kb(rows + [c.home_row()]))
            return True
        await self.home(c)
        return True


TPL = Quran()
