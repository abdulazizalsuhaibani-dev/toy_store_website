from django.contrib import admin
from django.utils import timezone

from .models import (
    Cart,
    CartItem,
    Category,
    Currency,
    DeliveryOption,
    Order,
    OrderItem,
    Product,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "name_ar", "slug", "color", "glyph", "sort_order", "product_count")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("sort_order", "name")

    @admin.display(description="toys")
    def product_count(self, obj):
        return obj.products.count()


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "rate", "decimal_places", "is_base", "sort_order")
    list_editable = ("rate", "is_base", "sort_order")


@admin.register(DeliveryOption)
class DeliveryOptionAdmin(admin.ModelAdmin):
    list_display = ("label", "key", "cost", "free_over", "sort_order")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("pname", "category", "pprice", "age_label", "badge", "rating", "review_count", "is_featured", "in_stock")
    list_filter = ("category", "badge", "play_type", "is_featured", "in_stock")
    search_fields = ("pname", "pname_ar", "blurb")
    list_editable = ("is_featured", "in_stock")
    prepopulated_fields = {"slug": ("pname",)}
    fieldsets = (
        (None, {"fields": ("pname", "pname_ar", "slug", "category", "pprice", "pimage")}),
        ("Copy", {"fields": ("blurb", "blurb_ar")}),
        ("On the shelf", {"fields": ("age_min", "age_max", "pieces", "play_type", "in_stock")}),
        ("Presentation", {"fields": ("badge", "card_color", "is_featured")}),
        ("Reviews", {"fields": ("rating", "review_count")}),
    )


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("pk", "user", "session_key", "count", "gift_wrap", "updated_at")
    inlines = [CartItemInline]


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    # The line is a snapshot taken at checkout; editing it after the fact would
    # rewrite what the customer was charged.
    readonly_fields = ("product", "product_name", "unit_price", "quantity")
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("reference", "full_name", "city", "total", "currency_code", "status", "payment_method", "created_at")
    list_filter = ("status", "payment_method", "delivery_option", "gift_wrap", "currency_code")
    search_fields = ("reference", "full_name", "phone", "city")
    readonly_fields = ("reference", "subtotal", "shipping_cost", "total", "currency_code", "status_changed_at", "created_at")
    inlines = [OrderItemInline]

    def save_model(self, request, obj, form, change):
        if change and "status" in form.changed_data:
            obj.status_changed_at = timezone.now()
        super().save_model(request, obj, form, change)
