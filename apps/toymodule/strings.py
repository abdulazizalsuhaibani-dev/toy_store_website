"""UI copy, in English and Arabic.

A direct port of the design's `STR` table. It is a plain dict rather than a
gettext catalogue because the whole storefront is two languages chosen by a
toggle in the header, not by the browser's Accept-Language: there is no .po
workflow to feed, no translator in the loop, and the Arabic here is part of
the design rather than a translation of the English. Swap this for gettext (or
django-parler for the model-side strings) the day a third language appears.

Every value is a (English, Arabic) pair. `translations()` flattens it for a
template, so a page says `{{ t.addToCart }}` and never picks an index.
"""

LANGUAGES = ("en", "ar")
DEFAULT_LANGUAGE = "en"

STRINGS = {
    # -- chrome ----------------------------------------------------------
    "brand": ("Happybox", "هابي بوكس"),
    "tagline": ("Toys worth the fun", "ألعاب تستحق المتعة"),
    "langLabel": ("العربية", "English"),
    "navHome": ("Home", "الرئيسية"),
    "navShop": ("Shop toys", "تسوّق الألعاب"),
    "menu": ("Menu", "القائمة"),
    "pricesIn": ("Prices in", "الأسعار بـ"),
    "search": ("Search", "بحث"),
    "cart": ("Cart", "السلة"),
    "signIn": ("Sign in", "تسجيل الدخول"),
    "signOut": ("Sign out", "تسجيل الخروج"),
    "dashboard": ("Dashboard", "لوحة التحكم"),

    # -- homepage --------------------------------------------------------
    "heroTitle1": ("Toys that get", "ألعاب لا تبقى"),
    "heroTitle2": ("played with.", "في الصندوق."),
    "heroBody": (
        "Hand-picked, tested-by-actual-kids toys for ages 3 to 10. Sorted by age, so you never guess.",
        "ألعاب مختارة بعناية وجرّبها أطفال حقيقيون، من 3 إلى 10 سنوات. مصنّفة بالعمر حتى لا تحتار.",
    ),
    "ctaShopAge": ("Shop by age", "تسوّق حسب العمر"),
    "ctaGift": ("Gift finder", "دليل الهدايا"),
    "mascotHi": ("Hi, I'm Happy!", "مرحبًا، أنا هابي!"),
    "catsTitle": ("Pick a playground", "اختر ساحة اللعب"),
    "seeAll": ("See all toys →", "شاهد كل الألعاب ←"),
    "catsSub": (
        "Every category is filtered by age, so what you see fits your kid.",
        "كل قسم مُرشَّح بالعمر، فما تراه يناسب طفلك.",
    ),
    "featTitle": ("Flying off the shelves", "الأكثر طلبًا هذا الأسبوع"),
    "trust1t": ("Age-checked, every toy", "كل لعبة مراجَعة بالعمر"),
    "trust1b": (
        "Ranges come from the maker plus our own play-testing.",
        "الأعمار من الشركة المصنّعة زائد تجربتنا الخاصة.",
    ),
    "trust2t": ("Safety on the label", "السلامة مكتوبة بوضوح"),
    "trust2b": (
        "Materials, choke-hazard notes and certifications on every page.",
        "المواد وتحذيرات الأجزاء الصغيرة والشهادات في كل صفحة.",
    ),
    "trust3t": ("60-day returns", "إرجاع خلال 60 يومًا"),
    "trust3b": (
        "Even if it's been opened. Kids change their minds.",
        "حتى لو فُتحت العلبة. الأطفال يغيّرون رأيهم.",
    ),
    "trust4t": ("Real humans", "بشر حقيقيون"),
    "trust4b": ("Call or chat 9–6, and a parent picks up.", "اتصل أو راسلنا من 9 إلى 6، ويجيبك أحد الوالدين."),
    "ages": ("Ages", "الأعمار"),
    "each": ("each", "للواحدة"),
    "emptyShelf": ("No toys here yet", "لا توجد ألعاب بعد"),
    "emptyShelfBody": (
        "Nothing has been added to this shelf. Sign in and add the first one.",
        "لم تُضف أي لعبة إلى هذا الرف. سجّل الدخول وأضف أول لعبة.",
    ),

    # -- listing ---------------------------------------------------------
    "crumbShop": ("Shop", "التسوق"),
    "ageLabel": ("Age", "العمر"),
    "sortPill": ("Sort: Popular", "الترتيب: الأكثر شعبية"),
    "add": ("Add", "أضف"),

    # -- detail ----------------------------------------------------------
    "reviewsSuffix": ("parent reviews", "تقييم من الأهل"),
    "inStock": ("In stock · ships tomorrow", "متوفر · يُشحن غدًا"),
    "outOfStock": ("Out of stock", "غير متوفر"),
    "only": ("Only", "فقط"),
    "left": ("left", "متبقٍ"),
    "noReviews": ("No reviews yet", "لا توجد مراجعات بعد"),
    "soldOut": ("“{name}” is sold out.", "«{name}» نفدت من المخزون."),
    "onlyLeftAdded": (
        "Only {n} of “{name}” left, so that's all we could add.",
        "لم يتبقَّ من «{name}» سوى {n}، وهذا كل ما أمكن إضافته.",
    ),
    "onlyLeftKept": (
        "Only {n} of “{name}” left, so we lowered your quantity.",
        "لم يتبقَّ من «{name}» سوى {n}، لذا خفّضنا الكمية.",
    ),
    "soldOutCheckout": (
        "“{name}” just sold out. Nothing was charged; remove it to continue.",
        "نفدت «{name}» للتو. لم يُخصم أي مبلغ؛ أزلها للمتابعة.",
    ),
    "onlyLeftCheckout": (
        "Only {n} of “{name}” left. Nothing was charged; lower the quantity to continue.",
        "لم يتبقَّ من «{name}» سوى {n}. لم يُخصم أي مبلغ؛ خفّض الكمية للمتابعة.",
    ),
    "ageRange": ("Age range", "الفئة العمرية"),
    "years": ("years", "سنة"),
    "pieces": ("Pieces", "القطع"),
    "playType": ("Play type", "نوع اللعب"),
    "addToCart": ("Add to cart 🎉", "أضف إلى السلة 🎉"),
    "detailNote": (
        "Free gift wrap at checkout · 60-day returns, even opened",
        "تغليف هدايا مجاني عند الدفع · إرجاع 60 يومًا حتى بعد الفتح",
    ),
    "grownups": ("For grown-ups", "للكبار"),
    "materials": ("Materials", "المواد"),
    "materialsV": (
        "FSC-certified beech, water-based non-toxic paint",
        "خشب زان معتمد FSC، دهان مائي غير سام",
    ),
    "safety": ("Safety", "السلامة"),
    "safetyV": (
        "EN71 & ASTM F963 tested. No small parts under 3.",
        "مُختبرة وفق EN71 و ASTM F963. لا أجزاء صغيرة لمن هم أقل من 3 سنوات.",
    ),
    "care": ("Care", "العناية"),
    "careV": (
        "Wipe with a damp cloth. Not dishwasher safe.",
        "تُنظَّف بقطعة قماش مبللة. غير مناسبة لغسالة الأطباق.",
    ),
    "boxSize": ("Box size", "مقاس العلبة"),
    "boxSizeV": ("32 × 24 × 12 cm, 1.4 kg", "32 × 24 × 12 سم، 1.4 كجم"),
    "relatedTitle": ("Plays well with", "يُلعب معها"),
    "quantity": ("Quantity", "الكمية"),

    # -- cart ------------------------------------------------------------
    "cartTitle": ("Your toy box", "صندوق ألعابك"),
    "items": ("items", "قطعة"),
    # Arabic uses the singular noun after a numeral here, so both are "قطعة".
    "item": ("item", "قطعة"),
    "step1": ("1 Cart", "1 السلة"),
    "step1done": ("1 Cart ✓", "1 السلة ✓"),
    "step2": ("2 Delivery", "2 التوصيل"),
    "step3": ("3 Payment", "3 الدفع"),
    "chev": ("›", "‹"),
    "remove": ("Remove", "إزالة"),
    "wrapTitle": ("Wrap it up — free", "غلّفها كهدية — مجانًا"),
    "wrapBody": (
        "Stripy paper, ribbon, and a card you write at checkout.",
        "ورق مقلَّم وشريطة وبطاقة تكتبها عند الدفع.",
    ),
    "keepShopping": ("← Keep shopping", "→ متابعة التسوق"),
    "summary": ("Order summary", "ملخّص الطلب"),
    "subtotal": ("Subtotal", "المجموع الفرعي"),
    "shipping": ("Shipping", "الشحن"),
    "giftWrap": ("Gift wrap", "تغليف الهدية"),
    "total": ("Total", "الإجمالي"),
    "goCheckout": ("Go to checkout", "إتمام الشراء"),
    "cartFoot1": ("Secure payment · 60-day returns", "دفع آمن · إرجاع 60 يومًا"),
    "cartFoot2": ("Ships within one working day", "يُشحن خلال يوم عمل واحد"),
    "emptyTitle": ("Nothing in the box yet", "الصندوق فارغ حتى الآن"),
    "emptyBody": ("Happy is a bit disappointed. Fix it?", "هابي حزين قليلاً. نصلح الأمر؟"),
    "emptyCta": ("Find some toys", "ابحث عن ألعاب"),
    "free": ("Free", "مجانًا"),

    # -- search ----------------------------------------------------------
    "searchTitle": ("What are we looking for?", "عن أي لعبة نبحث؟"),
    "searchPh": ("Try “blocks”, “kite”, “bear”…", "جرّب «مكعبات»، «طائرة ورقية»، «دبدوب»…"),
    "popular": ("Popular", "الأكثر شعبية"),
    "narrow": ("Narrow it down", "ضيّق النتائج"),
    "category": ("Category", "القسم"),
    "price": ("Price", "السعر"),
    "clearAll": ("Clear all filters", "مسح كل الفلاتر"),
    "clearFilters": ("Clear filters", "مسح الفلاتر"),
    "noMatchTitle": ("Nothing matched that", "لا نتائج مطابقة"),
    "noMatchBody": ("Try a wider age range, or clear the filters.", "جرّب فئة عمرية أوسع، أو امسح الفلاتر."),
    "all": ("All", "الكل"),
    "allAges": ("All ages", "كل الأعمار"),
    "any": ("Any", "أي سعر"),
    "priceUnder": ("Under", "أقل من"),
    "priceOver": ("Over", "أكثر من"),
    "priceUp": ("Price ↑", "السعر ↑"),
    "priceDown": ("Price ↓", "السعر ↓"),
    "oneToy": ("1 toy", "لعبة واحدة"),
    "toys": ("toys", "لعبة"),
    "apply": ("Apply", "تطبيق"),

    # -- checkout --------------------------------------------------------
    "coTitle": ("Almost there", "اقتربنا"),
    "whereTitle": ("Where's it going?", "إلى أين نوصلها؟"),
    "fullName": ("Full name", "الاسم الكامل"),
    "fullNamePh": ("Sam Rivera", "سامي الريان"),
    "phone": ("Phone", "الجوال"),
    "street": ("Street address", "العنوان"),
    "streetPh": ("18 Marbles Lane", "18 شارع الرخام"),
    "city": ("City", "المدينة"),
    "cityPh": ("Riyadh", "الرياض"),
    "postcode": ("Postcode", "الرمز البريدي"),
    "howFast": ("How fast?", "ما سرعة التوصيل؟"),
    "giftTitle": ("Gift wrap and a card — free", "تغليف وبطاقة — مجانًا"),
    "giftNote": ("Message on the card", "رسالة البطاقة"),
    "giftPh": (
        "Happy birthday, Noor! Build something enormous. — Auntie Sam",
        "كل عام وأنت بخير يا نور! ابنِ شيئًا ضخمًا. — خالتك سما",
    ),
    "payment": ("Payment", "الدفع"),
    "cardNumber": ("Card number", "رقم البطاقة"),
    "expiry": ("Expiry", "الانتهاء"),
    "cvc": ("CVC", "CVC"),
    "placeOrder": ("Place order", "تأكيد الطلب"),
    "coFoot1": ("No charge until it ships · 60-day returns", "لا خصم قبل الشحن · إرجاع 60 يومًا"),
    "coFoot2": ("You can edit the gift note after ordering", "يمكنك تعديل بطاقة الهدية بعد الطلب"),
    "demoPayNote": (
        "Demo shop — no card is charged and no card details are stored.",
        "متجر تجريبي — لا يتم خصم أي مبلغ ولا تُحفظ بيانات البطاقة.",
    ),

    # -- order placed ----------------------------------------------------
    "thanksTitle": ("Order placed — Happy is packing it now 📦", "تم الطلب — هابي يجهّزه الآن 📦"),
    "thanksBody": (
        "We've emailed nothing, because this is a demo. Your reference is below.",
        "لم نرسل أي بريد لأن هذا متجر تجريبي. رقم طلبك بالأسفل.",
    ),
    "reference": ("Reference", "رقم الطلب"),
    "backHome": ("Back to the shop", "العودة إلى المتجر"),
    "deliveringTo": ("Delivering to", "التوصيل إلى"),

    # -- misc ------------------------------------------------------------
    "freeOver": ("Free over", "مجاني فوق"),
    "backShop": ("← Shop", "→ التسوق"),
    "filters": ("Filters", "الفلاتر"),
    "freeShipOver": ("Free shipping over", "توصيل مجاني فوق"),
    "backTo": ("← Back to", "→ العودة إلى"),
    "inBoxSuffix": ("toys in the box", "لعبة في الصندوق"),
    "inBoxSuffixOne": ("toy in the box", "لعبة في الصندوق"),
    "pagination": ("Pages", "الصفحات"),
    "pagePrev": ("Previous", "السابق"),
    "pageNext": ("Next", "التالي"),
    "shownOf": ("shown", "معروضة"),
    "of": ("of", "من"),
    "addedSuffix": ("→ in the box 🎉", "→ في الصندوق 🎉"),
    "dStandard": ("Standard", "عادي"),
    "dNext": ("Next day", "اليوم التالي"),
    "dPick": ("Collect in store", "استلام من المتجر"),
    "dNextNote": ("Order before 4pm", "اطلب قبل 4 مساءً"),
    "dPickNote": ("Ready in 2 hours", "جاهز خلال ساعتين"),
    "dStandardNote": ("3–5 days, free over", "3–5 أيام، مجاني فوق"),
    "payCard": ("Card", "بطاقة"),
    "payApple": ("Apple Pay", "Apple Pay"),
    "payCod": ("Pay on delivery", "الدفع عند الاستلام"),

    # -- account / staff pages (not in the design; styled to match) -------
    "yourProfile": ("Your profile", "ملفك الشخصي"),
    "username": ("Username", "اسم المستخدم"),
    "email": ("Email", "البريد الإلكتروني"),
    "accountInfo": ("Account info", "معلومات الحساب"),
    "addProduct": ("Add a toy", "أضف لعبة"),
    "addProductBody": ("Put a new toy on the shelf.", "ضع لعبة جديدة على الرف."),
    "accountInfoBody": ("See the details on your account.", "اطّلع على تفاصيل حسابك."),
    "yourOrders": ("Your orders", "طلباتك"),
    "yourOrdersBody": ("Everything you've ordered from us.", "كل ما طلبته من متجرنا."),
    "noOrders": ("No orders yet.", "لا توجد طلبات بعد."),
    "save": ("Save", "حفظ"),
    "signUp": ("Sign up", "إنشاء حساب"),
    "needAccount": ("Need an account?", "ليس لديك حساب؟"),
    "haveAccount": ("Already have an account?", "لديك حساب؟"),
    "welcomeBack": ("Welcome back", "أهلًا بعودتك"),
    "joinUs": ("Join the toy box", "انضم إلى صندوق الألعاب"),
    "registerDone": ("You're in!", "تم تسجيلك!"),
    "registerDoneBody": ("Your account is ready. Sign in to start adding toys.", "حسابك جاهز. سجّل الدخول لتبدأ."),
    "badLogin": ("That username and password didn't match.", "اسم المستخدم أو كلمة المرور غير صحيحة."),

    # -- staff: categories and orders ---------------------------------------
    "manageCategories": ("Categories", "الفئات"),
    "manageCategoriesBody": ("Add, edit and reorder the shelves.", "أضف الفئات وعدّلها ورتّبها."),
    "addCategory": ("Add a category", "أضف فئة"),
    "editCategory": ("Edit category", "تعديل الفئة"),
    "edit": ("Edit", "تعديل"),
    "delete": ("Delete", "حذف"),
    "moveUp": ("Move up", "انقل للأعلى"),
    "moveDown": ("Move down", "انقل للأسفل"),
    "toysCount": ("toys", "ألعاب"),
    "categorySaved": ("Category saved.", "تم حفظ الفئة."),
    "categoryDeleted": ("Category deleted.", "تم حذف الفئة."),
    "categoryInUse": (
        "“{name}” still has toys on its shelf, so it can't be deleted. Move or remove them first.",
        "لا يمكن حذف «{name}» لأن عليها ألعابًا. انقلها أو احذفها أولًا.",
    ),
    "manageOrders": ("Manage orders", "إدارة الطلبات"),
    "manageOrdersBody": ("Track orders and move them along.", "تابع الطلبات وحدّث حالتها."),
    "orderStatus": ("Status", "الحالة"),
    "allStatuses": ("All statuses", "كل الحالات"),
    "customer": ("Customer", "العميل"),
    "date": ("Date", "التاريخ"),
    "updateStatus": ("Update status", "تحديث الحالة"),
    "statusSaved": ("Status updated.", "تم تحديث الحالة."),
    "statusChangedAt": ("Status changed", "تغيّرت الحالة"),
    "noMatchingOrders": ("No orders with that status.", "لا توجد طلبات بهذه الحالة."),
    "backToOrders": ("Back to", "العودة إلى"),
    "status_pending": ("Pending", "قيد الانتظار"),
    "status_confirmed": ("Confirmed", "تم التأكيد"),
    "status_packed": ("Packed", "تم التجهيز"),
    "status_shipped": ("Shipped", "تم الشحن"),
    "status_delivered": ("Delivered", "تم التسليم"),
    "status_cancelled": ("Cancelled", "أُلغي"),

    "footerRights": ("All rights reserved.", "جميع الحقوق محفوظة."),
    "footerBuilt": ("A Django demo shop by Abdulaziz Mohammad.", "متجر تجريبي بـ Django من عبدالعزيز محمد."),
}


def translations(lang):
    """Flatten STRINGS for a template: `{{ t.addToCart }}`."""
    index = 1 if lang == "ar" else 0
    return {key: pair[index] for key, pair in STRINGS.items()}


def direction(lang):
    return "rtl" if lang == "ar" else "ltr"
