"""Storefront views.

Function-based throughout, matching the rest of the app. The catalogue screens
(home, listing, search) share one filter/sort helper rather than each
hardcoding a queryset the way the old per-category views did — adding a
category is now a row in the database, not a new view plus a new URL plus a
new template.
"""

import random
from decimal import Decimal

from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.db import DatabaseError, connection, transaction
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponsePermanentRedirect, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import storefront
from .forms import AddProductForm, AddUserForm, CheckoutForm, LoginForm
from .models import CartItem, Category, DeliveryOption, Order, OrderItem, Product
from .strings import translations

# Age bands offered as filter pills. A product matches a band when its own
# range fits inside it, so "3–6" never offers a toy rated 3–10 to a five year
# old's parent. The design compared the range strings for equality, which does
# the same thing for its own eight products and nothing sensible beyond them.
AGE_BANDS = [("3-6", 3, 6), ("5-10", 5, 10), ("6-10", 6, 10)]

# Price bands, in the base currency (SAR). USD 20 / USD 40 at the seeded peg.
PRICE_BANDS = {
    "low": (None, Decimal("75")),
    "mid": (Decimal("75"), Decimal("150")),
    "high": (Decimal("150"), None),
}

SORTS = {
    "popular": ["-review_count", "pname"],
    "price_asc": ["pprice", "pname"],
    "price_desc": ["-pprice", "pname"],
}


# ---------------------------------------------------------------- helpers --


def _catalogue(request, base=None):
    """Apply the query-string filters shared by the listing and search screens.

    Returns (queryset, state) where state is what the template needs to render
    the pills in their selected/unselected form.
    """
    products = Product.objects.select_related("category") if base is None else base

    query = (request.GET.get("q") or "").strip()
    age = request.GET.get("age") or ""
    price = request.GET.get("price") or ""
    sort = request.GET.get("sort") or "popular"
    if sort not in SORTS:
        sort = "popular"

    if query:
        products = products.filter(
            Q(pname__icontains=query)
            | Q(pname_ar__icontains=query)
            | Q(blurb__icontains=query)
            | Q(blurb_ar__icontains=query)
            | Q(category__name__icontains=query)
            | Q(category__name_ar__icontains=query)
        )

    band = next((b for b in AGE_BANDS if b[0] == age), None)
    if band:
        products = products.filter(age_min__gte=band[1], age_max__lte=band[2])
    else:
        age = ""

    if price in PRICE_BANDS:
        low, high = PRICE_BANDS[price]
        if low is not None:
            products = products.filter(pprice__gte=low)
        if high is not None:
            products = products.filter(pprice__lt=high)
    else:
        price = ""

    products = products.order_by(*SORTS[sort])

    lang = storefront.get_language(request)
    t = translations(lang)
    currency = storefront.get_currency(request)

    def cash(amount):
        return storefront.format_money(amount, currency, lang)

    low_edge, high_edge = PRICE_BANDS["mid"]
    state = {
        "query": query,
        "age": age,
        "price": price,
        "sort": sort,
        "age_bands": [
            {"key": "", "label": t["allAges"], "selected": not age},
            *[{"key": key, "label": key.replace("-", "–"), "selected": age == key} for key, _, _ in AGE_BANDS],
        ],
        "price_bands": [
            {"key": "", "label": t["any"], "selected": not price},
            {"key": "low", "label": f"{t['priceUnder']} {cash(low_edge)}", "selected": price == "low"},
            {"key": "mid", "label": f"{cash(low_edge)}–{cash(high_edge)}", "selected": price == "mid"},
            {"key": "high", "label": f"{t['priceOver']} {cash(high_edge)}", "selected": price == "high"},
        ],
        "sort_options": [
            {"key": "popular", "label": t["popular"], "selected": sort == "popular"},
            {"key": "price_asc", "label": t["priceUp"], "selected": sort == "price_asc"},
            {"key": "price_desc", "label": t["priceDown"], "selected": sort == "price_desc"},
        ],
    }
    return products, state


