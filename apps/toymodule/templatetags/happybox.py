"""Template helpers for the storefront.

Prices and model copy both depend on request state (chosen currency, chosen
language) that a plain filter cannot see, so these are `takes_context` tags
reading what the storefront context processor already put there. The
alternative — decorating every product into a dict in the view, the way the
design's `decorate()` does — would mean every view that touches a product
repeating the same six lines.
"""

from django import template
from django.utils import timezone

from .. import storefront
from ..models import Currency
from ..strings import plural

register = template.Library()


@register.simple_tag(takes_context=True)
def money(context, amount):
    """Render an amount held in the base currency, in the shopper's currency."""
    if amount is None:
        return ""
    return storefront.format_money(amount, context.get("currency"), context.get("lang", "en"))


@register.simple_tag(takes_context=True)
def money_in(context, code, amount):
    """Render an amount in a named currency, whatever the header is showing.

    Receipts use this. An order records the currency the shopper agreed the
    total in; re-rendering it in whatever they have since switched the header
    to would show a number they never saw.
    """
    if amount is None:
        return ""
    # The context processor already loaded every currency, base rate attached.
    currency = next((c for c in context.get("currencies") or () if c.code == code), None)
    if currency is None:
        currency = Currency.objects.filter(code=code).first()
    return storefront.format_money(amount, currency, context.get("lang", "en"))


@register.simple_tag(takes_context=True)
def label(context, obj):
    """The object's name in the current language, falling back to English."""
    return obj.label(context.get("lang", "en")) if obj is not None else ""


@register.simple_tag(takes_context=True)
def status_label(context, order):
    """An order's status in the current language."""
    return context["t"].get(f"status_{order.status}", order.get_status_display())


@register.simple_tag(takes_context=True)
def payment_label(context, order):
    """How an order is being paid for, in the current language."""
    return order.payment_label(context.get("lang", "en"))


@register.simple_tag(takes_context=True)
def count(context, n, noun):
    """A number and its noun: `{% count cart_count "item" %}` -> "3 items"."""
    return plural(noun, n or 0, context.get("lang", "en"))


@register.simple_tag(takes_context=True)
def copy(context, key, **values):
    """A string with placeholders: `{% copy "onlyLeft" n=product.quantity %}`."""
    return context["t"][key].format(**values)


@register.simple_tag(takes_context=True)
def when(context, moment, time=False):
    """A date as "24 Sep 2026" (or "24 سبتمبر 2026"), optionally with the time.

    The `date` filter would print English month names on an Arabic page:
    Django's own translations are not switched on, because the language here
    comes from the header toggle, not from Django's i18n machinery.
    """
    if moment is None:
        return ""
    moment = timezone.localtime(moment)
    month = context["t"]["months"].split()[moment.month - 1]
    text = f"{moment.day} {month} {moment.year}"
    return f"{text} {moment:%H:%M}" if time else text


@register.simple_tag(takes_context=True)
def blurb(context, obj):
    return obj.blurb_for(context.get("lang", "en")) if obj is not None else ""


@register.simple_tag(takes_context=True)
def badge_label(context, product):
    return product.badge_label(context.get("lang", "en")) if product is not None else ""


@register.simple_tag(takes_context=True)
def play_label(context, product):
    return product.play_label(context.get("lang", "en")) if product is not None else ""


@register.simple_tag(takes_context=True)
def delivery_label(context, option):
    return option.label_for(context.get("lang", "en")) if option is not None else ""


@register.simple_tag(takes_context=True)
def delivery_note(context, option):
    return option.note_for(context.get("lang", "en")) if option is not None else ""


@register.simple_tag
def querystring(request, **overrides):
    """Rebuild the current query string with some parameters replaced.

    The listing and search screens carry several independent filters at once;
    clicking one pill must keep the others. Passing a value of None or "" drops
    the key entirely, which is how the "All"/"Any" pills reset a single filter.
    Changing any filter also drops `page` (page 3 of the old results means
    nothing in the new ones); the pager itself passes `page=` explicitly.
    """
    params = request.GET.copy()
    for key, value in overrides.items():
        if value in (None, ""):
            params.pop(key, None)
        else:
            params[key] = value
    if "page" not in overrides:
        params.pop("page", None)
    encoded = params.urlencode()
    return f"?{encoded}" if encoded else ""
