"""اللغات. النصوص مكتوبة بالعربية والإنجليزية؛ بقية اللغات تعرض الإنجليزية."""
import os

LANGS = [
    ("en", "English 🇺🇸"), ("es", "Español 🇪🇸"),
    ("pt", "Português 🇧🇷"), ("ar", "العربية 🇸🇦"),
    ("fr", "Français 🇫🇷"), ("de", "Deutsch 🇩🇪"),
    ("tr", "Türkçe 🇹🇷"), ("ru", "Русский 🇷🇺"),
    ("fa", "فارسی 🇮🇷"),
]
LANG_NAMES = dict(LANGS)
DEFAULT = os.environ.get("DEFAULT_LANG", "ar")


def norm(code: str | None) -> str:
    code = (code or "").lower()[:2]
    if not code:
        return DEFAULT
    return code if code in LANG_NAMES else "en"


TRANSLATIONS: dict[str, dict[str, str]] = {
    "ru": {
        "🛍 تصفّح المنتجات": "🛍 Просмотр товаров",
        "🛍 Browse products": "🛍 Просмотр товаров",
        "🍽 تصفّح المنيو": "🍽 Меню",
        "🍽 Browse the menu": "🍽 Меню",
        "🛒 سلتي": "🛒 Моя корзина",
        "🛒 My cart": "🛒 Моя корзина",
        "🛒 Cart": "🛒 Корзина",
        "🛒 السلة": "🛒 Корзина",
        "🧾 طلباتي": "🧾 Мои заказы",
        "🧾 My orders": "🧾 Мои заказы",
        "📍 الدفع والاستلام": "📍 Оплата и доставка",
        "📍 Payment & delivery": "📍 Оплата и доставка",
        "🌐 افتح المتجر على الويب": "🌐 Открыть веб-магазин",
        "🌐 Open the web store": "🌐 Открыть веб-магазин",
        "🛍 افتح المتجر": "🛍 Открыть магазин",
        "🛍 Open the store": "🛍 Открыть магазин",
        "✅ إتمام الطلب": "✅ Оформить заказ",
        "✅ Checkout": "✅ Оформить заказ",
        "➕ أضف إلى السلة": "➕ В корзину",
        "➕ Add to cart": "➕ В корзину",
        "➕ أضف المزيد": "➕ Добавить еще",
        "➕ Add more": "➕ Добавить еще",
        "🗑 تفريغ السلة": "🗑 Очистить корзину",
        "🗑 Empty cart": "🗑 Очистить корзину",
        "⬅️ رجوع": "⬅️ Назад",
        "⬅️ Back": "⬅️ Назад",
        "⬅️ الأقسام": "⬅️ Категории",
        "⬅️ Categories": "⬅️ Категории",
        "🏠 الرئيسية": "🏠 Главная",
        "🏠 Home": "🏠 Главная",
        "اختر القسم:": "Выберите категорию:",
        "Pick a category:": "Выберите категорию:",
        "🕒 قيد المراجعة": "🕒 В обработке",
        "🕒 Pending": "🕒 В обработке",
        "✅ مقبول": "✅ Принят",
        "✅ Accepted": "✅ Принят",
        "❌ مرفوض": "❌ Отклонен",
        "❌ Rejected": "❌ Отклонен",
        "📦 مكتمل": "📦 Выполнен",
        "📦 Completed": "📦 Выполнен",
        "🌐 لغة البوت": "🌐 Язык бота",
        "🌐 Bot language": "🌐 Язык бота",
        "🌍 تلقائية": "🌍 Автоматически",
        "🌍 Automatic": "🌍 Автоматически",
        "💰 الإجمالي": "💰 Итого",
        "💰 Total": "💰 Итого",
    },
    "tr": {
        "🛍 تصفّح المنتجات": "🛍 Ürünlere Göz At",
        "🛍 Browse products": "🛍 Ürünlere Göz At",
        "🍽 تصفّح المنيو": "🍽 Menü",
        "🍽 Browse the menu": "🍽 Menü",
        "🛒 سلتي": "🛒 Sepetim",
        "🛒 My cart": "🛒 Sepetim",
        "🛒 Cart": "🛒 Sepet",
        "🛒 السلة": "🛒 Sepet",
        "🧾 طلباتي": "🧾 Siparişlerim",
        "🧾 My orders": "🧾 Siparişlerim",
        "📍 الدفع والاستلام": "📍 Ödeme ve Teslimat",
        "📍 Payment & delivery": "📍 Ödeme ve Teslimat",
        "🌐 افتح المتجر على الويب": "🌐 Web Mağazasını Aç",
        "🌐 Open the web store": "🌐 Web Mağazasını Aç",
        "🛍 افتح المتجر": "🛍 Mağazayı Aç",
        "🛍 Open the store": "🛍 Mağazayı Aç",
        "✅ إتمام الطلب": "✅ Siparişi Tamamla",
        "✅ Checkout": "✅ Siparişi Tamamla",
        "➕ أضف إلى السلة": "➕ Sepete Ekle",
        "➕ Add to cart": "➕ Sepete Ekle",
        "➕ أضف المزيد": "➕ Daha Fazla Ekle",
        "➕ Add more": "➕ Daha Fazla Ekle",
        "🗑 تفريغ السلة": "🗑 Sepeti Boşalt",
        "🗑 Empty cart": "🗑 Sepeti Boşalt",
        "⬅️ رجوع": "⬅️ Geri",
        "⬅️ Back": "⬅️ Geri",
        "⬅️ الأقسام": "⬅️ Kategoriler",
        "⬅️ Categories": "⬅️ Kategoriler",
        "🏠 الرئيسية": "🏠 Ana Sayfa",
        "🏠 Home": "🏠 Ana Sayfa",
        "اختر القسم:": "Kategori seçin:",
        "Pick a category:": "Kategori seçin:",
        "🕒 قيد المراجعة": "🕒 İnceleniyor",
        "🕒 Pending": "🕒 İnceleniyor",
        "✅ مقبول": "✅ Onaylandı",
        "✅ Accepted": "✅ Onaylandı",
        "❌ مرفوض": "❌ Reddedildi",
        "❌ Rejected": "❌ Reddedildi",
        "📦 مكتمل": "📦 Tamamlandı",
        "📦 Completed": "📦 Tamamlandı",
        "🌐 لغة البوت": "🌐 Bot Dili",
        "🌐 Bot language": "🌐 Bot Dili",
        "🌍 تلقائية": "🌍 Otomatik",
        "🌍 Automatic": "🌍 Otomatik",
        "💰 الإجمالي": "💰 Toplam",
        "💰 Total": "💰 Toplam",
    },
    "fa": {
        "🛍 تصفّح المنتجات": "🛍 مشاهده محصولات",
        "🛍 Browse products": "🛍 مشاهده محصولات",
        "🍽 تصفّح المنيو": "🍽 منو",
        "🍽 Browse the menu": "🍽 منو",
        "🛒 سلتي": "🛒 سبد خرید من",
        "🛒 My cart": "🛒 سبد خرید من",
        "🛒 Cart": "🛒 سبد خرید",
        "🛒 السلة": "🛒 سبد خرید",
        "🧾 طلباتي": "🧾 سفارش‌های من",
        "🧾 My orders": "🧾 سفارش‌های من",
        "📍 الدفع والاستلام": "📍 پرداخت و تحویل",
        "📍 Payment & delivery": "📍 پرداخت و تحویل",
        "🌐 افتح المتجر على الويب": "🌐 باز کردن فروشگاه وب",
        "🌐 Open the web store": "🌐 باز کردن فروشگاه وب",
        "🛍 افتح المتجر": "🛍 باز کردن فروشگاه",
        "🛍 Open the store": "🛍 باز کردن فروشگاه",
        "✅ إتمام الطلب": "✅ تکمیل سفارش",
        "✅ Checkout": "✅ تکمیل سفارش",
        "➕ أضف إلى السلة": "➕ افزودن به سبد",
        "➕ Add to cart": "➕ افزودن به سبد",
        "➕ أضف المزيد": "➕ افزودن بیشتر",
        "➕ Add more": "➕ افزودن بیشتر",
        "🗑 تفريغ السلة": "🗑 خالی کردن سبد",
        "🗑 Empty cart": "🗑 خالی کردن سبد",
        "⬅️ رجوع": "⬅️ بازگشت",
        "⬅️ Back": "⬅️ بازگشت",
        "⬅️ الأقسام": "⬅️ دسته‌بندی‌ها",
        "⬅️ Categories": "⬅️ دسته‌بندی‌ها",
        "🏠 الرئيسية": "🏠 صفحه اصلی",
        "🏠 Home": "🏠 صفحه اصلی",
        "اختر القسم:": "دسته‌بندی را انتخاب کنید:",
        "Pick a category:": "دسته‌بندی را انتخاب کنید:",
        "🕒 قيد المراجعة": "🕒 در حال بررسی",
        "🕒 Pending": "🕒 در حال بررسی",
        "✅ مقبول": "✅ تأیید شده",
        "✅ Accepted": "✅ تأیید شده",
        "❌ مرفوض": "❌ رد شده",
        "❌ Rejected": "❌ رد شده",
        "📦 مكتمل": "📦 تکمیل شده",
        "📦 Completed": "📦 تکمیل شده",
        "🌐 لغة البوت": "🌐 زبان ربات",
        "🌐 Bot language": "🌐 زبان ربات",
        "🌍 تلقائية": "🌍 خودکار",
        "🌍 Automatic": "🌍 خودکار",
        "💰 الإجمالي": "💰 مجموع",
        "💰 Total": "💰 مجموع",
    }
}


def pick(lang: str, ar: str, en: str) -> str:
    if lang == "ar":
        return ar
    if lang in TRANSLATIONS:
        t_dict = TRANSLATIONS[lang]
        if en in t_dict:
            return t_dict[en]
        if ar in t_dict:
            return t_dict[ar]
        for k, v in t_dict.items():
            if k in ar:
                return ar.replace(k, v)
            if k in en:
                return en.replace(k, v)
    return en

