"""قالب مدمج: زيادة التفاعل + أرقام التفعيل في بوت واحد."""
from ._hub import Hub


class SmmSms(Hub):
    key = "smmsms"
    emoji = "🚀"
    ar = "التفاعل + الأرقام"
    en = "Boost + Numbers"
    d_ar = "متجر واحد يبيع زيادة التفاعل لكل المنصات وأرقام التفعيل معاً، بمحفظة وطلبات ومتجر مصغّر موحّد"
    d_en = "One store selling social boost and activation numbers together, with one wallet, orders and Mini App"
    parts = ("smm", "sms")
    intro_ar = "أهلاً بك 👋\nكل ما تحتاجه لحساباتك في مكان واحد: متابعين وتفاعل لكل المنصات، وأرقام تفعيل لأي تطبيق."
    intro_en = "Welcome 👋\nEverything for your accounts in one place: followers & engagement, and activation numbers."
    guide_ar = ("هذا البوت يجمع قسمين: «زيادة التفاعل» و«أرقام التفعيل». الزبون يشحن محفظة واحدة ويشتري من القسمين.\n"
                "المنتجات والمزودون من المنصة، ومع كل بيعة يُخصم سعر المنصة من رصيدك في الصانع ويبقى لك ربحك.\n"
                "من غرفة التحكم: اضبط هامش ربحك لكل قسم، وطرق الدفع، وراجع إيصالات الشحن.")
    guide_en = ("Two sections in one bot: social boost and activation numbers, sharing one wallet.\n"
                "Products and providers come from the platform; each sale deducts the platform price from your maker balance.")


TPL = SmmSms()
