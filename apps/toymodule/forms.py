import re

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import Group, User
from django.forms import ModelForm
from django.utils import timezone
from django.utils.text import slugify
from django.forms.widgets import TextInput

from .models import Category, Currency, DeliveryOption, Order, Product
from .roles import CUSTOMER_GROUP
from .strings import translations


class StorefrontForm:
    """Mixin: a form that speaks the shop's language, in either language.

    Labels and help texts come from `strings.py` through `copy_labels` and
    `copy_help` ({field: string key}). Errors are rewritten after validation by
    their code, so Django's own "This field is required." or a password
    validator's lecture becomes `err_required` or `err_password_too_short`:
    `err_<field>_<code>` first, then `err_<code>`. An error with no entry keeps
    Django's message rather than disappearing.

    The mixin must come first in the bases, and forms take `lang=` as a keyword.
    """

    copy_labels = {}
    copy_help = {}

    def __init__(self, *args, lang="en", **kwargs):
        super().__init__(*args, **kwargs)
        self.lang = lang
        self.t = translations(lang)
        for name, key in self.copy_labels.items():
            if name in self.fields:
                self.fields[name].label = self.t[key]
        for name, key in self.copy_help.items():
            if name in self.fields:
                self.fields[name].help_text = self.t[key]

    def full_clean(self):
        super().full_clean()
        for name, errors in (self._errors or {}).items():
            errors.data = [self._in_our_words(name, error) for error in errors.as_data()]

    def _in_our_words(self, name, error):
        text = self.t.get(f"err_{name}_{error.code}") or self.t.get(f"err_{error.code}")
        if text is None:
            return error
        try:
            text = text.format(**(error.params or {}))
        except (KeyError, IndexError):
            pass
        return forms.ValidationError(text, code=error.code)


class AddProductForm(StorefrontForm, ModelForm):
    """The staff-facing form behind /addProduct.

    Fields are listed explicitly rather than `__all__`: the model now carries
    columns nobody types by hand (`slug`, `created_at`), and `__all__` would
    have put them on the page the moment they were added.

    `pcategory` used to be a free-text CharField here, so two products could
    sit in "Baby toys" and "Baby Toys" and only one of them would ever show up
    on the category page. It is a ForeignKey now, which makes that unspellable.

    The price is typed in a currency of the person's choosing and converted to
    the base currency in `clean()`. It is still stored once, in the base
    currency, so `{% money %}` and every total downstream are untouched.
    `rating` and `review_count` are deliberately absent: they are derived
    values, not something to be typed.
    """

    currency = forms.ModelChoiceField(queryset=Currency.objects.all(), empty_label=None)
    field_order = ["pname", "pname_ar", "pimage", "currency", "pprice"]

    class Meta:
        model = Product
        fields = [
            "pname",
            "pname_ar",
            "pimage",
            "pprice",
            "category",
            "blurb",
            "blurb_ar",
            "age_min",
            "age_max",
            "pieces",
            "play_type",
            "badge",
            "card_color",
            "quantity",
            "is_featured",
        ]
        widgets = {
            "blurb": forms.Textarea(attrs={"rows": 3}),
            "blurb_ar": forms.Textarea(attrs={"rows": 3}),
            "card_color": forms.TextInput(attrs={"type": "color"}),
        }

    copy_labels = {
        "pname": "fieldName",
        "pname_ar": "fieldNameAr",
        "pimage": "fieldPhoto",
        "currency": "fieldCurrency",
        "pprice": "price",
        "category": "category",
        "blurb": "fieldBlurb",
        "blurb_ar": "fieldBlurbAr",
        "age_min": "fieldAgeMin",
        "age_max": "fieldAgeMax",
        "pieces": "pieces",
        "play_type": "playType",
        "badge": "fieldBadge",
        "card_color": "fieldCardColor",
        "quantity": "fieldQuantity",
        "is_featured": "fieldFeatured",
    }
    copy_help = {
        "card_color": "fieldCardColorHelp",
        "quantity": "fieldQuantityHelp",
        "is_featured": "fieldFeaturedHelp",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = self.lang
        field = self.fields["currency"]
        # Arabic shows the code alone: the currency names are English data.
        field.label_from_instance = lambda currency: currency.code if lang == "ar" else currency.label
        base = Currency.objects.filter(is_base=True).first()
        if base is not None:
            field.initial = base
            field.help_text = self.t["fieldCurrencyHelp"].format(code=base.code)
        self.fields["category"].label_from_instance = lambda category: category.label(lang)
        if lang == "ar":
            self.fields["play_type"].choices = [
                (value, Product.PLAY_AR.get(value, text)) for value, text in self.fields["play_type"].choices
            ]
        self.fields["badge"].choices = [
            (value, Product.BADGE_AR.get(value, text) if lang == "ar" else text) if value else ("", self.t["noBadge"])
            for value, text in self.fields["badge"].choices
        ]

    def clean(self):
        # One clean(), not two: a second definition silently replaced the
        # first, and with it the age check.
        cleaned = super().clean()
        low, high = cleaned.get("age_min"), cleaned.get("age_max")
        if low is not None and high is not None and low > high:
            self.add_error("age_max", forms.ValidationError("The oldest age cannot be below the youngest.", code="age_order"))
        price, currency = cleaned.get("pprice"), cleaned.get("currency")
        if price is not None and currency is not None:
            cleaned["pprice"] = currency.to_base(price)
        return cleaned

class AddUserForm(StorefrontForm, UserCreationForm):
    copy_labels = {
        "username": "username",
        "email": "email",
        "password1": "password",
        "password2": "passwordAgain",
    }
    copy_help = {
        "username": "usernameHelp",
        "password1": "passwordHelp",
        "password2": "passwordAgainHelp",
    }

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]

    def save(self, commit=True):
        """Every signup is a Customer. There is no self-service route to Admin."""
        user = super().save(commit=commit)
        if commit:
            customers, _ = Group.objects.get_or_create(name=CUSTOMER_GROUP)
            user.groups.add(customers)
        return user


