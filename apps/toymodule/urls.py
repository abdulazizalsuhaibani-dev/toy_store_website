from django.urls import path, re_path
from apps.toymodule import views
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('', views.index, name='index'),
    path('baby-toys', views.babyToys),
    path('outdoors', views.outdoors),
    path('dolls-and-playsets', views.dollsAndPlaysets),
    path('cars-and-bikes', views.carsAndBikes),
    path('login', views.login, name='login'),
    path('register', views.register),
    path('logout', views.logout, name='logout'),
    path('dashboard', views.dashboard, name='dashboard'),
    path('dashboard/account-info', views.accountInfo, name='account-info'),
    path('addProduct', views.addProduct, name='addProduct'),
    path('healthz', views.healthz, name='healthz'),
]

# Serve MEDIA_ROOT off the local filesystem during development only. The static()
# helper already returns [] when DEBUG is off, so the guard is not what makes
# this safe - it is here to say why nothing replaces it in production: deployed,
# uploads live in Supabase Storage and their URLs point straight at the bucket,
# so Django serves no media at all.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
