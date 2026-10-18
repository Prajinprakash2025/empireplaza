from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from orders import views as orders_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/accounts/', include('accounts.urls')),

    path('api/menu/', include('menu.urls')),
    path('api/orders/', include('orders.urls')),
    path('api/delivery/', include('delivery.urls')),
    path('api/settings/', include('settings.urls')),
    path('api/faq/', include('faq.urls')),
    path('api/feedback/', include('feedback.urls')),

    # Direct Razorpay Standard Web Checkout Endpoints
    path('api/create-order', orders_views.RazorpayCreateOrderView.as_view(), name='api-create-order'),
    path('api/verify-payment', orders_views.RazorpayVerifyPaymentView.as_view(), name='api-verify-payment'),

    # Direct fallback media route (Gunicorn / Reverse proxy compatibility)
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
