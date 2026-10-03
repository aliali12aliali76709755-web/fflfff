"""لعبة XO: ضد البوت (3 مستويات) أو ضد صديق برابط دعوة، مع رموز وإحصائيات."""
import random
import secrets

from urllib.parse import quote

from telegram.error import TelegramError

from .. import ui
from ..ctx import Ctx
from ..ui import B, esc, kb
from . import Tpl

WINS = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]
SYMS = [("❌", "⭕"), ("🔥", "💧"), ("🐱", "🐶"), ("⭐", "🌙"), ("🍎", "🍋")]
LEVELS = {"easy": ("😌 سهل", "😌 Easy"), "mid": ("🙂 متوسط", "🙂 Medium"), "hard": ("😈 صعب", "😈 Hard")}


def winner(b: list[int]) -> int:
    for x, y, z in WINS:
        if b[x] and b[x] == b[y] == b[z]:
            return b[x]
    return 0 if 0 in b else 3  # 3 = تعادل


def _minimax(b: list[int], me: int, turn: int) -> int:
    w = winner(b)
    if w == me:
        return 1
    if w == 3:
        return 0
    if w:
        return -1
    scores = []
    for i in range(9):
        if not b[i]:
            b[i] = turn
            scores.append(_minimax(b, me, 3 - turn))
            b[i] = 0
    return max(scores) if turn == me else min(scores)


def best_move(b: list[int], me: int) -> int:
    best, move = -2, -1
    for i in [4, 0, 2, 6, 8, 1, 3, 5, 7]:
        if not b[i]:
            b[i] = me
            s = _minimax(b, me, 3 - me)
            b[i] = 0
            if s > best:
                best, move = s, i
    return move


def bot_move(b: list[int], lvl: str) -> int:
    free = [i for i in range(9) if not b[i]]
    if lvl == "easy" or (lvl == "mid" and random.random() < 0.45):
        return random.choice(free)
    return best_move(b, 2)