class LoginForm(StorefrontForm, AuthenticationForm):
    # AuthenticationForm's own fields, not redeclared: they carry the
    # autocomplete hints ("username", "current-password") password managers read.
    copy_labels = {"username": "username", "password": "password"}


class CheckoutForm(StorefrontForm, ModelForm):
    """Delivery address, delivery speed, payment method and the gift note.

    Card fields are deliberately absent from the model and from this form. The
    checkout screen renders number/expiry/CVC inputs because the design has
    them, but they are unnamed and never posted: this is a demo shop with no
    payment processor, and a public repo is the last place to start collecting
    card numbers into a database. `Order.payment_method` records the choice,
    nothing more.
    """

    class Meta:
        model = Order
        fields = [
            "full_name",
            "phone",
            "street",
            "city",
            "postcode",
            "delivery_option",
            "payment_method",
            "gift_wrap",
            "gift_note",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["delivery_option"].queryset = DeliveryOption.objects.all()
        self.fields["delivery_option"].empty_label = None
        self.fields["postcode"].required = False
        self.fields["gift_note"].required = False
        for name, key in (("full_name", "fullNamePh"), ("street", "streetPh"), ("city", "cityPh")):
            self.fields[name].widget.attrs["placeholder"] = self.t[key]

    def clean(self):
        cleaned = super().clean()
        # A note typed and then un-ticked should not travel with the parcel.
        if not cleaned.get("gift_wrap"):
            cleaned["gift_note"] = ""
        return cleaned


class CategoryForm(StorefrontForm, ModelForm):
    """The staff-facing form behind the category screens.

    `sort_order` is not on it: new categories go to the end and the list
    screen's arrows reorder, so nobody has to type a position.
    """

    slug = forms.SlugField(max_length=70, required=False)
    copy_labels = {
        "name": "fieldName",
        "name_ar": "fieldNameAr",
        "slug": "fieldSlug",
        "blurb": "fieldBlurb",
        "blurb_ar": "fieldBlurbAr",
        "glyph": "fieldGlyph",
        "color": "fieldColor",
    }
    copy_help = {"slug": "fieldSlugHelp", "glyph": "fieldGlyphHelp"}

    class Meta:
        model = Category
        fields = ["name", "name_ar", "slug", "blurb", "blurb_ar", "glyph", "color"]
        widgets = {"color": TextInput(attrs={"type": "color"})}

    def clean_color(self):
        color = self.cleaned_data["color"]
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
            raise forms.ValidationError("Use a hex colour like #FFC93C.", code="color")
        return color

    def clean(self):
        cleaned = super().clean()
        # Derive the slug here rather than in Category.save(), so a name whose
        # slug collides with another category is a form error, not a 500.
        slug = cleaned.get("slug") or slugify(cleaned.get("name", ""))
        if cleaned.get("name") and not slug:
            self.add_error("slug", forms.ValidationError("Could not build a URL from that name.", code="slug_empty"))
        elif slug and Category.objects.filter(slug=slug).exclude(pk=self.instance.pk).exists():
            self.add_error("slug", forms.ValidationError("Another category uses this URL.", code="slug_taken"))
        cleaned["slug"] = slug
        return cleaned


class OrderStatusForm(StorefrontForm, ModelForm):
    copy_labels = {"status": "orderStatus"}

    class Meta:
        model = Order
        fields = ["status"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = [
            (value, self.t.get(f"status_{value}", text)) for value, text in self.fields["status"].choices
        ]

    def save(self, commit=True):
        order = super().save(commit=False)
        if "status" in self.changed_data:
            order.status_changed_at = timezone.now()
        if commit:
            order.save()
        return order
