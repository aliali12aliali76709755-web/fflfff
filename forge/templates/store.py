"""متجر مصغر: منتجات بأقسام وصور، سلة، طلبات تصل للمالك، وموقع متجر على الويب."""
from ._shop import Shop


class Store(Shop):
    ns = "store"
    emoji, ar, en = "🛍", "متجر مصغر", "Mini store"
    d_ar, d_en = "متجر بمنتجات وأقسام وسلة، مع موقع ويب للمتجر", "A store with products, categories and a cart, plus a web storefront"
    cats = ("biz",)
    w_item = ("منتج", "product")
    w_items = ("المنتجات", "Products")
    w_menu = ("🛍 تصفّح المنتجات", "🛍 Browse products")
    w_site = ("🌐 افتح المتجر على الويب", "🌐 Open the web store")
    w_app = ("🛍 افتح المتجر", "🛍 Open the store")
    w_intro = ("أهلاً بك في متجرنا 👋\nتصفّح المنتجات، أضف ما يعجبك إلى السلة، ثم أرسل طلبك.", "Welcome to our store 👋\nBrowse the products, add what you like to the cart, then place your order.")
    w_details = ("اسمك، رقم هاتفك، وعنوان التوصيل", "your name, phone number and delivery address")
    with_qr = False
    photo = True
    sample = [{"name": "منتج تجريبي", "price": "10$", "desc": "عدّل هذا المنتج أو احذفه من قائمة المنتجات.", "cat": ""}]
    guide_ar = ("متجر كامل داخل تيليجرام، وله موقع ويب بالمنتجات نفسها.\n\n"
                "1. أضف منتجاتك بصيغة <code>الاسم | السعر | الوصف | القسم</code>. لإضافة صورة أرسل الصورة واكتب البيانات في التعليق.\n"
                "2. المنتجات التي تحمل اسم القسم نفسه تُجمع في قسم واحد.\n"
                "3. اكتب طرق الدفع والتوصيل في «📍 نص الدفع والاستلام».\n"
                "4. الزبون يضيف إلى السلة ويرسل الطلب مع بياناته، من البوت أو من الموقع.\n"
                "5. يصلك الطلب بزرّي قبول ورفض، ثم «تم التسليم» عند اكتماله، ويصل الزبونَ إشعار بكل خطوة.\n\n"
                "أي منتج تخفيه مؤقتاً يبقى محفوظاً ولا يراه الزبائن. الدفع يتم بينك وبين الزبون مباشرة؛ البوت لا يحصّل أموالاً.")


TPL = Store()
