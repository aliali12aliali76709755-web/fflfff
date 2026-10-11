"""خط أنابيب الوسائط الآمن (Secure Media Upload & Processing Pipeline):
- التحقق الصارم من Magic Bytes ونوع الملف الحقيقي.
- إزالة بيانات EXIF والبيانات الوصفية الحساسة.
- ضغط الصور وتحويلها تلقائياً إلى WebP بأحجام متعددة (Full, Medium, Thumb).
- فحص قيود الحجم والامتدادات ومنع الملفات التنفيذية أو الخبيثة.
- تخزين معزول خارج مسار التنفيذ.
"""
from __future__ import annotations

import io
import logging
import os
import uuid
from pathlib import Path
from typing import Any
from PIL import Image, ImageOps

from .. import config

log = logging.getLogger("forge.media_pipe")

MEDIA_DIR = config.DATA_DIR / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

MAX_IMAGE_SIZE = 8 * 1024 * 1024       # 8 MB
MAX_VIDEO_SIZE = 15 * 1024 * 1024      # 15 MB

ALLOWED_IMAGE_MAGICS = {
    b"\xff\xd8\xff": "jpeg",
    b"\x89PNG\r\n\x1a\n": "png",
    b"GIF87a": "gif",
    b"GIF89a": "gif",
}


def detect_file_type(data: bytes) -> str | None:
    """يفحص أول بايتات من الملف للكشف عن نوعه الحقيقي (Magic Bytes)."""
    if len(data) < 12:
        return None

    # فحص الصور الشائعة
    for magic, kind in ALLOWED_IMAGE_MAGICS.items():
        if data.startswith(magic):
            return kind

    # فحص WebP
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"

    # فحص MP4 / QuickTime
    if data[4:8] == b"ftyp":
        return "mp4"

    return None


def process_and_save_image(data: bytes, base_name: str) -> dict[str, str]:
    """ينظف الصورة، يزيل EXIF، ويحفظ نسخ WebP محسنة."""
    img = Image.open(io.BytesIO(data))

    # ضبط التدوير التلقائي بناءً على بيانات EXIF ثم إزالتها
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    # تحويل نمط الألوان إلى RGB إن لزم الأمر
    if img.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGBA", img.size, (255, 255, 255, 0))
        background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    results = {}
    sizes = {
        "full": (1200, 1200),
        "medium": (600, 600),
        "thumb": (180, 180),
    }

    for size_name, (max_w, max_h) in sizes.items():
        copy_img = img.copy()
        copy_img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
        filename = f"{base_name}_{size_name}.webp"
        target_path = MEDIA_DIR / filename
        copy_img.save(target_path, "WEBP", quality=82, optimize=True)
        results[size_name] = f"/media/{filename}"

    # النسخة الافتراضية
    results["url"] = results["medium"]
    return results


def save_video(data: bytes, base_name: str) -> dict[str, str]:
    """يحفظ ملف الفيديو بعد التأكد من نوعه وحجمه."""
    filename = f"{base_name}.mp4"
    target_path = MEDIA_DIR / filename
    target_path.write_bytes(data)
    return {
        "url": f"/media/{filename}",
        "full": f"/media/{filename}",
        "type": "video",
    }


def handle_uploaded_file(raw_data: bytes, original_filename: str = "") -> dict[str, Any]:
    """المعالج الرئيسي لرفع وفحص وضغط الملفات وحفظها بأمان."""
    if not raw_data:
        raise ValueError("الملف فارغ")

    file_size = len(raw_data)
    file_type = detect_file_type(raw_data)

    if not file_type:
        raise ValueError("نوع الملف غير مدعوم أو غير صالح أمنياً")

    if file_type == "mp4":
        if file_size > MAX_VIDEO_SIZE:
            raise ValueError(f"حجم الفيديو يتجاوز الحد الأقصى المسموح ({MAX_VIDEO_SIZE // (1024*1024)}MB)")
        base_id = uuid.uuid4().hex
        return save_video(raw_data, base_id)

    # معالجة الصور
    if file_size > MAX_IMAGE_SIZE:
        raise ValueError(f"حجم الصورة يتجاوز الحد الأقصى المسموح ({MAX_IMAGE_SIZE // (1024*1024)}MB)")

    base_id = uuid.uuid4().hex
    res = process_and_save_image(raw_data, base_id)
    res["type"] = "image"
    res["ext"] = "webp"
    res["thumb_url"] = res.get("thumb", res.get("url"))
    return res
