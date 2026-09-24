"""Tests for the storefront.

Concentrated on the things the redesign introduced that could silently go
wrong: currency conversion (money the shopper sees), the cart and checkout
(money the shop takes), the filters (what the shopper is shown), and the
access rule on the order confirmation page.
"""

from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .models import Category, Currency, DeliveryOption, Order, Product
from .storefront import format_money


class CurrencyTests(TestCase):
    """Migration 0017 seeds these, so they are already present."""

    def test_base_currency_is_sar(self):
        base = Currency.objects.get(is_base=True)
        self.assertEqual(base.code, "SAR")

    def test_base_currency_converts_to_itself(self):
        sar = Currency.objects.get(code="SAR")
        self.assertEqual(sar.convert(Decimal("100")), Decimal("100.00"))

    def test_converts_to_usd_at_the_peg(self):
        usd = Currency.objects.get(code="USD")
        # SAR 150 / 3.75 = USD 40, the design's free-shipping threshold.
        self.assertEqual(usd.convert(Decimal("150")), Decimal("40.00"))

    def test_three_decimal_currency_keeps_its_precision(self):
        kwd = Currency.objects.get(code="KWD")
        self.assertEqual(kwd.decimal_places, 3)
        # SAR 150 = USD 40 = KWD 12.26.
        self.assertEqual(kwd.convert(Decimal("150")), Decimal("12.260"))

    def test_trailing_zeros_are_trimmed(self):
        sar = Currency.objects.get(code="SAR")
        self.assertEqual(format_money(Decimal("24.00"), sar, "en"), "SAR 24")
        self.assertEqual(format_money(Decimal("24.50"), sar, "en"), "SAR 24.5")

    def test_arabic_puts_the_symbol_after_the_number(self):
        sar = Currency.objects.get(code="SAR")
        self.assertEqual(format_money(Decimal("24"), sar, "ar"), "24 ر.س")

    def test_missing_currency_table_does_not_crash_formatting(self):
        # A half-migrated deploy should still serve a page.
        self.assertEqual(format_money(Decimal("24"), None, "en"), "24.00")


class CatalogueTests(TestCase):
    def setUp(self):
        self.baby = Category.objects.get(name="Baby Toys")
        self.outdoors = Category.objects.get(name="Outdoors")
        self.small = Product.objects.create(
            pname="Stacky", pprice=Decimal("40"), category=self.baby, age_min=3, age_max=6
        )
        self.big = Product.objects.create(
            pname="Mega Run", pprice=Decimal("200"), category=self.outdoors, age_min=6, age_max=10
        )

    def test_slug_is_generated_from_the_name(self):
        self.assertEqual(self.small.slug, "stacky")

    def test_duplicate_names_get_distinct_slugs(self):
        other = Product.objects.create(pname="Stacky", pprice=Decimal("10"), category=self.baby)
        self.assertNotEqual(other.slug, self.small.slug)

    def test_category_page_shows_only_its_own_products(self):
        response = self.client.get(reverse("category", args=[self.baby.slug]))
        self.assertContains(response, "Stacky")
        self.assertNotContains(response, "Mega Run")

    def test_age_filter_matches_ranges_that_overlap_the_band(self):
        # Stacky is 3-6 and Mega Run is 6-10: each appears under every band it touches.
        for band, present, absent in [
            ("3-5", ["Stacky"], ["Mega Run"]),
            ("6-8", ["Stacky", "Mega Run"], []),
            ("9-up", ["Mega Run"], ["Stacky"]),
            ("0-2", [], ["Stacky", "Mega Run"]),
        ]:
            response = self.client.get(reverse("shop"), {"age": band})
            for name in present:
                self.assertContains(response, name, msg_prefix=band)
            for name in absent:
                self.assertNotContains(response, name, msg_prefix=band)

    def test_a_toy_for_every_age_is_not_lost_from_the_filters(self):
        Product.objects.create(pname="Anything Ball", pprice=Decimal("10"), category=self.baby)  # default 3-10
        for band in ["3-5", "6-8", "9-up"]:
            self.assertContains(self.client.get(reverse("shop"), {"age": band}), "Anything Ball")

    def test_unknown_age_is_ignored(self):
        response = self.client.get(reverse("shop"), {"age": "banana"})
        self.assertContains(response, "Stacky")
        self.assertContains(response, "Mega Run")

    def test_price_band_filters(self):
        response = self.client.get(reverse("shop"), {"price": "high"})
        self.assertContains(response, "Mega Run")
        self.assertNotContains(response, "Stacky")

    def test_search_matches_the_arabic_name(self):
        self.small.pname_ar = "برج"
        self.small.save()
        response = self.client.get(reverse("search"), {"q": "برج"})
        self.assertContains(response, "Stacky")

    def test_unknown_sort_falls_back_instead_of_erroring(self):
        self.assertEqual(self.client.get(reverse("shop"), {"sort": "; drop table"}).status_code, 200)

    def test_legacy_category_url_redirects_permanently(self):
        response = self.client.get("/baby-toys")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], reverse("category", args=[self.baby.slug]))

    def test_product_detail_renders(self):
        response = self.client.get(reverse("product", args=[self.small.slug]))
        self.assertContains(response, "Stacky")


