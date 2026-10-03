"""موقع الويب المرتبط بالبوتات: عناوين، وحالة التفعيل."""
from __future__ import annotations

from urllib.parse import urlparse

from .. import config


def enabled() -> bool:
    return False


def base() -> str:
    return ""


def public() -> bool:
    return False


def https() -> bool:
    return False


def local_url() -> str:
    return ""


def site_url(username: str, k: str = "", path: str = "") -> str:
    return ""
