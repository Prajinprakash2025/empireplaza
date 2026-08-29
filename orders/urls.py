from django.urls import path
from . import views

urlpatterns = [
    # --- 🛒 CART URLS ---
    path('cart', views.CartDetailView.as_view(), name='cart-detail'),
    path('cart/items', views.CartItemAddView.as_view(), name='cart-item-add'),
    path('cart/items/<int:pk>', views.CartItemDetailView.as_view(), name='cart-item-detail'),
    path('cart/clear', views.CartClearView.as_view(), name='cart-clear'),

    # --- 📦 CHECKOUT & USER ORDERS ---
    path('checkout', views.CheckoutView.as_view(), name='order-checkout'),
    path('my-orders', views.CustomerOrderListView.as_view(), name='customer-order-list'),
    path('my-orders/<int:pk>', views.CustomerOrderDetailView.as_view(), name='customer-order-detail'),
    path('my-orders/<int:pk>/cancel', views.CustomerOrderCancelView.as_view(), name='customer-order-cancel'),

    # --- 👨‍💼 STAFF / ADMIN ORDER MANAGEMENT ---
    path('staff/orders', views.StaffOrderListView.as_view(), name='staff-order-list'),
    path('staff/orders/<int:pk>/status', views.StaffOrderStatusUpdateView.as_view(), name='staff-order-status-update'),

    path('cart/merge', views.CartMergeView.as_view(), name='cart-merge'),  # 👈 🌟 NEW MERGE ROUTE

]