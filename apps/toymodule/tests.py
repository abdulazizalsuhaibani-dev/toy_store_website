"""Tests for the storefront.

Concentrated on the things the redesign introduced that could silently go
wrong: currency conversion (money the shopper sees), the cart and checkout
(money the shop takes), the filters (what the shopper is shown), and the
access rule on the order confirmation page.
"""

import re
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.template.loader import render_to_string
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils.html import escape

from .models import Category, Currency, DeliveryOption, Order, Product
from .storefront import format_money
from .strings import STRINGS, plural, translations


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
        # Plenty in stock, so the 99 ceiling is what binds rather than the shelf.
        self.toy = Product.objects.create(
            pname="Stacky", pprice=Decimal("40"), category=Category.objects.get(name="Baby Toys"), quantity=500
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


class AddToyFormTests(StaffTestCase):
    def data(self, **extra):
        data = {
            "pname": "Rocket",
            "pname_ar": "",
            "currency": Currency.objects.get(code="SAR").pk,
            "pprice": "75",
            "category": Category.objects.get(name="Baby Toys").pk,
            "blurb": "",
            "blurb_ar": "",
            "age_min": 3,
            "age_max": 8,
            "pieces": 1,
            "play_type": Product.PlayType.SOLO,
            "card_color": "#CDEBFB",
            "quantity": 7,
        }
        data.update(extra)
        return data

    def add(self, **extra):
        self.client.force_login(self.admin)
        return self.client.post(reverse("addProduct"), self.data(**extra))

    def test_currency_defaults_to_the_base_currency(self):
        self.client.force_login(self.admin)
        form = self.client.get(reverse("addProduct")).context["form"]
        self.assertEqual(form.fields["currency"].initial.code, "SAR")

    def test_price_in_the_base_currency_is_stored_as_typed(self):
        self.add()
        self.assertEqual(Product.objects.get(pname="Rocket").pprice, Decimal("75.00"))

    def test_price_in_another_currency_is_converted_to_the_base(self):
        # USD 20 at the 3.75 peg is SAR 75.
        self.add(currency=Currency.objects.get(code="USD").pk, pprice="20")
        self.assertEqual(Product.objects.get(pname="Rocket").pprice, Decimal("75.00"))

    def test_three_decimal_currency_converts_and_rounds_to_two_places(self):
        # KWD 12.26 is about SAR 150 (0.3065 KWD per USD, 3.75 SAR per USD).
        self.add(currency=Currency.objects.get(code="KWD").pk, pprice="12.26")
        self.assertEqual(Product.objects.get(pname="Rocket").pprice, Decimal("150.00"))

    def test_to_base_undoes_convert(self):
        for code in ["USD", "AED", "KWD"]:
            currency = Currency.objects.get(code=code)
            self.assertEqual(currency.to_base(currency.convert(Decimal("150"))), Decimal("150.00"), code)

    def test_ratings_cannot_be_typed_in(self):
        self.client.force_login(self.admin)
        form = self.client.get(reverse("addProduct")).context["form"]
        self.assertNotIn("rating", form.fields)
        self.assertNotIn("review_count", form.fields)
        self.add(rating="5.0", review_count=9999)
        toy = Product.objects.get(pname="Rocket")
        self.assertEqual((toy.rating, toy.review_count), (Decimal("0.0"), 0))

    def test_quantity_is_saved(self):
        self.add()
        self.assertEqual(Product.objects.get(pname="Rocket").quantity, 7)

    def test_a_toy_with_no_reviews_says_so(self):
        toy = Product.objects.create(pname="Fresh", pprice=Decimal("10"), category=Category.objects.first())
        self.assertContains(self.client.get(reverse("product", args=[toy.slug])), "No reviews yet")

    def test_popular_sort_leads_with_featured_toys(self):
        baby = Category.objects.get(name="Baby Toys")
        Product.objects.create(pname="Aardvark", pprice=Decimal("10"), category=baby, review_count=900)
        star = Product.objects.create(pname="Zebra", pprice=Decimal("10"), category=baby, is_featured=True)
        names = [p.pname for p in self.client.get(reverse("shop")).context["products"]]
        self.assertEqual(names[0], star.pname)


class StockTests(TestCase):
    def setUp(self):
        self.baby = Category.objects.get(name="Baby Toys")
        self.toy = Product.objects.create(pname="Stacky", pprice=Decimal("40"), category=self.baby, quantity=3)

    def cart_count(self, client=None):
        return (client or self.client).get(reverse("cart")).context["count"]

    def address(self):
        return {
            "full_name": "Sam Rivera",
            "phone": "0500000000",
            "street": "18 Marbles Lane",
            "city": "Riyadh",
            "postcode": "12345",
            "delivery_option": DeliveryOption.objects.get(key="standard").pk,
            "payment_method": Order.Payment.CARD,
        }

    def test_in_stock_follows_quantity(self):
        self.assertTrue(self.toy.in_stock)
        self.toy.quantity = 0
        self.assertFalse(self.toy.in_stock)

    def test_low_stock_is_flagged_on_the_product_page(self):
        response = self.client.get(reverse("product", args=[self.toy.slug]))
        self.assertContains(response, "Only 3 left")
        self.assertContains(response, 'max="3"')

    def test_cannot_add_more_than_is_in_stock(self):
        response = self.client.post(reverse("cart-add", args=[self.toy.pk]), {"quantity": "50", "next": "cart"}, follow=True)
        self.assertEqual(self.cart_count(), 3)
        self.assertContains(response, "Only 3 of")

    def test_adding_again_cannot_pass_the_stock(self):
        for _ in range(3):
            self.client.post(reverse("cart-add", args=[self.toy.pk]), {"quantity": "2"})
        self.assertEqual(self.cart_count(), 3)

    def test_a_sold_out_toy_cannot_be_added(self):
        self.toy.quantity = 0
        self.toy.save()
        response = self.client.post(reverse("cart-add", args=[self.toy.pk]), {"next": "cart"}, follow=True)
        self.assertEqual(self.cart_count(), 0)
        self.assertContains(response, "sold out")

    def test_update_cannot_raise_a_line_past_the_stock(self):
        self.client.post(reverse("cart-add", args=[self.toy.pk]))
        line = self.client.get(reverse("cart")).context["items"][0]
        self.client.post(reverse("cart-update", args=[line.pk]), {"delta": "10"})
        self.assertEqual(self.cart_count(), 3)
        self.client.post(reverse("cart-update", args=[line.pk]), {"quantity": "10"})
        self.assertEqual(self.cart_count(), 3)

    def test_checkout_takes_the_stock(self):
        self.client.post(reverse("cart-add", args=[self.toy.pk]), {"quantity": "2"})
        self.client.post(reverse("checkout"), self.address())
        self.toy.refresh_from_db()
        self.assertEqual(self.toy.quantity, 1)
        self.assertEqual(Order.objects.count(), 1)

    def test_checking_out_the_last_one_sells_out_the_toy(self):
        self.toy.quantity = 1
        self.toy.save()
        self.client.post(reverse("cart-add", args=[self.toy.pk]))
        self.client.post(reverse("checkout"), self.address())
        self.toy.refresh_from_db()
        self.assertEqual(self.toy.quantity, 0)
        self.assertFalse(self.toy.in_stock)

    def test_second_checkout_of_the_last_one_is_rejected(self):
        # Both shoppers put the last toy in their carts while one was on the shelf.
        self.toy.quantity = 1
        self.toy.save()
        first, second = self.client_class(), self.client_class()
        for shopper in (first, second):
            shopper.post(reverse("cart-add", args=[self.toy.pk]))
        first.post(reverse("checkout"), self.address())
        response = second.post(reverse("checkout"), self.address(), follow=True)
        self.assertEqual(Order.objects.count(), 1)
        self.toy.refresh_from_db()
        self.assertEqual(self.toy.quantity, 0)
        self.assertContains(response, "Nothing was charged")

    def test_stock_that_dropped_after_the_cart_page_rejects_the_post(self):
        self.client.post(reverse("cart-add", args=[self.toy.pk]), {"quantity": "3"})
        Product.objects.filter(pk=self.toy.pk).update(quantity=1)
        response = self.client.post(reverse("checkout"), self.address(), follow=True)
        self.assertEqual(Order.objects.count(), 0)
        self.assertContains(response, "Only 1 of")
        self.toy.refresh_from_db()
        self.assertEqual(self.toy.quantity, 1)

    def test_a_short_line_rolls_back_the_others(self):
        other = Product.objects.create(pname="Blocky", pprice=Decimal("20"), category=self.baby, quantity=5)
        self.client.post(reverse("cart-add", args=[other.pk]), {"quantity": "2"})
        self.client.post(reverse("cart-add", args=[self.toy.pk]), {"quantity": "3"})
        Product.objects.filter(pk=self.toy.pk).update(quantity=0)
        self.client.post(reverse("checkout"), self.address())
        other.refresh_from_db()
        self.assertEqual(other.quantity, 5)
        self.assertEqual(Order.objects.count(), 0)

    def test_checkout_page_sends_a_short_cart_back(self):
        self.client.post(reverse("cart-add", args=[self.toy.pk]), {"quantity": "3"})
        Product.objects.filter(pk=self.toy.pk).update(quantity=2)
        self.assertRedirects(self.client.get(reverse("checkout")), reverse("cart"))


class QuantityMigrationTests(TransactionTestCase):
    serialized_rollback = True

    def test_stock_flag_becomes_a_count(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        MigrationExecutor(connection).migrate([("toymodule", "0020_order_status")])
        try:
            apps = MigrationExecutor(connection).loader.project_state([("toymodule", "0020_order_status")]).apps
            Historic = apps.get_model("toymodule", "Product")
            Historic.objects.create(pname="Has", slug="has", pprice=Decimal("1"), in_stock=True)
            Historic.objects.create(pname="Gone", slug="gone", pprice=Decimal("1"), in_stock=False)
            MigrationExecutor(connection).migrate([("toymodule", "0021_product_quantity")])
            self.assertEqual(Product.objects.get(slug="has").quantity, 10)
            self.assertEqual(Product.objects.get(slug="gone").quantity, 0)
        finally:
            call_command("migrate", "toymodule", verbosity=0)


class PaginationTests(TestCase):
    def setUp(self):
        self.baby = Category.objects.get(name="Baby Toys")
        self.outdoors = Category.objects.get(name="Outdoors")
        for i in range(30):
            Product.objects.create(
                pname=f"Toy {i:02d}", pprice=Decimal("10"), category=self.baby if i < 25 else self.outdoors
            )

    def names(self, response):
        return [p.pname for p in response.context["products"]]

    def test_shop_shows_a_page_at_a_time(self):
        sizes = [len(self.client.get(reverse("shop"), {"page": n}).context["products"]) for n in (1, 2, 3)]
        self.assertEqual(sizes, [12, 12, 6])

    def test_pages_do_not_overlap(self):
        seen = []
        for n in (1, 2, 3):
            seen += self.names(self.client.get(reverse("shop"), {"page": n}))
        self.assertEqual(len(seen), 30)
        self.assertEqual(len(set(seen)), 30)

    def test_junk_and_out_of_range_pages_do_not_error(self):
        self.assertEqual(self.client.get(reverse("shop"), {"page": "abc"}).context["products"].number, 1)
        self.assertEqual(self.client.get(reverse("shop"), {"page": "999"}).context["products"].number, 3)
        self.assertEqual(self.client.get(reverse("shop"), {"page": "-4"}).status_code, 200)

    def test_counter_shows_matches_against_the_whole_shelf(self):
        response = self.client.get(reverse("shop"), {"page": 2})
        self.assertContains(response, "30 of 30 shown")

    def test_category_page_is_paginated(self):
        response = self.client.get(reverse("category", args=[self.baby.slug]))
        self.assertEqual(len(response.context["products"]), 12)
        self.assertEqual(response.context["products"].paginator.count, 25)

    def test_search_is_paginated_and_counts_all_matches(self):
        response = self.client.get(reverse("search"), {"q": "Toy", "page": 3})
        self.assertEqual(len(response.context["products"]), 6)
        self.assertContains(response, "30 toys")

    def test_pager_links_keep_the_filters_and_filters_drop_the_page(self):
        response = self.client.get(reverse("shop"), {"sort": "price_asc", "page": 2})
        self.assertContains(response, "?sort=price_asc&amp;page=3")
        self.assertContains(response, 'rel="prev"')
        # The sort pills must not carry page=2 into a different ordering.
        self.assertContains(response, 'href="?sort=popular"')
        self.assertContains(response, 'href="?sort=price_desc"')

    def test_pager_is_hidden_when_one_page_is_enough(self):
        Product.objects.filter(category=self.baby).delete()
        self.assertNotContains(self.client.get(reverse("shop")), 'aria-label="Pages"')

    def test_long_catalogues_get_an_elided_pager(self):
        category = self.baby
        for i in range(30, 300):
            Product.objects.create(pname=f"Toy {i}", pprice=Decimal("10"), category=category)
        page = self.client.get(reverse("shop"), {"page": 12}).context["products"]
        self.assertIn(page.paginator.ELLIPSIS, page.elided)
        self.assertLess(len(page.elided), 12)

    def test_prices_still_cost_one_currency_query_per_page(self):
        with CaptureQueriesContext(connection) as captured:
            self.client.get(reverse("shop"))
        self.assertEqual(len(currency_queries(captured)), 1)

    def test_arabic_pager_renders(self):
        self.client.post(reverse("set-language"), {"lang": "ar"})
        self.assertContains(self.client.get(reverse("shop"), {"page": 2}), "التالي")


class HomepageTests(TestCase):
    def test_the_birthday_box_promo_is_gone(self):
        for lang in ("en", "ar"):
            self.client.post(reverse("set-language"), {"lang": lang})
            response = self.client.get(reverse("index"))
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, "Birthday box")
            self.assertNotContains(response, "صندوق أعياد الميلاد")


class HeaderTests(TestCase):
    """The site header: explicit regions, and no filters posing as navigation."""

    def header(self, response):
        html = response.content.decode()
        return html[html.index('<header class="hb-header">'):html.index("</header>")]

    def test_main_nav_is_home_and_shop_only(self):
        header = self.header(self.client.get(reverse("index")))
        nav = header[header.index(f'aria-label="{translations("en")["navMain"]}"'):]
        nav = nav[:nav.index("</nav>")]
        self.assertIn(f'href="{reverse("index")}"', nav)
        self.assertIn(f'href="{reverse("shop")}"', nav)
        self.assertFalse("?age=" in header)
        self.assertFalse("?sort=price_desc" in header)

    def test_regions_sit_inside_a_collapsible_menu(self):
        header = self.header(self.client.get(reverse("index")))
        menu = header[header.index('<details class="hb-menu">'):header.index("</details>")]
        for region in (f'aria-label="{translations("en")["navMain"]}"', 'class="hb-utility"', 'class="hb-account"'):
            with self.subTest(region=region):
                self.assertTrue(region in menu, region)
        for control in (reverse("set-language"), reverse("set-currency"), reverse("search")):
            with self.subTest(control=control):
                self.assertTrue(control in menu, control)
        # The cart stays visible at every width, so it is outside the menu.
        self.assertNotIn(reverse("cart"), menu)
        self.assertIn(reverse("cart"), header)

    def test_menu_toggle_is_translated(self):
        for lang, word in (("en", "Menu"), ("ar", "القائمة")):
            self.client.post(reverse("set-language"), {"lang": lang})
            header = self.header(self.client.get(reverse("index")))
            summary = header[header.index("<summary"):header.index("</summary>")]
            with self.subTest(lang=lang):
                self.assertIn(word, summary)

    def test_account_links_for_a_guest(self):
        header = self.header(self.client.get(reverse("index")))
        self.assertIn(reverse("login"), header)
        self.assertNotIn(reverse("dashboard"), header)
        self.assertNotIn(reverse("logout"), header)

    def test_account_links_when_signed_in(self):
        User.objects.create_user("parent", password="not-a-real-password-123")
        self.client.login(username="parent", password="not-a-real-password-123")
        header = self.header(self.client.get(reverse("index")))
        self.assertIn(reverse("dashboard"), header)
        self.assertIn(reverse("logout"), header)
        self.assertNotIn(f'href="{reverse("login")}"', header)

    def test_no_inline_layout_styles(self):
        # The shared logo carries its own sizing, and category pills take their
        # colour from the database; everything else is laid out by happybox.css.
        header = self.header(self.client.get(reverse("index")))
        header = header.replace(render_to_string("includes/logo.html"), "")
        header = re.sub(r'style="background:#[0-9A-Fa-f]{6}"', "", header)
        self.assertEqual(re.findall(r'style="[^"]*"', header), [])


# Django's own English, which must never reach a shopper browsing in Arabic.
DJANGO_ENGLISH = (
    "This field is required",
    "Please enter a correct username",
    "Enter a valid",
    "Your password",
    "The two password fields",
    "Required. 150 characters",
    "Password confirmation",
    "A user with that username",
)


class PluralTests(TestCase):
    def test_english_has_one_and_other(self):
        self.assertEqual(plural("toy", 1, "en"), "1 toy")
        self.assertEqual(plural("toy", 0, "en"), "0 toys")
        self.assertEqual(plural("toy", 4, "en"), "4 toys")

    def test_arabic_follows_the_number(self):
        cases = {
            0: "0 لعبة",
            1: "لعبة واحدة",
            2: "لعبتان",
            3: "3 ألعاب",
            10: "10 ألعاب",
            11: "11 لعبة",
            99: "99 لعبة",
            100: "100 لعبة",
            103: "103 ألعاب",
        }
        for n, text in cases.items():
            with self.subTest(n=n):
                self.assertEqual(plural("toy", n, "ar"), text)

    def test_arabic_accusative_after_eleven(self):
        self.assertEqual(plural("order", 15, "ar"), "15 طلبًا")
        self.assertEqual(plural("order", 200, "ar"), "200 طلب")


class StringTableTests(TestCase):
    def test_every_string_is_used(self):
        root = Path(__file__).resolve().parent
        sources = [p.read_text(encoding="utf-8") for p in root.parent.joinpath("templates").rglob("*.html")]
        sources += [p.read_text(encoding="utf-8") for p in root.rglob("*.py") if p.name not in ("strings.py", "tests.py")]
        text = "\n".join(sources)
        # Keys looked up by prefix: status_<value>, err_<code> and the months.
        dynamic = ("status_", "err_", "month")
        unused = [
            key for key in STRINGS
            if not key.startswith(dynamic)
            and not re.search(rf"t\.{key}\b|[\"']{key}[\"']", text)
        ]
        self.assertEqual(unused, [])

    def test_every_pair_has_both_languages(self):
        for key, pair in STRINGS.items():
            with self.subTest(key=key):
                self.assertEqual(len(pair), 2)
                self.assertTrue(pair[0] and pair[1])


class CopyTestCase(TestCase):
    def arabic(self):
        self.client.post(reverse("set-language"), {"lang": "ar"})
        return translations("ar")

    def assertNoDjangoEnglish(self, response):
        body = response.content.decode()
        for phrase in DJANGO_ENGLISH:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, body)