class LanguageAndCurrencyTests(TestCase):
    def test_language_toggle_switches_direction(self):
        self.client.post(reverse("set-language"), {"lang": "ar"})
        response = self.client.get(reverse("index"))
        self.assertContains(response, 'dir="rtl"')

    def test_language_toggle_rejects_an_unknown_language(self):
        self.client.post(reverse("set-language"), {"lang": "zz"})
        response = self.client.get(reverse("index"))
        self.assertContains(response, 'dir="ltr"')

    def test_currency_switch_changes_rendered_prices(self):
        Product.objects.create(
            pname="Stacky", pprice=Decimal("150"), category=Category.objects.get(name="Baby Toys")
        )
        self.assertContains(self.client.get(reverse("shop")), "SAR 150")
        self.client.post(reverse("set-currency"), {"currency": "USD"})
        self.assertContains(self.client.get(reverse("shop")), "USD 40")

    def test_toggle_is_post_only(self):
        self.assertEqual(self.client.get(reverse("set-language")).status_code, 405)

    def test_offsite_referer_is_not_followed(self):
        response = self.client.post(
            reverse("set-language"), {"lang": "ar"}, HTTP_REFERER="https://evil.example/steal"
        )
        self.assertEqual(response["Location"], reverse("index"))


class CartTests(TestCase):
    def setUp(self):
        self.toy = Product.objects.create(
            pname="Stacky", pprice=Decimal("40"), category=Category.objects.get(name="Baby Toys")
        )

    def test_adding_twice_increments_one_line(self):
        self.client.post(reverse("cart-add", args=[self.toy.pk]))
        self.client.post(reverse("cart-add", args=[self.toy.pk]), {"quantity": 2})
        response = self.client.get(reverse("cart"))
        self.assertEqual(response.context["count"], 3)
        self.assertEqual(len(response.context["items"]), 1)

    def test_decrementing_to_zero_removes_the_line(self):
        self.client.post(reverse("cart-add", args=[self.toy.pk]))
        item = self.client.get(reverse("cart")).context["items"][0]
        self.client.post(reverse("cart-update", args=[item.pk]), {"delta": "-1"})
        self.assertEqual(self.client.get(reverse("cart")).context["count"], 0)

    def test_shipping_is_free_over_the_threshold(self):
        self.client.post(reverse("cart-add", args=[self.toy.pk]), {"quantity": 4})  # SAR 160
        response = self.client.get(reverse("cart"))
        self.assertEqual(response.context["shipping"], Decimal("0"))

    def test_shipping_is_charged_under_the_threshold(self):
        self.client.post(reverse("cart-add", args=[self.toy.pk]))  # SAR 40
        self.assertEqual(self.client.get(reverse("cart")).context["shipping"], Decimal("18.50"))

    def test_a_visitor_who_only_browses_leaves_no_cart_row(self):
        self.client.get(reverse("index"))
        self.assertEqual(self.client.get(reverse("cart")).context["count"], 0)

    def test_cannot_touch_another_sessions_line(self):
        self.client.post(reverse("cart-add", args=[self.toy.pk]))
        item = self.client.get(reverse("cart")).context["items"][0]
        stranger = self.client_class()
        self.assertEqual(
            stranger.post(reverse("cart-update", args=[item.pk]), {"delta": "5"}).status_code, 404
        )


