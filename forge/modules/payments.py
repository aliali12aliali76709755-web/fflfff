"""بوابات الدفع والشحن المالي (المدفوعات اليدوية، نجوم تيليجرام، والعملات الرقمية).
إدارة طرق الدفع، حساب الرسوم، الإشعارات الفورية للبائع، والموافقة الذرية.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any
from sqlalchemy import select

from .. import db
from . import currency, ledger

log = logging.getLogger("forge.payments")

# القوالب الافتراضية لطرق الدفع المقترحة للبائع
DEFAULT_PAYMENT_METHODS: list[dict[str, Any]] = [
    {
        "id": "zain_cash",
        "name": "زين كاش (Zain Cash)",
        "on": False,
        "instructions": "قم بتحويل المبلغ إلى الرقم أدناه، ثم أرسل لقطة شاشة أو رقم عملية التحويل.",
        "account": "",
        "min": 1.0,
        "max": 1000.0,
        "fee_type": "seller",  # seller: يتحملها البائع | buyer: يتحملها المشتري نسبة | fixed: مبلغ إضافي
        "fee_val": 0.0,
    },
    {
        "id": "sham_cash",
        "name": "شام كاش (Sham Cash)",
        "on": False,
        "instructions": "أرسل الحوالة إلى الحساب المحدد وأرفق إشعار التحويل وصورة العملية.",
        "account": "",
        "min": 1.0,
        "max": 1000.0,
        "fee_type": "seller",
        "fee_val": 0.0,
    },
    {
        "id": "usdt_crypto",
        "name": "العملات الرقمية (USDT / Crypto)",
        "on": False,
        "instructions": "حوّل المبلغ بدقة عبر شبكة TRC20 أو TON إلى العنوان أدناه، ثم أرسل هاش العملية (TxID).",
        "account": "",
        "min": 2.0,
        "max": 5000.0,
        "fee_type": "buyer",
        "fee_val": 0.05,  # $0.05 fee
    },
    {
        "id": "telegram_stars",
        "name": "⭐ نجوم تيليجرام (Telegram Stars)",
        "on": True,
        "instructions": "ادفع مباشرة بنجوم تيليجرام بدون أي رسوم إضافية وبشحن فوري.",
        "account": "Telegram In-App",
        "min": 10.0,  # 10 Stars
        "max": 100000.0,
        "fee_type": "seller",
        "fee_val": 0.0,
    },
]


async def get_payment_methods(bot_id: int) -> list[dict[str, Any]]:
    """يعيد قائمة طرق الدفع المتاحة للبوت."""
    saved = await db.kv_get(bot_id, "pay:methods", None)
    if saved and isinstance(saved, list):
        return saved
    return [dict(m) for m in DEFAULT_PAYMENT_METHODS]


async def save_payment_methods(bot_id: int, methods: list[dict[str, Any]]) -> None:
    """يحفظ طرق الدفع المعدلة للبوت."""
    await db.kv_set(bot_id, "pay:methods", methods)


async def get_active_payment_methods(bot_id: int) -> list[dict[str, Any]]:
    """يعيد فقط طرق الدفع المفعلة من قِبل البائع."""
    all_methods = await get_payment_methods(bot_id)
    return [m for m in all_methods if m.get("on", False)]


def calculate_fees(amount: float, method_conf: dict[str, Any]) -> tuple[float, float, float]:
    """يحسب (المبلغ_الصافي_للشحن، الرسوم_المضافة_على_المشتري، المبلغ_الإجمالي_للدفع)."""
    fee_type = method_conf.get("fee_type", "seller")
    fee_val = float(method_conf.get("fee_val", 0.0))

    if fee_type == "buyer":
        # نسبة مئوية يتحملها المشتري
        fee = round(amount * (fee_val / 100.0), 2)
        total = round(amount + fee, 2)
        net = round(amount, 2)
    elif fee_type == "fixed":
        # مبلغ ثابت يتحمله المشتري
        fee = round(fee_val, 2)
        total = round(amount + fee, 2)
        net = round(amount, 2)
    else:
        # يتحملها البائع بالكامل
        fee = 0.0
        total = round(amount, 2)
        net = round(amount, 2)

    return net, fee, total


async def create_receipt(
    bot_id: int,
    user_id: int,
    user_name: str,
    username: str,
    method_name: str,
    amount: float,
    currency_code: str,
    amount_usd: float,
    *,
    proof_file_id: str = "",
    proof_text: str = "",
) -> db.PaymentReceipt:
    """ينشئ إيصال دفع جديد قيد المراجعة."""
    rcpt_id = f"rcpt_{uuid.uuid4().hex[:14]}"
    async with db.Session() as s:
        rcpt = db.PaymentReceipt(
            receipt_id=rcpt_id,
            bot_id=bot_id,
            user_id=user_id,
            user_name=(user_name or "")[:128],
            username=(username or "")[:64],
            method=method_name[:64],
            amount=amount,
            currency=currency_code[:16],
            amount_usd=amount_usd,
            status="pending",
            proof_file_id=proof_file_id,
            proof_text=proof_text[:2000],
        )
        s.add(rcpt)
        await s.commit()
        await s.refresh(rcpt)
    log.info("Created receipt %s for bot %d user %d (amount: $%.4f)", rcpt_id, bot_id, user_id, amount_usd)
    return rcpt


async def get_receipt(receipt_id: str) -> db.PaymentReceipt | None:
    """يجلب إيصال الدفع بواسطة معرفه الفريد."""
    async with db.Session() as s:
        res = await s.execute(select(db.PaymentReceipt).where(db.PaymentReceipt.receipt_id == receipt_id))
        return res.scalars().first()


async def approve_receipt(receipt_id: str, seller_note: str = "") -> tuple[bool, str, float]:
    """يوافق البائع على الإيصال ويتم شحن رصيد الزبون تلقائياً في دفتر الأستاذ.
    يعيد (نجاح؟، رسالة_الحالة، الرصيد_الجديد).
    """
    async with db.Session() as s:
        res = await s.execute(select(db.PaymentReceipt).where(db.PaymentReceipt.receipt_id == receipt_id))
        rcpt = res.scalars().first()
        if rcpt is None:
            return False, "الإيصال غير موجود", 0.0
        if rcpt.status != "pending":
            return False, f"تمت معالجة هذا الإيصال مسبقاً ({rcpt.status})", 0.0

        # شحن رصيد المستخدم بشكل ذري
        ok, tx, new_bal = await ledger.credit_user(
            rcpt.bot_id,
            rcpt.user_id,
            rcpt.amount_usd,
            kind="deposit_manual",
            ref_id=rcpt.receipt_id,
            description=f"شحن رصيد عبر {rcpt.method} ({rcpt.amount} {rcpt.currency})",
        )
        if not ok:
            return False, "فشل تسجيل العملية في دفتر الأستاذ", 0.0

        rcpt.status = "approved"
        rcpt.seller_note = seller_note[:250]
        rcpt.resolved_at = db.now()
        await s.commit()

    log.info("Receipt %s approved. User %d credited $%.4f", receipt_id, rcpt.user_id, rcpt.amount_usd)
    return True, "تمت الموافقة وشحن الرصيد بنجاح", new_bal


async def reject_receipt(receipt_id: str, reason: str = "") -> tuple[bool, str]:
    """يرفض البائع الإيصال مع تسجيل السبب الاختياري."""
    async with db.Session() as s:
        res = await s.execute(select(db.PaymentReceipt).where(db.PaymentReceipt.receipt_id == receipt_id))
        rcpt = res.scalars().first()
        if rcpt is None:
            return False, "الإيصال غير موجود"
        if rcpt.status != "pending":
            return False, f"تمت معالجة هذا الإيصال مسبقاً ({rcpt.status})"

        rcpt.status = "rejected"
        rcpt.seller_note = reason[:250]
        rcpt.resolved_at = db.now()
        await s.commit()

    log.info("Receipt %s rejected by seller (reason: %s)", receipt_id, reason)
    return True, "تم رفض الإيصال"


async def process_stars_deposit(bot_id: int, user_id: int, stars_amount: int) -> tuple[bool, str, float]:
    """يشحن رصيد المستخدم بعد الدفع الناجح بنجوم تيليجرام.
    تحويل النجوم للدولار: 1 Star ≈ $0.016 (أو 62.5 Star لكل دولار).
    """
    # حساب قيمة النجوم بالدولار
    star_rate_usd = 0.016
    usd_val = round(stars_amount * star_rate_usd, 4)
    ref = f"stars_{uuid.uuid4().hex[:12]}"

    ok, tx, new_bal = await ledger.credit_user(
        bot_id,
        user_id,
        usd_val,
        kind="deposit_stars",
        ref_id=ref,
        description=f"شحن فوري عبر نجوم تيليجرام ({stars_amount} ⭐)",
    )
    return ok, tx, new_bal
