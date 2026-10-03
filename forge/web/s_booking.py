"""صفحة الحجز: الخدمة ← اليوم ← الوقت ← البيانات، والحجز يصل صاحب البوت."""
from __future__ import annotations

from ..templates.booking import DAYS_AR, DAYS_EN, web_code
from . import kit
from .render import e


async def render(site):
    tpl, lite, t = site.tpl, site.lite(), site.t
    cfg = await tpl.cfg(lite)
    svcs = await tpl.items.all(lite)
    intro = await lite.kv("booking:intro") or ""
    names = DAYS_AR if site.lang == "ar" else DAYS_EN
    data = {
        "svcs": [{"id": kit.as_int(x.get("id")), "name": str(x.get("name", "")), "price": str(x.get("price", "")), "mins": kit.as_int(x.get("mins"), kit.as_int(cfg["slot"], 30))} for x in svcs],
        "days": [{"date": d.isoformat(), "dow": names[d.weekday()], "day": d.day, "mon": d.month} for d in tpl.days(cfg, 10)],
        "hours": f"{cfg['from']} – {cfg['to']}",
    }
    body = f'''
<section class="hero"><div class="avatar lg"><span>{tpl.emoji}</span><img src="{site.root}/avatar" alt="" onerror="this.remove()"></div>
<h1>{e(site.title)}</h1><p class="prose">{e(site.cfg.get("tagline") or kit.plain(intro) or t("احجز موعدك في أقل من دقيقة.", "Book your appointment in under a minute."))}</p>
<span class="badge">🕘 {e(data["hours"])}</span></section>
<section class="stack mt2">
<div class="step"><div class="n">1</div><div class="grow"><h3>{e(t("اختر الخدمة", "Choose a service"))}</h3><div class="links mt" id="svcs"></div></div></div>
<div class="step" id="s2" hidden><div class="n">2</div><div class="grow"><h3>{e(t("اختر اليوم", "Choose a day"))}</h3><div class="days mt" id="days"></div></div></div>
<div class="step" id="s3" hidden><div class="n">3</div><div class="grow"><h3>{e(t("اختر الوقت", "Choose a time"))}</h3><div class="slots mt" id="slots"></div>
<p class="muted small mt" id="noslots" hidden>{e(t("لا توجد أوقات متاحة في هذا اليوم. جرّب يوماً آخر.", "No free times on this day. Try another day."))}</p></div></div>
<div class="step" id="s4" hidden><div class="n">4</div><div class="grow"><h3>{e(t("بياناتك", "Your details"))}</h3>
<form id="bookForm" class="stack mt" novalidate>
<label>{e(t("الاسم", "Name"))}<input class="input" name="name" required maxlength="60" autocomplete="name"></label>
<label>{e(t("رقم الهاتف", "Phone number"))}<input class="input" name="phone" required maxlength="30" inputmode="tel" autocomplete="tel" dir="ltr"></label>
<label>{e(t("ملاحظة (اختياري)", "Note (optional)"))}<textarea name="note" maxlength="200"></textarea></label>
<div class="notice" id="summary"></div>
<button class="btn primary block" type="submit" id="bookBtn">{e(t("تأكيد الحجز", "Confirm booking"))}</button>
<p class="small muted center" id="hint"></p></form></div></div>
</section>
<div class="mt2">{kit.open_bot_btn(site, t("تابع حجوزاتك في البوت", "Manage your bookings in the bot"), "btn soft block")}</div>
<div class="scrim" id="doneSheet"><div class="sheet center" role="dialog" aria-modal="true"><div class="grab"></div><div id="doneBody" class="stack" style="padding:10px 0 6px"></div></div></div>
'''
    return await kit.shell(site, body, scripts=("booking.js",), data=data)


async def slots(site, body: dict) -> dict:
    tpl, lite = site.tpl, site.lite()
    kit.throttle(("slots", site.bot.id, kit.client_ip(site.req)), 90, 60)
    return {"slots": await tpl.free_slots(lite, await tpl.cfg(lite), kit.clean(body.get("date"), 10))}


async def book(site, body: dict) -> dict:
    tpl, lite, t = site.tpl, site.lite(), site.t
    cfg = await tpl.cfg(lite)
    svc = await tpl.items.get(lite, body.get("svc")) if type(body.get("svc")) is int else None
    date, time = kit.clean(body.get("date"), 10), kit.clean(body.get("time"), 5)
    name, phone, note = kit.clean(body.get("name"), 60), kit.clean(body.get("phone"), 30), kit.clean(body.get("note"), 200)
    if svc is None:
        raise kit.ApiError("svc", t("اختر الخدمة.", "Choose a service."))
    if len(name) < 2 or len(phone) < 5:
        raise kit.ApiError("details", t("أكمل الاسم ورقم الهاتف.", "Please fill in your name and phone."))
    if time not in await tpl.free_slots(lite, cfg, date):
        raise kit.ApiError("taken", t("هذا الوقت لم يعد متاحاً. اختر وقتاً آخر.", "That time is no longer available. Pick another."), 409)
    details = f"{name} · {phone}" + (f"\n{note}" if note else "")
    if site.uid:
        kit.throttle(("book", site.bot.id, site.uid), 4, 600)
        rid = await tpl.reserve(lite, svc, date, time, details, name, src="web")
        if rid is None:
            raise kit.ApiError("taken", t("هذا الوقت لم يعد متاحاً. اختر وقتاً آخر.", "That time is no longer available. Pick another."), 409)
        await lite.send(t(f"✅ <b>وصل طلب الحجز #{rid}</b>\n📌 {e(svc['name'])}\n📅 {date} ⏰ {time}\n\nسيصلك هنا التأكيد من صاحب الموعد.",
                          f"✅ <b>Booking request #{rid} received</b>\n📌 {e(svc['name'])}\n📅 {date} ⏰ {time}\n\nYou'll get the confirmation here."))
        return {"placed": True, "id": rid}
    kit.throttle(("webbook", site.bot.id, kit.client_ip(site.req)), 20, 600)
    if await lite.rec_count("book:web", status="wait") >= 300:
        raise kit.ApiError("busy", t("الطلبات كثيرة الآن. احجز من داخل البوت مباشرة.", "Too many pending requests right now. Please book inside the bot."), 429)
    rid = await lite.rec_add("book:web", {"svc": svc["name"], "price": svc.get("price", ""), "date": date, "time": time, "note": details, "name": name}, status="wait", user_id=0)
    return {"placed": False, "link": f"{site.tg_link}?start={web_code(site.bot.id, rid)}"}


API = {"slots": slots, "book": book}
