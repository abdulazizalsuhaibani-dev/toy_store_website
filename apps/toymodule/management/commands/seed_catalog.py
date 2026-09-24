"""Load the design's eight demo toys.

The reference data (categories, currencies, delivery options) is created by
migration 0017, because the site cannot render a price or complete a checkout
without it. Products are different — they are somebody's shop inventory — so
they live here, behind an explicit command, and never run on deploy.

    python manage.py seed_catalog
    python manage.py seed_catalog --reset   # replace the demo rows

Products are matched by slug and updated in place, so running it twice does
not duplicate anything. It will not touch a product whose slug it does not
recognise, so it is safe to run against a shop that has real rows in it.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.toymodule.models import Category, Product

# Prices are the design's USD figures at the seeded SAR peg (x3.75), rounded to
# something a shop would print. Everything else is verbatim.
DEMO_PRODUCTS = [
    {
        "slug": "rainbow-stacker-tower",
        "pname": "Rainbow Stacker Tower",
        "pname_ar": "برج الحلقات الملوّن",
        "pprice": Decimal("89.00"),
        "category": "Baby Toys",
        "age_min": 3, "age_max": 6,
        "badge": Product.Badge.NEW,
        "card_color": "#CDEBFB",
        "rating": Decimal("4.8"), "review_count": 214,
        "pieces": 12, "play_type": Product.PlayType.SOLO,
        "is_featured": False,
        "blurb": (
            "Twelve chunky beechwood rings on a wobbly base. Toddlers stack it, knock it over, "
            "and stack it again — which is the entire point."
        ),
        "blurb_ar": (
            "اثنتا عشرة حلقة سميكة من خشب الزان على قاعدة متمايلة. يركّبها الصغار ثم يُسقطونها ثم "
            "يركّبونها من جديد، وهذا هو المقصود تمامًا."
        ),
    },
    {
        "slug": "bumble-the-bear-plush",
        "pname": "Bumble the Bear Plush",
        "pname_ar": "الدبدوب بامبل",
        "pprice": Decimal("119.00"),
        "category": "Dolls and Playsets",
        "age_min": 3, "age_max": 10,
        "badge": Product.Badge.BEST_SELLER,
        "card_color": "#FFDCE9",
        "rating": Decimal("4.9"), "review_count": 861,
        "pieces": 1, "play_type": Product.PlayType.CUDDLE,
        "is_featured": True,
        "blurb": (
            "Machine-washable, weighted paws, and a stitched face with no small parts. "
            "The one toy that comes back from every sleepover."
        ),
        "blurb_ar": (
            "قابل للغسل في الغسالة، أطراف موزونة، ووجه مطرَّز بلا أجزاء صغيرة. "
            "اللعبة الوحيدة التي تعود من كل مبيت."
        ),
    },
    {
        "slug": "whizzo-wind-up-robot",
        "pname": "Whizzo Wind-Up Robot",
        "pname_ar": "الروبوت ويزو",
        "pprice": Decimal("69.00"),
        "category": "Cars and Bikes",
        "age_min": 5, "age_max": 10,
        "badge": Product.Badge.NONE,
        "card_color": "#FFE8A8",
        "rating": Decimal("4.6"), "review_count": 128,
        "pieces": 1, "play_type": Product.PlayType.SOLO,
        "is_featured": False,
        "blurb": (
            "No batteries, ever. Wind the key and Whizzo marches, turns and falls over "
            "dramatically. Metal body, painted by hand."
        ),
        "blurb_ar": (
            "بلا بطاريات أبدًا. لُف المفتاح فيمشي ويزو ويستدير ويقع بشكل مسرحي. "
            "جسم معدني مدهون يدويًا."
        ),
    },
    {
        "slug": "cloud-kite",
        "pname": "Cloud Kite",
        "pname_ar": "طائرة السحاب الورقية",
        "pprice": Decimal("79.00"),
        "category": "Outdoors",
        "age_min": 5, "age_max": 10,
        "badge": Product.Badge.NEW,
        "card_color": "#D6F5E7",
        "rating": Decimal("4.5"), "review_count": 76,
        "pieces": 3, "play_type": Product.PlayType.TOGETHER,
        "is_featured": False,
        "blurb": (
            "Flies in a light breeze, which means it actually flies. Ripstop nylon, "
            "fibreglass spars, 40 m line on a chunky handle."
        ),
        "blurb_ar": (
            "تطير مع نسمة خفيفة، أي أنها تطير فعلاً. نايلون مقاوم للتمزق، أعمدة فايبرجلاس، "
            "و40 مترًا من الخيط على مقبض سميك."
        ),
    },
    {
        "slug": "giant-block-bucket-100-pieces",
        "pname": "Giant Block Bucket, 100 pieces",
        "pname_ar": "دلو المكعبات العملاق، 100 قطعة",
        "pprice": Decimal("169.00"),
        "category": "Baby Toys",
        "age_min": 3, "age_max": 8,
        "badge": Product.Badge.BEST_SELLER,
        "card_color": "#FFC0BB",
        "rating": Decimal("4.9"), "review_count": 1204,
        "pieces": 100, "play_type": Product.PlayType.TOGETHER,
        "is_featured": True,
        "blurb": (
            "A hundred oversized blocks in six colours, in a bucket that a four-year-old can "
            "carry. Compatible with the big-brick sets you already own."
        ),
        "blurb_ar": (
            "مئة مكعب كبير بستة ألوان، في دلو يستطيع طفل بعمر أربع سنوات حمله. "
            "متوافق مع أطقم المكعبات الكبيرة التي لديكم."
        ),
    },
    {
        "slug": "balloon-animal-kit",
        "pname": "Balloon Animal Kit",
        "pname_ar": "طقم حيوانات البالونات",
        "pprice": Decimal("52.00"),
        "category": "Outdoors",
        "age_min": 6, "age_max": 10,
        "badge": Product.Badge.NONE,
        "card_color": "#EDE7F5",
        "rating": Decimal("4.3"), "review_count": 94,
        "pieces": 60, "play_type": Product.PlayType.TOGETHER,
        "is_featured": False,
        "blurb": (
            "Sixty balloons, a hand pump, and an illustrated card deck of twelve animals "
            "from easy dog to ambitious flamingo."
        ),
        "blurb_ar": (
            "ستون بالونًا ومنفاخ يدوي ومجموعة بطاقات مرسومة لاثني عشر حيوانًا، "
            "من كلب سهل إلى فلامنغو طموح."
        ),
    },
    {
        "slug": "squishy-snail-family",
        "pname": "Squishy Snail Family",
        "pname_ar": "عائلة الحلزون الطرية",
        "pprice": Decimal("59.00"),
        "category": "Baby Toys",
        "age_min": 3, "age_max": 6,
        "badge": Product.Badge.NONE,
        "card_color": "#FFDCE9",
        "rating": Decimal("4.7"), "review_count": 152,
        "pieces": 4, "play_type": Product.PlayType.SOLO,
        "is_featured": True,
        "blurb": (
            "Four snails in nesting sizes, slow-rise foam, no seams to split. "
            "Quietly excellent for fidgety hands in the car."
        ),
        "blurb_ar": (
            "أربعة حلزونات بمقاسات متداخلة، إسفنج بطيء الارتداد، بلا خيوط تتفكك. "
            "ممتازة بهدوء للأيدي القلقة في السيارة."
        ),
    },
    {
        "slug": "marble-run-mega-set",
        "pname": "Marble Run Mega Set",
        "pname_ar": "طقم مسار الرخام الضخم",
        "pprice": Decimal("219.00"),
        "category": "Others",
        "age_min": 6, "age_max": 10,
        "badge": Product.Badge.TOP_RATED,
        "card_color": "#CDEBFB",
        "rating": Decimal("4.8"), "review_count": 433,
        "pieces": 142, "play_type": Product.PlayType.TOGETHER,
        "is_featured": True,
        "blurb": (
            "142 pieces, forty marbles, and a booklet of eight builds — then they stop using "
            "the booklet, which is when it gets good."
        ),
        "blurb_ar": (
            "142 قطعة وأربعون كرة رخام وكتيّب بثمانية تصاميم — ثم يتوقفون عن الكتيّب، "
            "وهنا يبدأ المرح."
        ),
    },
]


class Command(BaseCommand):
    help = "Load the eight demo toys from the Happybox design."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete the demo toys first, discarding any local edits to them.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        slugs = [row["slug"] for row in DEMO_PRODUCTS]

        if options["reset"]:
            deleted, _ = Product.objects.filter(slug__in=slugs).delete()
            self.stdout.write(f"Removed {deleted} demo row(s).")

        categories = {c.name: c for c in Category.objects.all()}
        missing = {row["category"] for row in DEMO_PRODUCTS} - set(categories)
        if missing:
            raise CommandError(
                "Missing categories: "
                + ", ".join(sorted(missing))
                + ". Run `python manage.py migrate` first."
            )

        created = updated = 0
        for row in DEMO_PRODUCTS:
            fields = dict(row)
            slug = fields.pop("slug")
            fields["category"] = categories[fields.pop("category")]
            _, was_created = Product.objects.update_or_create(slug=slug, defaults=fields)
            created, updated = (created + 1, updated) if was_created else (created, updated + 1)

        self.stdout.write(
            self.style.SUCCESS(f"Catalogue seeded: {created} created, {updated} updated.")
        )
        self.stdout.write("Photos are not seeded — add them in the admin or via /addProduct.")