def _order_reference():
    """A short, human-readable order reference.

    Ambiguous glyphs are left out so somebody reading one over the phone does
    not have to say "zero, not the letter O".
    """
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    while True:
        ref = "HB-" + "".join(random.choices(alphabet, k=6))
        if not Order.objects.filter(reference=ref).exists():
            return ref


# ----------------------------------------------------------------- chrome --


def healthz(request):
    """Health check for the host (Render polls this after every deploy).

    Touches the database rather than just returning 200, so an instance that
    boots but cannot reach Supabase is reported unhealthy instead of serving
    500s. Exempt from the HTTPS redirect via SECURE_REDIRECT_EXEMPT: the probe
    is internal to the platform and arrives without X-Forwarded-Proto, so
    otherwise it would only ever see a 301.
    """
    try:
        connection.ensure_connection()
    except DatabaseError:
        return HttpResponse("database unavailable\n", status=503, content_type="text/plain")
    return HttpResponse("ok\n", content_type="text/plain")


def _back(request, fallback="index"):
    """Return to the page the shopper was on.

    Only same-origin referers are honoured, so a crafted link cannot use the
    language toggle as an open redirect.
    """
    referer = request.META.get("HTTP_REFERER", "")
    if referer and url_has_allowed_host_and_scheme(
        referer, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return HttpResponseRedirect(referer)
    return redirect(fallback)


@require_POST
def set_language(request):
    storefront.set_language(request, request.POST.get("lang", ""))
    return _back(request)


@require_POST
def set_currency(request):
    storefront.set_currency(request, request.POST.get("currency", ""))
    return _back(request)


# ------------------------------------------------------------- catalogue --


def index(request):
    featured = list(
        Product.objects.select_related("category").filter(is_featured=True).order_by("-review_count")[:4]
    )
    if not featured:
        # A shop with nothing flagged should still show the shelf rather than a
        # hole where four cards belong.
        featured = list(Product.objects.select_related("category").order_by("-review_count")[:4])
    return render(
        request,
        "toymodule/index.html",
        {
            # .order_by() restated because annotate() discards Meta.ordering:
            # aggregation queries build their own GROUP BY and drop it.
            "categories": Category.objects.annotate(product_count=Count("products")).order_by(
                "sort_order", "name"
            ),
            "featured": featured,
            "promo_from": Decimal("225"),
            "promo_for": Decimal("158"),
        },
    )


def shop(request):
    """Everything, filterable. The design's "See all toys"."""
    products, state = _catalogue(request)
    return render(
        request,
        "toymodule/listing.html",
        {"category": None, "products": products, "total": Product.objects.count(), **state},
    )


def category(request, slug):
    cat = get_object_or_404(Category, slug=slug)
    products, state = _catalogue(request, cat.products.select_related("category"))
    return render(
        request,
        "toymodule/listing.html",
        {"category": cat, "products": products, "total": cat.products.count(), **state},
    )


def product_detail(request, slug):
    product = get_object_or_404(Product.objects.select_related("category"), slug=slug)
    related = Product.objects.select_related("category").exclude(pk=product.pk)
    if product.category_id:
        in_category = list(related.filter(category=product.category)[:4])
        related = in_category or list(related[:4])
    else:
        related = list(related[:4])
    return render(
        request,
        "toymodule/detail.html",
        {"product": product, "related": related},
    )


def search(request):
    products, state = _catalogue(request)
    cat_slug = request.GET.get("cat") or ""
    categories = list(Category.objects.all())
    if cat_slug and any(c.slug == cat_slug for c in categories):
        products = products.filter(category__slug=cat_slug)
    else:
        cat_slug = ""
    return render(
        request,
        "toymodule/search.html",
        {
            "products": products,
            "categories": categories,
            "cat": cat_slug,
            "suggestions": ["blocks", "kite", "bear", "marble", "robot"],
            **state,
        },
    )


# ------------------------------------------------------------------ cart --


@require_POST
def cart_add(request, pk):
    product = get_object_or_404(Product, pk=pk)
    try:
        quantity = max(1, int(request.POST.get("quantity", 1)))
    except (TypeError, ValueError):
        quantity = 1

    cart = storefront.get_cart(request)
    item, created = CartItem.objects.get_or_create(cart=cart, product=product, defaults={"quantity": quantity})
    if not created:
        item.quantity += quantity
        item.save(update_fields=["quantity"])
    cart.save(update_fields=["updated_at"])

    if request.POST.get("next") == "cart":
        return redirect("cart")
    return _back(request)


@require_POST
def cart_update(request, pk):
    """Set or nudge a line's quantity. Dropping to zero removes the line."""
    cart = storefront.get_cart(request)
    item = get_object_or_404(CartItem, pk=pk, cart=cart)

    if "delta" in request.POST:
        try:
            item.quantity += int(request.POST["delta"])
        except (TypeError, ValueError):
            pass
    elif "quantity" in request.POST:
        try:
            item.quantity = int(request.POST["quantity"])
        except (TypeError, ValueError):
            pass
    else:
        item.quantity = 0

    if item.quantity <= 0:
        item.delete()
    else:
        item.save(update_fields=["quantity"])
    cart.save(update_fields=["updated_at"])
    return redirect("cart")


@require_POST
def cart_gift(request):
    cart = storefront.get_cart(request)
    cart.gift_wrap = not cart.gift_wrap
    cart.save(update_fields=["gift_wrap", "updated_at"])
    return _back(request, "cart")


def cart(request):
    basket = storefront.get_cart(request, create=False)
    items = list(basket.items.select_related("product")) if basket else []
    subtotal = sum((item.line_total for item in items), Decimal("0"))
    standard = DeliveryOption.objects.first()
    shipping = standard.cost_for(subtotal) if standard else Decimal("0")
    return render(
        request,
        "toymodule/cart.html",
        {
            "cart": basket,
            "items": items,
            "subtotal": subtotal,
            "shipping": shipping,
            "total": subtotal + shipping,
            "count": sum(item.quantity for item in items),
        },
    )


# -------------------------------------------------------------- checkout --


def checkout(request):
    basket = storefront.get_cart(request, create=False)
    items = list(basket.items.select_related("product")) if basket else []
    if not items:
        return redirect("cart")

    subtotal = sum((item.line_total for item in items), Decimal("0"))
    options = list(DeliveryOption.objects.all())

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            chosen = order.delivery_option
            shipping = chosen.cost_for(subtotal) if chosen else Decimal("0")
            currency = storefront.get_currency(request)

            order.reference = _order_reference()
            order.user = request.user if request.user.is_authenticated else None
            order.subtotal = subtotal
            order.shipping_cost = shipping
            order.total = subtotal + shipping
            order.currency_code = currency.code if currency else "SAR"
            order.language = storefront.get_language(request)

            # One transaction: an order that exists without its lines, or a
            # cart emptied against an order that failed to save, is worse than
            # a 500 the shopper can retry.
            with transaction.atomic():
                order.save()
                OrderItem.objects.bulk_create(
                    [
                        OrderItem(
                            order=order,
                            product=item.product,
                            product_name=item.product.pname,
                            unit_price=item.product.pprice,
                            quantity=item.quantity,
                        )
                        for item in items
                    ]
                )
                basket.items.all().delete()

            # Lets the confirmation page recognise the shopper who just placed
            # this order, including when they checked out signed out.
            request.session["last_order"] = order.reference
            return redirect("order-placed", reference=order.reference)
    else:
        initial = {"gift_wrap": basket.gift_wrap}
        if options:
            initial["delivery_option"] = options[0].pk
        if request.user.is_authenticated:
            initial.setdefault("full_name", request.user.get_full_name() or request.user.username)
        form = CheckoutForm(initial=initial)

    selected = None
    if form.is_bound and form.data.get("delivery_option"):
        selected = next((o for o in options if str(o.pk) == form.data.get("delivery_option")), None)
    if selected is None:
        selected = options[0] if options else None
    shipping = selected.cost_for(subtotal) if selected else Decimal("0")

    # Pre-render each option's shipping line and order total, so picking a
    # different delivery speed can update the summary without the page doing
    # currency arithmetic in JavaScript. Without JS the summary shows the
    # default option's figures and the server recomputes on POST regardless.
    currency = storefront.get_currency(request)
    lang = storefront.get_language(request)
    free_text = translations(lang)["free"]
    for option in options:
        cost = option.cost_for(subtotal)
        option.cost_display = storefront.format_money(cost, currency, lang) if cost else free_text
        option.total_display = storefront.format_money(subtotal + cost, currency, lang)

    return render(
        request,
        "toymodule/checkout.html",
        {
            "form": form,
            "cart": basket,
            "items": items,
            "subtotal": subtotal,
            "delivery_options": options,
            "selected_delivery": selected,
            "shipping": shipping,
            "total": subtotal + shipping,
            "count": sum(item.quantity for item in items),
            "payment_choices": Order.Payment.choices,
        },
    )


def order_placed(request, reference):
    """The confirmation page.

    Readable by the session that placed the order, or by the account that owns
    it. The reference is eight characters and the page carries a delivery
    address and phone number, so it is not something to hand out to anyone who
    can type a URL.
    """
    order = get_object_or_404(Order.objects.prefetch_related("items"), reference=reference)
    placed_here = request.session.get("last_order") == reference
    owns_it = bool(order.user_id) and request.user.is_authenticated and request.user.pk == order.user_id
    if not (placed_here or owns_it):
        return redirect("index")
    return render(request, "toymodule/order_placed.html", {"order": order})


# -------------------------------------------------------------- accounts --


def login(request):
    form = LoginForm()
    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                username=request.POST.get("username"),
                password=request.POST.get("password"),
            )
            if user is not None:
                # Look the cart up first: login() cycles the session key, and
                # the anonymous cart is keyed by the old one.
                anonymous_cart = storefront.get_cart(request, create=False)
                auth_login(request, user)
                storefront.adopt_cart(request, anonymous_cart)
                return redirect("dashboard")
    return render(request, "toymodule/login.html", {"loginform": form})


