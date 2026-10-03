"""شطرنج مباشر: لعبة حيّة بين لاعبين برابط دعوة، رقعة تفاعلية بالأزرار، ومؤقت لكل لاعب."""
import secrets
import time

import chess
from urllib.parse import quote

from telegram.error import TelegramError

from .. import ui
from ..ctx import Ctx
from ..ui import B, esc, kb
from . import Tpl
from ._util import bump

PIECES = {"P": "♙", "N": "♘", "B": "♗", "R": "♖", "Q": "♕", "K": "♔", "p": "♟", "n": "♞", "b": "♝", "r": "♜", "q": "♛", "k": "♚"}
TIMES = {"5": 300, "10": 600, "30": 1800, "0": 0}


def clock(sec: float) -> str:
    sec = max(0, int(sec))
    return f"{sec // 60}:{sec % 60:02d}"


class Chess(Tpl):
    emoji, ar, en = "♟", "شطرنج مباشر", "Live chess"
    d_ar, d_en = "شطرنج حيّ بين لاعبين برقعة تفاعلية ومؤقتات وروابط دعوة", "Live two-player chess with an interactive board, clocks and invite links"
    guide_ar = ("اللاعب ينشئ مباراة ويختار الوقت، ثم يرسل رابط الدعوة لخصمه. الرقعة تظهر لكل لاعب من جهته، "
                "يضغط القطعة ثم المربع الهدف، وتتحدث الرقعة عند الطرفين مباشرة. يُطبَّق كش مات والتعادل والاستسلام وانتهاء الوقت تلقائياً، "
                "والترقية تكون إلى وزير. كل بوت له مبارياته المعزولة. لا يحتاج القالب أي إعداد.")

    def games(self, c: Ctx) -> dict:
        return c.x.bot_data.setdefault("chess", {})

    async def home(self, c: Ctx) -> None:
        t = c.t
        s = await c.kv(f"chess:st:{c.uid}", {"w": 0, "l": 0, "d": 0})
        await c.edit(ui.head(c.brand) + "\n" + t(f"أنشئ مباراة وادعُ خصمك.\n\n🏆 {s['w']} · 😅 {s['l']} · 🤝 {s['d']}",
                                                           f"Create a match and invite your opponent.\n\n🏆 {s['w']} · 😅 {s['l']} · 🤝 {s['d']}"),
                     kb([[B(t("⏱ 5 دقائق", "⏱ 5 min"), "t:new:5"), B(t("⏱ 10 دقائق", "⏱ 10 min"), "t:new:10")],
                         [B(t("⏱ 30 دقيقة", "⏱ 30 min"), "t:new:30"), B(t("♾ بلا وقت", "♾ No clock"), "t:new:0")], c.tail()]))

    async def owner(self, c: Ctx):
        n = await c.kv("chess:count", 0)
        return c.t(f"♟ مباريات انتهت: {n}\n🟢 جارية الآن: {len(self.games(c))}", f"♟ Matches finished: {n}\n🟢 Running now: {len(self.games(c))}"), []

    # ── الحالة ──
    def remaining(self, g: dict, color: bool) -> float:
        left = g["clk"][0 if color else 1]
        if g["tc"] and g["p"][1] is not None and not g.get("over") and g["board"].turn == color:
            left -= time.time() - g["last"]
        return left

    def render(self, c: Ctx, g: dict, idx: int):
        board: chess.Board = g["board"]
        white = idx == 0
        sel = g["sel"].get(idx)
        targets = {m.to_square for m in board.legal_moves if m.from_square == sel} if sel is not None else set()
        rows = []
        for rank in (range(7, -1, -1) if white else range(8)):
            row = []
            for file in (range(8) if white else range(7, -1, -1)):
                sq = chess.square(file, rank)
                p = board.piece_at(sq)
                label = PIECES[p.symbol()] if p else ("·" if (file + rank) % 2 else "▫")
                if sq == sel:
                    label = f"[{label}]"
                elif sq in targets:
                    label = f"×{PIECES[p.symbol()]}" if p else "•"
                row.append(B(label, "noop" if g.get("over") else f"t:q:{g['id']}:{sq}"))
            rows.append(row)
        if g.get("over"):
            rows.append([B(c.t("🔁 مباراة جديدة", "🔁 New match"), "t:home")])
        elif g["p"][1] is not None:
            rows.append([B(c.t("🏳 استسلام", "🏳 Resign"), f"t:rs:{g['id']}"), B(c.t("🔄 تحديث", "🔄 Refresh"), f"t:rf:{g['id']}")])
        names = g["n"]
        tw, tb = (clock(self.remaining(g, True)), clock(self.remaining(g, False))) if g["tc"] else ("∞", "∞")
        if g.get("over"):
            status = g["over"]
        elif g["p"][1] is None:
            status = c.t("⏳ بانتظار انضمام الخصم…", "⏳ Waiting for the opponent…")
        else:
            mine = board.turn == white
            status = (c.t("🟢 دورك", "🟢 Your move") if mine else c.t("⏳ دور الخصم", "⏳ Opponent's move")) + (c.t(" — كش!", " — check!") if board.is_check() else "")
        last = f"\n↪️ {g['san']}" if g.get("san") else ""
        text = f"♔ {esc(names[0])} ⏱ {tw}\n♚ {esc(names[1] or '…')} ⏱ {tb}\n{ui.LINE}\n{status}{last}"
        return text, kb(rows)

    async def push(self, c: Ctx, g: dict) -> None:
        for idx, uid in enumerate(g["p"]):
            if uid is None:
                continue
            text, markup = self.render(c, g, idx)
            try:
                if g["m"][idx]:
                    await c.bot.edit_message_text(text, uid, g["m"][idx], reply_markup=markup, parse_mode="HTML")
                else:
                    g["m"][idx] = (await c.send(text, markup, chat_id=uid)).message_id
            except TelegramError as e:
                if "not modified" not in str(e).lower():
                    try:
                        g["m"][idx] = (await c.send(text, markup, chat_id=uid)).message_id
                    except TelegramError:
                        pass

    async def finish(self, c: Ctx, g: dict, text: str, winner: int | None) -> None:
        g["over"] = text
        for idx, uid in enumerate(g["p"]):
            if uid is None:
                continue
            s = await c.kv(f"chess:st:{uid}", {"w": 0, "l": 0, "d": 0})
            s["d" if winner is None else ("w" if winner == idx else "l")] += 1
            await c.kv_set(f"chess:st:{uid}", s)
        await bump(c, "chess:count")
        await self.push(c, g)
        self.games(c).pop(g["id"], None)

    async def check_end(self, c: Ctx, g: dict) -> bool:
        board, t = g["board"], c.t
        if g["tc"] and g["p"][1] is not None:
            for color, idx in ((True, 0), (False, 1)):
                if self.remaining(g, color) <= 0:
                    await self.finish(c, g, t(f"⌛️ انتهى وقت {esc(g['n'][idx])}. الفائز: {esc(g['n'][1 - idx])}",
                                              f"⌛️ {esc(g['n'][idx])} ran out of time. Winner: {esc(g['n'][1 - idx])}"), 1 - idx)
                    return True
        if board.is_checkmate():
            win = 1 if board.turn else 0
            await self.finish(c, g, t(f"♚ كش مات! الفائز: {esc(g['n'][win])}", f"♚ Checkmate! Winner: {esc(g['n'][win])}"), win)
            return True
        if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
            await self.finish(c, g, t("🤝 انتهت المباراة بالتعادل.", "🤝 The match is a draw."), None)
            return True
        return False

    async def start_param(self, c: Ctx, param: str) -> bool:
        if not param.startswith("ch_"):
            return False
        g = self.games(c).get(param[3:])
        if g is None or g["p"][1] is not None or g["p"][0] == c.uid:
            await c.send(c.t("⚠️ هذه المباراة غير متاحة.", "⚠️ This match is unavailable."), kb([c.home_row()]))
            return True
        g["p"][1], g["n"][1], g["last"] = c.uid, c.user.first_name, time.time()
        await self.push(c, g)
        return True

    async def cb(self, c: Ctx, a: list[str]) -> None:
        act, t = a[0], c.t
        if act == "new" and a[1] in TIMES:
            gid = secrets.token_hex(4)
            tc = TIMES[a[1]]
            self.games(c)[gid] = {"id": gid, "board": chess.Board(), "p": [c.uid, None], "n": [c.user.first_name, None],
                                  "m": [0, 0], "sel": {}, "tc": tc, "clk": [tc, tc], "last": time.time(), "san": ""}
            link = c.link(f"ch_{gid}")
            await c.edit(t(f"♟ أُنشئت المباراة (أنت الأبيض). أرسل الرابط لخصمك:\n\n<code>{link}</code>",
                           f"♟ Match created (you play white). Send the link to your opponent:\n\n<code>{link}</code>"),
                         kb([[B(t("📤 مشاركة", "📤 Share"), url=f"https://t.me/share/url?url={quote(link)}")], c.home_row()]))
            return
        if act not in ("q", "rs", "rf"):
            return
        g = self.games(c).get(a[1])
        if g is None or c.uid not in g["p"]:
            await c.answer(t("المباراة انتهت.", "The match is over."))
            return
        idx = g["p"].index(c.uid)
        g["m"][idx] = c.q.message.message_id
        if act == "rs":
            await self.finish(c, g, t(f"🏳 استسلم {esc(g['n'][idx])}. الفائز: {esc(g['n'][1 - idx] or '—')}",
                                      f"🏳 {esc(g['n'][idx])} resigned. Winner: {esc(g['n'][1 - idx] or '—')}"), 1 - idx)
            return
        if await self.check_end(c, g):
            return
        if act == "rf" or g["p"][1] is None:
            await self.push(c, g)
            return
        board: chess.Board = g["board"]
        color = idx == 0
        if board.turn != color:
            await c.answer(t("ليس دورك.", "Not your turn."))
            return
        sq = int(a[2])
        sel = g["sel"].get(idx)
        piece = board.piece_at(sq)
        if sel is not None and sq != sel:
            move = chess.Move(sel, sq)
            if board.piece_at(sel) and board.piece_at(sel).piece_type == chess.PAWN and chess.square_rank(sq) in (0, 7):
                move = chess.Move(sel, sq, promotion=chess.QUEEN)
            if move in board.legal_moves:
                g["san"] = board.san(move)
                now = time.time()
                if g["tc"]:
                    g["clk"][0 if color else 1] -= now - g["last"]
                g["last"] = now
                board.push(move)
                g["sel"].pop(idx, None)
                if not await self.check_end(c, g):
                    await self.push(c, g)
                return
        if piece is not None and piece.color == color:
            g["sel"][idx] = None if sel == sq else sq
            if g["sel"][idx] is None:
                g["sel"].pop(idx)
            text, markup = self.render(c, g, idx)
            await c.edit(text, markup)
        else:
            await c.answer(t("حركة غير قانونية.", "Illegal move."))

    async def msg(self, c: Ctx) -> bool:
        await self.home(c)
        return True


TPL = Chess()
