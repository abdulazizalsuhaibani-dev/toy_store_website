"""Per-request storefront state: language, currency, and the cart.

All three are things the shopper chooses in the header and expects to survive
navigation, so they live in the session. The cart is a row in the database
keyed by that session, not a dict inside it — see `Cart` for why.
"""

from decimal import Decimal

from .models import Cart, CartItem, Currency
from .strings import DEFAULT_LANGUAGE, LANGUAGES

LANG_SESSION_KEY = "storefront_lang"
CURRENCY_SESSION_KEY = "storefront_currency"

# The design's free-shipping threshold, quoted in the hero badge and applied by
# the Standard delivery option. Base currency (SAR), = USD 40 at the seeded peg.
FREE_SHIPPING_OVER = Decimal("150")


def get_language(request):
    lang = request.session.get(LANG_SESSION_KEY)
    return lang if lang in LANGUAGES else DEFAULT_LANGUAGE


def set_language(request, lang):
    if lang in LANGUAGES:
        request.session[LANG_SESSION_KEY] = lang


def get_currency(request):
    """The shopper's chosen currency, falling back to the base one.

    Returns None only when the Currency table is empty — a fresh database
    before `seed_catalog` has run. Callers render bare numbers in that case
    rather than crashing, so a half-migrated deploy still serves pages.
    """
    code = request.session.get(CURRENCY_SESSION_KEY)
    currencies = list(Currency.objects.all())
    if not currencies:
        return None
    by_code = {c.code: c for c in currencies}
    if code in by_code:
        return by_code[code]
    return next((c for c in currencies if c.is_base), currencies[0])


def set_currency(request, code):
    if Currency.objects.filter(code=code).exists():
        request.session[CURRENCY_SESSION_KEY] = code


def format_money(amount, currency, lang):
    """Render an amount held in the base currency.

    Mirrors the design's `money()`: trailing zeros are trimmed so SAR 24.00
    reads "SAR 24", and Arabic puts the symbol after the number.
    """
    if currency is None:
        return f"{Decimal(amount):.2f}"
    value = currency.convert(amount)
    text = f"{value:f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if lang == "ar" and currency.symbol_ar:
        return f"{text} {currency.symbol_ar}"
    return f"{currency.code} {text}"


def get_cart(request, create=True):
    """The cart for this request, creating one on first use.

    A signed-in shopper is followed by their account, so their cart comes with
    them to a new device. A signed-out one is followed by their session key. A
    session key has to exist before it can be a cart's key, so an anonymous
    first-time visitor gets their session saved here.
    """
    if not request.session.session_key:
        if not create:
            return None
        request.session.save()
    session_key = request.session.session_key
    user = request.user if request.user.is_authenticated else None

    if user is not None:
        cart = Cart.objects.filter(user=user).order_by("-updated_at").first()
    else:
        cart = Cart.objects.filter(session_key=session_key, user__isnull=True).first()

    if cart is not None:
        return cart
    if not create:
        return None
    return Cart.objects.create(session_key=session_key, user=user)


def adopt_cart(request, cart):
    """Hand a cart built while signed out to the account that just signed in.

    Must be called with the cart looked up *before* `login()`: Django cycles
    the session key on login to defeat session fixation, so by the time the
    user is authenticated the anonymous cart's key no longer matches anything.

    If the account already has a cart, the two are merged rather than one
    silently winning — a shopper who added a toy on their phone and another on
    their laptop should end up with both.
    """
    if cart is None or not request.user.is_authenticated:
        return

    existing = Cart.objects.filter(user=request.user).exclude(pk=cart.pk).order_by("-updated_at").first()
    if existing is None:
        cart.user = request.user
        cart.session_key = request.session.session_key or cart.session_key
        cart.save(update_fields=["user", "session_key", "updated_at"])
        return

    for item in cart.items.all():
        line, created = CartItem.objects.get_or_create(
            cart=existing, product=item.product, defaults={"quantity": item.quantity}
        )
        if not created:
            line.quantity += item.quantity
            line.save(update_fields=["quantity"])
    cart.delete()
    existing.session_key = request.session.session_key or existing.session_key
    existing.save(update_fields=["session_key", "updated_at"])


def cart_count(request):
    """Header badge count. Never creates a cart — a visitor who has only ever
    read the homepage should not leave a row behind."""
    cart = get_cart(request, create=False)
    return cart.count if cart else 0
