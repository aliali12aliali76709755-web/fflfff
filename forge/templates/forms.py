"""نماذج واستبيانات: المالك يكتب الأسئلة والمستخدمون يجيبون عنها بالترتيب."""
import csv
import io

from .. import ui
from ..ctx import Ctx
from ..ui import B, esc, kb
from . import Items, Tpl


class Forms(Tpl):
    emoji, ar, en = "📋", "نماذج واستبيانات", "Forms & surveys"
    d_ar, d_en = "اجمع إجابات المستخدمين بنماذج واضحة", "Collect users' answers with clear forms"
    cats = ("biz",)
    guide_ar = ("1. اضغط «➕ إضافة سؤال» وأرسل نص السؤال. للاختيار من متعدد اكتب الخيارات بعد علامة | مفصولة بفاصلة:\n"
                "<code>ما مدينتك؟ | الرقة, حلب, دمشق</code>\n2. المستخدم يضغط «ابدأ» ويجيب سؤالاً سؤالاً.\n"
                "3. كل إجابة مكتملة تصلك كإشعار، ومن «📊 الإجابات» تعرضها أو تصدّرها كملف CSV يفتح في Excel.")

    def __init__(self) -> None:
        self.items = Items("forms", fields=("name", "opts"), ar="سؤال", en="question",
                           fmt_ar="نص السؤال | خيار1, خيار2 (الخيارات اختيارية)", fmt_en="Question text | option1, option2 (options optional)",
                           sample=[{"name": "ما اسمك الكامل؟", "opts": ""}, {"name": "ما رأيك بخدمتنا؟", "opts": "ممتازة, جيدة, تحتاج تحسين"}])

    async def home(self, c: Ctx) -> None:
        qs = await self.items.all(c)
        intro = await c.kv("forms:intro") or c.t(f"📋 نموذج من {len(qs)} أسئلة. اضغط «ابدأ» للإجابة.", f"📋 A form with {len(qs)} questions. Tap “Start” to answer.")
        await c.edit(ui.head(c.brand) + "\n" + intro, kb([[B(c.t("▶️ ابدأ", "▶️ Start"), "t:go", style="success")], c.tail()]))

    async def owner(self, c: Ctx):
        n, q = await c.rec_count("resp"), len(await self.items.all(c))
        return (c.t(f"❓ الأسئلة: {q}\n📝 الإجابات المستلمة: {n}", f"❓ Questions: {q}\n📝 Responses: {n}"),
                [[B(c.t("➕ إضافة سؤال", "➕ Add question"), "t:ia:forms"), B(c.t("📋 الأسئلة", "📋 Questions"), "t:il:forms")],
                 [B(c.t(f"📊 الإجابات ({n})", f"📊 Responses ({n})"), "t:resp"), B(c.t("📤 تصدير CSV", "📤 Export CSV"), "t:csv")],
                 [B(c.t("✏️ نص مقدمة النموذج", "✏️ Form intro text"), "t:intro")]])

    async def ask(self, c: Ctx, i: int, answers: list) -> None:
        qs = await self.items.all(c)
        if i >= len(qs):
            c.clear_state()
            await c.rec_add("resp", {"name": c.user.full_name, "a": [{"q": q["name"], "v": v} for q, v in zip(qs, answers)]})
            await c.send(c.t("✅ شكراً لك، تم استلام إجاباتك.", "✅ Thank you, your answers were received."), kb([c.home_row()]))
            body = "\n".join(f"• <b>{esc(q['name'])}</b>\n  {esc(v)}" for q, v in zip(qs, answers))
            await c.notify_owner(c.t(f"🔔 <b>إجابة جديدة</b> من {c.name} (<code>{c.uid}</code>)\n\n{body}",
                                     f"🔔 <b>New response</b> from {c.name} (<code>{c.uid}</code>)\n\n{body}"))
            return
        c.set_state("form", i=i, a=answers)
        opts = [o.strip() for o in (qs[i].get("opts") or "").split(",") if o.strip()]
        rows = ui.grid([B(o[:30], f"t:opt:{n}") for n, o in enumerate(opts)], 2)
        await c.send(f"<b>{i + 1}/{len(qs)}</b> — {esc(qs[i]['name'])}" + ("" if opts else c.t("\n\n✍️ اكتب إجابتك.", "\n\n✍️ Type your answer.")),
                     kb(rows) if rows else None)

    async def cb(self, c: Ctx, a: list[str]) -> None:
        if await self.items.handle_cb(c, a):
            return
        act = a[0]
        if act == "go":
            if not await self.items.all(c):
                await c.answer(c.t("النموذج بلا أسئلة بعد.", "The form has no questions yet."), True)
                return
            await self.ask(c, 0, [])
        elif act == "opt":
            st = c.st
            if not st or st["k"] != "form":
                return
            qs = await self.items.all(c)
            opts = [o.strip() for o in (qs[st["i"]].get("opts") or "").split(",") if o.strip()]
            if int(a[1]) < len(opts):
                await self.ask(c, st["i"] + 1, st["a"] + [opts[int(a[1])]])
        elif not c.is_owner:
            return
        elif act == "resp":
            recs = await c.rec_list("resp", limit=8)
            text = "\n\n".join(f"👤 <b>{esc(r.data['name'])}</b> · {r.created:%m-%d %H:%M}\n" + "\n".join(
                f"• {esc(x['q'])}: {esc(x['v'])}" for x in r.data["a"]) for r in recs) or c.t("لا توجد إجابات بعد.", "No responses yet.")
            await c.edit(ui.head(c.t("📊 آخر الإجابات", "📊 Latest responses")) + "\n" + text[:3600],
                         kb([[B(c.t("📤 تصدير CSV", "📤 Export CSV"), "t:csv")], [B(c.t("🎛 غرفة التحكم", "🎛 Control room"), "o:home")]]))
        elif act == "csv":
            recs = await c.rec_list("resp", limit=5000, newest=False)
            if not recs:
                await c.answer(c.t("لا توجد إجابات.", "No responses."), True)
                return
            heads: list[str] = []
            for r in recs:
                for x in r.data["a"]:
                    if x["q"] not in heads:
                        heads.append(x["q"])
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["id", "user_id", "name", "date", *heads])
            for r in recs:
                ans = {x["q"]: x["v"] for x in r.data["a"]}
                w.writerow([r.id, r.user_id, r.data["name"], r.created.strftime("%Y-%m-%d %H:%M"), *[ans.get(h, "") for h in heads]])
            await c.doc(io.BytesIO(("﻿" + buf.getvalue()).encode("utf-8")), filename="responses.csv")
        elif act == "intro":
            c.set_state("form_intro")
            await c.edit(c.t("✍️ أرسل نص مقدمة النموذج.\n\n/cancel للإلغاء", "✍️ Send the form intro text.\n\n/cancel to abort"),
                         kb([[B(c.t("❌ إلغاء", "❌ Cancel"), "o:home")]]))

    async def msg(self, c: Ctx) -> bool:
        if c.is_owner and await self.items.handle_msg(c):
            return True
        st = c.st
        if st and st["k"] == "form_intro" and c.is_owner:
            await c.kv_set("forms:intro", c.msg.text_html or "")
            c.clear_state()
            await c.send(c.t("✅ تم الحفظ.", "✅ Saved."), kb([c.home_row()]))
            return True
        if st and st["k"] == "form":
            await self.ask(c, st["i"] + 1, st["a"] + [c.text[:500] or "—"])
            return True
        return False


TPL = Forms()
