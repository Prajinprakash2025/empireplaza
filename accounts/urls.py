from django.urls import path
from .views import SendOTPView, VerifyOTPView, AdminLoginView, LogoutView, CookieTokenRefreshView

urlpatterns = [
    path('send-otp', SendOTPView.as_view(), name='send_otp'),
    path('verify-otp', VerifyOTPView.as_view(), name='verify_otp'),
    path('admin/login', AdminLoginView.as_view(), name='admin_login'),
    path('token/refresh', CookieTokenRefreshView.as_view(), name='token_refresh'),
    path('logout', LogoutView.as_view(), name='logout'),
]