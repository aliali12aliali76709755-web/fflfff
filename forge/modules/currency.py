"""إدارة العملات وأسعار الصرف ونظام النقاط.
يدعم جلب أسعار الصرف تلقائياً مع Caching، تثبيت سعر يدوي من البائع،
والتحويل الدقيق مع الحفاظ على الحسابات الداخلية بالدولار.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any
import urllib.request
import json

from .. import db

log = logging.getLogger("forge.currency")

# تعريف شامل للعملات الحقيقية ونظام النقاط
CURRENCIES: dict[str, dict[str, Any]] = {
    "USD": {"name_ar": "دولار أمريكي", "name_en": "US Dollar", "symbol": "$", "decimals": 2, "default_rate": 1.0},
    "EUR": {"name_ar": "يورو", "name_en": "Euro", "symbol": "€", "decimals": 2, "default_rate": 0.92},
    "RUB": {"name_ar": "روبل روسي", "name_en": "Russian Ruble", "symbol": "₽", "decimals": 1, "default_rate": 92.0},
    "TRY": {"name_ar": "ليرة تركية", "name_en": "Turkish Lira", "symbol": "₺", "decimals": 1, "default_rate": 32.5},
    "IRR": {"name_ar": "ريال إيراني", "name_en": "Iranian Rial", "symbol": "﷼", "decimals": 0, "default_rate": 600000.0},
    "INR": {"name_ar": "روبية هندية", "name_en": "Indian Rupee", "symbol": "₹", "decimals": 1, "default_rate": 83.5},
    "PKR": {"name_ar": "روبية باكستانية", "name_en": "Pakistani Rupee", "symbol": "₨", "decimals": 0, "default_rate": 278.0},
    
    # العملات العربية
    "SAR": {"name_ar": "ريال سعودي", "name_en": "Saudi Riyal", "symbol": "ر.س", "decimals": 2, "default_rate": 3.75},
    "AED": {"name_ar": "درهم إماراتي", "name_en": "UAE Dirham", "symbol": "د.إ", "decimals": 2, "default_rate": 3.67},
    "KWD": {"name_ar": "دينار كويتي", "name_en": "Kuwaiti Dinar", "symbol": "د.ك", "decimals": 3, "default_rate": 0.31},
    "QAR": {"name_ar": "ريال قطري", "name_en": "Qatari Riyal", "symbol": "ر.ق", "decimals": 2, "default_rate": 3.64},
    "BHD": {"name_ar": "دينار بحريني", "name_en": "Bahraini Dinar", "symbol": "د.ب", "decimals": 3, "default_rate": 0.38},
    "OMR": {"name_ar": "ريال عماني", "name_en": "Omani Rial", "symbol": "ر.ع", "decimals": 3, "default_rate": 0.385},
    "IQD": {"name_ar": "دينار عراقي", "name_en": "Iraqi Dinar", "symbol": "د.ع", "decimals": 0, "default_rate": 1500.0},
    "JOD": {"name_ar": "دينار أردني", "name_en": "Jordanian Dinar", "symbol": "د.أ", "decimals": 2, "default_rate": 0.71},
    "SYP": {"name_ar": "ليرة سورية", "name_en": "Syrian Pound", "symbol": "ل.س", "decimals": 0, "default_rate": 14500.0},
    "LBP": {"name_ar": "ليرة لبنانية", "name_en": "Lebanese Pound", "symbol": "ل.ل", "decimals": 0, "default_rate": 89500.0},
    "EGP": {"name_ar": "جنيه مصري", "name_en": "Egyptian Pound", "symbol": "ج.م", "decimals": 2, "default_rate": 48.5},
    "LYD": {"name_ar": "دينار ليبي", "name_en": "Libyan Dinar", "symbol": "د.ل", "decimals": 2, "default_rate": 4.85},
    "TND": {"name_ar": "دينار تونسي", "name_en": "Tunisian Dinar", "symbol": "د.ت", "decimals": 2, "default_rate": 3.12},
    "DZD": {"name_ar": "دينار جزائري", "name_en": "Algerian Dinar", "symbol": "د.ج", "decimals": 1, "default_rate": 134.5},
    "MAD": {"name_ar": "درهم مغربي", "name_en": "Moroccan Dirham", "symbol": "د.م", "decimals": 2, "default_rate": 10.05},
    "SDG": {"name_ar": "جنيه سوداني", "name_en": "Sudanese Pound", "symbol": "ج.س", "decimals": 0, "default_rate": 2000.0},
    "YER": {"name_ar": "ريال يمني", "name_en": "Yemeni Rial", "symbol": "ر.ي", "decimals": 0, "default_rate": 1600.0},
    "SOS": {"name_ar": "شلن صومالي", "name_en": "Somali Shilling", "symbol": "ش.ص", "decimals": 0, "default_rate": 570.0},
    "MRU": {"name_ar": "أوقية موريتانية", "name_en": "Mauritanian Ouguiya", "symbol": "أ.م", "decimals": 1, "default_rate": 39.5},
    "DJF": {"name_ar": "فرنك جيبوتي", "name_en": "Djiboutian Franc", "symbol": "ف.ج", "decimals": 0, "default_rate": 178.0},
    "KMF": {"name_ar": "فرنك قمري", "name_en": "Comorian Franc", "symbol": "ف.ق", "decimals": 0, "default_rate": 455.0},
    "ILS": {"name_ar": "شيكل", "name_en": "Shekel", "symbol": "₪", "decimals": 2, "default_rate": 3.70},

    # نظام النقاط الافتراضي
    "POINTS": {"name_ar": "نقاط", "name_en": "Points", "symbol": "نقطة", "decimals": 0, "default_rate": 10000.0},
}

_RATES_CACHE: dict[str, float] = {}
_LAST_RATES_FETCH: float = 0.0
_FETCH_LOCK = asyncio.Lock()


async def fetch_live_rates() -> dict[str, float]:
    """يجلب أسعار الصرف العالمية مع كاش مدته 4 ساعات، ومصدر احتياطي."""
    global _RATES_CACHE, _LAST_RATES_FETCH
    now_ts = time.time()
    if _RATES_CACHE and (now_ts - _LAST_RATES_FETCH < 14400):  # 4 hours
        return _RATES_CACHE

    async with _FETCH_LOCK:
        if _RATES_CACHE and (time.time() - _LAST_RATES_FETCH < 14400):
            return _RATES_CACHE

        rates: dict[str, float] = {}
        # محاولة 1: open.er-api.com
        urls = [
            "https://open.er-api.com/v6/latest/USD",
            "https://api.exchangerate-api.com/v4/latest/USD"
        ]
        for url in urls:
            try:
                loop = asyncio.get_running_loop()
                def _do_req():
                    req = urllib.request.Request(url, headers={"User-Agent": "BotForge/1.0"})
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        return json.loads(resp.read().decode())
                data = await loop.run_in_executor(None, _do_req)
                live = data.get("rates", {})
                if live:
                    for c_code in CURRENCIES:
                        if c_code == "POINTS":
                            continue
                        if c_code in live:
                            rates[c_code] = float(live[c_code])
                    log.info("Live currency rates refreshed successfully from %s", url)
                    break
            except Exception as e:
                log.warning("Failed to fetch rates from %s: %s", url, e)

        # استكمال العملات التي قد لا يوفرها الـ API بأسعار السوق المعتمدة
        for code, info in CURRENCIES.items():
            if code not in rates:
                rates[code] = float(info["default_rate"])

        _RATES_CACHE = rates
        _LAST_RATES_FETCH = time.time()
        return _RATES_CACHE


async def get_bot_currency(bot_id: int) -> str:
    """يعيد كود العملة المعتمد للبوت (USD افتراضياً)."""
    if bot_id == 0:
        return "USD"
    code = await db.kv_get(bot_id, "cur:code", "USD")
    return code if code in CURRENCIES else "USD"


async def set_bot_currency(bot_id: int, currency_code: str) -> bool:
    """يحدد عملة المتجر للبوت."""
    if currency_code not in CURRENCIES or bot_id == 0:
        return False
    await db.kv_set(bot_id, "cur:code", currency_code)
    return True


async def get_effective_rate(bot_id: int, currency_code: str) -> float:
    """يعيد سعر الصرف مقابل الدولار الأمريكي (كم وحدة تساوي $1).
    يعطي الأولوية للسعر اليدوي المحدد من البائع إن وُجد.
    """
    if currency_code == "USD":
        return 1.0

    if currency_code == "POINTS":
        points_per_usd = await db.kv_get(bot_id, "cur:points_per_usd", None)
        if points_per_usd is not None and float(points_per_usd) > 0:
            return float(points_per_usd)
        return float(CURRENCIES["POINTS"]["default_rate"])

    manual_rates = await db.kv_get(bot_id, "cur:manual_rates", {})
    if isinstance(manual_rates, dict) and currency_code in manual_rates:
        try:
            val = float(manual_rates[currency_code])
            if val > 0:
                return val
        except (ValueError, TypeError):
            pass

    live = await fetch_live_rates()
    return float(live.get(currency_code, CURRENCIES.get(currency_code, {}).get("default_rate", 1.0)))


async def set_manual_rate(bot_id: int, currency_code: str, rate: float | None) -> None:
    """يحدد أو يلغي سعر صرف يدوي لعملة معينة لدى البائع."""
    if bot_id == 0:
        return
    if currency_code == "POINTS":
        if rate and rate > 0:
            await db.kv_set(bot_id, "cur:points_per_usd", rate)
        return

    manual_rates = dict(await db.kv_get(bot_id, "cur:manual_rates", {}) or {})
    if rate is None or rate <= 0:
        manual_rates.pop(currency_code, None)
    else:
        manual_rates[currency_code] = round(rate, 4)
    await db.kv_set(bot_id, "cur:manual_rates", manual_rates)


async def usd_to_currency(usd_amount: float, currency_code: str, bot_id: int) -> float:
    """يحول مبلغاً بالدولار إلى العملة المحددة للبوت."""
    rate = await get_effective_rate(bot_id, currency_code)
    decimals = CURRENCIES.get(currency_code, {}).get("decimals", 2)
    amount = usd_amount * rate
    return round(amount, decimals) if decimals > 0 else round(amount)


async def currency_to_usd(curr_amount: float, currency_code: str, bot_id: int) -> float:
    """يحول مبلغاً من عملة البوت إلى الدولار الأمريكي للتخزين والحسابات الداخلية."""
    rate = await get_effective_rate(bot_id, currency_code)
    if rate <= 0:
        return round(curr_amount, 4)
    return round(curr_amount / rate, 4)


def format_currency_value(amount: float, currency_code: str) -> str:
    """ينسق المبلغ مع رمز العملة والخانات العشرية المناسبة."""
    info = CURRENCIES.get(currency_code, CURRENCIES["USD"])
    decimals = info.get("decimals", 2)
    symbol = info.get("symbol", "$")
    
    if decimals == 0:
        val_str = f"{int(round(amount)):,}"
    elif decimals == 1:
        val_str = f"{amount:,.1f}"
    elif decimals == 3:
        val_str = f"{amount:,.3f}"
    else:
        val_str = f"{amount:,.2f}"

    if symbol == "$":
        return f"${val_str}"
    return f"{val_str} {symbol}"


async def format_price_for_bot(bot_id: int, usd_amount: float) -> str:
    """يحول مبلغاً بالدولار إلى عملة البوت الافتراضية ويعيده منسقاً للعرض."""
    cur_code = await get_bot_currency(bot_id)
    cur_amount = await usd_to_currency(usd_amount, cur_code, bot_id)
    return format_currency_value(cur_amount, cur_code)
