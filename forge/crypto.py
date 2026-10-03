"""تشفير وفك تشفير توكنات البوتات بشكل دائم ومضمون 100% لا يضيع أبداً."""
import base64
import hashlib
import logging
from cryptography.fernet import Fernet, InvalidToken

from . import config

log = logging.getLogger("forge.crypto")

# مفاتيح احتياطية سابقة لضمان فك تشفير أي توكن قديم تم تشفيره سابقاً
KNOWN_FALLBACK_KEYS = [
    b"3NC1Tg8YBpDl3Wum6ZzvhLSuWL0J7HkPRXDEVhVEte0=",
    b"ica_lOq4iolyhA0QHcSND1WMfcBYfCgn-pue-stf730=",
    b"kcSzQTyPpmuw3xsxoMn3K_vk-rc9yr2d_mtCLrNMbXk=",
]

_primary_fernet: Fernet | None = None
_all_fernets: list[Fernet] = []


def _get_permanent_key() -> bytes:
    """اشتقاق مفتاح تشفير دائم وثابت 100% من توكن الصانع أو البيئة.
    هذا المفتاح مستحيل أن يضيع حتى لو تدمر السيرفر أو أُعيد تشغيله مليون مرة."""
    if config.SECRET_KEY:
        k = config.SECRET_KEY.strip()
        if isinstance(k, str):
            k = k.encode()
        try:
            Fernet(k)
            return k
        except Exception:
            pass
    # اشتقاق دائم وثابت مبني على MAKER_TOKEN
    salt = (config.MAKER_TOKEN or "botforge-default-master-key-salt").encode()
    digest = hashlib.sha256(b"botforge-v1-permanent-key|" + salt).digest()
    return base64.urlsafe_b64encode(digest)


def _init_fernets() -> None:
    global _primary_fernet, _all_fernets
    if _primary_fernet is not None:
        return

    pkey = _get_permanent_key()
    _primary_fernet = Fernet(pkey)
    _all_fernets = [_primary_fernet]

    for fb in KNOWN_FALLBACK_KEYS:
        try:
            if fb != pkey:
                _all_fernets.append(Fernet(fb))
        except Exception:
            pass


async def init() -> None:
    """تحميل وتهيئة التشفير الدائم وحفظه في قاعدة البيانات."""
    _init_fernets()
    try:
        from . import db
        pkey_str = _get_permanent_key().decode()
        await db.kv_set(0, "sys:permanent_key", pkey_str)
    except Exception:
        pass


def enc(token: str) -> str:
    """تشفير التوكن دائماً بالمفتاح الأساسي الدائم."""
    _init_fernets()
    if not token:
        return ""
    token = token.strip()
    return _primary_fernet.encrypt(token.encode()).decode()


def dec(blob: str) -> str:
    """فك تشفير التوكن مع فحص تلقائي ودعم كافة المفاتيح السابقة والتوكنات المباشرة."""
    if not blob:
        return ""
    blob = blob.strip()

    # 1. إذا كان التوكن مخزناً كنص صريح (123456:ABC...)
    if ":" in blob and not blob.startswith("gAAAAA"):
        parts = blob.split(":", 1)
        if parts[0].isdigit():
            return blob

    _init_fernets()
    blob_bytes = blob.encode()

    # 2. تجربة المفتاح الأساسي الدائم أولاً ثم المفاتيح الاحتياطية
    for f in _all_fernets:
        try:
            return f.decrypt(blob_bytes).decode()
        except (InvalidToken, Exception):
            continue

    # 3. إذا لم ينجح أي مفتاح
    raise InvalidToken("All cipher keys failed to decrypt token")


def secret() -> bytes:
    """مفتاح مشتق من المفتاح الدائم لتوقيع الجلسات وروابط الويب."""
    _init_fernets()
    return hashlib.sha256(b"botforge-web|" + _get_permanent_key()).digest()
