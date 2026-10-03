"""اللغات. النصوص مكتوبة بالعربية والإنجليزية؛ بقية اللغات تعرض الإنجليزية."""
import os

LANGS = [
    ("en", "English 🇺🇸"), ("es", "Español 🇪🇸"),
    ("pt", "Português 🇧🇷"), ("ar", "العربية 🇸🇦"),
    ("fr", "Français 🇫🇷"), ("de", "Deutsch 🇩🇪"),
    ("tr", "Türkçe 🇹🇷"), ("ru", "Русский 🇷🇺"),
    ("fa", "فارسی 🇮🇷"),
]
LANG_NAMES = dict(LANGS)
DEFAULT = os.environ.get("DEFAULT_LANG", "ar")


def norm(code: str | None) -> str:
    code = (code or "").lower()[:2]
    if not code:
        return DEFAULT
    return code if code in LANG_NAMES else "en"


def pick(lang: str, ar: str, en: str) -> str:
    return ar if lang == "ar" else en
