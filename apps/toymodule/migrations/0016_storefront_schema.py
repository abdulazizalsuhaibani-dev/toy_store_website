"""Add the storefront schema the Happybox design needs.

Split into three migrations on purpose. This one only widens things: every new
column is nullable or defaulted, `slug` is not yet unique, and `pcategory` is
still there. 0017 fills in the data, and 0018 tightens what can only be
tightened once the data exists. Running them as one migration would fail on
any database that already has products in it.
"""

import decimal

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("toymodule", "0015_alter_product_pimage"),
    ]

    operations = [
        migrations.CreateModel(
            name="Category",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=60, unique=True)),
                ("name_ar", models.CharField(blank=True, max_length=60)),
                ("slug", models.SlugField(max_length=70, unique=True)),
                ("blurb", models.CharField(blank=True, max_length=200)),
                ("blurb_ar", models.CharField(blank=True, max_length=200)),
                ("color", models.CharField(default="#FFC93C", max_length=7)),
                ("glyph", models.CharField(blank=True, help_text="Emoji shown on the category card.", max_length=8)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
            ],
            options={"verbose_name_plural": "categories", "ordering": ["sort_order", "name"]},
        ),
        migrations.CreateModel(
            name="Currency",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=3, unique=True)),
                ("label", models.CharField(max_length=60)),
                ("symbol_ar", models.CharField(blank=True, max_length=12)),
                ("rate", models.DecimalField(decimal_places=6, help_text="Units per 1 USD.", max_digits=12)),
                ("decimal_places", models.PositiveSmallIntegerField(default=2)),
                ("is_base", models.BooleanField(default=False)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
            ],
            options={"verbose_name_plural": "currencies", "ordering": ["sort_order", "code"]},
        ),
        migrations.CreateModel(
            name="DeliveryOption",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.SlugField(max_length=30, unique=True)),
                ("label", models.CharField(max_length=60)),
                ("label_ar", models.CharField(blank=True, max_length=60)),
                ("note", models.CharField(blank=True, max_length=120)),
                ("note_ar", models.CharField(blank=True, max_length=120)),
                ("cost", models.DecimalField(decimal_places=2, default=decimal.Decimal("0"), max_digits=8)),
                ("free_over", models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
            ],
            options={"ordering": ["sort_order", "key"]},
        ),
        # -- Product ---------------------------------------------------
        migrations.AddField(
            model_name="product",
            name="slug",
            # Not unique yet: every existing row would collide on "".
            field=models.SlugField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="product",
            name="pname_ar",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="product",
            name="category",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="products",
                to="toymodule.category",
            ),
        ),
        migrations.AddField(model_name="product", name="blurb", field=models.TextField(blank=True)),
        migrations.AddField(model_name="product", name="blurb_ar", field=models.TextField(blank=True)),
        migrations.AddField(model_name="product", name="age_min", field=models.PositiveSmallIntegerField(default=3)),
        migrations.AddField(model_name="product", name="age_max", field=models.PositiveSmallIntegerField(default=10)),
        migrations.AddField(
            model_name="product",
            name="badge",
            field=models.CharField(
                blank=True,
                choices=[("", "No badge"), ("new", "New!"), ("best", "Best Seller!"), ("top", "Top Rated")],
                default="",
                max_length=8,
            ),
        ),
        migrations.AddField(model_name="product", name="pieces", field=models.PositiveIntegerField(default=1)),
        migrations.AddField(
            model_name="product",
            name="play_type",
            field=models.CharField(
                choices=[("solo", "Solo"), ("cuddle", "Cuddle"), ("together", "Together")],
                default="solo",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="rating",
            field=models.DecimalField(
                decimal_places=1,
                default=decimal.Decimal("0.0"),
                max_digits=2,
                validators=[
                    django.core.validators.MinValueValidator(decimal.Decimal("0")),
                    django.core.validators.MaxValueValidator(decimal.Decimal("5")),
                ],
            ),
        ),
        migrations.AddField(model_name="product", name="review_count", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(
            model_name="product", name="card_color", field=models.CharField(default="#CDEBFB", max_length=7)
        ),
        migrations.AddField(model_name="product", name="in_stock", field=models.BooleanField(default=True)),
        migrations.AddField(
            model_name="product",
            name="is_featured",
            field=models.BooleanField(
                default=False, help_text="Shown in the homepage 'Flying off the shelves' row."
            ),
        ),
        migrations.AddField(
            model_name="product", name="created_at", field=models.DateTimeField(auto_now_add=True, null=True)
        ),
        migrations.AlterField(
            model_name="product",
            name="pprice",
            # Was a FloatField. Prices are summed into order totals now, and
            # float dust in a total is a bug a customer can see.
            field=models.DecimalField(decimal_places=2, max_digits=10),
        ),
        migrations.AlterModelOptions(name="product", options={"ordering": ["pname"]}),
        # -- cart and orders -------------------------------------------
        migrations.CreateModel(
            name="Cart",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("session_key", models.CharField(db_index=True, max_length=40)),
                ("gift_wrap", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="carts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="CartItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField(default=1)),
                (
                    "cart",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="items", to="toymodule.cart"
                    ),
                ),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="toymodule.product")),
            ],
            options={"ordering": ["pk"], "unique_together": {("cart", "product")}},
        ),
        migrations.CreateModel(
            name="Order",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference", models.CharField(max_length=12, unique=True)),
                ("full_name", models.CharField(max_length=120)),
                ("phone", models.CharField(max_length=40)),
                ("street", models.CharField(max_length=200)),
                ("city", models.CharField(max_length=80)),
                ("postcode", models.CharField(blank=True, max_length=20)),
                (
                    "payment_method",
                    models.CharField(
                        choices=[("card", "Card"), ("apple", "Apple Pay"), ("cod", "Pay on delivery")],
                        default="card",
                        max_length=10,
                    ),
                ),
                ("gift_wrap", models.BooleanField(default=False)),
                ("gift_note", models.TextField(blank=True)),
                ("subtotal", models.DecimalField(decimal_places=2, max_digits=10)),
                ("shipping_cost", models.DecimalField(decimal_places=2, default=decimal.Decimal("0"), max_digits=8)),
                ("total", models.DecimalField(decimal_places=2, max_digits=10)),
                ("currency_code", models.CharField(default="SAR", max_length=3)),
                ("language", models.CharField(default="en", max_length=2)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "delivery_option",
                    models.ForeignKey(
                        null=True, on_delete=django.db.models.deletion.PROTECT, to="toymodule.deliveryoption"
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="orders",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="OrderItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("product_name", models.CharField(max_length=100)),
                ("unit_price", models.DecimalField(decimal_places=2, max_digits=10)),
                ("quantity", models.PositiveIntegerField(default=1)),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="items", to="toymodule.order"
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        null=True, on_delete=django.db.models.deletion.SET_NULL, to="toymodule.product"
                    ),
                ),
            ],
            options={"ordering": ["pk"]},
        ),
    ]
