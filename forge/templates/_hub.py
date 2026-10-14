"""قالب مدمج: يجمع عدة قوالب تجارية في بوت واحد (أقسام) مع محفظة وطلبات ومتجر مصغّر موحّد.

كل قسم هو قالب كامل (التفاعل، الأرقام، الرقمي، النجوم). العضو يختار القسم فيُوجَّه كل ما يضغطه
إلى قالب ذلك القسم. لوحة المالك تجمع لوحات الأقسام، وأزرارها موسومة بالقسم (t:@<رمز>:...)
حتى تصل للقالب الصحيح مهما كان القسم المفتوح. المحفظة مشتركة بين الأقسام (رصيد واحد في البوت).
"""
from __future__ import annotations

import importlib

from telegram import InlineKeyboardButton

from .. import config, ui
from ..ctx import Ctx
from ..modules import ledger
from ..ui import B, esc, kb
from . import Tpl

# رموز قصيرة للأقسام (حدود callback_data في تيليجرام 64 بايت)
CODES = {"digital": "d", "smm": "m", "sms": "s", "tgstars": "g"}
BY_CODE = {v: k for k, v in CODES.items()}
SEC_LABEL = {
    "digital": ("🎮 الألعاب والاشتراكات", "🎮 Games & subscriptions"),
    "smm": ("🚀 زيادة التفاعل", "🚀 Social boost"),
    "sms": ("📱 أرقام التفعيل", "📱 Activation numbers"),
    "tgstars": ("⭐ نجوم وبريميوم تيليجرام", "⭐ Telegram Stars & Premium"),
}


def _sub(key: str) -> Tpl:
    return importlib.import_module(f"{__package__}.{key}").TPL


class Hub(Tpl):
    parts: tuple[str, ...] = ()
    intro_ar = ""
    intro_en = ""

    def subs(self) -> list[tuple[str, Tpl]]:
        return [(k, _sub(k)) for k in self.parts]

    def _active_key(self, c: Ctx) -> str:
        k = (c.x.user_data or {}).get("hub_sec") if c.x else None
        return k if k in self.parts else self.parts[0]

    def _set_active(self, c: Ctx, key: str) -> None:
        if c.x is not None and c.x.user_data is not None and key in self.parts:
            c.x.user_data["hub_sec"] = key

    # ── واجهة العضو ──
    async def home(self, c: Ctx) -> None:
        from ._commerce import customer_home
        t = c.t
        secs = [B(t(*SEC_LABEL[k]), f"t:sec:{k}") for k, _ in self.subs()]
        await customer_home(c, self.key, browse=secs, intro_key="hub:intro", default_intro=t(self.intro_ar, self.intro_en))

    async def cb(self, c: Ctx, a: list[str]) -> None:
        if not a:
            return await self.home(c)
        act = a[0]
        if act == "sec" and len(a) > 1 and a[1] in self.parts:
            self._set_active(c, a[1])
            return await _sub(a[1]).home(c)
        if act.startswith("@") and act[1:] in BY_CODE and BY_CODE[act[1:]] in self.parts:
            key = BY_CODE[act[1:]]
            self._set_active(c, key)
            return await _sub(key).cb(c, a[1:])
        if act == "orders" and len(a) == 1:
            return await self._orders(c)
        return await _sub(self._active_key(c)).cb(c, a)

    async def _orders(self, c: Ctx) -> None:
        """طلبات العضو من كل الأقسام معاً."""
        from sqlalchemy import select

        from .. import db
        t = c.t
        async with db.Session() as s:
            rows = (await s.execute(select(db.ServiceOrder).where(db.ServiceOrder.bot_id == c.bot_id, db.ServiceOrder.user_id == c.uid)
                                    .order_by(db.ServiceOrder.created.desc()).limit(12))).scalars().all()
        st = {"completed": "✅", "processing": "⚙️", "queued": "⏳", "pending": "⏳", "waiting_sms": "📱", "refunded": "↩️", "canceled": "❌"}
        lines = [f"{st.get(o.status, '•')} <code>#{o.order_id[-8:]}</code> {esc(o.service_name)[:40]} · <b>${o.price_user_usd:.2f}</b>"
                 for o in rows]
        await c.edit(ui.head(t("📦 طلباتي", "📦 My orders")) + ("\n".join(lines) or t("لا توجد طلبات بعد.", "No orders yet.")),
                     kb([[B(t(*SEC_LABEL[k]), f"t:@{CODES[k]}:orders")] for k in self.parts] + [[B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")]]))

    async def msg(self, c: Ctx) -> bool:
        first = self._active_key(c)
        order = [first] + [k for k in self.parts if k != first]
        for k in order:
            if await _sub(k).msg(c):
                return True
        return False

    async def start_param(self, c: Ctx, param: str) -> bool:
        for _k, sub in self.subs():
            if await sub.start_param(c, param):
                return True
        return False

    def setup(self, app) -> None:
        for _k, sub in self.subs():
            sub.setup(app)

    async def checklist(self, c: Ctx) -> list:
        out = []
        for _k, sub in self.subs():
            out += await sub.checklist(c)
        return out

    # ── لوحة المالك: لوحات الأقسام مجمّعة، وأزرار كل قسم موسومة به ──
    @staticmethod
    def _tag(btn, code: str):
        if not isinstance(btn, InlineKeyboardButton) or not (btn.callback_data or "").startswith("t:"):
            return btn
        data = f"t:@{code}:{btn.callback_data[2:]}"
        if len(data.encode()) > 64:
            return btn
        d = btn.to_dict()
        d["callback_data"] = data
        return InlineKeyboardButton.de_json(d, None)

    async def owner(self, c: Ctx) -> tuple[str, list]:
        from ._commerce import owner_panel
        return await owner_panel(c, rcpt_cb=f"t:@{CODES[self.parts[0]]}:adm:rcpts")

    async def owner_legacy(self, c: Ctx) -> tuple[str, list]:
        texts, rows = [], []
        for k, sub in self.subs():
            info, srows = await getattr(sub, "owner_legacy", sub.owner)(c)
            if info:
                texts.append(info)
            rows.append([B(f"── {c.t(*SEC_LABEL[k])} ──", "noop")])
            for r in srows:
                if not r:
                    continue
                r = r if isinstance(r, (list, tuple)) else [r]
                rows.append([self._tag(b, CODES[k]) for b in r if b is not None])
        return "\n\n".join(texts), rows
