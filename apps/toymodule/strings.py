"""UI copy, in English and Arabic.

A direct port of the design's `STR` table. It is a plain dict rather than a
gettext catalogue because the whole storefront is two languages chosen by a
toggle in the header, not by the browser's Accept-Language: there is no .po
workflow to feed, no translator in the loop, and the Arabic here is part of
the design rather than a translation of the English. Swap this for gettext (or
django-parler for the model-side strings) the day a third language appears.

Every value is a (English, Arabic) pair. `translations()` flattens it for a
template, so a page says `{{ t.addToCart }}` and never picks an index.

Two families are looked up by prefix rather than by name: `status_<value>`
(an order's status) and `err_<code>` (a form error, keyed by Django's error
code; see `forms.StorefrontForm`). A number followed by a noun goes through
`plural()` instead, because Arabic has five forms where English has two.
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
    "navMain": ("Main menu", "القائمة الرئيسية"),
    "menu": ("Menu", "القائمة"),
    "skipToContent": ("Skip to content", "انتقل إلى المحتوى"),
    "breadcrumb": ("You are here", "أنت هنا"),
    "pricesIn": ("Prices in", "الأسعار بـ"),
    "search": ("Search", "بحث"),
    "cart": ("Cart", "السلة"),
    "signIn": ("Sign in", "تسجيل الدخول"),
    "signOut": ("Sign out", "تسجيل الخروج"),
    "dashboard": ("Dashboard", "لوحة التحكم"),
    # "Jan Feb …" — split on spaces by the `when` tag.
    "months": (
        "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec",
        "يناير فبراير مارس أبريل مايو يونيو يوليو أغسطس سبتمبر أكتوبر نوفمبر ديسمبر",
    ),

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
        "كل قسم مصنّف حسب العمر، فما تراه يناسب طفلك.",
    ),
    "featTitle": ("Flying off the shelves", "الأكثر طلبًا هذا الأسبوع"),
    "trust1t": ("Age-checked, every toy", "عمر مناسب لكل لعبة، بعد مراجعة"),
    "trust1b": (
        "Ranges come from the maker plus our own play-testing.",
        "الأعمار من الشركة المصنّعة ومن تجاربنا في اللعب.",
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
    "trust4b": (
        "Call or chat 9–6, and a parent picks up.",
        "اتصل أو راسلنا من 9 إلى 6، ويرد عليك أحد الآباء أو الأمهات في فريقنا.",
    ),
    "ages": ("Ages", "الأعمار"),
    "each": ("each", "للواحدة"),
    "emptyShelf": ("No toys here yet", "لا توجد ألعاب بعد"),
    "emptyShelfBody": (
        "New toys land here soon. Peek at another shelf meanwhile.",
        "ألعاب جديدة في الطريق. ألقِ نظرة على رف آخر حتى ذلك الحين.",
    ),

    # -- listing ---------------------------------------------------------
    "crumbShop": ("Shop", "التسوق"),
    "ageLabel": ("Age", "العمر"),
    "add": ("Add", "أضف"),

    # -- detail ----------------------------------------------------------
    "inStock": ("In stock · ships tomorrow", "متوفر · يُشحن غدًا"),
    "outOfStock": ("Out of stock", "غير متوفر"),
    "onlyLeft": ("Only {n} left", "بقي {n} فقط"),
    "noReviews": ("No reviews yet", "لا توجد مراجعات بعد"),
    "soldOut": ("“{name}” is sold out.", "نفدت الكمية من «{name}»."),
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
        "نفدت الكمية من «{name}» للتو. لم يُخصم أي مبلغ؛ أزِل هذه اللعبة للمتابعة.",
    ),
    "onlyLeftCheckout": (
        "Only {n} of “{name}” left. Nothing was charged; lower the quantity to continue.",
        "لم يتبقَّ من «{name}» سوى {n}. لم يُخصم أي مبلغ؛ خفّض الكمية للمتابعة.",
    ),
    "ageRange": ("Age range", "الفئة العمرية"),
    "years": ("years", "سنوات"),
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
    "relatedTitle": ("Plays well with", "ألعاب تكمّلها"),
    "quantity": ("Quantity", "الكمية"),

    # -- cart ------------------------------------------------------------
    "cartTitle": ("Your toy box", "صندوق ألعابك"),
    "checkoutSteps": ("Checkout steps", "خطوات الشراء"),
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
    "shipping": ("Delivery", "التوصيل"),
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
    # Single words, split on spaces; each must match a toy name in its language.
    "searchSuggestions": ("blocks kite bear marble robot", "مكعبات طائرة دبدوب رخام روبوت"),
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
    "apply": ("Apply", "تطبيق"),

    # -- checkout --------------------------------------------------------
    "coTitle": ("Almost there", "خطوة أخيرة"),
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
    "expiry": ("Expiry", "تاريخ الانتهاء"),
    "cvc": ("CVC", "CVC"),
    "placeOrder": ("Place order", "تأكيد الطلب"),
    "coFoot1": ("No charge until it ships · 60-day returns", "لا خصم قبل الشحن · إرجاع 60 يومًا"),
    "coFoot2": ("You can edit the gift note after ordering", "يمكنك تعديل بطاقة الهدية بعد الطلب"),
    "demoPayNote": (
        "Demo shop — no card is charged and no card details are stored.",
        "متجر تجريبي — لا يتم خصم أي مبلغ ولا تُحفظ بيانات البطاقة.",
    ),
    "inTheBox": ("in the box", "في الصندوق"),

    # -- order placed ----------------------------------------------------
    "thanksTitle": ("Order placed — Happy is packing it now 📦", "وصلنا طلبك — هابي يجهّزه الآن 📦"),
    "thanksBody": (
        "We've emailed nothing, because this is a demo. Your reference is below.",
        "لم نرسل أي بريد لأن هذا متجر تجريبي. رقم طلبك بالأسفل.",
    ),
    "reference": ("Reference", "رقم الطلب"),
    "backHome": ("Back to the shop", "العودة إلى المتجر"),
    "deliveringTo": ("Delivering to", "التوصيل إلى"),

    # -- misc ------------------------------------------------------------
    "freeShipOver": ("Free delivery over", "توصيل مجاني فوق"),
    "backTo": ("← Back to", "→ العودة إلى"),
    "pagination": ("Pages", "الصفحات"),
    "pagePrev": ("Previous", "السابق"),
    "pageNext": ("Next", "التالي"),
    "shownOf": ("shown", "معروضة"),
    "of": ("of", "من"),
    "payCard": ("Card", "بطاقة"),
    "payApple": ("Apple Pay", "Apple Pay"),
    "payCod": ("Pay on delivery", "الدفع عند الاستلام"),
    "notFoundTitle": ("This toy wandered off", "هذه اللعبة ضاعت"),
    "notFoundBody": (
        "The page you were after isn't here. Maybe it's hiding under the sofa?",
        "الصفحة التي تبحث عنها غير موجودة. ربما تختبئ تحت الكنبة؟",
    ),

    # -- account / staff pages (not in the design; styled to match) -------
    "yourProfile": ("Your profile", "ملفك الشخصي"),
    "username": ("Username", "اسم المستخدم"),
    "usernameHelp": ("Letters, numbers and @ . + - _ only.", "حروف وأرقام والرموز ‎@ . + - _‎ فقط."),
    "email": ("Email", "البريد الإلكتروني"),
    "password": ("Password", "كلمة المرور"),
    "passwordHelp": (
        "At least 8 characters, not only numbers, and hard to guess.",
        "8 أحرف على الأقل، ليست أرقامًا فقط، ويصعب تخمينها.",
    ),
    "passwordAgain": ("Password again", "أعد كتابة كلمة المرور"),
    "passwordAgainHelp": ("Type it once more, just to be sure.", "اكتبها مرة أخرى للتأكد."),
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
    "joinUsBody": ("Save your address and track every order.", "احفظ عنوانك وتابع كل طلباتك."),
    "registerDone": ("You're in!", "تم تسجيلك!"),
    "registerDoneBody": ("Your account is ready. Sign in and start shopping.", "حسابك جاهز. سجّل الدخول وابدأ التسوق."),

    # -- staff: the add-a-toy and category forms ----------------------------
    "fieldName": ("Name", "الاسم"),
    "fieldNameAr": ("Name in Arabic", "الاسم بالعربية"),
    "fieldPhoto": ("Photo", "الصورة"),
    "fieldCurrency": ("Price currency", "عملة السعر"),
    "fieldCurrencyHelp": (
        "Type the price in this currency. It is stored in {code}, the shop's base currency.",
        "اكتب السعر بهذه العملة، وسيُحفظ بـ{code}، عملة المتجر الأساسية.",
    ),
    "priceInCode": ("Price ({code})", "السعر ({code})"),
    "fieldBlurb": ("Description", "الوصف"),
    "fieldBlurbAr": ("Description in Arabic", "الوصف بالعربية"),
    "fieldAgeMin": ("Youngest age", "أصغر عمر"),
    "fieldAgeMax": ("Oldest age", "أكبر عمر"),
    "fieldBadge": ("Badge", "الشارة"),
    "noBadge": ("No badge", "بلا شارة"),
    "fieldCardColor": ("Card colour", "لون البطاقة"),
    "fieldCardColorHelp": (
        "The colour behind the photo on the toy's card, e.g. #CDEBFB.",
        "اللون خلف الصورة في بطاقة اللعبة، مثل ‎#CDEBFB.",
    ),
    "fieldQuantity": ("Stock quantity", "الكمية في المخزون"),
    "fieldQuantityHelp": ("How many are in stock.", "عدد القطع المتوفرة."),
    "fieldFeatured": ("Featured", "لعبة مميّزة"),
    "fieldFeaturedHelp": (
        "Show this toy in the “Flying off the shelves” row on the homepage.",
        "اعرض هذه اللعبة في صف «الأكثر طلبًا هذا الأسبوع» في الصفحة الرئيسية.",
    ),
    "fieldSlug": ("Web address", "الرابط"),
    "fieldSlugHelp": ("Leave blank to use the name.", "اتركه فارغًا ليُبنى من الاسم."),
    "fieldGlyph": ("Emoji", "الرمز التعبيري"),
    "fieldGlyphHelp": ("Shown on the category card.", "يظهر على بطاقة القسم."),
    "fieldColor": ("Colour", "اللون"),

    # -- staff: categories and orders ---------------------------------------
    "manageCategories": ("Categories", "الأقسام"),
    "manageCategoriesBody": ("Add, edit and reorder the shelves.", "أضف الأقسام وعدّلها ورتّبها."),
    "addCategory": ("Add a category", "أضف قسمًا"),
    "editCategory": ("Edit category", "تعديل القسم"),
    "edit": ("Edit", "تعديل"),
    "delete": ("Delete", "حذف"),
    "moveUp": ("Move up", "انقل للأعلى"),
    "moveDown": ("Move down", "انقل للأسفل"),
    "categorySaved": ("Category saved.", "تم حفظ القسم."),
    "categoryDeleted": ("Category deleted.", "تم حذف القسم."),
    "categoryInUse": (
        "“{name}” still has toys on its shelf, so it can't be deleted. Move or remove them first.",
        "لا يمكن حذف قسم «{name}» لأن فيه ألعابًا. انقلها أو احذفها أولًا.",
    ),
    "manageOrders": ("Manage orders", "إدارة الطلبات"),
    "manageOrdersBody": ("Track orders and move them along.", "تابع الطلبات وحدّث حالتها."),
    "orderStatus": ("Status", "الحالة"),
    "allStatuses": ("All statuses", "كل الحالات"),
    "updateStatus": ("Update status", "تحديث الحالة"),
    "statusSaved": ("Status updated.", "تم تحديث الحالة."),
    "statusChangedAt": ("Status changed", "تغيّرت الحالة"),
    "noMatchingOrders": ("No orders with that status.", "لا توجد طلبات بهذه الحالة."),
    "status_pending": ("Pending", "قيد الانتظار"),
    "status_confirmed": ("Confirmed", "تم التأكيد"),
    "status_packed": ("Packed", "تم التجهيز"),
    "status_shipped": ("Shipped", "تم الشحن"),
    "status_delivered": ("Delivered", "تم التسليم"),
    "status_cancelled": ("Cancelled", "ملغى"),

    # -- form errors, keyed by Django's error code --------------------------
    # `err_<field>_<code>` wins over `err_<code>`. Placeholders are the
    # error's own params (`min_length`, `limit_value`).
    "err_required": ("Oops, this one's needed.", "عذرًا، هذه الخانة مطلوبة."),
    "err_invalid": ("That doesn't look quite right.", "يبدو أن هذه القيمة غير صحيحة."),
    "err_invalid_choice": ("Pick one of the options.", "اختر أحد الخيارات."),
    "err_min_value": ("Use {limit_value} or more.", "استخدم {limit_value} أو أكثر."),
    "err_max_value": ("Use {limit_value} or less.", "استخدم {limit_value} أو أقل."),
    "err_max_length": ("Keep it to {limit_value} characters.", "الحد الأقصى للأحرف: {limit_value}."),
    "err_invalid_image": ("That file isn't a picture we can open.", "لا يمكننا فتح هذا الملف كصورة."),
    "err_email_invalid": ("That email doesn't look quite right.", "يبدو أن البريد الإلكتروني غير صحيح."),
    "err_username_invalid": (
        "Use only letters, numbers and @ . + - _",
        "استخدم الحروف والأرقام والرموز ‎@ . + - _‎ فقط.",
    ),
    "err_username_unique": ("That username is taken. Try another?", "اسم المستخدم هذا محجوز. جرّب اسمًا آخر؟"),
    "err_invalid_login": ("That username and password didn't match.", "اسم المستخدم أو كلمة المرور غير صحيحة."),
    "err_inactive": ("This account is switched off.", "هذا الحساب موقوف."),
    "err_password_mismatch": ("The two passwords don't match.", "كلمتا المرور غير متطابقتين."),
    "err_password_too_short": ("Make it at least {min_length} characters.", "اجعلها {min_length} أحرف على الأقل."),
    "err_password_too_common": ("That password is too easy to guess.", "كلمة المرور هذه سهلة التخمين."),
    "err_password_entirely_numeric": ("Mix in some letters, not just numbers.", "أضف بعض الحروف، لا أرقامًا فقط."),
    "err_password_too_similar": (
        "That's too close to your username or email.",
        "كلمة المرور قريبة جدًا من اسم المستخدم أو البريد.",
    ),
    "err_age_order": ("The oldest age can't be below the youngest.", "لا يمكن أن يكون أكبر عمر أقل من أصغر عمر."),
    "err_color": ("Use a hex colour like #FFC93C.", "استخدم لونًا بصيغة ‎#FFC93C."),
    "err_slug_empty": (
        "We couldn't build a web address from that name; type one in.",
        "تعذّر بناء رابط من هذا الاسم؛ اكتب رابطًا بنفسك.",
    ),
    "err_slug_taken": ("Another category already uses this web address.", "هذا الرابط مستخدم لقسم آخر."),

    "footerRights": ("All rights reserved.", "جميع الحقوق محفوظة."),
    "footerBuilt": (
        "A Django demo shop by Abdulaziz Mohammad.",
        "متجر تجريبي مبني بـ Django، من تطوير عبدالعزيز محمد.",
    ),
}

# Counted nouns. English is (one, other). Arabic is (one, two, few, many,
# other), the CLDR categories: 1 and 2 are phrases with no digit ("لعبتان"),
# 3-10 take the plural, 11-99 the accusative singular, and 0 and round
# hundreds the genitive singular.
PLURALS = {
    "toy": (("toy", "toys"), ("لعبة واحدة", "لعبتان", "ألعاب", "لعبة", "لعبة")),
    "item": (("item", "items"), ("قطعة واحدة", "قطعتان", "قطع", "قطعة", "قطعة")),
    "order": (("order", "orders"), ("طلب واحد", "طلبان", "طلبات", "طلبًا", "طلب")),
    "review": (
        ("parent review", "parent reviews"),
        ("تقييم واحد من الأهل", "تقييمان من الأهل", "تقييمات من الأهل", "تقييمًا من الأهل", "تقييم من الأهل"),
    ),
}


def plural(noun, n, lang):
    """`n` and the right form of `noun`: "3 toys", "3 ألعاب", "لعبتان"."""
    english, arabic = PLURALS[noun]
    if lang != "ar":
        return f"{n} {english[0] if n == 1 else english[1]}"
    one, two, few, many, other = arabic
    if n == 1:
        return one
    if n == 2:
        return two
    if 3 <= n % 100 <= 10:
        return f"{n} {few}"
    if 11 <= n % 100 <= 99:
        return f"{n} {many}"
    return f"{n} {other}"


def translations(lang):
    """Flatten STRINGS for a template: `{{ t.addToCart }}`."""
    index = 1 if lang == "ar" else 0
    return {key: pair[index] for key, pair in STRINGS.items()}


def direction(lang):
    return "rtl" if lang == "ar" else "ltr"
