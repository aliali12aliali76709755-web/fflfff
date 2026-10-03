"""المصحف على الويب: فهرس السور، قراءة، استماع، تفسير، وموضع قراءة يتزامن مع البوت."""
from __future__ import annotations

from ..templates import quran as q
from . import kit
from .render import e

# عدد آيات كل سورة ونوعها (مكية/مدنية) لعرض الفهرس دون اتصال بالمصدر
AYAHS = [7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52, 99, 128, 111, 110, 98, 135, 112, 78, 118, 64, 77, 227, 93, 88, 69, 60, 34, 30, 73, 54, 45,
         83, 182, 88, 75, 85, 54, 53, 89, 59, 37, 35, 38, 29, 18, 45, 60, 49, 62, 55, 78, 96, 29, 22, 24, 13, 14, 11, 11, 18, 12, 12, 30, 52, 52, 44, 28, 28, 20, 56, 40,
         31, 50, 40, 46, 42, 29, 19, 36, 25, 22, 17, 19, 26, 30, 20, 15, 21, 11, 8, 8, 19, 5, 8, 8, 11, 11, 8, 3, 9, 5, 4, 7, 3, 6, 3, 5, 4, 5, 6]
MADANI = {2, 3, 4, 5, 8, 9, 13, 22, 24, 33, 47, 48, 49, 55, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 76, 98, 99, 110}
assert len(AYAHS) == 114 and sum(AYAHS) == 6236


_tafsir: dict[tuple[int, int], str] = {}


async def _state(site) -> dict:
    lite = site.lite()
    r = await site.tpl.user(lite)
    d = r.data if isinstance(r.data, dict) else {}
    s = min(114, max(1, kit.as_int(d.get("s"), 1)))
    hifz = d.get("hifz") if isinstance(d.get("hifz"), list) else []
    return {"s": s, "off": min(AYAHS[s - 1] - 1, max(0, kit.as_int(d.get("off")))), "hifz": sorted({x for x in hifz if type(x) is int and 1 <= x <= 114}),
            "rec": min(len(q.RECITERS) - 1, max(0, kit.as_int(d.get("rec"))))}


async def render(site):
    t = site.t
    data = {"surahs": [{"n": i + 1, "name": name, "ayahs": AYAHS[i], "madani": (i + 1) in MADANI} for i, name in enumerate(q.SURAHS)],
            "reciters": [{"id": rid, "name": name} for rid, name in q.RECITERS],
            "state": await _state(site) if site.uid else None}
    body = f'''
<div id="home">
<section class="hero"><div class="avatar lg"><span>{site.tpl.emoji}</span><img src="{site.root}/avatar" alt="" onerror="this.remove()"></div>
<h1>{e(site.title)}</h1><p>{e(site.cfg.get("tagline") or "﴿ وَرَتِّلِ الْقُرْآنَ تَرْتِيلًا ﴾")}</p></section>
<button class="card row between mt" id="resume" style="width:100%;text-align:start" hidden></button>
<div class="search mt"><input class="input" id="q" type="search" placeholder="{e(t("ابحث عن سورة بالاسم أو الرقم…", "Search surah by name or number…"))}" autocomplete="off"></div>
<div class="tabs mt" role="tablist"><button class="tab on" data-tab="all">{e(t("كل السور", "All surahs"))}</button><button class="tab" data-tab="hifz">{e(t("❤️ حفظي", "❤️ Memorized"))}</button></div>
<section class="card pad0 mt"><div class="list" id="list"></div></section>
<div class="mt2">{kit.open_bot_btn(site, t("الورد اليومي والبحث في البوت", "Daily reminder and search in the bot"), "btn soft block")}</div>
</div>
<div id="reader" hidden>
<div class="row between mt"><button class="btn sm" id="back">{e(t("→ السور", "← Surahs"))}</button><h2 id="sTitle"></h2><button class="btn sm" id="hz"></button></div>
<section class="card mt"><label class="small">{e(t("القارئ", "Reciter"))}<select id="reciter"></select></label><audio class="mt" id="audio" controls preload="none"></audio></section>
<section class="card mt"><div class="basmala" id="basmala" hidden>بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ</div><div class="mushaf" id="text" dir="rtl" lang="ar"></div>
<div class="empty" id="loading">{e(t("جارٍ تحميل السورة…", "Loading the surah…"))}</div></section>
<div class="row mt"><button class="btn grow" id="prev"></button><button class="btn grow" id="next"></button></div>
</div>
<div class="scrim" id="ayahSheet"><div class="sheet" role="dialog" aria-modal="true"><div class="grab"></div><div id="ayahBody" class="stack"></div></div></div>
'''
    return await kit.shell(site, body, scripts=("quran.js",), data=data, quran=True)


async def surah(site, body: dict) -> dict:
    n = body.get("n")
    if type(n) is not int or not 1 <= n <= 114:
        raise kit.ApiError("bad")
    try:
        return {"ayahs": await q.ayahs(n)}
    except Exception:  # noqa: BLE001
        raise kit.ApiError("source", site.t("تعذّر الاتصال بمصدر المصحف الآن. حاول بعد قليل.", "Couldn't reach the Quran source. Try again shortly."), 502) from None


async def tafsir(site, body: dict) -> dict:
    s, n = body.get("s"), body.get("n")
    if not (type(s) is int and type(n) is int and 1 <= s <= 114 and 1 <= n <= AYAHS[s - 1]):
        raise kit.ApiError("bad")
    if (s, n) in _tafsir:
        return {"text": _tafsir[(s, n)]}
    kit.throttle(("tafsir", kit.client_ip(site.req)), 40, 60)
    try:
        text = await q.tafsir(s, n)
        if len(_tafsir) > 3000:
            _tafsir.clear()
        _tafsir[(s, n)] = text
        return {"text": text}
    except Exception:  # noqa: BLE001
        raise kit.ApiError("source", site.t("تعذّر جلب التفسير الآن.", "Couldn't load the tafsir right now."), 502) from None


async def save(site, body: dict) -> dict:
    """يحفظ موضع القراءة والمحفوظات في سجل العضو نفسه الذي يستخدمه البوت."""
    if not site.uid:
        return {"saved": False}
    lite = site.lite()
    r = await site.tpl.user(lite)
    d = dict(r.data)
    s, off = body.get("s"), body.get("off")
    if type(s) is int and 1 <= s <= 114:
        d["s"] = s
        d["off"] = off if type(off) is int and 0 <= off < AYAHS[s - 1] else 0
    if isinstance(body.get("hifz"), list):
        d["hifz"] = sorted({x for x in body["hifz"][:200] if type(x) is int and 1 <= x <= 114})
    if type(body.get("rec")) is int and 0 <= body["rec"] < len(q.RECITERS):
        d["rec"] = body["rec"]
    await lite.rec_update(r.id, data=d)
    return {"saved": True}


async def state(site, body: dict) -> dict:
    return {"state": await _state(site) if site.uid else None, "user": bool(site.uid)}


API = {"surah": surah, "tafsir": tafsir, "save": save, "state": state}