def logout(request):
    auth_logout(request)
    return redirect("index")


def register(request):
    form = AddUserForm()
    if request.method == "POST":
        form = AddUserForm(request.POST)
        if form.is_valid():
            form.save()
            return render(request, "toymodule/registerSuccess.html")
    return render(request, "toymodule/register.html", {"registerform": form})


@login_required(login_url="login")
def addProduct(request):
    if request.method == "POST":
        form = AddProductForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect("dashboard")
    else:
        form = AddProductForm()
    return render(request, "toymodule/addProduct.html", {"form": form})


@login_required(login_url="login")
def dashboard(request):
    return render(
        request,
        "toymodule/dashboard.html",
        {"order_count": Order.objects.filter(user=request.user).count()},
    )


@login_required(login_url="login")
def accountInfo(request):
    return render(
        request,
        "toymodule/accountInfo.html",
        {"username": request.user.username, "email": request.user.email},
    )


@login_required(login_url="login")
def orders(request):
    return render(
        request,
        "toymodule/orders.html",
        {"orders": Order.objects.filter(user=request.user).prefetch_related("items")},
    )


# ------------------------------------------------------- legacy redirects --


def legacy_category(request, name):
    """Keep the original /baby-toys style URLs working.

    They were the only way to reach a category for the life of the app, so
    they are almost certainly bookmarked and linked. 301, because the new
    /c/<slug>/ path is where they live now.
    """
    cat = Category.objects.filter(name__iexact=name).first()
    if cat is None:
        return redirect("shop")
    return HttpResponsePermanentRedirect(reverse("category", args=[cat.slug]))
