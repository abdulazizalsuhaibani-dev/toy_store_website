"""Storefront views.

Function-based throughout, matching the rest of the app. The catalogue screens
(home, listing, search) share one filter/sort helper rather than each
hardcoding a queryset the way the old per-category views did — adding a
category is now a row in the database, not a new view plus a new URL plus a
new template.
"""

import random
from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import DatabaseError, connection, transaction
from django.db.models import Count, F, Max, Q
from django.http import Http404, HttpResponse, HttpResponsePermanentRedirect, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import storefront
from .forms import AddProductForm, AddUserForm, CategoryForm, CheckoutForm, LoginForm, OrderStatusForm
from .models import CartItem, Category, DeliveryOption, Order, OrderItem, Product
from .strings import translations

# Age bands offered as filter pills: (key, label, lowest age, highest age). The
# bands are contiguous and the last is open-ended, so every toy is reachable. A
# product matches a band when its age range *overlaps* it: a toy for 3-10 is
# right for a five year old, so it belongs under 3-5 as well as 6-8.
AGE_BANDS = [
    ("0-2", "0–2", 0, 2),
    ("3-5", "3–5", 3, 5),
    ("6-8", "6–8", 6, 8),
    ("9-up", "9+", 9, None),
]

# Price bands as the design specified them, in USD. `_price_bands()` turns
# them into base-currency thresholds, so they follow `Currency.is_base`.
PRICE_BANDS_USD = {
    "low": (None, Decimal("20")),
    "mid": (Decimal("20"), Decimal("40")),
    "high": (Decimal("40"), None),
}

# Toys per page on the listing and search screens. Twelve fills the card grid
# in rows of two, three, four and six, so no page ends on a ragged row.
PAGE_SIZE = 12


def _paginate(request, products):
    """One page of a catalogue queryset, from `?page=`.

    `get_page` forgives a junk or out-of-range value (first page for the former,
    last for the latter) so a stale bookmark shows toys rather than a 404. The
    elided range keeps the pager short however large the catalogue grows.
    """
    paginator = Paginator(products, PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page"))
    page.elided = list(paginator.get_elided_page_range(page.number, on_each_side=2, on_ends=1))
    return page


def _price_bands(request):
    return {
        key: tuple(None if edge is None else storefront.usd_to_base(request, edge) for edge in edges)
        for key, edges in PRICE_BANDS_USD.items()
    }

SORTS = {
    # Reviews do not exist yet, so review_count alone would rank by whatever
    # was typed into it. Featured toys lead; review_count breaks ties.
    "popular": ["-is_featured", "-review_count", "pname"],
    "price_asc": ["pprice", "pname"],
    "price_desc": ["-pprice", "pname"],
}


# ---------------------------------------------------------------- helpers --


def permission_required(perm):
    """Gate a staff-facing view on a Django permission.

    Anonymous visitors are sent to sign in, like @login_required. A signed-in
    customer is authenticated but not allowed, so they get a 403 rather than a
    redirect to a login page they have already passed.
    """

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path(), reverse("login"))
            if not request.user.has_perm(perm):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


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
        _, _, band_low, band_high = band
        products = products.filter(age_max__gte=band_low)
        if band_high is not None:
            products = products.filter(age_min__lte=band_high)
    else:
        age = ""

    price_bands = _price_bands(request)
    if price in price_bands:
        low, high = price_bands[price]
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

    low_edge, high_edge = price_bands["mid"]
    state = {
        "query": query,
        "age": age,
        "price": price,
        "sort": sort,
        "age_bands": [
            {"key": "", "label": t["allAges"], "selected": not age},
            *[{"key": key, "label": text, "selected": age == key} for key, text, _, _ in AGE_BANDS],
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
    threshold = storefront.free_shipping_threshold()
    free_shipping_text = (
        storefront.format_money(
            threshold, storefront.get_currency(request), storefront.get_language(request)
        )
        if threshold is not None
        else ""
    )
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
            "free_shipping_text": free_shipping_text,
        },
    )


def shop(request):
    """Everything, filterable. The design's "See all toys"."""
    products, state = _catalogue(request)
    page = _paginate(request, products)
    return render(
        request,
        "toymodule/listing.html",
        {"category": None, "products": page, "page_obj": page, "total": Product.objects.count(), **state},
    )


