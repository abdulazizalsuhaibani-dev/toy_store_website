"""Storefront models.

The schema here follows the Happybox design (claude.ai/design project
56e1a170) rather than growing organically: every column below is something a
screen in that design actually renders. Where the design carried a value as a
hard-coded literal in its `CATS`/`PRODUCTS`/`CURRENCIES` arrays, it lives in a
column so the site can be run by a shop owner instead of a redeploy.

The one thing the design does *not* answer is what currency `Product.pprice`
is stored in. Its comment claims USD, but every template in this repo has
rendered `{{ p.pprice }} SAR` since the app was written, so SAR is what the
existing rows mean. `Currency.is_base` records which one that is and
`convert()` goes through it, so the design's USD-pegged rates transfer
verbatim and existing prices keep their meaning.
"""

from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    """A shelf in the shop.

    Replaces the free-text `Product.pcategory` string the app used to filter
    on. The design gives every category a colour, a glyph and a blurb, and
    those cannot live in a view that hardcodes `pcategory__exact`, so the
    category became a row. `name` stays the canonical English string the old
    column held ("Baby Toys", "Outdoors", ...) — the data migration that
    introduced this model keyed off exactly those values.
    """

    name = models.CharField(max_length=60, unique=True)
    name_ar = models.CharField(max_length=60, blank=True)
    slug = models.SlugField(max_length=70, unique=True)
    blurb = models.CharField(max_length=200, blank=True)
    blurb_ar = models.CharField(max_length=200, blank=True)
    # Card background on the homepage "Pick a playground" grid. Hex, because
    # the design's palette is per-category and not derivable from anything.
    color = models.CharField(max_length=7, default="#FFC93C")
    glyph = models.CharField(max_length=8, blank=True, help_text="Emoji shown on the category card.")
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def label(self, lang):
        return self.name_ar if lang == "ar" and self.name_ar else self.name

    def blurb_for(self, lang):
        return self.blurb_ar if lang == "ar" and self.blurb_ar else self.blurb


class Currency(models.Model):
    """One entry of the design's `CURRENCIES` array.

    `rate` is units per 1 USD, copied from the design. Conversion divides by
    the base currency's rate rather than assuming USD is the base, so the
    numbers stay the ones the design specified while `pprice` keeps meaning
    SAR. Gulf currencies are pegged to the dollar, so these are stable; add a
    non-pegged currency and this needs a live feed instead.
    """

    code = models.CharField(max_length=3, unique=True)
    label = models.CharField(max_length=60)
    symbol_ar = models.CharField(max_length=12, blank=True)
    rate = models.DecimalField(max_digits=12, decimal_places=6, help_text="Units per 1 USD.")
    decimal_places = models.PositiveSmallIntegerField(default=2)
    # Exactly one row should carry this: the currency `Product.pprice` is in.
    is_base = models.BooleanField(default=False)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name_plural = "currencies"
        ordering = ["sort_order", "code"]

    def __str__(self):
        return self.code

    # The base currency's rate, attached by `storefront.get_currencies()` so a
    # page full of prices does not ask the database for it once per price.
    # None means "not resolved": convert() then looks it up itself.
    base_rate = None

    def convert(self, amount):
        """Convert `amount`, expressed in the base currency, into this one."""
        base_rate = self.base_rate
        if base_rate is None:
            base = Currency.objects.filter(is_base=True).first()
            base_rate = base.rate if base else Decimal("1")
        if not base_rate:
            base_rate = Decimal("1")
        value = Decimal(amount) * (self.rate / base_rate)
        quantum = Decimal(1).scaleb(-self.decimal_places)
        return value.quantize(quantum, rounding=ROUND_HALF_UP)


class DeliveryOption(models.Model):
    """The three choices on the checkout's "How fast?" card."""

    key = models.SlugField(max_length=30, unique=True)
    label = models.CharField(max_length=60)
    label_ar = models.CharField(max_length=60, blank=True)
    note = models.CharField(max_length=120, blank=True)
    note_ar = models.CharField(max_length=120, blank=True)
    # In the base currency, like every other price in the schema.
    cost = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0"))
    # When set, the cost is waived on orders at or above this subtotal. The
    # design's free-shipping threshold, which the hero badge also quotes.
    free_over = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "key"]

    def __str__(self):
        return self.label

    def label_for(self, lang):
        return self.label_ar if lang == "ar" and self.label_ar else self.label

    def note_for(self, lang):
        return self.note_ar if lang == "ar" and self.note_ar else self.note

    def cost_for(self, subtotal):
        if self.free_over is not None and Decimal(subtotal) >= self.free_over:
            return Decimal("0")
        return self.cost