class AuthCopyTests(CopyTestCase):
    def test_a_bad_login_says_so_once(self):
        response = self.client.post(reverse("login"), {"username": "nobody", "password": "x"})
        self.assertContains(response, escape(translations("en")["err_invalid_login"]), count=1)
        self.assertNoDjangoEnglish(response)

    def test_a_bad_login_in_arabic(self):
        t = self.arabic()
        response = self.client.post(reverse("login"), {"username": "nobody", "password": "x"})
        self.assertContains(response, t["err_invalid_login"], count=1)
        self.assertContains(response, t["username"])
        self.assertContains(response, t["password"])
        self.assertNoDjangoEnglish(response)

    def test_a_bad_signup_in_arabic(self):
        t = self.arabic()
        User.objects.create_user("taken", password="not-a-real-password-123")
        response = self.client.post(
            reverse("register"),
            {"username": "taken", "email": "nope", "password1": "123", "password2": "456"},
        )
        for key in ("err_username_unique", "err_email_invalid", "err_password_mismatch"):
            with self.subTest(key=key):
                self.assertContains(response, t[key])
        self.assertNoDjangoEnglish(response)

    def test_weak_passwords_are_explained_in_arabic(self):
        t = self.arabic()
        response = self.client.post(
            reverse("register"), {"username": "newparent", "password1": "12345", "password2": "12345"}
        )
        self.assertContains(response, t["err_password_too_short"].format(min_length=8))
        self.assertContains(response, t["err_password_entirely_numeric"])
        self.assertNoDjangoEnglish(response)

    def test_signup_page_has_its_own_subtitle(self):
        t = translations("en")
        response = self.client.get(reverse("register"))
        self.assertContains(response, t["joinUsBody"])
        self.assertNotContains(response, t["catsSub"])

    def test_signup_still_works(self):
        response = self.client.post(
            reverse("register"),
            {"username": "newparent", "email": "p@example.com",
             "password1": "a-long-enough-pass-42", "password2": "a-long-enough-pass-42"},
        )
        self.assertRedirects(response, reverse("register-success"))


