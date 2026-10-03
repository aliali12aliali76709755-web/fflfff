"""مراقب المحافظ: مراقبة محافظ الكريبتو على TRON و TON و Ethereum/Base/Polygon وإشعار بكل معاملة جديدة."""
import asyncio
import logging
import re

from telegram.error import TelegramError

from .. import db, ui
from .. import plat
from ..ctx import Ctx
from ..ui import B, esc, kb
from . import Tpl
from ._util import get_json

log = logging.getLogger("forge.wallets")
EVM = {"eth": ("Ethereum", "ETH", "https://eth.blockscout.com/api", "https://etherscan.io/tx/"),
       "base": ("Base", "ETH", "https://base.blockscout.com/api", "https://basescan.org/tx/"),
       "polygon": ("Polygon", "POL", "https://polygon.blockscout.com/api", "https://polygonscan.com/tx/")}
NAMES = {"tron": "TRON", "ton": "TON", **{k: v[0] for k, v in EVM.items()}}
MAX_PER_USER = 5


def detect(addr: str) -> list[str]:
    if re.fullmatch(r"T[1-9A-HJ-NP-Za-km-z]{33}", addr):
        return ["tron"]
    if re.fullmatch(r"0x[0-9a-fA-F]{40}", addr):
        return list(EVM)
    if re.fullmatch(r"[EU]Q[A-Za-z0-9_\-]{46}", addr):
        return ["ton"]
    return []


def short(a: str) -> str:
    return f"{a[:6]}…{a[-5:]}" if a and len(a) > 14 else (a or "?")


async def latest(chain: str, addr: str) -> list[dict]:
    """أحدث المعاملات: [{id, dir, amount, sym, peer, url}] الأحدث أولاً."""
    out: list[dict] = []
    if chain == "tron":
        d = await get_json(f"https://api.trongrid.io/v1/accounts/{addr}/transactions/trc20", params={"limit": 8})
        for x in d.get("data", []):
            tok = x.get("token_info") or {}
            amt = int(x.get("value", 0)) / 10 ** int(tok.get("decimals", 6) or 6)
            inc = x.get("to") == addr
            out.append({"id": x["transaction_id"], "ts": x.get("block_timestamp", 0), "dir": "in" if inc else "out", "amount": amt,
                        "sym": tok.get("symbol", "TRC20"), "peer": x.get("from") if inc else x.get("to"), "url": f"https://tronscan.org/#/transaction/{x['transaction_id']}"})
        d = await get_json(f"https://api.trongrid.io/v1/accounts/{addr}/transactions", params={"limit": 8, "only_confirmed": "true"})
        for x in d.get("data", []):
            try:
                c0 = x["raw_data"]["contract"][0]
                if c0["type"] != "TransferContract":
                    continue
                v = c0["parameter"]["value"]
                out.append({"id": x["txID"], "ts": x.get("block_timestamp", 0), "dir": "?", "amount": int(v.get("amount", 0)) / 1e6, "sym": "TRX",
                            "peer": "", "url": f"https://tronscan.org/#/transaction/{x['txID']}"})
            except (KeyError, IndexError):
                continue
        out.sort(key=lambda t: -t["ts"])
    elif chain == "ton":
        d = await get_json("https://toncenter.com/api/v2/getTransactions", params={"address": addr, "limit": 8})
        for x in d.get("result", []):
            im = x.get("in_msg") or {}
            val = int(im.get("value", 0) or 0)
            if val:
                out.append({"id": x["transaction_id"]["hash"], "dir": "in", "amount": val / 1e9, "sym": "TON", "peer": im.get("source", ""),
                            "url": f"https://tonviewer.com/transaction/{x['transaction_id']['hash']}"})
            for om in x.get("out_msgs") or []:
                out.append({"id": x["transaction_id"]["hash"], "dir": "out", "amount": int(om.get("value", 0) or 0) / 1e9, "sym": "TON",
                            "peer": om.get("destination", ""), "url": f"https://tonviewer.com/transaction/{x['transaction_id']['hash']}"})
    else:
        _, sym, api, exp = EVM[chain]
        for action in ("txlist", "tokentx"):
            d = await get_json(api, params={"module": "account", "action": action, "address": addr, "sort": "desc", "page": 1, "offset": 8})
            for x in d.get("result") or []:
                if not isinstance(x, dict):
                    continue
                inc = (x.get("to") or "").lower() == addr.lower()
                dec = int(x.get("tokenDecimal") or 18)
                amt = int(x.get("value") or 0) / 10 ** dec
                if action == "txlist" and not amt:
                    continue
                out.append({"id": x["hash"], "ts": int(x.get("timeStamp") or 0), "dir": "in" if inc else "out", "amount": amt,
                            "sym": x.get("tokenSymbol") or sym, "peer": x.get("from") if inc else x.get("to"), "url": exp + x["hash"]})
        out.sort(key=lambda t: -t.get("ts", 0))
    return out


