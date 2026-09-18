from django.conf import settings
from django.conf.urls.static import static
from django.urls import path

from apps.toymodule import views

urlpatterns = [
    path('', views.index, name='index'),

    # Catalogue. One category view driven by a slug, rather than the four
    # hardcoded views this app used to carry — a new shelf is now a row.
    path('shop/', views.shop, name='shop'),
    path('c/<slug:slug>/', views.category, name='category'),
    path('toy/<slug:slug>/', views.product_detail, name='product'),
    path('search/', views.search, name='search'),

    # Cart and checkout.
    path('cart/', views.cart, name='cart'),
    path('cart/add/<int:pk>/', views.cart_add, name='cart-add'),
    path('cart/item/<int:pk>/', views.cart_update, name='cart-update'),
    path('cart/gift/', views.cart_gift, name='cart-gift'),
    path('checkout/', views.checkout, name='checkout'),
    path('order/<str:reference>/', views.order_placed, name='order-placed'),

    # Header controls. POST-only, so they are never a GET a crawler can follow
    # into changing somebody's session.
    path('set-language/', views.set_language, name='set-language'),
    path('set-currency/', views.set_currency, name='set-currency'),

    # Accounts.
    path('login', views.login, name='login'),
    path('register', views.register, name='register'),
    path('logout', views.logout, name='logout'),
    path('dashboard', views.dashboard, name='dashboard'),
    path('dashboard/account-info', views.accountInfo, name='account-info'),
    path('dashboard/orders', views.orders, name='orders'),
    path('addProduct', views.addProduct, name='addProduct'),

    path('healthz', views.healthz, name='healthz'),

    # The original category URLs. Permanently redirected rather than deleted:
    # they were the only route to a category for the life of the app, so they
    # are the ones anybody has bookmarked or linked to.
    path('baby-toys', views.legacy_category, {'name': 'Baby Toys'}),
    path('outdoors', views.legacy_category, {'name': 'Outdoors'}),
    path('dolls-and-playsets', views.legacy_category, {'name': 'Dolls and Playsets'}),
    path('cars-and-bikes', views.legacy_category, {'name': 'Cars and Bikes'}),
]

# Serve MEDIA_ROOT off the local filesystem during development only. The static()
# helper already returns [] when DEBUG is off, so the guard is not what makes
# this safe - it is here to say why nothing replaces it in production: deployed,
# uploads live in Supabase Storage and their URLs point straight at the bucket,
# so Django serves no media at all.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
