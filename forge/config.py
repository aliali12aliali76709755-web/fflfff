"""إعدادات المنصة — تُقرأ من متغيرات البيئة أو من ملف .env بجانب run.py."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_env() -> None:
    f = ROOT / ".env"
    if not f.exists():
        return
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()


def _int(name: str, default: int = 0) -> int:
    try:
        return int(os.environ.get(name, default) or default)
    except ValueError:
        return default


DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
TMP_DIR = DATA_DIR / "tmp"
TMP_DIR.mkdir(exist_ok=True)

MAKER_TOKEN = os.environ.get("MAKER_TOKEN", "")
ADMIN_ID = _int("ADMIN_ID")
DATABASE_URL = os.environ.get("DATABASE_URL") or f"sqlite+aiosqlite:///{(DATA_DIR / 'forge.db').as_posix()}"
SECRET_KEY = os.environ.get("SECRET_KEY", "")

# خادم Bot API. اتركه افتراضياً، أو ضع عنوان خادمك المحلي لرفع ملفات حتى 2GB.
BOT_API_BASE = os.environ.get("BOT_API_BASE", "https://api.telegram.org/bot")
BOT_API_FILE_BASE = os.environ.get("BOT_API_FILE_BASE", "https://api.telegram.org/file/bot")
LOCAL_API = os.environ.get("LOCAL_API", "0") == "1"
MAX_UPLOAD_MB = _int("MAX_UPLOAD_MB", 2000 if LOCAL_API else 49)
MAX_DOWNLOAD_MB = _int("MAX_DOWNLOAD_MB", 2000 if LOCAL_API else 20)

BRAND = os.environ.get("BRAND", "صانع البوتات")
BRAND_EN = os.environ.get("BRAND_EN", "Bot Maker")
UPDATES_URL = os.environ.get("UPDATES_URL", "")
PRIVACY_URL = os.environ.get("PRIVACY_URL", "")
GUIDE_URL = os.environ.get("GUIDE_URL", "")
MAX_BOTS_PER_USER = _int("MAX_BOTS_PER_USER", 0)  # 0 = بلا حد
MANAGED_BOTS = os.environ.get("MANAGED_BOTS", "1") == "1"  # زر «إنشاء فوري عبر BotFather»
TZ_HOURS = _int("TZ_HOURS", 3)  # فرق التوقيت عن UTC لعرض التواريخ والتقرير اليومي

# مفتاح خدمة ocr.space (مجاني) يُستخدم لقراءة الصور حين لا يكون Tesseract مثبتاً على الجهاز
OCR_SPACE_KEY = os.environ.get("OCR_SPACE_KEY", "helloworld")

_PORT = _int("PORT", 0)
WEB_PORT = _PORT if _PORT > 0 else _int("WEB_PORT", 0)
WEB_HOST = os.environ.get("WEB_HOST", "0.0.0.0")
# الرابط العام الذي يصل به الناس إلى الخادم، مثل https://bots.example.com — بدونه تبقى المواقع محلية ولا تظهر أزرارها في البوتات
PUBLIC_URL = os.environ.get("PUBLIC_URL", "").strip().rstrip("/")

# نفق https تلقائي حين لا يوجد PUBLIC_URL: يشغّل cloudflared ليحصل على رابط عام مؤقت، فتفتح مواقع البوتات داخل تيليجرام من جهازك مباشرة.
# عند أول تشغيل ينزّل برنامج cloudflared الرسمي من صفحة إصدارات Cloudflare على GitHub إلى data/tools (إن لم يكن مثبتاً).
AUTO_TUNNEL = os.environ.get("AUTO_TUNNEL", "0") == "1"
CLOUDFLARED = os.environ.get("CLOUDFLARED", "").strip()   # مسار البرنامج إن أردت تحديده يدوياً
