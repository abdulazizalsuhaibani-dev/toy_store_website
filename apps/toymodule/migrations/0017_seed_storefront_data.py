"""Fill in the rows the new schema needs, and move products onto them.

Two jobs. First, seed the reference data the design specifies but which has no
sensible empty state: a shop with no currencies cannot print a price, and a
checkout with no delivery options cannot be completed.

Second, turn the free-text `Product.pcategory` string into a `Category` row.
The five canonical spellings come from the design (which took them from this
app's own views); anything else already in the column gets a category of its
own rather than being dropped on the floor, because a typo in that column is
still somebody's product.
"""

from django.db import migrations
from django.utils.text import slugify

# (code, label, symbol_ar, rate per USD, decimal places, is_base)
# Rates and decimal places are the design's `CURRENCIES` array verbatim. SAR is
# the base because that is the currency every template in this repo has printed
# next to `pprice` since the app was written.
CURRENCIES = [
    ("SAR", "SAR — Saudi riyal", "ر.س", "3.750000", 2, True),
    ("AED", "AED — UAE dirham", "د.إ", "3.672500", 2, False),
    ("QAR", "QAR — Qatari riyal", "ر.ق", "3.640000", 2, False),
    ("KWD", "KWD — Kuwaiti dinar", "د.ك", "0.306500", 3, False),
    ("BHD", "BHD — Bahraini dinar", "د.ب", "0.376000", 3, False),
    ("OMR", "OMR — Omani rial", "ر.ع", "0.384500", 3, False),
    ("USD", "USD — US dollar", "دولار", "1.000000", 2, False),
]

# Costs converted from the design's USD figures at the SAR peg and rounded to
# something a shop would actually print.
DELIVERY = [
    ("standard", "Standard", "عادي", "3–5 days, free over", "3–5 أيام، مجاني فوق", "18.50", "150.00"),
    ("next-day", "Next day", "اليوم التالي", "Order before 4pm", "اطلب قبل 4 مساءً", "26.00", None),
    ("collect", "Collect in store", "استلام من المتجر", "Ready in 2 hours", "جاهز خلال ساعتين", "0.00", None),
]

# name, name_ar, colour, glyph, blurb, blurb_ar
CATEGORIES = [
    (
        "Baby Toys",
        "ألعاب الصغار",
        "#FFC93C",
        "🧱",
        "First stacks, first sorts, and nothing small enough to swallow.",
        "أول برج، وأول تصنيف، ولا قطعة صغيرة تُبلع.",
    ),
    (
        "Cars and Bikes",
        "سيارات ودراجات",
        "#3FB8F5",
        "🚗",
        "Things with wheels, and the ramps to launch them off.",
        "كل ما له عجلات، والمنحدرات التي تنطلق منها.",
    ),
    (
        "Dolls and Playsets",
        "دمى وعوالم لعب",
        "#FF74B8",
        "🧸",
        "Characters, houses, and the stories kids build around them.",
        "شخصيات وبيوت وقصص يبنيها الأطفال حولها.",
    ),
    (
        "Outdoors",
        "ألعاب خارجية",
        "#3FD1A0",
        "🪁",
        "Kites, balls and bats — for the garden, the park, the beach.",
        "طائرات ورقية وكرات ومضارب — للحديقة والحوش والبحر.",
    ),
    (
        "Others",
        "منوعات",
        "#A78BFA",
        "🧩",
        "The odd ones out: kits, puzzles and one enormous marble run.",
        "الأشياء المختلفة: أطقم وألغاز ومسار رخام ضخم.",
    ),
]

FALLBACK_COLORS = ["#FFC93C", "#3FB8F5", "#FF74B8", "#3FD1A0", "#A78BFA", "#CDEBFB"]


def unique_slug(model, base, field="slug"):
    base = base or "item"
    slug, n = base, 2
    while model.objects.filter(**{field: slug}).exists():
        slug, n = f"{base}-{n}", n + 1
    return slug


def seed(apps, schema_editor):
    Currency = apps.get_model("toymodule", "Currency")
    DeliveryOption = apps.get_model("toymodule", "DeliveryOption")
    Category = apps.get_model("toymodule", "Category")
    Product = apps.get_model("toymodule", "Product")

    for order, (code, label, symbol, rate, dp, is_base) in enumerate(CURRENCIES):
        Currency.objects.update_or_create(
            code=code,
            defaults={
                "label": label,
                "symbol_ar": symbol,
                "rate": rate,
                "decimal_places": dp,
                "is_base": is_base,
                "sort_order": order,
            },
        )

    for order, (key, label, label_ar, note, note_ar, cost, free_over) in enumerate(DELIVERY):
        DeliveryOption.objects.update_or_create(
            key=key,
            defaults={
                "label": label,
                "label_ar": label_ar,
                "note": note,
                "note_ar": note_ar,
                "cost": cost,
                "free_over": free_over,
                "sort_order": order,
            },
        )

    by_name = {}
    for order, (name, name_ar, color, glyph, blurb, blurb_ar) in enumerate(CATEGORIES):
        cat, _ = Category.objects.update_or_create(
            name=name,
            defaults={
                "name_ar": name_ar,
                "slug": slugify(name),
                "color": color,
                "glyph": glyph,
                "blurb": blurb,
                "blurb_ar": blurb_ar,
                "sort_order": order,
            },
        )
        by_name[name.casefold()] = cat

    # Anything in pcategory that is not one of the five canonical spellings.
    extras = (
        Product.objects.exclude(pcategory="")
        .values_list("pcategory", flat=True)
        .distinct()
    )
    for raw in extras:
        if raw is None or raw.casefold() in by_name:
            continue
        name = raw.strip()
        if not name or name.casefold() in by_name:
            continue
        cat = Category.objects.create(
            name=name,
            slug=unique_slug(Category, slugify(name)),
            color=FALLBACK_COLORS[len(by_name) % len(FALLBACK_COLORS)],
            sort_order=100,
        )
        by_name[name.casefold()] = cat

    others = by_name["others"]
    for product in Product.objects.all():
        raw = (product.pcategory or "").strip().casefold()
        product.category = by_name.get(raw, others)
        if not product.slug:
            product.slug = unique_slug(Product, slugify(product.pname))
        product.save(update_fields=["category", "slug"])


def unseed(apps, schema_editor):
    """Put the category string back, so 0016 can drop the table underneath it."""
    Product = apps.get_model("toymodule", "Product")
    for product in Product.objects.select_related("category"):
        product.pcategory = product.category.name if product.category else "Others"
        product.category = None
        product.save(update_fields=["pcategory", "category"])

    apps.get_model("toymodule", "Category").objects.all().delete()
    apps.get_model("toymodule", "DeliveryOption").objects.all().delete()
    apps.get_model("toymodule", "Currency").objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [("toymodule", "0016_storefront_schema")]

    operations = [migrations.RunPython(seed, unseed)]
