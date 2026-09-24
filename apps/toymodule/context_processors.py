"""Storefront context: the things every page's chrome needs.

The header renders the language toggle, the currency picker, the category nav
and the cart badge on every single page, so passing those through each view's
context dict by hand would be four lines of noise per view and one bug the
first time somebody forgets.
"""

from .models import Category
from . import storefront
from .strings import direction, translations


def storefront_context(request):
    lang = storefront.get_language(request)
    currency = storefront.get_currency(request)
    return {
        "t": translations(lang),
        "lang": lang,
        "text_dir": direction(lang),
        "is_rtl": lang == "ar",
        "other_lang": "en" if lang == "ar" else "ar",
        "currency": currency,
        "currencies": storefront.get_currencies(request),
        "nav_categories": list(Category.objects.all()),
        "cart_count": storefront.cart_count(request),
    }
