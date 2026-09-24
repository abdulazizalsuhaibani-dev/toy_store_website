import re

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import Group, User
from django.forms import ModelForm
from django.utils import timezone
from django.utils.text import slugify
from django.forms.widgets import PasswordInput, TextInput

from .models import Category, DeliveryOption, Order, Product
from .roles import CUSTOMER_GROUP


class AddProductForm(ModelForm):
    """The staff-facing form behind /addProduct.

    Fields are listed explicitly rather than `__all__`: the model now carries
    columns nobody types by hand (`slug`, `created_at`), and `__all__` would
    have put them on the page the moment they were added.

    `pcategory` used to be a free-text CharField here, so two products could
    sit in "Baby toys" and "Baby Toys" and only one of them would ever show up
    on the category page. It is a ForeignKey now, which makes that unspellable.
    """

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
            "rating",
            "review_count",
            "in_stock",
            "is_featured",
        ]
        labels = {
            "pname": "Name",
            "pname_ar": "Name (Arabic)",
            "pimage": "Photo",
            "pprice": "Price",
            "blurb": "Description",
            "blurb_ar": "Description (Arabic)",
            "age_min": "Youngest age",
            "age_max": "Oldest age",
            "card_color": "Card colour",
            "review_count": "Number of reviews",
        }
        help_texts = {
            "card_color": "Hex colour behind the photo on the product card, e.g. #CDEBFB.",
            "is_featured": "Show this toy in the 'Flying off the shelves' row on the homepage.",
        }
        widgets = {
            "blurb": forms.Textarea(attrs={"rows": 3}),
            "blurb_ar": forms.Textarea(attrs={"rows": 3}),
            "card_color": forms.TextInput(attrs={"type": "color"}),
        }

    def clean(self):
        cleaned = super().clean()
        low, high = cleaned.get("age_min"), cleaned.get("age_max")
        if low is not None and high is not None and low > high:
            self.add_error("age_max", "The oldest age cannot be below the youngest age.")
        return cleaned


class AddUserForm(UserCreationForm):
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


class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=TextInput())
    password = forms.CharField(widget=PasswordInput())


class CheckoutForm(ModelForm):
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

    def clean(self):
        cleaned = super().clean()
        # A note typed and then un-ticked should not travel with the parcel.
        if not cleaned.get("gift_wrap"):
            cleaned["gift_note"] = ""
        return cleaned


class CategoryForm(ModelForm):
    """The staff-facing form behind the category screens.

    `sort_order` is not on it: new categories go to the end and the list
    screen's arrows reorder, so nobody has to type a position.
    """

    slug = forms.SlugField(max_length=70, required=False, help_text="Leave blank to use the name.")

    class Meta:
        model = Category
        fields = ["name", "name_ar", "slug", "blurb", "blurb_ar", "glyph", "color"]
        widgets = {"color": TextInput(attrs={"type": "color"})}

    def clean_color(self):
        color = self.cleaned_data["color"]
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
            raise forms.ValidationError("Use a hex colour like #FFC93C.")
        return color

    def clean(self):
        cleaned = super().clean()
        # Derive the slug here rather than in Category.save(), so a name whose
        # slug collides with another category is a form error, not a 500.
        slug = cleaned.get("slug") or slugify(cleaned.get("name", ""))
        if cleaned.get("name") and not slug:
            self.add_error("slug", "Could not build a URL from that name; enter one.")
        elif slug and Category.objects.filter(slug=slug).exclude(pk=self.instance.pk).exists():
            self.add_error("slug", "Another category already uses this URL.")
        cleaned["slug"] = slug
        return cleaned


class OrderStatusForm(ModelForm):
    class Meta:
        model = Order
        fields = ["status"]

    def save(self, commit=True):
        order = super().save(commit=False)
        if "status" in self.changed_data:
            order.status_changed_at = timezone.now()
        if commit:
            order.save()
        return order