class Product(models.Model):
    """A toy.

    `pname`, `pimage` and `pprice` keep their original names: they are what
    fifteen migrations and every template already call them, and renaming them
    would be churn with no payoff. Everything added below comes from a product
    card or the product detail screen in the design.
    """

    class Badge(models.TextChoices):
        NONE = "", "No badge"
        NEW = "new", "New!"
        BEST_SELLER = "best", "Best Seller!"
        TOP_RATED = "top", "Top Rated"

    class PlayType(models.TextChoices):
        SOLO = "solo", "Solo"
        CUDDLE = "cuddle", "Cuddle"
        TOGETHER = "together", "Together"

    # Badge colours are fixed per badge in the design, so they are a lookup
    # rather than a column — a shop owner picking a badge should not also have
    # to pick a colour that the palette already decided.
    BADGE_COLORS = {Badge.NEW: "#FFC93C", Badge.BEST_SELLER: "#FF74B8", Badge.TOP_RATED: "#3FD1A0"}
    BADGE_AR = {Badge.NEW: "جديد!", Badge.BEST_SELLER: "الأكثر مبيعًا!", Badge.TOP_RATED: "الأعلى تقييمًا"}
    PLAY_AR = {PlayType.SOLO: "لعب فردي", PlayType.CUDDLE: "للعناق", PlayType.TOGETHER: "لعب جماعي"}

    pname = models.CharField(max_length=100)
    pname_ar = models.CharField(max_length=100, blank=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    pimage = models.ImageField(blank=True, null=True, default="picture.png")
    # Decimal, not the original float: prices are summed into order totals now,
    # and float dust in a total is a bug a customer can see.
    pprice = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="products", null=True, blank=True
    )

    blurb = models.TextField(blank=True)
    blurb_ar = models.TextField(blank=True)

    # The design writes age ranges as "3–6" strings and matches them exactly.
    # Two integers instead, so the filter bands can contain a range rather
    # than string-compare it, and so "ages 4+" is expressible later.
    age_min = models.PositiveSmallIntegerField(default=3)
    age_max = models.PositiveSmallIntegerField(default=10)

    badge = models.CharField(max_length=8, choices=Badge.choices, blank=True, default=Badge.NONE)
    pieces = models.PositiveIntegerField(default=1)
    play_type = models.CharField(max_length=10, choices=PlayType.choices, default=PlayType.SOLO)
    rating = models.DecimalField(
        max_digits=2,
        decimal_places=1,
        default=Decimal("0.0"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("5"))],
    )
    review_count = models.PositiveIntegerField(default=0)
    # Card background behind the product photo. Part of the design's rhythm:
    # adjacent cards deliberately do not share a colour.
    card_color = models.CharField(max_length=7, default="#CDEBFB")
    in_stock = models.BooleanField(default=True)
    is_featured = models.BooleanField(
        default=False, help_text="Shown in the homepage 'Flying off the shelves' row."
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        ordering = ["pname"]

    def __str__(self):
        return self.pname

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.pname) or "toy"
            slug, n = base, 2
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        super().save(*args, **kwargs)

    # -- display helpers -------------------------------------------------

    def label(self, lang):
        return self.pname_ar if lang == "ar" and self.pname_ar else self.pname

    def blurb_for(self, lang):
        return self.blurb_ar if lang == "ar" and self.blurb_ar else self.blurb

    @property
    def age_label(self):
        return f"{self.age_min}–{self.age_max}"

    @property
    def badge_color(self):
        return self.BADGE_COLORS.get(self.badge, "#FFC93C")

    def badge_label(self, lang):
        if not self.badge:
            return ""
        if lang == "ar":
            return self.BADGE_AR.get(self.badge, self.get_badge_display())
        return self.get_badge_display()

    def play_label(self, lang):
        if lang == "ar":
            return self.PLAY_AR.get(self.play_type, self.get_play_type_display())
        return self.get_play_type_display()


class Cart(models.Model):
    """A toy box in progress.

    Keyed by session so a signed-out shopper keeps their cart, with `user` set
    once they sign in. Rows rather than a session dict because the design's
    cart survives a device change for a signed-in shopper, and because an
    abandoned-cart row is worth something to a shop owner.
    """

    session_key = models.CharField(max_length=40, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name="carts")
    gift_wrap = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart {self.pk} ({self.session_key[:8]})"

    @property
    def count(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def subtotal(self):
        return sum((item.line_total for item in self.items.all()), Decimal("0"))


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = [("cart", "product")]
        ordering = ["pk"]

    def __str__(self):
        return f"{self.quantity} x {self.product.pname}"

    @property
    def line_total(self):
        return self.product.pprice * self.quantity


class Order(models.Model):
    """A placed order.

    Money is stored twice on purpose: in the base currency (what the shop
    banks) and as the currency code the shopper saw. Re-deriving the displayed
    total from today's rate would show a different number than the one they
    agreed to.
    """

    class Payment(models.TextChoices):
        CARD = "card", "Card"
        APPLE_PAY = "apple", "Apple Pay"
        ON_DELIVERY = "cod", "Pay on delivery"

    PAYMENT_AR = {Payment.CARD: "بطاقة", Payment.APPLE_PAY: "Apple Pay", Payment.ON_DELIVERY: "الدفع عند الاستلام"}

    reference = models.CharField(max_length=12, unique=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")

    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=40)
    street = models.CharField(max_length=200)
    city = models.CharField(max_length=80)
    postcode = models.CharField(max_length=20, blank=True)

    delivery_option = models.ForeignKey(DeliveryOption, on_delete=models.PROTECT, null=True)
    payment_method = models.CharField(max_length=10, choices=Payment.choices, default=Payment.CARD)
    gift_wrap = models.BooleanField(default=False)
    gift_note = models.TextField(blank=True)

    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_cost = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0"))
    total = models.DecimalField(max_digits=10, decimal_places=2)
    # What the shopper was looking at when they placed it.
    currency_code = models.CharField(max_length=3, default="SAR")
    language = models.CharField(max_length=2, default="en")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.reference


class OrderItem(models.Model):
    """A line on an order.

    Name and price are copied rather than joined: a product that is renamed or
    repriced next month must not rewrite what an old receipt says.
    """

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    product_name = models.CharField(max_length=100)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return f"{self.quantity} x {self.product_name}"

    @property
    def line_total(self):
        return self.unit_price * self.quantity
