"""دورة الإنجليزية على الويب: دروس، مفردات، مراجعة متباعدة، واختبار مستوى — بتقدّم يتزامن مع البوت."""
from __future__ import annotations

import datetime as dt

from ..templates._english_data import LESSONS, LEVELS, PLACEMENT, WORDS
from ..templates.english import GAPS
from . import kit
from .render import e


def _clean(u) -> dict | None:
    """يقبل من المتصفح حالة تقدّم معقولة فقط."""
    if not isinstance(u, dict):
        return None
    lvl, xp, done_in, box_in = u.get("lvl"), u.get("xp"), u.get("done") or [], u.get("box") or {}
    if type(lvl) is not int or lvl not in (0, 1, 2, 3) or type(xp) is not int or not 0 <= xp <= 1_000_000:
        return None
    if not isinstance(done_in, list) or not isinstance(box_in, dict):
        return None
    done = sorted({i for i in done_in if type(i) is int and 0 <= i < len(LESSONS)})
    box = {}
    for k, v in box_in.items():
        k = str(k)
        if (k.isascii() and k.isdecimal() and len(k) < 5 and int(k) < len(WORDS) and isinstance(v, list) and len(v) == 2
                and all(type(x) is int for x in v) and 0 <= v[0] < len(GAPS) and 700000 < v[1] < 800000):
            box[str(int(k))] = [v[0], v[1]]
    return {"lvl": lvl, "xp": xp, "done": done, "box": box}


async def render(site):
    t, lite = site.t, site.lite()
    u = _clean(await lite.kv(f"en:u:{site.uid}")) if site.uid else None      # تنقية قبل تضمينها في الصفحة
    data = {"levels": LEVELS, "today": dt.date.today().toordinal(), "gaps": GAPS, "state": u,
            "lessons": [{"lv": lv, "title": title, "body": body, "ex": ex, "quiz": [{"q": q, "o": o, "a": a} for q, o, a in quiz]} for lv, title, body, ex, quiz in LESSONS],
            "words": [{"lv": lv, "w": w, "m": m} for lv, w, m in WORDS],
            "placement": [{"q": q, "o": o, "a": a, "lv": lv} for q, o, a, lv in PLACEMENT]}
    body = f'''
<section class="hero" style="padding-bottom:0"><h1>{e(site.title)}</h1><p>{e(site.cfg.get("tagline") or t("تعلّم الإنجليزية خطوة بخطوة: دروس قصيرة، كلمات جديدة، ومراجعة ذكية.", "Learn English step by step."))}</p></section>
<section class="kpis mt" style="grid-template-columns:repeat(3,minmax(0,1fr))">
<div class="kpi center"><div class="v center" id="kLvl" style="font-size:1.15rem">—</div><div class="l">{e(t("المستوى", "Level"))}</div></div>
<div class="kpi center"><div class="v center" id="kXp">0</div><div class="l">{e(t("النقاط", "XP"))}</div></div>
<div class="kpi center"><div class="v center" id="kDue">0</div><div class="l">{e(t("للمراجعة اليوم", "Due today"))}</div></div></section>
<div class="tabs mt" role="tablist"><button class="tab on" data-tab="lessons">{e(t("الدروس", "Lessons"))}</button><button class="tab" data-tab="words">{e(t("الكلمات", "Words"))}</button>
<button class="tab" data-tab="review">{e(t("المراجعة", "Review"))}</button><button class="tab" data-tab="me">{e(t("تقدّمي", "Progress"))}</button></div>
<div id="view" class="mt"></div>
<p class="small muted center mt" id="syncNote"></p>
<div class="mt2">{kit.open_bot_btn(site, t("تابع في البوت", "Continue in the bot"), "btn soft block")}</div>
'''
    return await kit.shell(site, body, scripts=("english.js",), data=data)


async def sync(site, body: dict) -> dict:
    if not site.uid:
        return {"saved": False}
    u = _clean(body.get("u"))
    if u is None:
        raise kit.ApiError("bad")
    lite = site.lite()
    if await lite.kv(f"en:u:{site.uid}") is None:
        await lite.kv_set("en:learners", int(await lite.kv("en:learners", 0)) + 1)
    await lite.kv_set(f"en:u:{site.uid}", u)
    return {"saved": True}


async def state(site, body: dict) -> dict:
    """تقدّم العضو المحفوظ — تطلبه الصفحة حين تُفتح داخل تيليجرام بلا رمز في الرابط (زر القائمة)."""
    return {"state": _clean(await site.lite().kv(f"en:u:{site.uid}")) if site.uid else None, "user": bool(site.uid)}


API = {"sync": sync, "state": state}
