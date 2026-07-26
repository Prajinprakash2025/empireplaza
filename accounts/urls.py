from django.urls import path, include
from .views import SendOTPView, VerifyOTPView, LogoutView, CookieTokenRefreshView, StaffAndAdminLoginView, StaffManagementViewSet
from rest_framework.routers import DefaultRouter


router = DefaultRouter(trailing_slash=False)
router.register(r'admin/staff', StaffManagementViewSet, basename='staff_management')

urlpatterns = [
    path('', include(router.urls)),
    path('send-otp', SendOTPView.as_view(), name='send_otp'),
    path('verify-otp', VerifyOTPView.as_view(), name='verify_otp'),
    # admin and staff login
    path('admin/login', StaffAndAdminLoginView.as_view(), name='staff_admin_login'),
    
    path('token/refresh', CookieTokenRefreshView.as_view(), name='token_refresh'),
    path('logout', LogoutView.as_view(), name='logout'),
]