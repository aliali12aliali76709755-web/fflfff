"""تشفير توكنات البوتات قبل حفظها في قاعدة البيانات."""
from cryptography.fernet import Fernet

from . import config

_f = None


def _fernet() -> Fernet:
    global _f
    if _f is None:
        key = config.SECRET_KEY
        if not key:
            kf = config.DATA_DIR / "secret.key"
            if not kf.exists():
                kf.write_bytes(Fernet.generate_key())
                kf.chmod(0o600)
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
