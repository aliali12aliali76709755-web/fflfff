"""مُجمّع مواقع التفاعل (SMM Aggregator):
- يسحب كل الخدمات من كل المواقع المربوطة (بروتوكول API v2 القياسي: action=services / balance).
- يصنّف كل خدمة (المنصة + النوع + الجودة + الضمان) ويجمع الخدمات المتشابهة من كل المواقع في منتج واحد.
- سعر المنتج = أرخص موقع دائماً، ومعه قائمة مرتبة بالمواقع البديلة (إذا فشل الأرخص يُحوَّل الطلب للتالي).
- يعيد المقارنة كل 24 ساعة تلقائياً، فتظهر الخدمات الجديدة وتتحدث الأسعار وتختفي الخدمات المحذوفة.
- أسعار المواقع بعملات غير الدولار تُحوَّل للدولار.

التخزين: KV للمنصة (bot_id=0) بالمفتاح "smm:agg" = {"ts", "items", "provs"} + نسخة في الذاكرة للسرعة.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from typing import Any

from .. import config, db

log = logging.getLogger("forge.smm_agg")

KEY = "smm:agg"
SEED_FLAG = "smm:seeded"
REFRESH_SEC = 24 * 3600
FALLBACK_MAX_RATIO = 1.25     # البديل يُستخدم فقط إن كان سعره ≤ 125% من الأرخص (حتى لا تخسر المنصة)
MAX_OFFERS = 6
MAX_VARIANTS = 6              # أقصى عدد منتجات لكل (منصة + نوع) — «ما بدنا نكثر»

_MEM: dict[str, Any] | None = None
_RUNNING: asyncio.Task | None = None

# ── التصنيف ──
PLAT_RX: list[tuple[str, str]] = [
    ("threads", r"\bthreads?\b"),
    ("instagram", r"instagram|\binsta\b|\big\b|reels?\b"),
    ("tiktok", r"tik\s?tok|\btt\b"),
    ("telegram", r"telegram|\btg\b"),
    ("youtube", r"youtube|\byt\b|shorts"),
    ("x", r"twitter|\btweets?\b|\bx\.com\b|^\s*x\s|\[x\]|\(x\)|\bx\s*[-|/]\s"),
    ("facebook", r"facebook|\bfb\b"),
    ("snapchat", r"snap\s?chat"),
    ("spotify", r"spotify"),
    ("twitch", r"twitch"),
    ("discord", r"discord"),
    ("linkedin", r"linked\s?in"),
    ("whatsapp", r"whatsapp"),
    ("kick", r"\bkick\b"),
    ("soundcloud", r"soundcloud"),
    ("pinterest", r"pinterest"),
]

METRIC_RX: list[tuple[str, str]] = [
    ("live", r"live\s*(stream)?\s*(views|viewers)|\blive\b"),
    ("story", r"stor(y|ies)"),
    ("comments", r"comments?"),
    ("reactions", r"reactions?|emoji"),
    ("shares", r"shares?|reposts?|retweets?"),
    ("saves", r"saves?"),
    ("votes", r"votes?|poll"),
    ("followers", r"followers?|subscribers?|\bsubs\b|members?"),
    ("likes", r"likes?|hearts?|favorites?"),
    ("views", r"views?|plays?|streams?|impressions?|watch\s*time"),
]

# خدمات نتجاهلها: تحتاج مدخلات خاصة، أو استهداف دولة معينة، أو اشتراكات تلقائية
SKIP_RX = re.compile(
    r"custom|mention|drip|auto\b|automatic|subscription|package|\bpoll\s*answer|"
    r"\b(usa|us|uk|india|indian|brazil|brazilian|turkey|turkish|russia|russian|indonesia|indonesian|"
    r"korea|korean|japan|japanese|germany|german|france|french|italy|italian|spain|spanish|"
    r"vietnam|thai|thailand|pakistan|bangladesh|nigeria|mexico|philippines|iran|persian|china|chinese)\b",
    re.I)
ARAB_RX = re.compile(r"\barab|عرب|saudi|ksa|egypt|iraq|gulf|khaleej", re.I)
REFILL_NO = re.compile(r"no\s*refill|non[\s-]*refill|no\s*guarantee|without\s*refill|\bnr\b", re.I)
REFILL_YES = re.compile(r"refill|guarant|\br\d{1,3}\b|lifetime|non[\s-]*drop|no[\s-]*drop", re.I)
HQ_RX = re.compile(r"\breal\b|high\s*quality|\bhq\b|premium|active|organic", re.I)
PREMIUM_TG = re.compile(r"premium", re.I)
SUB_RX: list[tuple[str, str]] = [("reels", r"reels?"), ("shorts", r"shorts"), ("video", r"video"), ("post", r"\bposts?\b|photo")]

PLAT_NAMES = {
    "instagram": ("انستغرام", "Instagram", "📸"), "tiktok": ("تيك توك", "TikTok", "🎵"), "telegram": ("تلغرام", "Telegram", "📢"),
    "youtube": ("يوتيوب", "YouTube", "🎬"), "x": ("إكس (تويتر)", "X (Twitter)", "🐦"), "facebook": ("فيسبوك", "Facebook", "👤"),
    "threads": ("ثريدز", "Threads", "🧵"), "snapchat": ("سناب شات", "Snapchat", "👻"), "spotify": ("سبوتيفاي", "Spotify", "🎧"),
    "twitch": ("تويتش", "Twitch", "🎮"), "discord": ("ديسكورد", "Discord", "💬"), "linkedin": ("لينكدإن", "LinkedIn", "💼"),
    "whatsapp": ("واتساب", "WhatsApp", "🟢"), "kick": ("كيك", "Kick", "🟩"), "soundcloud": ("ساوند كلاود", "SoundCloud", "☁️"),
    "pinterest": ("بنترست", "Pinterest", "📌"),
}
METRIC_NAMES = {
    "followers": ("متابعين", "Followers"), "likes": ("إعجابات", "Likes"), "views": ("مشاهدات", "Views"),
    "comments": ("تعليقات", "Comments"), "shares": ("مشاركات", "Shares"), "saves": ("حفظ", "Saves"),
    "reactions": ("تفاعلات ريأكشن", "Reactions"), "votes": ("تصويتات", "Votes"),
    "story": ("مشاهدات ستوري", "Story views"), "live": ("مشاهدات بث مباشر", "Live viewers"),
}
FOLLOW_WORD = {"telegram": ("أعضاء", "Members"), "youtube": ("مشتركين", "Subscribers"), "discord": ("أعضاء", "Members"),
               "twitch": ("متابعين", "Followers")}
VIEW_WORD = {"spotify": ("استماعات", "Plays"), "soundcloud": ("استماعات", "Plays")}
SUB_NAMES = {"reels": ("ريلز", "Reels"), "shorts": ("شورتس", "Shorts"), "video": ("فيديو", "Video"), "post": ("منشورات", "Posts")}


def classify(name: str, category: str = "") -> dict | None:
    """يحوّل اسم خدمة المزود لمفتاح موحّد، أو None إن كانت خدمة لا نبيعها."""
    txt = f"{category} | {name}".lower()
    if SKIP_RX.search(txt):
        return None
    nm0, cat0 = name.lower(), category.lower()
    plat = next((p for p, rx in PLAT_RX if re.search(rx, nm0, re.I)), None) or \
        next((p for p, rx in PLAT_RX if re.search(rx, cat0, re.I)), None)
    if not plat:
        return None
    nm = name.lower()
    metric = next((m for m, rx in METRIC_RX if re.search(rx, nm, re.I)), None) or \
        next((m for m, rx in METRIC_RX if re.search(rx, txt, re.I)), None)
    if not metric:
        return None
    sub = ""
    if metric in ("views", "likes"):
        sub = next((s for s, rx in SUB_RX if re.search(rx, nm, re.I)), "")
        if plat == "youtube" and sub == "video":
            sub = ""
    if plat == "telegram" and metric == "followers" and PREMIUM_TG.search(nm):
        sub = "premium"
        nm = PREMIUM_TG.sub("", nm)
    refill = bool(REFILL_YES.search(nm)) and not REFILL_NO.search(nm)
    hq = bool(HQ_RX.search(nm))
    arab = bool(ARAB_RX.search(txt))
    return {"platform": plat, "metric": metric, "sub": sub, "refill": refill, "hq": hq, "arab": arab}


def group_key(c: dict) -> str:
    return "|".join([c["platform"], c["metric"], c["sub"], "hq" if c["hq"] else "std", "r" if c["refill"] else "nr", "ar" if c["arab"] else ""])


def item_id(gk: str) -> str:
    return "a_" + hashlib.sha1(gk.encode()).hexdigest()[:10]


def _names(c: dict) -> tuple[str, str]:
    pa, pe, _ = PLAT_NAMES[c["platform"]]
    ma, me = METRIC_NAMES[c["metric"]]
    if c["metric"] == "followers" and c["platform"] in FOLLOW_WORD:
        ma, me = FOLLOW_WORD[c["platform"]]
    if c["metric"] == "views" and c["platform"] in VIEW_WORD:
        ma, me = VIEW_WORD[c["platform"]]
    ar, en = f"{ma} {pa}", f"{pe} {me}"
    if c["sub"] == "premium":
        ar, en = ar + " بريميوم", en + " (Premium)"
    elif c["sub"]:
        sa, se = SUB_NAMES[c["sub"]]
        ar, en = f"{ar} ({sa})", f"{en} ({se})"
    if c["arab"]:
        ar, en = ar + " عرب", en + " — Arab"
    if c["hq"]:
        ar, en = ar + " — جودة عالية", en + " — HQ"
    if c["refill"]:
        ar, en = ar + " — مع ضمان", en + " — Refill"
    return ar, en


def _f(v, d=0.0) -> float:
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return d


# ── المزودون ──
async def providers_conf() -> list[dict]:
    p = await db.kv_get(0, "smm:providers", []) or []
    return [x for x in p if isinstance(x, dict) and x.get("on", True) and x.get("api_url") and x.get("api_key")]


def parse_providers_text(text: str) -> list[dict]:
    """يستخرج (الموقع، المفتاح) من أي نص: سطر «الموقع | المفتاح» أو الموقع ثم المفتاح في السطر التالي."""
    out, pend = [], None
    dom_rx = re.compile(r"(?:https?://)?(?:www\.)?([a-z0-9][a-z0-9\-]*(?:\.[a-z0-9\-]+)+)(/[^\s|]*)?", re.I)
    key_rx = re.compile(r"\b([a-f0-9]{24,64})\b", re.I)
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        k = key_rx.search(line)
        d = dom_rx.search(key_rx.sub(" ", line))
        if d:
            host = d.group(1).lower()
            path = d.group(2) or ""
            pend = {"name": host.split(".")[0][:40], "api_url": f"https://{host}{path if path.startswith('/api') else '/api/v2'}"}
        if k and pend:
            pend["api_key"] = k.group(1)
            out.append(pend)
            pend = None
    seen, res = set(), []
    for p in out:
        if p["api_url"] not in seen:
            seen.add(p["api_url"])
            res.append(p)
    return res


async def import_providers(text: str) -> tuple[int, int]:
    """يضيف المواقع للمنصة (أو يحدّث مفتاح الموجود). يعيد (المضاف، المحدّث)."""
    new = parse_providers_text(text)
    provs = await db.kv_get(0, "smm:providers", []) or []
    added = updated = 0
    for p in new:
        cur = next((x for x in provs if x.get("api_url") == p["api_url"]), None)
        if cur:
            if cur.get("api_key") != p["api_key"]:
                cur["api_key"] = p["api_key"]
                updated += 1
        else:
            provs.append({**p, "on": True})
            added += 1
    if added or updated:
        await db.kv_set(0, "smm:providers", provs)
    return added, updated


SMS_URLS = {"hero-sms.com": "https://hero-sms.com/stubs/handler_api.php"}


def split_seed(text: str) -> tuple[str, str]:
    """الملف قسمان: مواقع التفاعل أولاً، وبعد سطر [sms] مواقع الأرقام."""
    parts = re.split(r"^\s*\[sms\]\s*$", text or "", maxsplit=1, flags=re.M | re.I)
    return parts[0], (parts[1] if len(parts) > 1 else "")


async def import_sms_providers(text: str) -> int:
    """مواقع الأرقام (بروتوكول SMS-Activate): «الموقع | المفتاح» أو رابط handler_api كامل."""
    provs = await db.kv_get(0, "sms:providers", []) or []
    n = 0
    for p in parse_providers_text(text):
        host = re.sub(r"^https://([^/]+).*$", r"\1", p["api_url"])
        url = SMS_URLS.get(host) or (p["api_url"] if "handler_api" in p["api_url"] else f"https://{host}/stubs/handler_api.php")
        cur = next((x for x in provs if x.get("api_url") == url), None)
        if cur:
            if cur.get("api_key") != p["api_key"]:
                cur["api_key"] = p["api_key"]
                n += 1
        else:
            provs.append({"name": p["name"], "api_url": url, "api_key": p["api_key"], "on": True})
            n += 1
    if n:
        await db.kv_set(0, "sms:providers", provs)
    return n


async def seed_once() -> int:
    """عند أول تشغيل: يربط المواقع المكتوبة في seed_providers.txt تلقائياً (مرة واحدة لكل قسم)."""
    f = config.ROOT / "seed_providers.txt"
    if not f.is_file() or (os.environ.get("PROVIDERS_MOCK") == "1" and not os.environ.get("SEED_TEST")):
        return 0          # بيئة الاختبار لا تتصل بالمواقع الحقيقية
    smm_txt, sms_txt = split_seed(f.read_text(encoding="utf-8"))
    n = 0
    try:
        if not await db.kv_get(0, SEED_FLAG, False):
            n, _ = await import_providers(smm_txt)
            await db.kv_set(0, SEED_FLAG, True)
            log.info("seed_providers: linked %d SMM panels", n)
        if sms_txt.strip() and not await db.kv_get(0, "sms:seeded", False):
            k = await import_sms_providers(sms_txt)
            await db.kv_set(0, "sms:seeded", True)
            log.info("seed_providers: linked %d SMS providers", k)
            n += k
    except Exception:  # noqa: BLE001
        log.exception("seed_providers failed")
    return n


# ── الذاكرة ──
async def load() -> dict:
    global _MEM
    if _MEM is None:
        d = await db.kv_get(0, KEY, None)
        _MEM = d if isinstance(d, dict) else {"ts": 0, "items": [], "provs": {}}
        _MEM["_by"] = {i["id"]: i for i in _MEM.get("items", [])}
    return _MEM


def items_now() -> list[dict]:
    """منتجات المقارنة الحالية من الذاكرة (فارغة إن لم تُجرَ مقارنة بعد)."""
    return list((_MEM or {}).get("items") or [])


def get_item(iid: str) -> dict | None:
    return ((_MEM or {}).get("_by") or {}).get(iid)


def reset_memory() -> None:
    global _MEM
    _MEM = None


# ── السحب والمقارنة ──
async def _fetch(p: dict) -> tuple[list, str]:
    from .providers.smm import StandardSMMAdapter
    ad = StandardSMMAdapter(p["name"], p["api_url"], p["api_key"])
    ad.timeout = 45
    services = await ad.get_services()
    cur = "USD"
    try:
        bal = await ad._post({"action": "balance"})
        cur = str((bal or {}).get("currency") or "USD").upper().strip()[:8]
    except Exception:  # noqa: BLE001
        pass
    return services, cur


async def refresh() -> dict:
    """يسحب كل المواقع ويبني الكتالوج الموحّد (أرخص سعر لكل منتج + بدائل)."""
    from .currency import fetch_live_rates
    provs = await providers_conf()
    if not provs:
        return {"ok": False, "error": "no_providers"}
    sem = asyncio.Semaphore(6)
    rates: dict[str, float] = {}

    async def one(p):
        async with sem:
            t0 = time.time()
            try:
                svcs, cur = await _fetch(p)
                return p, svcs, cur, "", round(time.time() - t0, 1)
            except Exception as e:  # noqa: BLE001
                return p, [], "USD", str(e)[:160], round(time.time() - t0, 1)

    results = await asyncio.gather(*(one(p) for p in provs))
    if any(cur != "USD" for _, _, cur, _, _ in results):
        try:
            rates = await fetch_live_rates()
        except Exception:  # noqa: BLE001
            rates = {}

    groups: dict[str, dict] = {}
    pstat: dict[str, dict] = {}
    for p, svcs, cur, err, secs in results:
        used = 0
        fx = 1.0
        if cur != "USD":
            r = float(rates.get(cur) or 0)
            if r <= 0:
                err = err or f"عملة غير مدعومة: {cur}"
                svcs = []
            else:
                fx = 1.0 / r
        for s in svcs if isinstance(svcs, list) else []:
            if not isinstance(s, dict):
                continue
            typ = str(s.get("type") or "Default").strip().lower()
            if typ not in ("default", ""):
                continue
            name = str(s.get("name") or "")[:200]
            c = classify(name, str(s.get("category") or ""))
            if not c:
                continue
            rate = round(_f(s.get("rate")) * fx, 6)
            mn, mx = int(_f(s.get("min"), 0)), int(_f(s.get("max"), 0))
            if rate <= 0 or rate > 5000 or mn <= 0 or mx < mn or str(s.get("service", "")) == "":
                continue
            gk = group_key(c)
            g = groups.setdefault(gk, {"c": c, "offers": []})
            g["offers"].append({"p": p["name"], "u": p["api_url"], "sid": str(s["service"])[:32], "rate": rate, "min": mn, "max": mx,
                                "refill": bool(s.get("refill")) or c["refill"], "cancel": bool(s.get("cancel"))})
            used += 1
        pstat[p["name"]] = {"ok": not err, "err": err, "count": used, "cur": cur, "secs": secs}

    items = []
    for gk, g in groups.items():
        offs = sorted(g["offers"], key=lambda o: (o["rate"], -o["max"]))
        # موقع واحد يكفي له عرض واحد (الأرخص لديه) — البدائل من مواقع مختلفة
        uniq, seen = [], set()
        for o in offs:
            if o["u"] in seen:
                continue
            seen.add(o["u"])
            uniq.append(o)
        best = uniq[0]
        c = g["c"]
        ar, en = _names(c)
        items.append({
            "id": item_id(gk), "gk": gk, "platform": c["platform"], "category": c["metric"], "sub": c["sub"],
            "name_ar": ar, "name_en": en, "rate_per_1k": best["rate"], "min": best["min"], "max": best["max"],
            "refill": c["refill"], "hq": c["hq"], "avg_time": "",
            "desc_ar": f"أفضل سعر من بين {len(uniq)} مزود — يتحدث يومياً." if len(uniq) > 1 else "يتحدث السعر يومياً.",
            "desc_en": f"Best price among {len(uniq)} providers — updated daily." if len(uniq) > 1 else "Price updated daily.",
            "offers": uniq[:MAX_OFFERS], "n": len(uniq),
        })
    # تقليل العدد: لكل (منصة + نوع) نحتفظ بأفضل التنويعات (الأكثر توفراً ثم الأرخص)
    by_pm: dict[tuple, list] = {}
    for it in items:
        by_pm.setdefault((it["platform"], it["category"]), []).append(it)
    final = []
    for k, lst in by_pm.items():
        lst.sort(key=lambda i: (-min(i["n"], 3), i["rate_per_1k"]))
        final += lst[:MAX_VARIANTS]
    order = list(PLAT_NAMES)
    morder = list(METRIC_NAMES)
    final.sort(key=lambda i: (order.index(i["platform"]), morder.index(i["category"]), i["rate_per_1k"]))

    old = await load()
    old_ids = {i["id"] for i in old.get("items", [])}
    data = {"ts": time.time(), "items": final, "provs": pstat, "new": len([i for i in final if i["id"] not in old_ids]) if old_ids else 0}
    if final or not old.get("items"):
        await db.kv_set(0, KEY, data)
        global _MEM
        _MEM = dict(data)
        _MEM["_by"] = {i["id"]: i for i in final}
        try:
            from ..web import store_api
            store_api._CAT_CACHE.clear()
        except Exception:  # noqa: BLE001
            pass
    log.info("SMM aggregate: %d products from %d panels", len(final), len([1 for v in pstat.values() if v["ok"]]))
    return {"ok": True, "items": len(final), "provs": pstat}


def running() -> bool:
    return _RUNNING is not None and not _RUNNING.done()


def start_refresh() -> bool:
    """يبدأ المقارنة في الخلفية (لا يحجب البوت)."""
    global _RUNNING
    if running():
        return False

    async def _run():
        try:
            await refresh()
        except Exception:  # noqa: BLE001
            log.exception("SMM aggregate refresh failed")
    _RUNNING = asyncio.get_running_loop().create_task(_run())
    return True


async def maybe_refresh() -> None:
    """من المهام الدورية: كل 24 ساعة."""
    if os.environ.get("PROVIDERS_MOCK") == "1" and not os.environ.get("SMM_AGG_TEST"):
        return
    d = await load()
    if time.time() - float(d.get("ts") or 0) >= REFRESH_SEC and await providers_conf():
        start_refresh()


def status() -> dict:
    d = _MEM or {}
    return {"ts": d.get("ts", 0), "items": len(d.get("items") or []), "provs": d.get("provs") or {}, "running": running(),
            "new": d.get("new", 0)}


def offers_for(iid: str, qty: int, cap: float | None = None) -> list[dict]:
    """البدائل المناسبة للكمية بالترتيب (الأرخص أولاً) وضمن حد الخسارة.
    cap = أقصى تكلفة مقبولة لكل 1000 (سعر المنصة على البائع) — وإلا 125% من الأرخص."""
    it = get_item(iid)
    if not it:
        return []
    cap = max(float(cap or 0), float(it["rate_per_1k"]) * FALLBACK_MAX_RATIO)
    return [o for o in it["offers"] if o["min"] <= qty <= o["max"] and o["rate"] <= cap + 1e-9]


def dumps_status() -> str:
    return json.dumps(status(), ensure_ascii=False)


# ── متابعة حالة الطلبات لدى المواقع ──
_LAST_TRACK = 0.0
TRACK_SEC = 600
DONE = {"completed", "complete", "success"}
CANCEL = {"canceled", "cancelled", "refunded", "fail", "failed", "error"}


async def track_orders(notify=None) -> dict:
    """كل 10 دقائق: يسأل المواقع عن طلبات التفاعل الجارية.
    مكتمل → مكتمل · ملغى → استرجاع كامل تلقائي للزبون والبائع · جزئي → استرجاع قيمة الكمية الناقصة."""
    global _LAST_TRACK
    import datetime as dt

    from sqlalchemy import select

    from . import ledger
    from .providers.smm import StandardSMMAdapter
    _LAST_TRACK = time.time()
    conf = {p["name"]: p for p in await providers_conf()}
    if not conf:
        return {}
    since = db.now() - dt.timedelta(days=30)
    async with db.Session() as s:
        rows = (await s.execute(select(db.ServiceOrder).where(
            db.ServiceOrder.status.in_(["processing", "pending", "queued"]), db.ServiceOrder.provider_order_id != "",
            db.ServiceOrder.provider_name.in_(list(conf)), db.ServiceOrder.created >= since,
        ).order_by(db.ServiceOrder.created).limit(400))).scalars().all()
    by_p: dict[str, list] = {}
    for o in rows:
        by_p.setdefault(o.provider_name, []).append(o)
    stats = {"done": 0, "refund": 0, "partial": 0}

    async def one(pname, orders):
        p = conf[pname]
        ad = StandardSMMAdapter(pname, p["api_url"], p["api_key"])
        for i in range(0, len(orders), 100):
            chunk = orders[i:i + 100]
            try:
                res = await ad._post({"action": "status", "orders": ",".join(o.provider_order_id for o in chunk)})
            except Exception as e:  # noqa: BLE001
                log.warning("track %s: %s", pname, e)
                return
            for o in chunk:
                r = res.get(o.provider_order_id) if isinstance(res, dict) else None
                if not isinstance(r, dict) or r.get("error"):
                    continue
                st = str(r.get("status", "")).strip().lower()
                if st in DONE:
                    async with db.Session() as s:
                        row = await s.get(db.ServiceOrder, o.id)
                        if row and row.status in ("processing", "pending", "queued"):
                            row.status = "completed"
                            await s.commit()
                            stats["done"] += 1
                elif st in CANCEL:
                    ok, _m, _r = await ledger.atomic_dual_refund(o.order_id, reason="ألغاه المزود — استرجاع تلقائي")
                    if ok:
                        stats["refund"] += 1
                        if notify:
                            await notify(o, "refund")
                elif st == "partial":
                    remains = int(_f(r.get("remains"), 0))
                    frac = (remains / o.quantity) if o.quantity else 0
                    ok, _amt = await ledger.partial_dual_refund(o.order_id, frac, reason=f"تنفيذ جزئي: نقص {remains}")
                    if ok:
                        stats["partial"] += 1
                        if notify:
                            await notify(o, "partial")

    await asyncio.gather(*(one(k, v) for k, v in by_p.items()))
    return stats


async def maybe_track(notify=None) -> None:
    if time.time() - _LAST_TRACK >= TRACK_SEC:
        try:
            await track_orders(notify)
        except Exception:  # noqa: BLE001
            log.exception("track_orders failed")
