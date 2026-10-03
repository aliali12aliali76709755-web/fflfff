"""الزخرفة: زخرفة أسماء ونصوص عربية ولاتينية."""
from .. import ui
from ..ctx import Ctx
from ..ui import B, esc, kb
from . import Tpl

_A = "abcdefghijklmnopqrstuvwxyz"


def _mk(lower: str, upper: str | None = None, digits: str | None = None):
    table = {}
    lo = list(lower)
    up = list(upper) if upper else lo
    for i, ch in enumerate(_A):
        table[ch] = lo[i]
        table[ch.upper()] = up[i]
    if digits:
        for i, d in enumerate(digits):
            table[str(i)] = d
    return table


def _rng(start_lower: int, start_upper: int, start_digit: int | None = None):
    return _mk("".join(chr(start_lower + i) for i in range(26)), "".join(chr(start_upper + i) for i in range(26)),
               "".join(chr(start_digit + i) for i in range(10)) if start_digit else None)


LATIN = [
    ("𝗕𝗼𝗹𝗱", _rng(0x1D5EE, 0x1D5D4, 0x1D7EC)),
    ("𝘐𝘵𝘢𝘭𝘪𝘤", _rng(0x1D622, 0x1D608)),
    ("𝙱𝚘𝚕𝚍 𝙼𝚘𝚗𝚘", _rng(0x1D68A, 0x1D670, 0x1D7F6)),
    ("𝓢𝓬𝓻𝓲𝓹𝓽", _rng(0x1D4EA, 0x1D4D0)),
    ("𝕯𝖔𝖚𝖇𝖑𝖊", _rng(0x1D586, 0x1D56C)),
    ("𝔻𝕠𝕦𝕓𝕝𝕖", _mk("𝕒𝕓𝕔𝕕𝕖𝕗𝕘𝕙𝕚𝕛𝕜𝕝𝕞𝕟𝕠𝕡𝕢𝕣𝕤𝕥𝕦𝕧𝕨𝕩𝕪𝕫", "𝔸𝔹ℂ𝔻𝔼𝔽𝔾ℍ𝕀𝕁𝕂𝕃𝕄ℕ𝕆ℙℚℝ𝕊𝕋𝕌𝕍𝕎𝕏𝕐ℤ", "𝟘𝟙𝟚𝟛𝟜𝟝𝟞𝟟𝟠𝟡")),
    ("Ⓒⓘⓡⓒⓛⓔ", _rng(0x24D0, 0x24B6)),
    ("🅂🅀🅄🄰🅁🄴", _mk("".join(chr(0x1F130 + i) for i in range(26)))),
    ("🅱🅻🅰🅲🅺", _mk("".join(chr(0x1F170 + i) for i in range(26)))),
    ("ｗｉｄｅ", _rng(0xFF41, 0xFF21, 0xFF10)),
    ("sᴍᴀʟʟ ᴄᴀᴘs", _mk("ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ", "ABCDEFGHIJKLMNOPQRSTUVWXYZ")),
    ("ɟlᴉd", None),
]
_FLIP = dict(zip("abcdefghijklmnopqrstuvwxyz", "ɐqɔpǝɟƃɥᴉɾʞlɯuodbɹsʇnʌʍxʎz"))

_KASHIDA_OK = set("بتثجحخسشصضطظعغفقكلمنهيئ")
_TASHKEEL = ["َ", "ُ", "ِ", "ّ", "ْ", "ً"]
_AR_MAPS = [
    ("حروف مزخرفة ١", str.maketrans({"ا": "آ", "ك": "ڪ", "ي": "ے", "ه": "ہ", "ة": "ۃ", "ر": "ڕ", "و": "ۆ", "ف": "ڤ", "ج": "چ", "ز": "ژ"})),
    ("حروف مزخرفة ٢", str.maketrans({"ك": "گ", "ي": "ێ", "ه": "ھ", "ب": "پ", "ن": "ڼ", "ل": "ڵ", "س": "ښ", "د": "ډ", "ط": "ڟ"})),
]
FRAMES = ["『{}』", "꧁ {} ꧂", "★彡 {} 彡★", "•°¯`•• {} ••`¯°•", "✿ {} ✿", "◥꧁ {} ꧂◤", "⚡ {} ⚡", "♛ {} ♛", "▁ ▂ ▄ {} ▄ ▂ ▁", "≪ {} ≫"]


