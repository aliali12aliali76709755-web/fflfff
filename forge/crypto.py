"""تشفير توكنات البوتات قبل حفظها في قاعدة البيانات."""
from cryptography.fernet import Fernet

from . import config

_f = None


async def init() -> None:
    """تحميل أو تهيئة مفتاح التشفير الدائم من قاعدة البيانات أو البيئة."""
    global _f
    key = config.SECRET_KEY
    if not key:
        try:
            from . import db
            key = await db.kv_get(0, "sys:secret_key")
            if not key:
                key = Fernet.generate_key().decode()
                await db.kv_set(0, "sys:secret_key", key)
        except Exception:
            key = None

    if not key:
        kf = config.DATA_DIR / "secret.key"
        if not kf.exists():
            kf.write_bytes(Fernet.generate_key())
            try:
                kf.chmod(0o600)
            except Exception:
                pass
        key = kf.read_text().strip()

    config.SECRET_KEY = key
    _f = Fernet(key.encode() if isinstance(key, str) else key)


def _fernet() -> Fernet:
    global _f
    if _f is None:
        key = config.SECRET_KEY
        if not key:
            kf = config.DATA_DIR / "secret.key"
            if not kf.exists():
                kf.write_bytes(Fernet.generate_key())
                try:
                    kf.chmod(0o600)
                except Exception:
                    pass
            key = kf.read_text().strip()
        _f = Fernet(key.encode() if isinstance(key, str) else key)
    return _f


def enc(token: str) -> str:
    return _fernet().encrypt(token.encode()).decode()


def dec(blob: str) -> str:
    return _fernet().decrypt(blob.encode()).decode()


def secret() -> bytes:
    """مفتاح مشتق من مفتاح التشفير، لتوقيع روابط الويب والجلسات."""
    import hashlib
    _fernet()
    key = config.SECRET_KEY or (config.DATA_DIR / "secret.key").read_text().strip()
    return hashlib.sha256(b"botforge-web|" + (key.encode() if isinstance(key, str) else key)).digest()
