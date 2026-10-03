"""توقيع روابط الويب: هوية العضو، روابط الصور، جلسات لوحات التحكم، والتحقق من بيانات Telegram WebApp."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from .. import crypto


def sig(*parts) -> str:
    msg = "|".join(str(p) for p in parts).encode()
    return hmac.new(crypto.secret(), msg, hashlib.sha256).hexdigest()[:24]


def _same(a: str, b: str) -> bool:
    """مقارنة ثابتة الزمن تقبل أي نص (compare_digest يرفض النص غير اللاتيني)."""
    return hmac.compare_digest(str(a).encode("utf-8", "surrogatepass"), str(b).encode("utf-8", "surrogatepass"))


def same(a: str, b: str) -> bool:
    return _same(a, b)


def user_token(bot_id: int, uid: int) -> str:
    return f"{uid}-{sig('u', bot_id, uid)}"


def check_user(bot_id: int, token: str) -> int:
    uid, _, s = (token or "").partition("-")
    if uid.isascii() and uid.isdecimal() and s and _same(s, sig("u", bot_id, uid)):
        return int(uid)
    return 0


def img(bot_id: int, file_id: str) -> str:
    return sig("img", bot_id, file_id)


def session(kind: str, uid: int, ttl: int = 3600, **extra) -> str:
    body = base64.urlsafe_b64encode(json.dumps({"k": kind, "u": uid, "e": int(time.time()) + ttl, **extra}).encode()).decode().rstrip("=")
    return f"{body}.{sig('s', body)}"


def check_session(token: str, kind: str) -> dict | None:
    body, _, s = (token or "").partition(".")
    if not body or not _same(s, sig("s", body)):
        return None
    try:
        d = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except (ValueError, json.JSONDecodeError):
        return None
    return d if d.get("k") == kind and d.get("e", 0) > time.time() else None


def check_init_data(init_data: str, bot_token: str, max_age: int = 86400) -> dict | None:
    """يتحقق من initData التي يرسلها تيليجرام للصفحة المفتوحة داخل التطبيق، ويعيد بيانات المستخدم."""
    try:
        pairs = dict(parse_qsl(init_data or "", strict_parsing=True))
    except ValueError:
        return None
    got = pairs.pop("hash", "")
    if not got or "user" not in pairs:
        return None
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    want = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not _same(got, want):
        return None
    if max_age and time.time() - int(pairs.get("auth_date", 0) or 0) > max_age:
        return None
    try:
        user = json.loads(pairs["user"])
    except json.JSONDecodeError:
        return None
    return user if isinstance(user, dict) and user.get("id") else None