def latin(text: str) -> list[str]:
    out = []
    for _, table in LATIN:
        if table is None:
            out.append("".join(_FLIP.get(ch, ch) for ch in text.lower())[::-1])
        else:
            out.append("".join(table.get(ch, ch) for ch in text))
    return out


def arabic(text: str) -> list[str]:
    out = []
    for n in (1, 2):
        out.append("".join(ch + ("ـ" * n if ch in _KASHIDA_OK and i + 1 < len(text) and text[i + 1] != " " else "")
                           for i, ch in enumerate(text)))
    out.append("".join(ch + (_TASHKEEL[i % len(_TASHKEEL)] if "ء" <= ch <= "ي" else "") for i, ch in enumerate(text)))
    out.append(" ".join(text))
    out.append("".join(ch + "۪۪" if ch != " " else ch for ch in text))
    out.append("".join(ch + "ٰ" if ch != " " else ch for ch in text))
    for _, table in _AR_MAPS:
        out.append(text.translate(table))
    return out


def decorate(text: str) -> list[str]:
    has_ar = any("؀" <= ch <= "ۿ" for ch in text)
    has_lat = any(ch.isascii() and ch.isalpha() for ch in text)
    res: list[str] = []
    if has_ar:
        res += arabic(text)
    if has_lat:
        res += latin(text)
    base = res[:6] or [text]
    res += [f.format(base[i % len(base)]) for i, f in enumerate(FRAMES)]
    seen, uniq = set(), []
    for r in res:
        if r not in seen and r != text:
            seen.add(r)
            uniq.append(r)
    return uniq


class Decor(Tpl):
    emoji, ar, en = "🎨", "الزخرفة", "Text decorator"
    d_ar, d_en = "زخرفة أسماء ونصوص عربية ولاتينية", "Decorate Arabic and Latin names and texts"
    cats = ()
    guide_ar = "يرسل المستخدم اسماً أو نصاً فيرد البوت بعشرات الزخارف الجاهزة للنسخ بضغطة واحدة. لا يحتاج القالب أي إعداد."

    async def home(self, c: Ctx) -> None:
        await c.edit(ui.head(f"🎨 {c.t('الزخرفة', 'Text decorator')}") + "\n" +
                     c.t("✍️ أرسل اسمك أو أي نص (عربي أو إنجليزي) وسأزخرفه لك بعدة أشكال.\nاضغط على أي زخرفة لنسخها.",
                         "✍️ Send your name or any text (Arabic or English) and I'll decorate it.\nTap any result to copy it."),
                     kb([c.tail()]))

    async def owner(self, c: Ctx):
        n = await c.kv("decor:count", 0)
        return c.t(f"✨ نصوص تمت زخرفتها: {n}", f"✨ Texts decorated: {n}"), []

    async def msg(self, c: Ctx) -> bool:
        text = (c.msg.text or "").strip()
        if not text or text.startswith("/"):
            return False
        text = text[:60]
        res = decorate(text)
        await c.kv_set("decor:count", int(await c.kv("decor:count", 0)) + 1)
        body = "\n\n".join(f"<code>{esc(r)}</code>" for r in res[:24])
        await c.send(c.t(f"🎨 زخارف «{esc(text)}»:\n\n", f"🎨 Styles for “{esc(text)}”:\n\n") + body, kb([c.home_row()]))
        return True


TPL = Decor()
