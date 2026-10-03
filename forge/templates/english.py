"""تعليم الإنجليزية: تحديد مستوى، دروس مرتبة، مفردات، مراجعة متباعدة، واختبارات تقدم."""
import datetime as dt
import random

from .. import ui
from ..ctx import Ctx
from ..ui import B, esc, kb
from . import Tpl
from ._english_data import LESSONS, LEVELS, PLACEMENT, WORDS

GAPS = [0, 1, 3, 7, 14, 30]  # أيام الانتظار حسب صندوق المراجعة


def day() -> int:
    return dt.date.today().toordinal()


class English(Tpl):
    emoji, ar, en = "📚", "تعليم الإنجليزية", "English course"
    d_ar, d_en = "تحديد مستوى، دروس مرتبة، كلمات، مراجعة ذكية، واختبارات تقدم", "Placement test, ordered lessons, vocabulary, smart review and progress quizzes"
    cats = ("edu",)
    site = True
    guide_ar = ("دورة إنجليزية مصغرة للمتحدثين بالعربية، ومعها موقع ويب للتعلّم يتزامن تقدّم العضو فيه مع البوت:\n• اختبار تحديد مستوى من 12 سؤالاً (A1 / A2 / B1).\n"
                "• 9 دروس قواعد مرتبة، كل درس بشرح وأمثلة واختبار قصير.\n• 90 كلمة موزعة على المستويات، يتعلمها المستخدم على دفعات.\n"
                "• مراجعة متباعدة: الكلمة التي يجيب عنها صحيحاً تعود بعد يوم ثم 3 ثم 7 ثم 14 ثم 30 يوماً، والخاطئة تعود فوراً.\n"
                "• صفحة تقدم بالنقاط والدروس والكلمات. لا يحتاج القالب أي إعداد.")

    async def u(self, c: Ctx) -> dict:
        return await c.kv(f"en:u:{c.uid}") or {"lvl": 0, "xp": 0, "done": [], "box": {}}

    async def save(self, c: Ctx, u: dict) -> None:
        await c.kv_set(f"en:u:{c.uid}", u)

    async def home(self, c: Ctx) -> None:
        t, u = c.t, await self.u(c)
        due = sum(1 for v in u["box"].values() if v[1] <= day())
        site = [c.site_btn("🌐 تعلّم على الويب", "🌐 Learn on the web", "🎓 افتح الدورة", "🎓 Open the course")]
        lvl = LEVELS.get(u["lvl"], t("غير محدد — ابدأ باختبار المستوى", "not set — take the placement test"))
        await c.edit(ui.head(c.brand) + "\n" + t(f"🎯 مستواك: <b>{lvl}</b>\n⭐ نقاطك: {u['xp']}\n🔁 كلمات للمراجعة اليوم: {due}",
                                                           f"🎯 Level: <b>{lvl}</b>\n⭐ XP: {u['xp']}\n🔁 Words due today: {due}"), kb([
            site if c.mini_app() else None,
            [B(t("🎯 اختبار تحديد المستوى", "🎯 Placement test"), "t:pt:0:0")],
            [B(t("📖 الدروس", "📖 Lessons"), "t:ls"), B(t("🆕 كلمات جديدة", "🆕 New words"), "t:nw")],
            [B(t(f"🔁 مراجعة ({due})", f"🔁 Review ({due})"), "t:rv"), B(t("📊 تقدمي", "📊 My progress"), "t:pg")],
            None if c.mini_app() else site, c.tail()]))

    async def owner(self, c: Ctx):
        data = await c.kv("en:learners", 0)
        return c.t(f"🎓 متعلمون بدأوا الدورة: {data}", f"🎓 Learners started: {data}"), []

    def quiz_kb(self, opts: list[str], pfx: str, extra: list | None = None):
        return kb([[B(o, f"{pfx}:{i}")] for i, o in enumerate(opts)] + (extra or []))

    async def review_card(self, c: Ctx, u: dict) -> None:
        due = [int(k) for k, v in u["box"].items() if v[1] <= day()]
        if not due:
            await c.edit(c.t("✅ لا توجد كلمات للمراجعة الآن. تعلّم كلمات جديدة أو عد غداً.", "✅ Nothing to review now. Learn new words or come back tomorrow."),
                         kb([[B(c.t("🆕 كلمات جديدة", "🆕 New words"), "t:nw")], c.home_row()]))
            return
        idx = random.choice(due)
        _, word, meaning = WORDS[idx]
        wrong = random.sample([w[2] for i, w in enumerate(WORDS) if i != idx], 3)
        opts = wrong + [meaning]
        random.shuffle(opts)
        c.x.user_data["en_rv"] = {"idx": idx, "opts": opts}
        await c.edit(c.t(f"🔁 ما معنى:\n\n<b>{esc(word)}</b>\n\nالمتبقي: {len(due)}", f"🔁 What does this mean?\n\n<b>{esc(word)}</b>\n\nLeft: {len(due)}"),
                     self.quiz_kb(opts, "t:ra", [c.home_row()]))

    async def cb(self, c: Ctx, a: list[str]) -> None:  # noqa: C901
        act, t = a[0], c.t
        u = await self.u(c)
        if act == "pt":  # pt:<سؤال>:<نقاط مشفّرة> ثم ptx للإجابة
            i = int(a[1])
            if i == 0:
                c.x.user_data["en_pt"] = []
                if not u["lvl"] and not u["xp"]:
                    await c.kv_set("en:learners", int(await c.kv("en:learners", 0)) + 1)
            if i >= len(PLACEMENT):
                ans = c.x.user_data.pop("en_pt", [])
                score = {1: 0, 2: 0, 3: 0}
                for (q, _, right, lv), got in zip(PLACEMENT, ans):
                    score[lv] += got == right
                lvl = 1 if score[1] < 3 else (2 if score[2] < 3 else 3)
                u["lvl"] = lvl
                u["xp"] += sum(score.values()) * 2
                await self.save(c, u)
                await c.edit(t(f"🎯 <b>نتيجتك: {sum(score.values())}/{len(PLACEMENT)}</b>\n\nمستواك: <b>{LEVELS[lvl]}</b>\nسنبدأ معك من دروس ومفردات هذا المستوى.",
                               f"🎯 <b>Score: {sum(score.values())}/{len(PLACEMENT)}</b>\n\nYour level: <b>{LEVELS[lvl]}</b>"),
                             kb([[B(t("📖 ابدأ الدروس", "📖 Start lessons"), "t:ls")], c.home_row()]))
                return
            q, opts, _, _ = PLACEMENT[i]
            await c.edit(f"<b>{i + 1}/{len(PLACEMENT)}</b>\n\n{esc(q)}", self.quiz_kb(opts, f"t:pa:{i}"))
        elif act == "pa":
            ans = c.x.user_data.setdefault("en_pt", [])
            if len(ans) == int(a[1]):
                ans.append(int(a[2]))
            await self.cb(c, ["pt", str(int(a[1]) + 1), "0"])
        elif act == "ls":
            rows = []
            for i, (lv, title, *_rest) in enumerate(LESSONS):
                mark = "✅" if i in u["done"] else ("📖" if lv <= max(1, u["lvl"]) else "🔒")
                rows.append([B(f"{mark} {LEVELS[lv].split()[0]} · {title}"[:60], f"t:le:{i}")])
            await c.edit(ui.head(t("📖 الدروس", "📖 Lessons")) + "\n" + t("الدروس مرتبة من الأسهل للأصعب. يمكنك فتح أي درس.", "Ordered from easiest to hardest. Open any lesson."),
                         kb(rows + [c.home_row()]))
        elif act == "le":
            i = int(a[1])
            lv, title, body, examples, _ = LESSONS[i]
            await c.edit(f"<b>{esc(title)}</b> · {LEVELS[lv]}\n{ui.LINE}\n{body}\n\n<b>{t('أمثلة', 'Examples')}</b>\n" + "\n".join(f"• {esc(e)}" for e in examples),
                         kb([[B(t("📝 اختبر نفسك", "📝 Quiz me"), f"t:lq:{i}:0:0")], [B(t("⬅️ الدروس", "⬅️ Lessons"), "t:ls")]]))
        elif act == "lq":
            i, qn, score = int(a[1]), int(a[2]), int(a[3])
            quiz = LESSONS[i][4]
            if qn >= len(quiz):
                if score == len(quiz) and i not in u["done"]:
                    u["done"].append(i)
                    u["xp"] += 10
                    await self.save(c, u)
                await c.edit(t(f"📝 نتيجتك: {score}/{len(quiz)}" + ("\n✅ أتممت الدرس! +10 نقاط" if score == len(quiz) else "\nراجع الشرح وحاول مرة أخرى."),
                               f"📝 Score: {score}/{len(quiz)}" + ("\n✅ Lesson completed! +10 XP" if score == len(quiz) else "\nReview the lesson and try again.")),
                             kb([[B(t("⏭ الدرس التالي", "⏭ Next lesson"), f"t:le:{i + 1}")] if i + 1 < len(LESSONS) else None,
                                 [B(t("⬅️ الدروس", "⬅️ Lessons"), "t:ls")]]))
                return
            q, opts, _ = quiz[qn]
            await c.edit(f"<b>{qn + 1}/{len(quiz)}</b>\n\n{esc(q)}", kb([[B(o, f"t:lx:{i}:{qn}:{score}:{k}")] for k, o in enumerate(opts)]))
        elif act == "lx":
            i, qn, score, k = (int(x) for x in a[1:5])
            ok = k == LESSONS[i][4][qn][2]
            await c.answer(t("✅ صحيح", "✅ Correct") if ok else t(f"❌ الصحيح: {LESSONS[i][4][qn][1][LESSONS[i][4][qn][2]]}", f"❌ Correct: {LESSONS[i][4][qn][1][LESSONS[i][4][qn][2]]}"), not ok)
            await self.cb(c, ["lq", str(i), str(qn + 1), str(score + ok)])
        elif act == "nw":
            lvl = max(1, u["lvl"])
            fresh = [i for i, w in enumerate(WORDS) if w[0] <= lvl and str(i) not in u["box"]][:5]
            if not fresh:
                fresh = [i for i, w in enumerate(WORDS) if str(i) not in u["box"]][:5]
            if not fresh:
                await c.edit(t("🎉 تعلمت كل الكلمات المتاحة! واصل المراجعة لتثبيتها.", "🎉 You've learned every word! Keep reviewing."), kb([c.home_row()]))
                return
            for i in fresh:
                u["box"][str(i)] = [0, day()]
            u["xp"] += len(fresh)
            await self.save(c, u)
            await c.edit(ui.head(t("🆕 كلمات جديدة", "🆕 New words")) + "\n" + "\n".join(f"• <b>{esc(WORDS[i][1])}</b> — {esc(WORDS[i][2])}" for i in fresh)
                         + t("\n\nاحفظها ثم اختبر نفسك في المراجعة.", "\n\nMemorize them, then test yourself in review."),
                         kb([[B(t("🔁 راجع الآن", "🔁 Review now"), "t:rv")], [B(t("🆕 5 كلمات أخرى", "🆕 5 more"), "t:nw")], c.home_row()]))
        elif act == "rv":
            await self.review_card(c, u)
        elif act == "ra":
            card = c.x.user_data.pop("en_rv", None)
            if not card:
                await self.review_card(c, u)
                return
            idx = card["idx"]
            ok = card["opts"][int(a[1])] == WORDS[idx][2]
            box = u["box"].get(str(idx), [0, day()])[0]
            box = min(box + 1, len(GAPS) - 1) if ok else 0
            u["box"][str(idx)] = [box, day() + (GAPS[box] if ok else 0) + (0 if ok else 0)]
            if not ok:
                u["box"][str(idx)][1] = day()
            u["xp"] += 2 if ok else 0
            await self.save(c, u)
            await c.answer(t("✅ صحيح", "✅ Correct") if ok else t(f"❌ {WORDS[idx][1]} = {WORDS[idx][2]}", f"❌ {WORDS[idx][1]} = {WORDS[idx][2]}"), not ok)
            if not ok:  # لا نعيد نفس الكلمة فوراً في نفس الجلسة
                u2 = dict(u, box={k: v for k, v in u["box"].items() if k != str(idx)})
                await self.review_card(c, u2)
            else:
                await self.review_card(c, u)
        elif act == "pg":
            learned = sum(1 for v in u["box"].values() if v[0] >= 3)
            await c.edit(ui.head(t("📊 تقدمي", "📊 My progress")) + ui.rows([
                (t("المستوى", "Level"), LEVELS.get(u["lvl"], "—")), (t("النقاط", "XP"), u["xp"]),
                (t("الدروس المكتملة", "Lessons completed"), f"{len(u['done'])}/{len(LESSONS)}"),
                (t("كلمات بدأت تعلمها", "Words started"), f"{len(u['box'])}/{len(WORDS)}"),
                (t("كلمات ثبتت (3 مراجعات+)", "Words mastered (3+ reviews)"), learned)]), kb([c.home_row()]))

    async def msg(self, c: Ctx) -> bool:
        await self.home(c)
        return True


TPL = English()
