from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/accounts/', include('accounts.urls')),

    path('api/menu/', include('menu.urls')),
    path('api/orders/', include('orders.urls')),
    # path('api/delivery/', include('delivery.urls')),
    path('api/settings/', include('settings.urls')),
    path('api/faq/', include('faq.urls')),
    path('api/feedback/', include('feedback.urls')),


] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