class CheckoutCopyTests(CopyTestCase):
    def setUp(self):
        toy = Product.objects.create(
            pname="Stacky", pname_ar="ستاكي", pprice=Decimal("40"), quantity=3,
            category=Category.objects.get(name="Baby Toys"),
        )
        self.client.post(reverse("cart-add", args=[toy.pk]), {"quantity": 1})

    def test_missing_fields_are_explained_in_arabic(self):
        t = self.arabic()
        response = self.client.post(reverse("checkout"), {})
        self.assertContains(response, t["err_required"])
        self.assertNoDjangoEnglish(response)

    def test_missing_fields_in_english_use_the_shop_voice(self):
        response = self.client.post(reverse("checkout"), {})
        self.assertContains(response, escape(translations("en")["err_required"]))
        self.assertNoDjangoEnglish(response)

    def test_address_fields_have_placeholders(self):
        t = translations("en")
        response = self.client.get(reverse("checkout"))
        for key in ("fullNamePh", "streetPh", "cityPh"):
            with self.subTest(key=key):
                self.assertContains(response, f'placeholder="{t[key]}"')

    def test_cart_count_reads_naturally_in_arabic(self):
        self.arabic()
        self.assertContains(self.client.get(reverse("cart")), "قطعة واحدة")

    def test_low_stock_is_one_sentence(self):
        self.arabic()
        self.assertContains(self.client.get(reverse("cart")), "بقي 3 فقط")