def category(request, slug):
    cat = get_object_or_404(Category, slug=slug)
    products, state = _catalogue(request, cat.products.select_related("category"))
    page = _paginate(request, products)
    return render(
        request,
        "toymodule/listing.html",
        {"category": cat, "products": page, "page_obj": page, "total": cat.products.count(), **state},
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
    page = _paginate(request, products)
    return render(
        request,
        "toymodule/search.html",
        {
            "products": page,
            "page_obj": page,
            "categories": categories,
            "cat": cat_slug,
            # Words that match the seeded toys by name in each language.
            "suggestions": _t(request)["searchSuggestions"].split(),
            **state,
        },
    )


# ------------------------------------------------------------------ cart --


def _posted_int(request, key, default):
    try:
        return int(request.POST[key])
    except (KeyError, TypeError, ValueError):
        return default


@require_POST
def cart_add(request, pk):
    product = get_object_or_404(Product, pk=pk)
    wanted = max(1, _posted_int(request, "quantity", 1))

    if not product.in_stock:
        messages.error(request, _t(request)["soldOut"].format(name=product.pname))
        return redirect("cart") if request.POST.get("next") == "cart" else _back(request)

    cart = storefront.get_cart(request)
    item = CartItem.objects.filter(cart=cart, product=product).first()
    have = item.quantity if item else 0
    if have + wanted > product.quantity:
        messages.info(request, _t(request)["onlyLeftAdded"].format(name=product.pname, n=product.quantity))
    quantity = min(have + wanted, product.max_orderable)
    if item is None:
        CartItem.objects.create(cart=cart, product=product, quantity=quantity)
    elif quantity != item.quantity:
        item.quantity = quantity
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
        item.quantity += _posted_int(request, "delta", 0)
    elif "quantity" in request.POST:
        item.quantity = _posted_int(request, "quantity", item.quantity)
    else:
        item.quantity = 0

    product = item.product
    if item.quantity > product.quantity:
        text = _t(request)["soldOut" if not product.in_stock else "onlyLeftKept"]
        messages.info(request, text.format(name=product.pname, n=product.quantity))
    item.quantity = min(item.quantity, product.max_orderable)

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


def _stock_problem(request, product):
    """Send the shopper back to the cart, saying which toy ran short.

    Nothing was charged and no order exists: the decrement happens inside the
    same transaction as the order, so a failure here rolls all of it back.
    """
    product.refresh_from_db(fields=["quantity"])
    text = _t(request)["soldOutCheckout" if not product.in_stock else "onlyLeftCheckout"]
    messages.error(request, text.format(name=product.pname, n=product.quantity))
    return redirect("cart")


def cart(request):
    basket = storefront.get_cart(request, create=False)
    items = list(basket.items.select_related("product")) if basket else []
    for item in items:
        item.over_stock = item.quantity > item.product.quantity
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


class OutOfStock(Exception):
    """Raised inside the checkout transaction when a line can no longer be filled."""

    def __init__(self, product):
        self.product = product


def checkout(request):
    basket = storefront.get_cart(request, create=False)
    items = list(basket.items.select_related("product")) if basket else []
    if not items:
        return redirect("cart")
    short = next((item for item in items if item.quantity > item.product.quantity), None)
    if short is not None:
        return _stock_problem(request, short.product)

    subtotal = sum((item.line_total for item in items), Decimal("0"))
    options = list(DeliveryOption.objects.all())

    if request.method == "POST":
        form = CheckoutForm(request.POST, lang=_lang(request))
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
            try:
                with transaction.atomic():
                    # Take the stock first. The conditional UPDATE is the whole
                    # check: it only matches while enough is left, so two
                    # checkouts of the last toy cannot both win however the
                    # cart page looked when each shopper opened it.
                    for item in items:
                        taken = Product.objects.filter(
                            pk=item.product_id, quantity__gte=item.quantity
                        ).update(quantity=F("quantity") - item.quantity)
                        if not taken:
                            raise OutOfStock(item.product)
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
            except OutOfStock as short:
                return _stock_problem(request, short.product)

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
        form = CheckoutForm(initial=initial, lang=_lang(request))

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
    form = LoginForm(lang=_lang(request))
    if request.method == "POST":
        form = LoginForm(request, data=request.POST, lang=_lang(request))
        if form.is_valid():
            # AuthenticationForm.clean() already authenticated; reuse its result
            # rather than hashing the password a second time.
            user = form.get_user()
            # Look the cart up first: login() cycles the session key, and
            # the anonymous cart is keyed by the old one.
            anonymous_cart = storefront.get_cart(request, create=False)
            auth_login(request, user)
            storefront.adopt_cart(request, anonymous_cart)
            # @login_required builds ?next=; the form posts back to the same
            # URL, so it arrives in the query string.
            target = request.POST.get("next") or request.GET.get("next", "")
            if target and url_has_allowed_host_and_scheme(
                target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
            ):
                return redirect(target)
            return redirect("dashboard")
    return render(request, "toymodule/login.html", {"loginform": form})


@require_POST
def logout(request):
    auth_logout(request)
    return redirect("index")


def register(request):
    form = AddUserForm(lang=_lang(request))
    if request.method == "POST":
        form = AddUserForm(request.POST, lang=_lang(request))
        if form.is_valid():
            form.save()
            return redirect("register-success")
    return render(request, "toymodule/register.html", {"registerform": form})


def register_success(request):
    return render(request, "toymodule/registerSuccess.html")


@permission_required("toymodule.add_product")
def addProduct(request):
    if request.method == "POST":
        form = AddProductForm(request.POST, request.FILES, lang=_lang(request))
        if form.is_valid():
            form.save()
            return redirect("dashboard")
    else:
        form = AddProductForm(lang=_lang(request))
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


# ------------------------------------------------------ staff: categories --


def _lang(request):
    return storefront.get_language(request)


def _t(request):
    return translations(_lang(request))


@permission_required("toymodule.view_category")
def category_list(request):
    return render(
        request,
        "toymodule/category_list.html",
        {"categories": Category.objects.annotate(product_count=Count("products")).order_by("sort_order", "name")},
    )


def _category_form(request, category):
    form = CategoryForm(request.POST or None, instance=category, lang=_lang(request))
    if request.method == "POST" and form.is_valid():
        saved = form.save(commit=False)
        saved.slug = form.cleaned_data["slug"]
        if saved.pk is None:
            saved.sort_order = (Category.objects.aggregate(top=Max("sort_order"))["top"] or 0) + 1
        saved.save()
        messages.success(request, _t(request)["categorySaved"])
        return redirect("category-list")
    return render(request, "toymodule/category_form.html", {"form": form, "category": category})


@permission_required("toymodule.add_category")
def category_create(request):
    return _category_form(request, None)


@permission_required("toymodule.change_category")
def category_edit(request, pk):
    return _category_form(request, get_object_or_404(Category, pk=pk))


@require_POST
@permission_required("toymodule.delete_category")
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    # Product.category is PROTECT: say so, rather than let the delete 500.
    if category.products.exists():
        messages.error(request, _t(request)["categoryInUse"].format(name=category.name))
    else:
        category.delete()
        messages.success(request, _t(request)["categoryDeleted"])
    return redirect("category-list")


@require_POST
@permission_required("toymodule.change_category")
def category_move(request, pk):
    """Swap a category with its neighbour.

    Renumbers the whole list first: seeded rows can share a sort_order, and
    swapping two equal numbers would move nothing.
    """
    ordered = list(Category.objects.all())
    index = next((i for i, c in enumerate(ordered) if c.pk == pk), None)
    if index is None:
        raise Http404
    target = index - 1 if request.POST.get("direction") == "up" else index + 1
    if 0 <= target < len(ordered):
        ordered[index], ordered[target] = ordered[target], ordered[index]
    for position, category in enumerate(ordered):
        if category.sort_order != position:
            Category.objects.filter(pk=category.pk).update(sort_order=position)
    return redirect("category-list")


# ---------------------------------------------------------- staff: orders --


@permission_required("toymodule.view_order")
def manage_orders(request):
    status = request.GET.get("status", "")
    orders = Order.objects.select_related("user")
    if status in Order.Status.values:
        orders = orders.filter(status=status)
    else:
        status = ""
    return render(
        request,
        "toymodule/manage_orders.html",
        {"orders": orders.order_by("-created_at", "-pk"), "status": status, "statuses": [(v, _t(request)[f"status_{v}"]) for v in Order.Status.values]},
    )


@permission_required("toymodule.view_order")
def manage_order(request, reference):
    order = get_object_or_404(Order.objects.select_related("user", "delivery_option").prefetch_related("items"), reference=reference)
    form = OrderStatusForm(instance=order, lang=_lang(request))
    if request.method == "POST":
        if not request.user.has_perm("toymodule.change_order"):
            raise PermissionDenied
        form = OrderStatusForm(request.POST, instance=order, lang=_lang(request))
        if form.is_valid():
            form.save()
            messages.success(request, _t(request)["statusSaved"])
            return redirect("manage-order", reference=order.reference)
    return render(request, "toymodule/manage_order.html", {"order": order, "form": form})


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