class XO(Tpl):
    emoji, ar, en = "❎", "لعبة XO", "Tic-tac-toe"
    d_ar, d_en = "لعبة XO متقدمة ضد البوت أو صديق مع صعوبات ورموز وإحصائيات", "Advanced tic-tac-toe vs the bot or a friend, with levels, symbols and stats"
    cats = ("fun",)
    guide_ar = "المستخدم يلعب ضد البوت بثلاثة مستويات، أو ينشئ لعبة ويرسل رابط الدعوة لصديقه فيلعبان مباشرة. يختار كل لاعب رموزه وتُحفظ إحصائياته. لا يحتاج القالب أي إعداد."

    def syms(self, c: Ctx) -> tuple[str, str]:
        return SYMS[c.x.user_data.get("xo_sym", 0) % len(SYMS)]

    async def stat(self, c: Ctx, uid: int, key: str | None = None) -> dict:
        s = await c.kv(f"xo:st:{uid}", {"w": 0, "l": 0, "d": 0})
        if key:
            s[key] += 1
            await c.kv_set(f"xo:st:{uid}", s)
        return s

    async def home(self, c: Ctx) -> None:
        t = c.t
        await c.edit(ui.head(c.brand) + "\n" + t("اختر طريقة اللعب:", "Choose how to play:"), kb([
            [B(t("🤖 ضد البوت", "🤖 Vs bot"), "t:lv"), B(t("👥 ضد صديق", "👥 Vs friend"), "t:fr")],
            [B(t("🎨 الرموز", "🎨 Symbols"), "t:sym"), B(t("📊 إحصائياتي", "📊 My stats"), "t:st")], c.tail()]))

    async def owner(self, c: Ctx):
        n = await c.kv("xo:games", 0)
        return c.t(f"🎮 ألعاب لُعبت: {n}", f"🎮 Games played: {n}"), []

    def board_kb(self, c: Ctx, b: list[int], pfx: str, sx: str, so: str, over: bool):
        cells = [B({0: "⬜", 1: sx, 2: so}[v], "noop" if (v or over) else f"{pfx}:{i}") for i, v in enumerate(b)]
        rows = ui.grid(cells, 3)
        if over:
            rows.append([B(c.t("🔁 لعبة جديدة", "🔁 New game"), "t:home")])
        return kb(rows)

    # ── ضد البوت ──
    async def solo(self, c: Ctx, g: dict) -> None:
        sx, so = self.syms(c)
        w = winner(g["b"])
        if w:
            c.x.user_data.pop("xo", None)
            await self.stat(c, c.uid, {1: "w", 2: "l", 3: "d"}[w])
            await c.kv_set("xo:games", int(await c.kv("xo:games", 0)) + 1)
        head = {0: c.t("دورك! اختر خانة:", "Your turn! Pick a cell:"), 1: c.t("🏆 فزت!", "🏆 You win!"),
                2: c.t("😅 فاز البوت.", "😅 The bot wins."), 3: c.t("🤝 تعادل.", "🤝 Draw.")}[w]
        await c.edit(f"<b>{sx} {c.t('أنت', 'You')}  vs  {so} {c.t('البوت', 'Bot')}</b> · {c.t(*LEVELS[g['lvl']])}\n\n{head}",
                     self.board_kb(c, g["b"], "t:m", sx, so, bool(w)))

    # ── ضد صديق ──
    def games(self, c: Ctx) -> dict:
        return c.x.bot_data.setdefault("xo_games", {})

    async def duel_show(self, c: Ctx, gid: str) -> None:
        g = self.games(c).get(gid)
        if g is None:
            return
        w = winner(g["b"])
        for idx, uid in enumerate(g["p"]):
            if uid is None:
                continue
            if w == 3:
                head = c.t("🤝 تعادل.", "🤝 Draw.")
            elif w:
                head = c.t("🏆 فزت!", "🏆 You win!") if w == idx + 1 else c.t("😅 خسرت.", "😅 You lost.")
            else:
                head = c.t("دورك!", "Your turn!") if g["turn"] == idx + 1 else c.t("⏳ دور خصمك…", "⏳ Opponent's turn…")
            text = f"<b>{g['s'][0]} {esc(g['n'][0])}  vs  {g['s'][1]} {esc(g['n'][1] or '…')}</b>\n\n{head}"
            markup = self.board_kb(c, g["b"], f"t:d:{gid}", g["s"][0], g["s"][1], bool(w) or g["p"][1] is None)
            try:
                if g["m"][idx]:
                    await c.bot.edit_message_text(text, uid, g["m"][idx], reply_markup=markup, parse_mode="HTML")
                else:
                    g["m"][idx] = (await c.send(text, markup, chat_id=uid)).message_id
            except TelegramError:
                pass
        if w:
            for idx, uid in enumerate(g["p"]):
                await self.stat(c, uid, "d" if w == 3 else ("w" if w == idx + 1 else "l"))
            await c.kv_set("xo:games", int(await c.kv("xo:games", 0)) + 1)
            self.games(c).pop(gid, None)

    async def start_param(self, c: Ctx, param: str) -> bool:
        if not param.startswith("xo_"):
            return False
        g = self.games(c).get(param[3:])
        if g is None or g["p"][1] is not None:
            await c.send(c.t("⚠️ هذه اللعبة غير متاحة أو بدأت بالفعل.", "⚠️ This game is unavailable or already started."), kb([c.home_row()]))
            return True
        if g["p"][0] == c.uid:
            await c.send(c.t("أرسل الرابط لصديقك لينضم.", "Send the link to your friend."))
            return True
        g["p"][1], g["n"][1] = c.uid, c.user.first_name
        await self.duel_show(c, param[3:])
        return True

    async def cb(self, c: Ctx, a: list[str]) -> None:
        act, t = a[0], c.t
        if act == "lv":
            await c.edit(t("اختر مستوى الصعوبة:", "Pick a difficulty:"), kb([[B(t(*v), f"t:go:{k}") for k, v in LEVELS.items()], c.home_row()]))
        elif act == "go" and a[1] in LEVELS:
            g = {"b": [0] * 9, "lvl": a[1]}
            if random.random() < 0.5:
                g["b"][bot_move(g["b"], a[1])] = 2
            c.x.user_data["xo"] = g
            await self.solo(c, g)
        elif act == "m":
            g = c.x.user_data.get("xo")
            i = int(a[1])
            if not g or g["b"][i]:
                return
            g["b"][i] = 1
            if not winner(g["b"]):
                g["b"][bot_move(g["b"], g["lvl"])] = 2
            await self.solo(c, g)
        elif act == "fr":
            gid = secrets.token_hex(4)
            self.games(c)[gid] = {"b": [0] * 9, "p": [c.uid, None], "n": [c.user.first_name, None], "s": list(self.syms(c)), "turn": 1, "m": [0, 0]}
            link = c.link(f"xo_{gid}")
            await c.edit(t(f"👥 أُنشئت اللعبة. أرسل هذا الرابط لصديقك:\n\n<code>{link}</code>\n\nستبدأ اللعبة فور انضمامه.",
                           f"👥 Game created. Send this link to your friend:\n\n<code>{link}</code>\n\nIt starts as soon as they join."),
                         kb([[B(t("📤 مشاركة", "📤 Share"), url=f"https://t.me/share/url?url={quote(link)}")], c.home_row()]))
        elif act == "d":
            g = self.games(c).get(a[1])
            i = int(a[2])
            if g is None or c.uid not in g["p"] or g["p"][1] is None:
                return
            me = g["p"].index(c.uid) + 1
            if g["turn"] != me:
                await c.answer(t("ليس دورك.", "Not your turn."))
                return
            if g["b"][i]:
                return
            g["b"][i], g["turn"] = me, 3 - me
            g["m"][me - 1] = c.q.message.message_id
            await self.duel_show(c, a[1])
        elif act == "sym":
            cur = c.x.user_data.get("xo_sym", 0)
            await c.edit(t("🎨 اختر رموزك:", "🎨 Pick your symbols:"),
                         kb(ui.grid([B(("✓ " if i == cur else "") + f"{x} {o}", f"t:ss:{i}") for i, (x, o) in enumerate(SYMS)], 3) + [c.home_row()]))
        elif act == "ss":
            c.x.user_data["xo_sym"] = int(a[1])
            await self.home(c)
        elif act == "st":
            s = await self.stat(c, c.uid)
            total = s["w"] + s["l"] + s["d"]
            await c.edit(ui.head(t("📊 إحصائياتي", "📊 My stats")) + ui.rows([
                (t("الألعاب", "Games"), total), (t("🏆 فوز", "🏆 Wins"), s["w"]), (t("😅 خسارة", "😅 Losses"), s["l"]),
                (t("🤝 تعادل", "🤝 Draws"), s["d"]), (t("نسبة الفوز", "Win rate"), f"{round(s['w'] * 100 / total) if total else 0}%")]), kb([c.home_row()]))

    async def msg(self, c: Ctx) -> bool:
        await self.home(c)
        return True


TPL = XO()