class ChromeCopyTests(CopyTestCase):
    def test_accessible_labels_are_translated(self):
        t = self.arabic()
        page = self.client.get(reverse("index")).content.decode()
        self.assertIn(f'aria-label="{t["navMain"]}"', page)
        self.assertIn(t["skipToContent"], page)
        self.assertNotIn("Skip to content", page)
        self.assertNotIn('aria-label="Main"', page)

    def test_search_suggestions_are_arabic_words(self):
        self.arabic()
        page = self.client.get(reverse("search"))
        self.assertContains(page, "دبدوب</a>")
        self.assertNotContains(page, ">bear<")

    def test_breadcrumb_label_is_translated(self):
        t = self.arabic()
        page = self.client.get(reverse("category", args=["baby-toys"]))
        self.assertContains(page, f'aria-label="{t["breadcrumb"]}"')

    def test_missing_page_is_branded_and_translated(self):
        t = self.arabic()
        response = self.client.get("/toy/no-such-toy/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, t["notFoundTitle"], status_code=404)
        self.assertContains(response, 'dir="rtl"', status_code=404)

    def test_empty_shelf_does_not_ask_shoppers_to_add_toys(self):
        self.assertNotIn("add the first", translations("en")["emptyShelfBody"])


class AccountCopyTests(CopyTestCase, StaffTestCase):
    def make_order(self, **extra):
        fields = dict(
            reference="HB-COPY01", full_name="Sam Rivera", phone="050", street="18 Marbles Lane", city="Riyadh",
            subtotal=Decimal("75"), total=Decimal("75"), user=self.customer,
            payment_method=Order.Payment.ON_DELIVERY,
        )
        fields.update(extra)
        return Order.objects.create(**fields)

    def test_dashboard_counts_orders_not_items(self):
        self.make_order()
        self.client.force_login(self.customer)
        page = self.client.get(reverse("dashboard"))
        self.assertContains(page, "1 order")
        self.assertNotContains(page, "1 item")

    def test_order_history_is_arabic_throughout(self):
        order = self.make_order()
        Order.objects.filter(pk=order.pk).update(created_at=datetime(2026, 9, 24, 10, 0, tzinfo=dt_timezone.utc))
        self.client.force_login(self.customer)
        self.arabic()
        page = self.client.get(reverse("orders"))
        self.assertContains(page, "الدفع عند الاستلام")
        self.assertContains(page, "24 سبتمبر 2026")
        self.assertNotContains(page, "Pay on delivery")
        self.assertNotContains(page, "Sep")

    def test_category_count_is_pluralised(self):
        cat = Category.objects.get(name="Others")
        Product.objects.filter(category=cat).delete()
        Product.objects.create(pname="Lonely", pprice=Decimal("5"), category=cat)
        self.client.force_login(self.admin)
        page = self.client.get(reverse("category-list"))
        self.assertContains(page, "1 toy<")
        self.assertNotContains(page, "1 toys")


class StaffCopyTests(CopyTestCase, StaffTestCase):
    def test_add_toy_form_is_arabic(self):
        t = self.arabic()
        self.client.force_login(self.admin)
        response = self.client.post(reverse("addProduct"), {"pname": "", "age_min": 9, "age_max": 3})
        self.assertContains(response, t["fieldName"])
        self.assertContains(response, t["err_required"])
        self.assertContains(response, t["err_age_order"])
        self.assertNoDjangoEnglish(response)
        for english in ("Youngest age", "Is featured", "Stock quantity", "Solo"):
            with self.subTest(english=english):
                self.assertNotContains(response, english)

    def test_category_form_is_arabic(self):
        t = self.arabic()
        self.client.force_login(self.admin)
        response = self.client.post(reverse("category-create"), {"name": "!!!", "color": "red"})
        self.assertContains(response, t["err_slug_empty"])
        self.assertContains(response, t["err_color"])
        for english in ("Name ar", "Blurb ar", "Glyph"):
            with self.subTest(english=english):
                self.assertNotContains(response, english)

    def test_status_picker_is_arabic(self):
        order = Order.objects.create(
            reference="HB-COPY02", full_name="Sam", phone="050", street="x", city="y",
            subtotal=Decimal("1"), total=Decimal("1"),
        )
        self.arabic()
        self.client.force_login(self.admin)
        page = self.client.get(reverse("manage-order", args=[order.reference]))
        self.assertContains(page, "قيد الانتظار</option>")
        self.assertNotContains(page, ">Pending</option>")
