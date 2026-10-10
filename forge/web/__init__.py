"""موقع الويب المرتبط بالبوتات: عناوين، وحالة التفعيل."""
from __future__ import annotations

from urllib.parse import urlparse

from .. import config


def enabled() -> bool:
    return config.WEB_PORT > 0


def base() -> str:
    return config.PUBLIC_URL


def public() -> bool:
    """هل يوجد رابط عام صالح لوضعه في أزرار تيليجرام؟ (تيليجرام يرفض localhost والعناوين الداخلية)"""
    if not enabled() or not config.PUBLIC_URL:
        return False
    host = (urlparse(config.PUBLIC_URL).hostname or "").lower()
    return bool(host) and host not in ("localhost", "127.0.0.1", "0.0.0.0", "::1") and "." in host


def https() -> bool:
    """الفتح داخل تيليجرام (Mini App) يتطلب https."""
    return public() and config.PUBLIC_URL.lower().startswith("https://")


def local_url() -> str:
    return f"http://localhost:{config.WEB_PORT}"


def site_url(username: str, k: str = "", path: str = "") -> str:
    """رابط موقع بوت. يعيد الرابط المحلي إن لم يُضبط رابط عام (للمعاينة على نفس الجهاز)."""
    root = base() if config.PUBLIC_URL else local_url()
    url = f"{root}/{username}{path}"
    return f"{url}?k={k}" if k else url
