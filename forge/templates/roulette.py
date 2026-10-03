"""لعبة روليت: سحوبات عامة برابط مشاركة، وروليت سريع من قائمة أسماء."""
import random

from urllib.parse import quote

from telegram.error import TelegramError

from .. import ui
from ..ctx import Ctx
from ..ui import B, esc, kb
from . import Tpl
from ._util import bump


class Roulette(Tpl):
    emoji, ar, en = "🎰", "لعبة روليت", "Roulette"
    d_ar, d_en = "سحوبات عامة وروليت سريع ومسابقات آمنة", "Public giveaways, quick roulette and safe contests"
    cats = ("fun",)
    guide_ar = ("<b>سحب عام:</b> أي مستخدم ينشئ سحباً بعنوان وعدد فائزين، ويشارك رابطه (أو ينشره في قناته). كل شخص يدخل مرة واحدة فقط، "
                "ومنشئ السحب يضغط «اسحب الآن» ليختار البوت الفائزين عشوائياً ويبلغ الجميع.\n\n"
                "<b>روليت سريع:</b> أرسل قائمة أسماء (كل اسم في سطر) والبوت يختار واحداً.\n\n"
                "لفرض الاشتراك في قناتك قبل المشاركة فعّل «الاشتراك الإجباري» من إعدادات البوت.")

    async def home(self, c: Ctx) -> None:
        t = c.t
        await c.edit(ui.head(c.brand) + "\n" + t("أنشئ سحباً وشارك رابطه، أو جرّب الروليت السريع.", "Create a giveaway and share its link, or try the quick roulette."),
                     kb([[B(t("🎁 سحب جديد", "🎁 New giveaway"), "t:new", style="success")], [B(t("🎲 روليت سريع", "🎲 Quick roulette"), "t:quick")],
                         [B(t("📂 سحوباتي", "📂 My giveaways"), "t:mine")], c.tail()]))

    async def owner(self, c: Ctx):
        n, o = await c.kv("rl:count", 0), await c.rec_count("gw", status="open")
        return c.t(f"🎁 سحوبات أُنشئت: {n}\n🟢 مفتوحة الآن: {o}", f"🎁 Giveaways created: {n}\n🟢 Open now: {o}"), []

    def card(self, c: Ctx, r) -> str:
        d = r.data
        st = c.t("🟢 مفتوح", "🟢 Open") if r.status == "open" else c.t("🏁 انتهى", "🏁 Finished")
        text = (f"🎁 <b>{esc(d['title'])}</b>\n{st}\n" + c.t(f"🏆 عدد الفائزين: {d['n']}\n👥 المشاركون: {len(d['parts'])}",
                                                           f"🏆 Winners: {d['n']}\n👥 Participants: {len(d['parts'])}"))
        if d.get("winners"):
            text += "\n\n" + c.t("🎉 الفائزون:\n", "🎉 Winners:\n") + "\n".join(f"• {esc(w['name'])}" for w in d["winners"])
        return text

    def manage_kb(self, c: Ctx, r):
        link = c.link(f"gw_{r.id}")
        rows = []
        if r.status == "open":
            rows += [[B(c.t("🎉 اسحب الآن", "🎉 Draw now"), f"t:draw:{r.id}", style="success")],
                     [B(c.t("📤 مشاركة الرابط", "📤 Share link"), url=f"https://t.me/share/url?url={quote(link)}"), B(c.t("📢 نشر في قناة", "📢 Post to channel"), f"t:pub:{r.id}")]]
        rows += [[B(c.t("🔄 تحديث", "🔄 Refresh"), f"t:v:{r.id}")], c.home_row()]
        return kb(rows)

    async def start_param(self, c: Ctx, param: str) -> bool:
        if not (param.startswith("gw_") and param[3:].isdigit()):
            return False
        r = await c.rec_get(int(param[3:]))
        if r is None or r.kind != "gw":
            return False
        if r.status == "open" and all(p["id"] != c.uid for p in r.data["parts"]):
            d = dict(r.data)
            d["parts"] = list(d["parts"]) + [{"id": c.uid, "name": c.user.full_name}]
            await c.rec_update(r.id, data=d)
            r.data = d
            note = c.t("✅ تم تسجيلك في السحب. بالتوفيق!", "✅ You're in. Good luck!")
        elif r.status != "open":
            note = c.t("🏁 انتهى هذا السحب.", "🏁 This giveaway has ended.")
        else:
            note = c.t("أنت مسجّل مسبقاً في هذا السحب.", "You're already in.")
        await c.send(note + "\n\n" + self.card(c, r), kb([[B(c.t("🎁 أنشئ سحبك", "🎁 Create your own"), "t:new")]]))
        return True

    async def cb(self, c: Ctx, a: list[str]) -> None:
        act, t = a[0], c.t
        if act == "new":
            c.set_state("gw_title")
            await c.edit(t("🎁 أرسل عنوان السحب (مثلاً: سحب على اشتراك شهر).\n\n/cancel للإلغاء", "🎁 Send the giveaway title.\n\n/cancel to abort"), kb([c.home_row()]))
        elif act == "quick":
            c.set_state("rl_quick")
            await c.edit(t("🎲 أرسل الأسماء، كل اسم في سطر. لاختيار أكثر من فائز اكتب العدد في السطر الأول (مثلاً 3).",
                           "🎲 Send the names, one per line. For several winners put the number on the first line (e.g. 3)."), kb([c.home_row()]))
        elif act == "mine":
            recs = await c.rec_list("gw", user_id=c.uid, limit=10)
            rows = [[B(f"{'🟢' if r.status == 'open' else '🏁'} {r.data['title']}"[:50], f"t:v:{r.id}")] for r in recs]
            await c.edit(ui.head(t("📂 سحوباتي", "📂 My giveaways")) + ("" if recs else "\n" + t("لا توجد سحوبات.", "No giveaways.")), kb(rows + [c.home_row()]))
        elif act in ("v", "draw", "pub"):
            r = await c.rec_get(int(a[1]))
            if r is None or r.kind != "gw" or r.user_id != c.uid:
                await c.answer(t("غير متاح", "Unavailable"), True)
                return
            if act == "pub":
                c.set_state("gw_pub", rid=r.id)
                await c.send(t("📢 أرسل معرّف القناة (@channel). يجب أن أكون مشرفاً فيها وأنت كذلك.", "📢 Send the channel @username. Both of us must be admins there."))
                return
            if act == "draw" and r.status == "open":
                parts = r.data["parts"]
                if not parts:
                    await c.answer(t("لا يوجد مشاركون بعد.", "No participants yet."), True)
                    return
                winners = random.SystemRandom().sample(parts, min(int(r.data["n"]), len(parts)))
                d = dict(r.data, winners=winners)
                await c.rec_update(r.id, data=d, status="done")
                r.data, r.status = d, "done"
                names = "\n".join(f"• {esc(w['name'])}" for w in winners)
                for p in parts[:3000]:
                    won = any(w["id"] == p["id"] for w in winners)
                    try:
                        await c.send((t("🎉 <b>مبروك! فزت في السحب</b>", "🎉 <b>Congratulations! You won</b>") if won else t("🏁 <b>انتهى السحب</b>", "🏁 <b>Giveaway finished</b>"))
                                     + f" «{esc(d['title'])}»\n\n" + t("الفائزون:\n", "Winners:\n") + names, chat_id=p["id"])
                    except TelegramError:
                        pass
            await c.edit(self.card(c, r) + (f"\n\n🔗 <code>{c.link(f'gw_{r.id}')}</code>" if r.status == "open" else ""), self.manage_kb(c, r))

    async def msg(self, c: Ctx) -> bool:
        st, t = c.st, c.t
        if not st:
            await self.home(c)
            return True
        if st["k"] == "gw_title":
            c.set_state("gw_n", title=c.text[:100] or "🎁")
            await c.send(t("🏆 كم عدد الفائزين؟ أرسل رقماً.", "🏆 How many winners? Send a number."))
        elif st["k"] == "gw_n":
            if not c.text.isdigit() or not 1 <= int(c.text) <= 100:
                await c.send(t("أرسل رقماً بين 1 و100.", "Send a number between 1 and 100."))
                return True
            c.clear_state()
            rid = await c.rec_add("gw", {"title": st["title"], "n": int(c.text), "parts": []}, status="open")
            await bump(c, "rl:count")
            r = await c.rec_get(rid)
            await c.send(t("✅ أُنشئ السحب. شارك الرابط ليدخل المشاركون:\n\n", "✅ Giveaway created. Share the link:\n\n") + self.card(c, r)
                         + f"\n\n🔗 <code>{c.link(f'gw_{rid}')}</code>", self.manage_kb(c, r))
        elif st["k"] == "gw_pub":
            r = await c.rec_get(st["rid"])
            ref = c.text if c.text.startswith("@") else "@" + c.text.rsplit("/", 1)[-1]
            try:
                chat = await c.bot.get_chat(ref)
                who = await c.bot.get_chat_member(chat.id, c.uid)
                assert who.status in ("administrator", "creator")
                await c.bot.send_message(chat.id, f"🎁 <b>{esc(r.data['title'])}</b>\n\n" + t(f"🏆 عدد الفائزين: {r.data['n']}\nاضغط الزر للمشاركة 👇",
                                                                                           f"🏆 Winners: {r.data['n']}\nTap the button to join 👇"),
                                         parse_mode="HTML", reply_markup=kb([[B(t("🎟 شارك الآن", "🎟 Join now"), url=c.link(f"gw_{r.id}"))]]))
            except Exception:
                await c.send(t("⚠️ تعذّر النشر. تأكد أننا مشرفان في القناة.", "⚠️ Couldn't post. Make sure we're both admins there."))
                return True
            c.clear_state()
            await c.send(t("✅ نُشر السحب في القناة.", "✅ Posted to the channel."))
        elif st["k"] == "rl_quick":
            lines = [x.strip() for x in c.text.splitlines() if x.strip()]
            n = 1
            if lines and lines[0].isdigit():
                n, lines = int(lines[0]), lines[1:]
            if len(lines) < 2:
                await c.send(t("أرسل اسمين على الأقل، كل اسم في سطر.", "Send at least two names, one per line."))
                return True
            picks = random.SystemRandom().sample(lines, min(max(1, n), len(lines)))
            await c.send("🎲 " + t(f"من بين {len(lines)} اسماً، الاختيار وقع على:\n\n", f"Out of {len(lines)} names, the pick is:\n\n")
                         + "\n".join(f"🏆 <b>{esc(p)}</b>" for p in picks), kb([[B(t("🔁 مرة أخرى", "🔁 Again"), "t:quick")], c.home_row()]))
        else:
            return False
        return True


TPL = Roulette()
