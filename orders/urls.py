from django.urls import path
from .views import UserOrderView, KitchenOrderView

urlpatterns = [
    path('', UserOrderView.as_view(), name='user_orders'),
    path('kitchen/', KitchenOrderView.as_view(), name='kitchen_orders'),
    path('kitchen/<int:pk>/', KitchenOrderView.as_view(), name='kitchen_order_update'),
]