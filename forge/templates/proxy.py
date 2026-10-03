"""بروكسي تيليجرام: بروكسيات MTProto مع اختيار الدولة والاتصال بضغطة واحدة."""
import random
import re
import time

from .. import ui
from ..ctx import Ctx
from ..ui import B, esc, kb
from . import Tpl
from ._util import bump, get_json

SOURCES = ["https://mtpro.xyz/api/?type=mtproto",
           "https://raw.githubusercontent.com/hookzof/socks5_list/master/tg/mtproto.json"]
_cache: dict = {"at": 0.0, "list": []}
LINK_RE = re.compile(r"server=([^&\s]+)&port=(\d+)&secret=([A-Za-z0-9_\-=%+/]+)")


def flag(cc: str) -> str:
    cc = (cc or "").upper()
    return "".join(chr(0x1F1E6 + ord(ch) - 65) for ch in cc) if len(cc) == 2 and cc.isalpha() else "🌐"


async def fetch() -> list[dict]:
    """قائمة البروكسيات العامة (تُخزَّن 10 دقائق). يجرّب أكثر من مصدر."""
    if time.time() - _cache["at"] < 600 and _cache["list"]:
        return _cache["list"]
    for src in SOURCES:
        try:
            data = await get_json(src, timeout=15)
            out = []
            for p in data if isinstance(data, list) else []:
                host, port, secret = p.get("host") or p.get("server"), p.get("port"), p.get("secret")
                if host and port and secret:
                    out.append({"h": str(host), "p": int(port), "s": str(secret), "c": str(p.get("country") or "").upper()[:2]})
            if out:
                _cache.update(at=time.time(), list=out)
                break
        except Exception:
            continue
    return _cache["list"]


def url(p: dict) -> str:
    return f"https://t.me/proxy?server={p['h']}&port={p['p']}&secret={p['s']}"


class Proxy(Tpl):
    emoji, ar, en = "⚡", "بروكسي تيليجرام", "Telegram proxy"
    d_ar, d_en = "احصل على بروكسيات تيليجرام واتصل بها بسهولة.", "Get Telegram proxies and connect easily."
    guide_ar = ("البوت يعرض بروكسيات MTProto مجانية مصنفة حسب الدولة، والمستخدم يتصل بضغطة زر.\n\n"
                "• القائمة العامة تُجلب تلقائياً من مصدر مفتوح وتتجدد كل 10 دقائق، وجودتها ليست مضمونة.\n"
                "• من «➕ إضافة بروكسي» تضيف بروكسياتك الخاصة (أرسل رابط https://t.me/proxy?server=…)، وتظهر للمستخدمين أولاً بعلامة ⭐.")

    async def mine(self, c: Ctx) -> list[dict]:
        return await c.kv("proxy:own", [])

    async def home(self, c: Ctx) -> None:
        await c.edit(ui.head(c.brand) + "\n" + c.t("اختر طريقة الحصول على البروكسي، ثم اضغط «اتصال» ليُضاف إلى تيليجرام مباشرة.",
                                                             "Choose how to get a proxy, then tap “Connect” to add it to Telegram."),
                     kb([[B(c.t("⚡ بروكسي سريع", "⚡ Quick proxy"), "t:rnd", style="success")],
                         [B(c.t("🌍 اختيار الدولة", "🌍 Pick a country"), "t:cc")], c.tail()]))

    async def owner(self, c: Ctx):
        own, n = await self.mine(c), await c.kv("proxy:count", 0)
        return (c.t(f"⭐ بروكسياتك الخاصة: {len(own)}\n⚡ بروكسيات وُزّعت: {n}", f"⭐ Your own proxies: {len(own)}\n⚡ Proxies served: {n}"),
                [[B(c.t("➕ إضافة بروكسي", "➕ Add proxy"), "t:add"), B(c.t("🗑 حذف بروكسياتي", "🗑 Clear mine"), "t:clr")]])

    async def give(self, c: Ctx, pool: list[dict], title: str) -> None:
        if not pool:
            await c.edit(c.t("⚠️ لا توجد بروكسيات متاحة الآن. حاول بعد قليل.", "⚠️ No proxies available right now. Try again shortly."), kb([c.home_row()]))
            return
        picks = random.sample(pool, min(4, len(pool)))
        await bump(c, "proxy:count", len(picks))
        rows = [[B(f"{'⭐' if p.get('own') else flag(p.get('c', ''))} {c.t('اتصال', 'Connect')} · {p['h'][:22]}", url=url(p))] for p in picks]
        rows.append([B(c.t("🔄 غيرها", "🔄 More"), c.q.data if c.q else "t:rnd")])
        rows.append(c.home_row())
        await c.edit(ui.head(title) + "\n" + c.t("اضغط أي زر للاتصال. إن لم يعمل أحدها جرّب غيره.", "Tap any button to connect. If one fails, try another."), kb(rows))

    async def cb(self, c: Ctx, a: list[str]) -> None:
        act, t = a[0], c.t
        own = [dict(p, own=True) for p in await self.mine(c)]
        if act == "rnd":
            pub = await fetch()
            await self.give(c, own + random.sample(pub, min(30, len(pub))), t("⚡ بروكسي سريع", "⚡ Quick proxy"))
        elif act == "cc":
            pub = await fetch()
            counts: dict[str, int] = {}
            for p in pub:
                if p["c"]:
                    counts[p["c"]] = counts.get(p["c"], 0) + 1
            top = sorted(counts.items(), key=lambda x: -x[1])[:24]
            await c.edit(ui.head(t("🌍 اختر الدولة", "🌍 Pick a country")) + ("" if top else "\n" + t("لا توجد بيانات الآن.", "No data right now.")),
                         kb(ui.grid([B(f"{flag(k)} {k} ({v})", f"t:c:{k}") for k, v in top], 3) + [c.home_row()]))
        elif act == "c":
            await self.give(c, [p for p in await fetch() if p["c"] == a[1]], f"{flag(a[1])} {a[1]}")
        elif not c.is_owner:
            return
        elif act == "add":
            c.set_state("proxy_add")
            await c.edit(t("➕ أرسل رابط البروكسي:\n<code>https://t.me/proxy?server=1.2.3.4&port=443&secret=…</code>\n\n/cancel للإلغاء",
                           "➕ Send the proxy link:\n<code>https://t.me/proxy?server=1.2.3.4&port=443&secret=…</code>\n\n/cancel to abort"),
                         kb([[B(t("❌ إلغاء", "❌ Cancel"), "o:home")]]))
        elif act == "clr":
            await c.kv_set("proxy:own", [])
            await c.answer(t("تم الحذف", "Cleared"), True)

    async def msg(self, c: Ctx) -> bool:
        st = c.st
        if st and st["k"] == "proxy_add" and c.is_owner:
            found = LINK_RE.findall(c.text)
            if not found:
                await c.send(c.t("⚠️ رابط غير صالح.", "⚠️ Invalid link."))
                return True
            own = await self.mine(c)
            own += [{"h": h, "p": int(p), "s": s, "c": ""} for h, p, s in found]
            await c.kv_set("proxy:own", own[-50:])
            c.clear_state()
            await c.send(c.t(f"✅ أُضيف {len(found)} بروكسي.", f"✅ Added {len(found)}."), kb([c.home_row()]))
            return True
        await self.home(c)
        return True


TPL = Proxy()