class CartClampTests(TestCase):
    def setUp(self):
        self.toy = Product.objects.create(
            pname="Stacky", pprice=Decimal("40"), category=Category.objects.get(name="Baby Toys")
        )

    def quantity(self):
        return self.client.get(reverse("cart")).context["count"]

    def test_add_clamps_a_huge_quantity(self):
        self.client.post(reverse("cart-add", args=[self.toy.pk]), {"quantity": "99999999999"})
        self.assertEqual(self.quantity(), 99)

    def test_adding_again_cannot_pass_the_ceiling(self):
        for _ in range(3):
            self.client.post(reverse("cart-add", args=[self.toy.pk]), {"quantity": "60"})
        self.assertEqual(self.quantity(), 99)

    def test_add_survives_a_non_numeric_quantity(self):
        self.client.post(reverse("cart-add", args=[self.toy.pk]), {"quantity": "lots"})
        self.assertEqual(self.quantity(), 1)

    def test_update_clamps_quantity_and_delta(self):
        self.client.post(reverse("cart-add", args=[self.toy.pk]))
        line = self.client.get(reverse("cart")).context["items"][0]
        self.client.post(reverse("cart-update", args=[line.pk]), {"quantity": "99999999999"})
        self.assertEqual(self.quantity(), 99)
        self.client.post(reverse("cart-update", args=[line.pk]), {"delta": "99999999999"})
        self.assertEqual(self.quantity(), 99)
        self.client.post(reverse("cart-update", args=[line.pk]), {"quantity": "lots"})
        self.assertEqual(self.quantity(), 99)


class CheckoutTests(TestCase):
    def setUp(self):
        self.toy = Product.objects.create(
            pname="Stacky", pprice=Decimal("40"), category=Category.objects.get(name="Baby Toys")
        )
        self.standard = DeliveryOption.objects.get(key="standard")
        self.client.post(reverse("cart-add", args=[self.toy.pk]), {"quantity": 2})  # SAR 80

    def address(self, **extra):
        data = {
            "full_name": "Sam Rivera",
            "phone": "0500000000",
            "street": "18 Marbles Lane",
            "city": "Riyadh",
            "postcode": "12345",
            "delivery_option": self.standard.pk,
            "payment_method": Order.Payment.CARD,
            "gift_wrap": "on",
            "gift_note": "Happy birthday!",
        }
        data.update(extra)
        return data

    def test_empty_cart_cannot_reach_checkout(self):
        empty = self.client_class()
        self.assertRedirects(empty.get(reverse("checkout")), reverse("cart"))

    def test_placing_an_order_records_the_totals(self):
        response = self.client.post(reverse("checkout"), self.address())
        order = Order.objects.get()
        self.assertRedirects(response, reverse("order-placed", args=[order.reference]))
        self.assertEqual(order.subtotal, Decimal("80"))
        self.assertEqual(order.shipping_cost, Decimal("18.50"))
        self.assertEqual(order.total, Decimal("98.50"))
        self.assertEqual(order.currency_code, "SAR")

    def test_order_lines_snapshot_name_and_price(self):
        self.client.post(reverse("checkout"), self.address())
        line = Order.objects.get().items.get()
        self.assertEqual(line.product_name, "Stacky")
        self.assertEqual(line.unit_price, Decimal("40"))
        self.toy.pname = "Renamed"
        self.toy.pprice = Decimal("999")
        self.toy.save()
        line.refresh_from_db()
        self.assertEqual(line.product_name, "Stacky")
        self.assertEqual(line.unit_price, Decimal("40"))

    def test_placing_an_order_empties_the_cart(self):
        self.client.post(reverse("checkout"), self.address())
        self.assertEqual(self.client.get(reverse("cart")).context["count"], 0)

    def test_an_invalid_address_does_not_create_an_order(self):
        response = self.client.post(reverse("checkout"), self.address(full_name=""))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.exists())
        self.assertEqual(self.client.get(reverse("cart")).context["count"], 2)

    def test_gift_note_is_dropped_when_wrapping_is_off(self):
        self.client.post(reverse("checkout"), self.address(gift_wrap="", gift_note="hello"))
        self.assertEqual(Order.objects.get().gift_note, "")

    def test_the_currency_shown_at_checkout_is_the_one_recorded(self):
        self.client.post(reverse("set-currency"), {"currency": "USD"})
        self.client.post(reverse("checkout"), self.address())
        self.assertEqual(Order.objects.get().currency_code, "USD")

    def test_confirmation_is_visible_to_the_session_that_placed_it(self):
        self.client.post(reverse("checkout"), self.address())
        order = Order.objects.get()
        self.assertContains(self.client.get(reverse("order-placed", args=[order.reference])), order.reference)

    def test_confirmation_is_not_visible_to_a_stranger(self):
        self.client.post(reverse("checkout"), self.address())
        order = Order.objects.get()
        stranger = self.client_class()
        self.assertRedirects(
            stranger.get(reverse("order-placed", args=[order.reference])), reverse("index")
        )

    def test_owner_can_reopen_their_order_from_a_new_session(self):
        User.objects.create_user("parent", password="not-a-real-password-123")
        self.client.post(reverse("login"), {"username": "parent", "password": "not-a-real-password-123"})
        self.client.post(reverse("cart-add", args=[self.toy.pk]))
        self.client.post(reverse("checkout"), self.address())
        order = Order.objects.get()

        later = self.client_class()
        later.post(reverse("login"), {"username": "parent", "password": "not-a-real-password-123"})
        self.assertContains(later.get(reverse("order-placed", args=[order.reference])), order.reference)


class AccountTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("parent", password="not-a-real-password-123")
        self.admin = User.objects.create_user("owner", password="not-a-real-password-123")
        self.admin.groups.add(Group.objects.get(name="Admin"))

    def test_dashboard_requires_sign_in(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

    def test_add_product_requires_sign_in(self):
        response = self.client.get(reverse("addProduct"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

    def test_customer_cannot_add_a_product(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("addProduct")).status_code, 403)
        self.assertEqual(self.client.post(reverse("addProduct"), {"pname": "Sneaky"}).status_code, 403)
        self.assertFalse(Product.objects.filter(pname="Sneaky").exists())

    def test_admin_can_open_add_product(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("addProduct")).status_code, 200)

    def test_signup_makes_a_customer_not_an_admin(self):
        self.client.post(
            reverse("register"),
            {"username": "newbie", "password1": "not-a-real-password-123", "password2": "not-a-real-password-123"},
        )
        newbie = User.objects.get(username="newbie")
        self.assertEqual(list(newbie.groups.values_list("name", flat=True)), ["Customer"])
        self.client.force_login(newbie)
        self.assertEqual(self.client.get(reverse("addProduct")).status_code, 403)

    def test_dashboard_shows_add_a_toy_only_to_admins(self):
        add_url = reverse("addProduct")
        self.client.force_login(self.user)
        self.assertNotContains(self.client.get(reverse("dashboard")), add_url)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("dashboard")), add_url)

    def test_signing_in_adopts_a_cart_built_while_signed_out(self):
        toy = Product.objects.create(
            pname="Stacky", pprice=Decimal("40"), category=Category.objects.get(name="Baby Toys")
        )
        self.client.post(reverse("cart-add", args=[toy.pk]))
        self.client.post(reverse("login"), {"username": "parent", "password": "not-a-real-password-123"})
        self.assertEqual(self.client.get(reverse("cart")).context["count"], 1)

    def test_login_honours_a_same_site_next(self):
        response = self.client.post(
            reverse("login") + "?next=/dashboard/orders",
            {"username": "parent", "password": "not-a-real-password-123"},
        )
        self.assertRedirects(response, "/dashboard/orders", fetch_redirect_response=False)

    def test_login_ignores_an_off_site_next(self):
        response = self.client.post(
            reverse("login") + "?next=https://evil.example/",
            {"username": "parent", "password": "not-a-real-password-123"},
        )
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)

    def test_logout_needs_a_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)
        self.client.post(reverse("logout"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_register_redirects_so_refresh_does_not_resubmit(self):
        response = self.client.post(
            reverse("register"),
            {"username": "newbie", "password1": "not-a-real-password-123", "password2": "not-a-real-password-123"},
        )
        self.assertRedirects(response, reverse("register-success"))
        self.assertTrue(User.objects.filter(username="newbie").exists())

    def test_add_product_rejects_an_inverted_age_range(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("addProduct"),
            {
                "pname": "Backwards",
                "pprice": "10",
                "category": Category.objects.get(name="Baby Toys").pk,
                "age_min": 8,
                "age_max": 3,
                "pieces": 1,
                "play_type": Product.PlayType.SOLO,
                "card_color": "#CDEBFB",
                "rating": "0",
                "review_count": 0,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Product.objects.filter(pname="Backwards").exists())


class SmokeTests(TestCase):
    """Every page renders with an empty database.

    A fresh clone has no products, and a page that only works once somebody has
    added one is a page nobody can debug.
    """

    def test_pages_render_without_any_products(self):
        for name in ["index", "shop", "search", "cart", "login", "register"]:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_healthz(self):
        self.assertEqual(self.client.get(reverse("healthz")).status_code, 200)


def currency_queries(captured):
    return [q for q in captured.captured_queries if 'FROM "toymodule_currency"' in q["sql"]]


class CurrencyQueryTests(TestCase):
    def test_shop_reads_the_currency_table_once(self):
        category = Category.objects.get(name="Baby Toys")
        for i in range(20):
            Product.objects.create(pname=f"Toy {i}", pprice=Decimal("40"), category=category)
        with CaptureQueriesContext(connection) as captured:
            self.client.get(reverse("shop"))
        self.assertEqual(len(currency_queries(captured)), 1)

    def test_receipt_reads_the_currency_table_once(self):
        toy = Product.objects.create(
            pname="Stacky", pprice=Decimal("40"), category=Category.objects.get(name="Baby Toys")
        )
        self.client.post(reverse("cart-add", args=[toy.pk]), {"quantity": 2})
        self.client.post(
            reverse("checkout"),
            {
                "full_name": "Sam Rivera",
                "phone": "0500000000",
                "street": "18 Marbles Lane",
                "city": "Riyadh",
                "postcode": "12345",
                "delivery_option": DeliveryOption.objects.get(key="standard").pk,
                "payment_method": Order.Payment.CARD,
            },
        )
        order = Order.objects.get()
        with CaptureQueriesContext(connection) as captured:
            self.client.get(reverse("order-placed", args=[order.reference]))
        self.assertEqual(len(currency_queries(captured)), 1)


class BaseCurrencyDerivedTests(TestCase):
    def test_hero_badge_follows_the_delivery_option(self):
        DeliveryOption.objects.filter(key="standard").update(free_over=Decimal("200"))
        self.assertContains(self.client.get(reverse("index")), "SAR 200")

    def test_hero_badge_hidden_when_nothing_ships_free(self):
        DeliveryOption.objects.update(free_over=None)
        self.assertNotContains(self.client.get(reverse("index")), "🚚")

    def test_price_bands_follow_the_base_currency(self):
        Currency.objects.filter(code="SAR").update(is_base=False)
        Currency.objects.filter(code="USD").update(is_base=True)
        category = Category.objects.get(name="Baby Toys")
        Product.objects.create(pname="Cheap", pprice=Decimal("15"), category=category)  # USD 15
        Product.objects.create(pname="Dear", pprice=Decimal("50"), category=category)  # USD 50
        response = self.client.get(reverse("shop"), {"price": "low"})
        names = [p.pname for p in response.context["products"]]
        self.assertEqual(names, ["Cheap"])


class ReverseSeedMigrationTests(TransactionTestCase):
    serialized_rollback = True

    """Reversing 0017 must survive a database that has taken an order."""

    def test_reverse_keeps_delivery_options_an_order_depends_on(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        executor = MigrationExecutor(connection)
        executor.migrate([("toymodule", "0017_seed_storefront_data")])
        apps = MigrationExecutor(connection).loader.project_state(
            [("toymodule", "0017_seed_storefront_data")]
        ).apps
        try:
            option = apps.get_model("toymodule", "DeliveryOption").objects.get(key="standard")
            apps.get_model("toymodule", "Order").objects.create(
                reference="HB-TESTTT",
                full_name="Sam",
                phone="1",
                street="s",
                city="c",
                delivery_option=option,
                subtotal=Decimal("10"),
                total=Decimal("10"),
            )
            executor = MigrationExecutor(connection)
            executor.migrate([("toymodule", "0016_storefront_schema")])  # would raise ProtectedError
        finally:
            call_command("migrate", "toymodule", verbosity=0)


class StaffTestCase(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user("parent", password="not-a-real-password-123")
        self.customer.groups.add(Group.objects.get(name="Customer"))
        self.admin = User.objects.create_user("owner", password="not-a-real-password-123")
        self.admin.groups.add(Group.objects.get(name="Admin"))


class CategoryManagementTests(StaffTestCase):
    def data(self, **extra):
        data = {"name": "Puzzles", "name_ar": "ألغاز", "slug": "", "blurb": "", "blurb_ar": "", "glyph": "🧩", "color": "#FFC93C"}
        data.update(extra)
        return data

    def test_only_admins_reach_the_screens(self):
        pk = Category.objects.first().pk
        urls = [reverse("category-list"), reverse("category-create"), reverse("category-edit", args=[pk])]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302, url)
        self.client.force_login(self.customer)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 403, url)
        self.client.force_login(self.admin)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_list_shows_product_counts(self):
        baby = Category.objects.get(name="Baby Toys")
        Product.objects.create(pname="Stacky", pprice=Decimal("40"), category=baby)
        self.client.force_login(self.admin)
        cats = self.client.get(reverse("category-list")).context["categories"]
        self.assertEqual({c.name: c.product_count for c in cats}["Baby Toys"], 1)

    def test_create_derives_the_slug_and_goes_last(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("category-create"), self.data())
        created = Category.objects.get(name="Puzzles")
        self.assertEqual(created.slug, "puzzles")
        self.assertEqual(list(Category.objects.all())[-1], created)

    def test_colliding_slug_is_a_form_error_not_a_500(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("category-create"), self.data(name="Other Outdoors", slug="outdoors"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("slug", response.context["form"].errors)

    def test_bad_colour_is_rejected(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("category-create"), self.data(color="red"))
        self.assertIn("color", response.context["form"].errors)
        self.assertFalse(Category.objects.filter(name="Puzzles").exists())

    def test_editing_keeps_the_url(self):
        outdoors = Category.objects.get(name="Outdoors")
        self.client.force_login(self.admin)
        self.client.post(reverse("category-edit", args=[outdoors.pk]), self.data(name="Great Outdoors", slug=outdoors.slug))
        outdoors.refresh_from_db()
        self.assertEqual((outdoors.name, outdoors.slug), ("Great Outdoors", "outdoors"))

    def test_a_category_with_toys_cannot_be_deleted(self):
        baby = Category.objects.get(name="Baby Toys")
        Product.objects.create(pname="Stacky", pprice=Decimal("40"), category=baby)
        self.client.force_login(self.admin)
        response = self.client.post(reverse("category-delete", args=[baby.pk]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Category.objects.filter(pk=baby.pk).exists())
        self.assertContains(response, "still has toys")

    def test_an_empty_category_can_be_deleted(self):
        empty = Category.objects.create(name="Empty", slug="empty")
        self.client.force_login(self.admin)
        self.client.post(reverse("category-delete", args=[empty.pk]))
        self.assertFalse(Category.objects.filter(pk=empty.pk).exists())

    def test_customers_cannot_change_categories(self):
        target = Category.objects.get(name="Outdoors")
        self.client.force_login(self.customer)
        self.assertEqual(self.client.post(reverse("category-delete", args=[target.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("category-move", args=[target.pk]), {"direction": "up"}).status_code, 403)
        self.assertTrue(Category.objects.filter(pk=target.pk).exists())

    def test_delete_and_move_refuse_get(self):
        pk = Category.objects.first().pk
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("category-delete", args=[pk])).status_code, 405)
        self.assertEqual(self.client.get(reverse("category-move", args=[pk])).status_code, 405)

    def test_move_swaps_with_the_neighbour_even_when_sort_orders_tie(self):
        Category.objects.update(sort_order=0)
        names = [c.name for c in Category.objects.all()]
        second = Category.objects.get(name=names[1])
        self.client.force_login(self.admin)
        self.client.post(reverse("category-move", args=[second.pk]), {"direction": "up"})
        after = [c.name for c in Category.objects.all()]
        self.assertEqual(after[:2], [names[1], names[0]])
        self.assertEqual(after[2:], names[2:])

    def test_moving_the_first_up_changes_nothing(self):
        names = [c.name for c in Category.objects.all()]
        self.client.force_login(self.admin)
        self.client.post(reverse("category-move", args=[Category.objects.first().pk]), {"direction": "up"})
        self.assertEqual([c.name for c in Category.objects.all()], names)


class OrderManagementTests(StaffTestCase):
    def make_order(self, reference="HB-AAAAAA", **extra):
        fields = dict(
            reference=reference, full_name="Sam Rivera", phone="050", street="18 Marbles Lane", city="Riyadh",
            subtotal=Decimal("75"), total=Decimal("75"), currency_code="USD", user=self.customer,
        )
        fields.update(extra)
        return Order.objects.create(**fields)

    def test_new_orders_start_pending(self):
        self.assertEqual(self.make_order().status, Order.Status.PENDING)

    def test_only_admins_reach_order_management(self):
        order = self.make_order()
        urls = [reverse("manage-orders"), reverse("manage-order", args=[order.reference])]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302, url)
        self.client.force_login(self.customer)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 403, url)
        self.client.force_login(self.admin)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_list_filters_by_status_newest_first(self):
        old = self.make_order("HB-OLDOLD", status=Order.Status.SHIPPED)
        new = self.make_order("HB-NEWNEW")
        self.client.force_login(self.admin)
        everything = self.client.get(reverse("manage-orders")).context["orders"]
        self.assertEqual([o.pk for o in everything], [new.pk, old.pk])
        shipped = self.client.get(reverse("manage-orders"), {"status": "shipped"}).context["orders"]
        self.assertEqual([o.pk for o in shipped], [old.pk])
        junk = self.client.get(reverse("manage-orders"), {"status": "nonsense"}).context["orders"]
        self.assertEqual(len(junk), 2)

    def test_detail_shows_the_total_in_the_recorded_currency(self):
        order = self.make_order()
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("manage-order", args=[order.reference])), "USD 20")

    def test_admin_changes_status_and_it_is_timestamped(self):
        order = self.make_order()
        self.assertIsNone(order.status_changed_at)
        self.client.force_login(self.admin)
        self.client.post(reverse("manage-order", args=[order.reference]), {"status": "packed"})
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PACKED)
        self.assertIsNotNone(order.status_changed_at)

    def test_resaving_the_same_status_does_not_move_the_timestamp(self):
        order = self.make_order()
        self.client.force_login(self.admin)
        self.client.post(reverse("manage-order", args=[order.reference]), {"status": "pending"})
        order.refresh_from_db()
        self.assertIsNone(order.status_changed_at)

    def test_customer_cannot_change_status(self):
        order = self.make_order()
        self.client.force_login(self.customer)
        self.assertEqual(self.client.post(reverse("manage-order", args=[order.reference]), {"status": "delivered"}).status_code, 403)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_owner_sees_their_status_and_a_stranger_does_not(self):
        order = self.make_order(status=Order.Status.SHIPPED)
        self.client.force_login(self.customer)
        self.assertContains(self.client.get(reverse("order-placed", args=[order.reference])), "Shipped")
        self.assertContains(self.client.get(reverse("orders")), "Shipped")
        stranger = User.objects.create_user("stranger", password="not-a-real-password-123")
        self.client.force_login(stranger)
        self.assertRedirects(self.client.get(reverse("order-placed", args=[order.reference])), reverse("index"))

    def test_status_is_translated(self):
        order = self.make_order(status=Order.Status.SHIPPED)
        self.client.force_login(self.customer)
        self.client.post(reverse("set-language"), {"lang": "ar"})
        self.assertContains(self.client.get(reverse("order-placed", args=[order.reference])), "تم الشحن")

    def test_dashboard_links_follow_the_role(self):
        self.client.force_login(self.customer)
        page = self.client.get(reverse("dashboard"))
        self.assertNotContains(page, reverse("category-list"))
        self.assertNotContains(page, reverse("manage-orders"))
        self.client.force_login(self.admin)
        page = self.client.get(reverse("dashboard"))
        self.assertContains(page, reverse("category-list"))
        self.assertContains(page, reverse("manage-orders"))
