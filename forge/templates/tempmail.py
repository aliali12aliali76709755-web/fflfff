"""بريد مؤقت: عناوين بريد مؤقتة عبر خدمة mail.tm العامة."""
import re
import secrets

import httpx

from .. import ui
from ..ctx import Ctx
from ..ui import B, esc, kb
from . import Tpl
from ._util import UA, bump

API = "https://api.mail.tm"


async def _api(method: str, path: str, token: str = "", **kw):
    headers = dict(UA, Accept="application/json")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with httpx.AsyncClient(timeout=20, headers=headers) as cl:
        r = await cl.request(method, API + path, **kw)
        r.raise_for_status()
        return r.json() if r.content else {}


async def new_account() -> dict:
    doms = await _api("GET", "/domains")
    doms = doms.get("hydra:member", doms) if isinstance(doms, dict) else doms
    domain = doms[0]["domain"]
    addr, pwd = f"{secrets.token_hex(5)}@{domain}", secrets.token_urlsafe(12)
    await _api("POST", "/accounts", json={"address": addr, "password": pwd})
    tok = await _api("POST", "/token", json={"address": addr, "password": pwd})
    return {"addr": addr, "pwd": pwd, "token": tok["token"]}


class TempMail(Tpl):
    emoji, ar, en = "📧", "بريد مؤقت", "Temp mail"
    d_ar, d_en = "قم بإنشاء عناوين بريد إلكتروني مؤقتة بسرعة.", "Create temporary email addresses quickly."
    guide_ar = ("كل مستخدم يحصل على عنوان بريد مؤقت يستقبل الرسائل (رموز التفعيل وغيرها) ويقرؤها من داخل البوت، ويستطيع استبداله بعنوان جديد.\n\n"
                "القالب يعتمد على خدمة mail.tm العامة والمجانية، لذا يعمل ما دامت الخدمة متاحة، وبعض المواقع ترفض عناوينها.")

    async def box(self, c: Ctx) -> dict | None:
        return await c.kv(f"tm:{c.uid}")

    def kb_main(self, c: Ctx):
        return kb([[B(c.t("📥 صندوق الوارد", "📥 Inbox"), "t:inbox")], [B(c.t("♻️ عنوان جديد", "♻️ New address"), "t:new")], c.tail()])

    async def home(self, c: Ctx) -> None:
        b = await self.box(c)
        if b is None:
            await c.edit(ui.head(c.brand) + "\n" + c.t("احصل على بريد مؤقت لاستقبال رموز التفعيل دون كشف بريدك الحقيقي.",
                                                                 "Get a temporary mailbox to receive codes without exposing your real email."),
                         kb([[B(c.t("✨ إنشاء بريد مؤقت", "✨ Create temp mail"), "t:new", style="success")], c.tail()]))
            return
        await c.edit(ui.head(c.brand) + "\n" + c.t(f"📧 عنوانك الحالي:\n<code>{esc(b['addr'])}</code>\n\nاضغط العنوان لنسخه، ثم افتح «صندوق الوارد» لقراءة الرسائل.",
                                                             f"📧 Your address:\n<code>{esc(b['addr'])}</code>\n\nTap to copy, then open the inbox to read messages."),
                     self.kb_main(c))

    async def owner(self, c: Ctx):
        n = await c.kv("tm:count", 0)
        return c.t(f"📧 عناوين أُنشئت: {n}", f"📧 Addresses created: {n}"), []

    async def cb(self, c: Ctx, a: list[str]) -> None:
        act, t = a[0], c.t
        try:
            if act == "new":
                b = await new_account()
                await c.kv_set(f"tm:{c.uid}", b)
                await bump(c, "tm:count")
                await self.home(c)
                return
            b = await self.box(c)
            if b is None:
                await self.home(c)
                return
            if act == "inbox":
                data = await _api("GET", "/messages", b["token"])
                msgs = data.get("hydra:member", data) if isinstance(data, dict) else data
                rows = [[B(f"✉️ {(m.get('subject') or '—')[:40]}", f"t:rd:{m['id']}")] for m in msgs[:10]]
                await c.edit(ui.head(t("📥 صندوق الوارد", "📥 Inbox")) + f"\n<code>{esc(b['addr'])}</code>\n\n" + (
                    t(f"الرسائل: {len(msgs)}", f"Messages: {len(msgs)}") if msgs else t("لا توجد رسائل بعد. اضغط تحديث بعد قليل.", "No messages yet. Refresh in a moment.")),
                    kb(rows + [[B(t("🔄 تحديث", "🔄 Refresh"), "t:inbox")], c.home_row()]))
            elif act == "rd":
                m = await _api("GET", f"/messages/{a[1]}", b["token"])
                body = m.get("text") or re.sub(r"<[^>]+>", " ", " ".join(m.get("html") or []))
                frm = (m.get("from") or {}).get("address", "")
                await c.edit(f"✉️ <b>{esc(m.get('subject') or '—')}</b>\n👤 {esc(frm)}\n{ui.LINE}\n{esc(body.strip()[:3300])}",
                             kb([[B(t("⬅️ صندوق الوارد", "⬅️ Inbox"), "t:inbox")]]))
        except Exception:
            await c.answer(t("⚠️ خدمة البريد المؤقت غير متاحة الآن. حاول بعد قليل.", "⚠️ The temp mail service is unavailable. Try again shortly."), True)

    async def msg(self, c: Ctx) -> bool:
        await self.home(c)
        return True


TPL = TempMail()
