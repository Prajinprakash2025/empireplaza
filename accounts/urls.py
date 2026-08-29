from django.urls import path, include
from .views import SendOTPView, SignUpView, UserProfileView, VerifyOTPView, LogoutView, CookieTokenRefreshView, StaffAndAdminLoginView, StaffManagementViewSet,DeliveryBoyManagementViewSet, DeliveryBoyLoginView,ContactMessageViewSet,TableBookingViewSet
from rest_framework.routers import DefaultRouter


router = DefaultRouter(trailing_slash=False)
router.register(r'admin/staff', StaffManagementViewSet, basename='staff_management')
router.register(r'admin/delivery-boys', DeliveryBoyManagementViewSet, basename='delivery_boy_management')
router.register(r'contact', ContactMessageViewSet, basename='contact_messages')
router.register(r'table-bookings', TableBookingViewSet, basename='table_bookings')




urlpatterns = [
    path('', include(router.urls)),

    path('signup', SignUpView.as_view(), name='user_signup'),           # 👈 Sign Up (Full Name, Phone, Email)
    path('send-otp', SendOTPView.as_view(), name='send_otp'),           # 👈 Login (Existing Users)
    path('verify-otp', VerifyOTPView.as_view(), name='verify_otp'),     # 👈 OTP Verification
    path('profile', UserProfileView.as_view(), name='user_profile'),
    path('send-otp', SendOTPView.as_view(), name='send_otp'),
    path('verify-otp', VerifyOTPView.as_view(), name='verify_otp'),
    # admin and staff login
    path('admin/login', StaffAndAdminLoginView.as_view(), name='staff_admin_login'),
    # delivery boy login
    path('delivery-boy/login', DeliveryBoyLoginView.as_view(), name='delivery_boy_login'),

    
    
    path('token/refresh', CookieTokenRefreshView.as_view(), name='token_refresh'),
    path('logout', LogoutView.as_view(), name='logout'),
]