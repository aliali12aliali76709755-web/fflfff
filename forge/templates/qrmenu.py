"""منيو QR: منيو رقمي بأقسام وأسعار وصور، يفتح على الويب بمسح رمز QR، والطلبات تصل للمالك."""
from ._shop import Shop


class QRMenu(Shop):
    ns = "qrmenu"
    emoji, ar, en = "🍽", "منيو QR", "QR menu"
    d_ar, d_en = "منيو رقمي بأقسام وأسعار يفتح بمسح رمز QR", "A digital menu with categories and prices, opened by scanning a QR code"
    cats = ("biz",)
    w_item = ("صنف", "item")
    w_items = ("الأصناف", "Items")
    w_menu = ("🍽 تصفّح المنيو", "🍽 Browse the menu")
    w_site = ("🌐 افتح المنيو على الويب", "🌐 Open the web menu")
    w_app = ("🍽 افتح المنيو", "🍽 Open the menu")
    w_intro = ("أهلاً بك 👋\nتصفّح المنيو، أضف ما تشتهي إلى السلة، ثم أرسل طلبك.", "Welcome 👋\nBrowse the menu, add what you fancy to the cart, then place your order.")
    w_details = ("اسمك، رقم هاتفك، ورقم الطاولة أو عنوان التوصيل", "your name, phone number and table number or delivery address")
    with_qr = True
    photo = True
    sample = [{"name": "برغر كلاسيك", "price": "8$", "desc": "صنف تجريبي: عدّله أو احذفه من قائمة الأصناف.", "cat": ""}]
    guide_ar = ("منيو رقمي لمطعمك أو كافيهك، يفتح على الويب بمسح رمز QR دون تثبيت شيء.\n\n"
                "1. اضغط «➕ إضافة صنف» وأرسله بصيغة <code>الاسم | السعر | الوصف | القسم</code>. لإضافة صورة أرسل الصورة واكتب البيانات في التعليق.\n"
                "2. استخدم القسم لتجميع الأصناف: مشروبات، وجبات، حلويات…\n"
                "3. من «🔳 رمز QR للطباعة» احصل على الرمز وضعه على الطاولات.\n"
                "4. الزبون يتصفح ويطلب من الموقع أو من البوت، والطلب يصلك هنا بزرّي قبول ورفض.\n\n"
                "الصنف الذي نفد تخفيه مؤقتاً بضغطة ثم تظهره لاحقاً.")


TPL = QRMenu()
