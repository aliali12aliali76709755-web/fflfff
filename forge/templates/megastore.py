"""قالب مدمج شامل: الألعاب والاشتراكات + التفاعل + الأرقام + نجوم تيليجرام في بوت واحد."""
from ._hub import Hub


class MegaStore(Hub):
    key = "megastore"
    emoji = "🏬"
    ar = "المتجر الشامل"
    en = "All-in-one Store"
    d_ar = "بِع كل شيء معاً: شحن الألعاب والاشتراكات، زيادة التفاعل، أرقام التفعيل، ونجوم وبريميوم تيليجرام"
    d_en = "Sell everything together: game top-ups & subscriptions, social boost, activation numbers, Telegram Stars & Premium"
    parts = ("digital", "smm", "sms", "tgstars")
    intro_ar = "أهلاً بك في متجرنا الشامل 🏬\nشحن ألعاب واشتراكات، متابعين وتفاعل، أرقام تفعيل، ونجوم تيليجرام — كلها بمحفظة واحدة."
    intro_en = "Welcome to our all-in-one store 🏬\nGame top-ups, subscriptions, social boost, numbers and Telegram Stars — one wallet."
    guide_ar = ("متجر شامل بأربعة أقسام تشترك في محفظة واحدة للزبون.\n"
                "المنتجات والمزودون من المنصة، ومع كل بيعة يُخصم سعر المنصة من رصيدك في الصانع ويبقى لك ربحك.\n"
                "من غرفة التحكم: هامش ربحك لكل قسم، طرق الدفع، الإيصالات، وأكواد الخصم.")
    guide_en = ("Four sections sharing one customer wallet.\n"
                "Products and providers come from the platform; each sale deducts the platform price from your maker balance.")


TPL = MegaStore()
