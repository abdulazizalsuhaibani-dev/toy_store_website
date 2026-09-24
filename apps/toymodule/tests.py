"""Tests for the storefront.

Concentrated on the things the redesign introduced that could silently go
wrong: currency conversion (money the shopper sees), the cart and checkout
(money the shop takes), the filters (what the shopper is shown), and the
access rule on the order confirmation page.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
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

    def test_age_filter_excludes_a_range_that_does_not_fit(self):
        response = self.client.get(reverse("shop"), {"age": "3-6"})
        self.assertContains(response, "Stacky")
        self.assertNotContains(response, "Mega Run")

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

    def test_dashboard_requires_sign_in(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

    def test_add_product_requires_sign_in(self):
        self.assertEqual(self.client.get(reverse("addProduct")).status_code, 302)

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
        self.client.force_login(self.user)
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
