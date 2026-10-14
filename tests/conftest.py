"""إعداد مشترك لاختبارات pytest: قاعدة بيانات مؤقتة معزولة لكل تشغيل، محاكي المزودين، وإيقاف وضع الصيانة."""
import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="forge_pytest_")
os.environ["DATA_DIR"] = _tmp
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmp}/t.db"
os.environ.setdefault("PROVIDERS_MOCK", "1")
os.environ.setdefault("MAINTENANCE", "0")
