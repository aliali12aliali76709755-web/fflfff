"""حجز مواعيد: خدمات، أيام، وفترات زمنية متاحة مع تأكيد من المالك."""
import asyncio
import datetime as dt
import re

from telegram.error import TelegramError

from .. import ui
from ..ctx import Ctx
from ..ui import B, esc, kb
from . import Items, Tpl

DAYS_AR = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
DAYS_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
ST = {"new": ("🕒 بانتظار التأكيد", "🕒 Awaiting confirmation"), "ok": ("✅ مؤكد", "✅ Confirmed"), "no": ("❌ ملغي", "❌ Cancelled")}
DEF = {"from": "09:00", "to": "17:00", "slot": 30, "tz": 3, "off": [4]}


def _mins(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _valid_time(hhmm: str) -> bool:
    return bool(re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d|24:00", hhmm))


_locks: dict[int, asyncio.Lock] = {}


def web_code(bot_id: int, rid: int) -> str:
    from ..web import sign
    return f"b{rid}_{sign.sig('webbook', bot_id, rid)[:10]}"


class Booking(Tpl):
    emoji, ar, en = "📅", "حجز مواعيد", "Appointments"
    d_ar, d_en = "حجز مواعيد وخدمات، مع صفحة حجز على الويب", "Appointment and service booking, with a web booking page"
    cats = ("biz",)
    site = True
    guide_ar = ("1. أضف خدماتك بصيغة <code>الخدمة | السعر | المدة بالدقائق</code>.\n"
                "2. من «⏰ أوقات العمل» حدّد ساعات الدوام، طول الموعد، فرق التوقيت، وأيام العطلة.\n"
                "3. الزبون يختار الخدمة ثم اليوم ثم الوقت المتاح ويرسل رقم هاتفه.\n4. يصلك الحجز بزرّي تأكيد وإلغاء، والوقت المحجوز لا يظهر لغيره.")

    def __init__(self) -> None:
        self.items = Items("booking", fields=("name", "price", "mins"), ar="خدمة", en="service",
                           fmt_ar="الخدمة | السعر | المدة بالدقائق", fmt_en="Service | Price | Duration in minutes",
                           sample=[{"name": "استشارة", "price": "10$", "mins": "30"}])

    async def cfg(self, c: Ctx) -> dict:
        return {**DEF, **(await c.kv("booking:cfg", {}) or {})}

    def now_local(self, cfg: dict) -> dt.datetime:
        return dt.datetime.utcnow() + dt.timedelta(hours=float(cfg["tz"]))

    async def home(self, c: Ctx) -> None:
        await c.edit(ui.head(c.brand) + (await c.kv("booking:intro") or c.t(
            "أهلاً بك 👋\nاحجز موعدك في ثلاث خطوات: الخدمة، اليوم، ثم الوقت.", "Welcome 👋\nBook in three steps: service, day, then time.")),
            kb([[c.site_btn("🌐 احجز من صفحة الويب", "🌐 Book on the web page", "📅 افتح صفحة الحجز", "📅 Open the booking page")] if c.mini_app() else None,
                [B(c.t("📅 احجز موعداً", "📅 Book now"), "t:svc", style=None if c.mini_app() else "success")],
                None if c.mini_app() else [c.site_btn("🌐 احجز من صفحة الويب", "🌐 Book on the web page")],
                [B(c.t("🗓 حجوزاتي", "🗓 My bookings"), "t:mine")], c.tail()]))

    def days(self, cfg: dict, count: int = 8) -> list[dt.date]:
        today, out = self.now_local(cfg).date(), []
        for i in range(21):
            d = today + dt.timedelta(days=i)
            if d.weekday() not in cfg["off"]:
                out.append(d)
            if len(out) == count:
                break
        return out

    async def free_slots(self, c, cfg: dict, date: str) -> list[str]:
        """الأوقات المتاحة في يوم (YYYY-MM-DD): ضمن الدوام، غير محجوزة، ولم يمضِ وقتها."""
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date or ""):      # الصيغة نفسها التي تُحفظ بها الحجوزات
            return []
        try:
            day = dt.date.fromisoformat(date)
        except ValueError:
            return []
        now = self.now_local(cfg)
        if day < now.date() or day > now.date() + dt.timedelta(days=30) or day.weekday() in cfg["off"]:
            return []
        taken = await self.taken(c, date)
        try:
            start, end, step = max(0, _mins(cfg["from"])), min(1440, _mins(cfg["to"])), max(5, int(cfg["slot"]))
        except (ValueError, TypeError):
            return []
        out = []
        for m in range(start, end, step):
            hhmm = f"{m // 60:02d}:{m % 60:02d}"
            if hhmm not in taken and not (day == now.date() and m <= now.hour * 60 + now.minute):
                out.append(hhmm)
        return out

    async def reserve(self, c, svc: dict, date: str, time: str, note: str, name: str, src: str = "bot") -> int | None:
        """يحجز الوقت إن كان ما زال متاحاً. القفل يمنع أن يأخذ طلبان متزامنان (من البوت والموقع) الوقت نفسه."""
        async with _locks.setdefault(c.bot_id, asyncio.Lock()):
            if time not in await self.free_slots(c, await self.cfg(c), date):
                return None
            return await self.create(c, svc, date, time, note, name, src)

    async def create(self, c, svc: dict, date: str, time: str, note: str, name: str, src: str = "bot") -> int:
        """ينشئ الحجز ويبلغ المالك. يعمل من البوت ومن صفحة الويب."""
        d = {"svc": svc["name"], "price": svc.get("price", ""), "date": date, "time": time, "note": note[:300], "name": name[:80], "src": src}
        rid = await c.rec_add("book", d, status="new")
        t = c.t
        via = t(" · 🌐 من صفحة الويب", " · 🌐 via web page") if src == "web" else ""
        await c.notify_owner(t(f"🔔 <b>حجز جديد #{rid}</b>{via}\n📌 {esc(d['svc'])} — {esc(d['price'])}\n📅 {d['date']} ⏰ {d['time']}\n👤 {esc(name)} (<code>{c.uid}</code>)\n📝 {esc(d['note'])}",
                               f"🔔 <b>New booking #{rid}</b>{via}\n📌 {esc(d['svc'])} — {esc(d['price'])}\n📅 {d['date']} ⏰ {d['time']}\n👤 {esc(name)} (<code>{c.uid}</code>)\n📝 {esc(d['note'])}"),
                             kb([[B(t("✅ تأكيد", "✅ Confirm"), f"t:st:{rid}:ok", style="success"), B(t("❌ إلغاء", "❌ Cancel"), f"t:st:{rid}:no", style="danger")]]))
        return rid

    async def start_param(self, c: Ctx, param: str) -> bool:
        """رابط صفحة الويب: b<رقم>_<توقيع> لتأكيد حجز أُرسل من الصفحة."""
        m = re.fullmatch(r"b(\d+)_([0-9a-f]{10})", param)
        if not m:
            return False
        rid, t = int(m.group(1)), c.t
        r = await c.rec_get(rid)
        if r is None or r.kind != "book:web" or param != web_code(c.bot_id, rid):
            await c.send(t("⚠️ رابط الحجز غير صالح.", "⚠️ This booking link is not valid."), kb([c.home_row()]))
            return True
        if r.status != "wait":
            await c.send(t("ℹ️ هذا الحجز أُرسل من قبل. تجده في «حجوزاتي».", "ℹ️ This booking was already sent. See “My bookings”."), kb([[B(t("🗓 حجوزاتي", "🗓 My bookings"), "t:mine")]]))
            return True
        await c.rec_update(rid, status="done")
        d = r.data
        new = await self.reserve(c, {"name": d["svc"], "price": d.get("price", "")}, d["date"], d["time"], d.get("note", ""), d.get("name") or c.user.full_name, src="web")
        if new is None:
            await c.send(t("⚠️ هذا الوقت حُجز قبل تأكيدك. اختر وقتاً آخر.", "⚠️ That slot was taken before you confirmed. Pick another one."), kb([[B(t("📅 احجز موعداً", "📅 Book now"), "t:svc")]]))
            return True
        await c.send(t(f"✅ <b>وصل طلب الحجز #{new}</b>\n📌 {esc(d['svc'])}\n📅 {d['date']} ⏰ {d['time']}\n\nسيصلك هنا التأكيد من صاحب الموعد.",
                       f"✅ <b>Booking request #{new} received</b>\n📌 {esc(d['svc'])}\n📅 {d['date']} ⏰ {d['time']}\n\nYou'll get the confirmation here."),
                     kb([[B(t("🗓 حجوزاتي", "🗓 My bookings"), "t:mine")], c.home_row()]))
        return True

    async def owner(self, c: Ctx):
        cfg = await self.cfg(c)
        n = await c.rec_count("book", status="new")
        off = "، ".join(DAYS_AR[d] for d in cfg["off"]) or "—"
        return (c.t(f"🕘 الدوام: {cfg['from']}–{cfg['to']} · موعد كل {cfg['slot']} د · UTC{cfg['tz']:+g}\n🚫 العطلة: {off}\n🕒 حجوزات تنتظر التأكيد: {n}",
                    f"🕘 Hours: {cfg['from']}–{cfg['to']} · {cfg['slot']} min slots · UTC{cfg['tz']:+g}\n🕒 Awaiting confirmation: {n}"),
                [[B(c.t("➕ إضافة خدمة", "➕ Add service"), "t:ia:booking"), B(c.t("📋 الخدمات", "📋 Services"), "t:il:booking")],
                 [B(c.t(f"🗓 الحجوزات ({n})", f"🗓 Bookings ({n})"), "t:all"), B(c.t("⏰ أوقات العمل", "⏰ Working hours"), "t:hours")]])

    def line(self, c: Ctx, r) -> str:
        d = r.data
        return (f"#{r.id} · <b>{esc(d['svc'])}</b>\n📅 {d['date']} ⏰ {d['time']} · {c.t(*ST.get(r.status, ST['new']))}"
                + (f"\n📝 {esc(d['note'])}" if d.get("note") else ""))

    async def taken(self, c: Ctx, date: str) -> set[str]:
        recs = await c.rec_list("book", limit=800)
        return {r.data["time"] for r in recs if r.data.get("date") == date and r.status in ("new", "ok")}

    async def cb(self, c: Ctx, a: list[str]) -> None:  # noqa: C901
        if await self.items.handle_cb(c, a):
            return
        act, t = a[0], c.t
        cfg = await self.cfg(c)
        if act == "svc":
            svcs = await self.items.all(c)
            rows = [[B(f"{s['name']} — {s.get('price', '')} · {s.get('mins') or cfg['slot']}′"[:60], f"t:s:{s['id']}")] for s in svcs]
            await c.edit(ui.head(t("1️⃣ اختر الخدمة", "1️⃣ Choose a service")) + ("" if svcs else "\n" + t("لا توجد خدمات بعد.", "No services yet.")),
                         kb(rows + [c.home_row()]))
        elif act == "s":
            btns = [B(f"{(DAYS_AR if c.lang == 'ar' else DAYS_EN)[d.weekday()]} {d:%d/%m}", f"t:d:{a[1]}:{d:%Y%m%d}") for d in self.days(cfg)]
            await c.edit(ui.head(t("2️⃣ اختر اليوم", "2️⃣ Choose a day")), kb(ui.grid(btns, 2) + [[B(t("⬅️ رجوع", "⬅️ Back"), "t:svc")]]))
        elif act == "d":
            date = f"{a[2][:4]}-{a[2][4:6]}-{a[2][6:]}"
            btns = [B(hhmm, f"t:h:{a[1]}:{a[2]}:{hhmm.replace(':', '')}") for hhmm in await self.free_slots(c, cfg, date)]
            await c.edit(ui.head(t(f"3️⃣ اختر الوقت — {date}", f"3️⃣ Choose a time — {date}")) + (
                "" if btns else "\n" + t("لا توجد أوقات متاحة في هذا اليوم.", "No free slots that day.")),
                kb(ui.grid(btns[:48], 4) + [[B(t("⬅️ رجوع", "⬅️ Back"), f"t:s:{a[1]}")]]))
        elif act == "h":
            svc = await self.items.get(c, int(a[1]))
            if svc is None:
                return
            date, time = f"{a[2][:4]}-{a[2][4:6]}-{a[2][6:]}", f"{a[3][:2]}:{a[3][2:]}"
            c.set_state("book", svc=svc["name"], price=svc.get("price", ""), date=date, time=time)
            await c.edit(t(f"📌 <b>{esc(svc['name'])}</b>\n📅 {date} ⏰ {time}\n\n📝 أرسل اسمك ورقم هاتفك لتأكيد الحجز.\n\n/cancel للإلغاء",
                           f"📌 <b>{esc(svc['name'])}</b>\n📅 {date} ⏰ {time}\n\n📝 Send your name and phone number to confirm.\n\n/cancel to abort"),
                         kb([[B(t("❌ إلغاء", "❌ Cancel"), "t:svc")]]))
        elif act == "mine":
            recs = await c.rec_list("book", user_id=c.uid, limit=8)
            rows = [[B(t(f"❌ إلغاء #{r.id}", f"❌ Cancel #{r.id}"), f"t:x:{r.id}")] for r in recs if r.status in ("new", "ok")]
            await c.edit(ui.head(t("🗓 حجوزاتي", "🗓 My bookings")) + "\n" + ("\n\n".join(self.line(c, r) for r in recs) or t("لا توجد حجوزات.", "No bookings.")),
                         kb(rows + [c.home_row()]))
        elif act == "x":
            r = await c.rec_get(int(a[1]))
            if r is not None and r.kind == "book" and (r.user_id == c.uid or c.is_owner):
                await c.rec_update(r.id, status="no")
                await c.answer(t("تم الإلغاء", "Cancelled"), True)
                if r.user_id == c.uid and not c.is_owner:
                    await c.notify_owner(t(f"ℹ️ ألغى {c.name} الحجز #{r.id} ({r.data['date']} {r.data['time']}).",
                                           f"ℹ️ {c.name} cancelled booking #{r.id} ({r.data['date']} {r.data['time']})."))
            await self.cb(c, ["mine"])
        elif not c.is_owner:
            return
        elif act == "all":
            recs = [r for r in await c.rec_list("book", limit=40) if r.status in ("new", "ok")][:12]
            rows = []
            for r in recs:
                rows.append([B(f"✅ #{r.id}", f"t:st:{r.id}:ok") if r.status == "new" else None, B(f"❌ #{r.id}", f"t:st:{r.id}:no")])
            text = "\n\n".join(self.line(c, r) + f"\n👤 {esc(r.data.get('name', ''))}" for r in recs) or t("لا توجد حجوزات قادمة.", "No upcoming bookings.")
            await c.edit(ui.head(t("🗓 الحجوزات", "🗓 Bookings")) + "\n" + text, kb(rows + [[B(t("🎛 غرفة التحكم", "🎛 Control room"), "o:home")]]))
        elif act == "st":
            r = await c.rec_get(int(a[1]))
            if r is not None and r.kind == "book":
                await c.rec_update(r.id, status=a[2])
                r.status = a[2]
                try:
                    await c.send(t("🔔 تحديث على حجزك:\n\n", "🔔 Update on your booking:\n\n") + self.line(c, r), chat_id=r.user_id)
                except TelegramError:
                    pass
            await self.cb(c, ["all"])
        elif act == "hours":
            c.set_state("book_hours")
            await c.edit(t("⏰ أرسل أوقات العمل بهذه الصيغة:\n<code>09:00-17:00 | 30 | 3 | 5</code>\n\n"
                           "• من-إلى\n• طول الموعد بالدقائق\n• فرق التوقيت عن UTC (سوريا وتركيا = 3)\n"
                           "• أيام العطلة بالأرقام مفصولة بفاصلة (1=الاثنين … 5=الجمعة … 7=الأحد)، أو 0 بلا عطلة\n\n/cancel للإلغاء",
                           "⏰ Send working hours as:\n<code>09:00-17:00 | 30 | 3 | 5</code>\n\n• from-to\n• slot length in minutes\n• UTC offset\n"
                           "• days off as numbers (1=Mon … 7=Sun), or 0 for none\n\n/cancel to abort"), kb([[B(t("❌ إلغاء", "❌ Cancel"), "o:home")]]))

    async def msg(self, c: Ctx) -> bool:
        if c.is_owner and await self.items.handle_msg(c):
            return True
        st, t = c.st, c.t
        if st and st["k"] == "book_hours" and c.is_owner:
            try:
                p = [x.strip() for x in c.text.split("|")]
                fr, to = [x.strip() for x in p[0].split("-")]
                assert _valid_time(fr) and _valid_time(to) and _mins(fr) < _mins(to)
                assert len(p) < 2 or 5 <= int(p[1]) <= 480
                assert len(p) < 3 or -12 <= float(p[2]) <= 14
                off = [int(x) - 1 for x in p[3].replace("،", ",").split(",") if x.strip().isdigit() and 1 <= int(x) <= 7] if len(p) > 3 else []
                cfg = {"from": fr, "to": to, "slot": int(p[1]) if len(p) > 1 else 30, "tz": float(p[2]) if len(p) > 2 else 3, "off": off}
            except Exception:
                await c.send(t("⚠️ صيغة غير صحيحة. مثال: <code>09:00-17:00 | 30 | 3 | 5</code>", "⚠️ Invalid format. Example: <code>09:00-17:00 | 30 | 3 | 5</code>"))
                return True
            await c.kv_set("booking:cfg", cfg)
            c.clear_state()
            await c.send(t("✅ تم حفظ أوقات العمل.", "✅ Working hours saved."), kb([c.home_row()]))
            return True
        if st and st["k"] == "book":
            c.clear_state()
            rid = await self.reserve(c, {"name": st["svc"], "price": st["price"]}, st["date"], st["time"], c.text, c.user.full_name)
            if rid is None:
                await c.send(t("⚠️ هذا الوقت حُجز للتو. اختر وقتاً آخر.", "⚠️ That slot was just taken. Pick another."), kb([[B(t("📅 احجز", "📅 Book"), "t:svc")]]))
                return True
            await c.send(t(f"✅ <b>وصل طلب الحجز #{rid}</b>\n📌 {esc(st['svc'])}\n📅 {st['date']} ⏰ {st['time']}\n\nسيصلك هنا التأكيد من صاحب الموعد.",
                           f"✅ <b>Booking request #{rid} received</b>\n📌 {esc(st['svc'])}\n📅 {st['date']} ⏰ {st['time']}\n\nYou'll get the confirmation here."),
                         kb([[B(t("🗓 حجوزاتي", "🗓 My bookings"), "t:mine")], c.home_row()]))
            return True
        return False

    async def checklist(self, c: Ctx) -> list:
        svcs = await self.items.all(c)
        real = [x for x in svcs if x.get("name") != "استشارة"]
        return [(bool(real), c.t("أضف خدماتك الحقيقية", "Add your real services"), "t:ia:booking"),
                (bool(await c.kv("booking:cfg")), c.t("حدّد أوقات العمل وأيام العطلة", "Set working hours and days off"), "t:hours")]


TPL = Booking()