async def balance(chain: str, addr: str) -> str:
    if chain == "tron":
        d = await get_json(f"https://api.trongrid.io/v1/accounts/{addr}")
        acc = (d.get("data") or [{}])[0]
        parts = [f"{acc.get('balance', 0) / 1e6:,.2f} TRX"]
        for tok in acc.get("trc20", []):
            for contract, val in tok.items():
                if contract == "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t":
                    parts.append(f"{int(val) / 1e6:,.2f} USDT")
        return " · ".join(parts)
    if chain == "ton":
        d = await get_json("https://toncenter.com/api/v2/getAddressBalance", params={"address": addr})
        return f"{int(d.get('result', 0)) / 1e9:,.4f} TON"
    _, sym, api, _ = EVM[chain]
    d = await get_json(api, params={"module": "account", "action": "balance", "address": addr})
    return f"{int(d.get('result', 0)) / 1e18:,.6f} {sym}"


def tx_line(tx: dict, lang: str) -> str:
    arrow = {"in": "🟢 +", "out": "🔴 −"}.get(tx["dir"], "🔁 ")
    peer = f" · {short(tx['peer'])}" if tx.get("peer") else ""
    return f"{arrow}{tx['amount']:,.6g} {esc(tx['sym'])}{peer}\n<a href=\"{tx['url']}\">{'تفاصيل المعاملة' if lang == 'ar' else 'View transaction'}</a>"


class Wallets(Tpl):
    emoji, ar, en = "👛", "مراقب المحافظ", "Wallet watcher"
    d_ar, d_en = "مراقبة محافظ الكريبتو على عدة شبكات (TRON, TON, ETH+)", "Watch crypto wallets on several networks (TRON, TON, ETH+)"
    cats = ("top",)
    guide_ar = ("المستخدم يرسل عنوان محفظة فيتعرف البوت على الشبكة ويبدأ مراقبتها، ويصله إشعار بكل معاملة واردة أو صادرة مع المبلغ ورابط المعاملة، "
                "ويستطيع عرض الرصيد وآخر المعاملات. الحد 5 محافظ لكل مستخدم.\n\n"
                "القراءة فقط: البوت لا يطلب مفاتيح خاصة ولا يستطيع تحريك الأموال. يعتمد على واجهات عامة مجانية (TronGrid، TonCenter، Blockscout) "
                "قد تتأخر أو تحدّ الطلبات عند الضغط، والفحص يتم كل دقيقتين تقريباً.")

    def setup(self, app) -> None:
        if app.job_queue is not None:
            app.job_queue.run_repeating(self._poll, interval=120, first=45, name="wallet_poll")

    async def _poll(self, context) -> None:
        bot_id = context.bot_data["bot_id"]
        if plat.admin_lock(context.bot_data) is not None:      # البوت مغلق من الإدارة: لا مهام مجدولة
            return
        for r in await db.rec_list(bot_id, "wal", limit=400):
            d = r.data
            try:
                txs = await latest(d["chain"], d["addr"])
            except Exception:
                await asyncio.sleep(1)
                continue
            if not txs:
                continue
            last = d.get("last")
            new = []
            for tx in txs:
                if tx["id"] == last:
                    break
                new.append(tx)
            if txs[0]["id"] != last:
                await db.rec_update(bot_id, r.id, data=dict(d, last=txs[0]["id"]))
            if last is None:
                continue  # أول فحص: نحفظ النقطة فقط دون إشعارات قديمة
            for tx in reversed(new[:5]):
                try:
                    await context.bot.send_message(r.user_id, f"🔔 <b>{esc(d.get('label') or short(d['addr']))}</b> · {NAMES[d['chain']]}\n{tx_line(tx, 'ar')}",
                                                   parse_mode="HTML", disable_web_page_preview=True)
                except TelegramError:
                    break
            await asyncio.sleep(0.6)

    async def home(self, c: Ctx) -> None:
        recs = await c.rec_list("wal", user_id=c.uid, limit=MAX_PER_USER)
        rows = [[B(f"👛 {r.data.get('label') or short(r.data['addr'])} · {NAMES[r.data['chain']]}"[:60], f"t:w:{r.id}")] for r in recs]
        await c.edit(ui.head(c.brand) + "\n" + c.t(
            f"📮 أرسل عنوان محفظة (TRON أو TON أو Ethereum) لبدء مراقبتها.\n\nمحافظك: {len(recs)}/{MAX_PER_USER}",
            f"📮 Send a wallet address (TRON, TON or Ethereum) to start watching it.\n\nYour wallets: {len(recs)}/{MAX_PER_USER}"), kb(rows + [c.tail()]))

    async def owner(self, c: Ctx):
        n = await c.rec_count("wal")
        return c.t(f"👛 محافظ تحت المراقبة: {n}", f"👛 Wallets being watched: {n}"), []

    async def cb(self, c: Ctx, a: list[str]) -> None:
        act, t = a[0], c.t
        if act == "ch":
            addr = c.x.user_data.get("wal_addr")
            if addr and a[1] in NAMES:
                await self.add(c, a[1], addr)
            return
        if act not in ("w", "bal", "tx", "rm", "lbl"):
            return
        r = await c.rec_get(int(a[1]))
        if r is None or r.kind != "wal" or r.user_id != c.uid:
            await self.home(c)
            return
        d = r.data
        head = f"👛 <b>{esc(d.get('label') or short(d['addr']))}</b> · {NAMES[d['chain']]}\n<code>{esc(d['addr'])}</code>"
        menu = kb([[B(t("💰 الرصيد", "💰 Balance"), f"t:bal:{r.id}"), B(t("🧾 آخر المعاملات", "🧾 Recent txs"), f"t:tx:{r.id}")],
                   [B(t("✏️ تسمية", "✏️ Label"), f"t:lbl:{r.id}"), B(t("🗑 إيقاف المراقبة", "🗑 Stop watching"), f"t:rm:{r.id}")], c.home_row()])
        try:
            if act == "w":
                await c.edit(head, menu)
            elif act == "bal":
                await c.edit(head + f"\n\n💰 {esc(await balance(d['chain'], d['addr']))}", menu)
            elif act == "tx":
                txs = await latest(d["chain"], d["addr"])
                await c.edit(head + "\n\n" + ("\n\n".join(tx_line(x, c.lang) for x in txs[:6]) or t("لا توجد معاملات.", "No transactions.")), menu)
            elif act == "rm":
                await c.rec_del(r.id)
                await self.home(c)
            elif act == "lbl":
                c.set_state("wal_lbl", rid=r.id)
                await c.send(t("✏️ أرسل اسماً لهذه المحفظة.", "✏️ Send a label for this wallet."))
        except TelegramError:
            raise
        except Exception:
            await c.answer(t("⚠️ تعذّر جلب البيانات من الشبكة الآن.", "⚠️ Couldn't fetch data from the network right now."), True)

    async def add(self, c: Ctx, chain: str, addr: str) -> None:
        if await c.rec_count("wal", user_id=c.uid) >= MAX_PER_USER:
            await c.send(c.t(f"⚠️ الحد الأقصى {MAX_PER_USER} محافظ. احذف واحدة أولاً.", f"⚠️ Limit is {MAX_PER_USER} wallets. Remove one first."))
            return
        last = None
        try:
            txs = await latest(chain, addr)
            last = txs[0]["id"] if txs else ""
        except Exception:
            pass
        rid = await c.rec_add("wal", {"chain": chain, "addr": addr, "label": "", "last": last})
        c.x.user_data.pop("wal_addr", None)
        await c.send(c.t(f"✅ بدأت مراقبة المحفظة على {NAMES[chain]}. سيصلك إشعار بكل معاملة جديدة.", f"✅ Now watching on {NAMES[chain]}. You'll be notified of every new transaction."),
                     kb([[B(c.t("👛 فتح المحفظة", "👛 Open wallet"), f"t:w:{rid}")], c.home_row()]))

    async def msg(self, c: Ctx) -> bool:
        st = c.st
        if st and st["k"] == "wal_lbl":
            r = await c.rec_get(st["rid"])
            c.clear_state()
            if r is not None and r.user_id == c.uid:
                await c.rec_update(r.id, data=dict(r.data, label=c.text[:30]))
            await self.home(c)
            return True
        addr = c.text.strip()
        chains = detect(addr)
        if not chains:
            await c.send(c.t("⚠️ لم أتعرف على العنوان. أرسل عنوان TRON (يبدأ بـ T)، أو Ethereum (يبدأ بـ 0x)، أو TON (يبدأ بـ EQ/UQ).",
                             "⚠️ Unrecognized address. Send a TRON (T…), Ethereum (0x…) or TON (EQ/UQ…) address."))
            return True
        if len(chains) == 1:
            await self.add(c, chains[0], addr)
        else:
            c.x.user_data["wal_addr"] = addr
            await c.send(c.t("اختر الشبكة:", "Pick the network:"), kb([[B(NAMES[k], f"t:ch:{k}") for k in chains]]))
        return True


TPL = Wallets()
