from django.urls import path
from .views import (
    AvailableDeliveriesView,
    AcceptDeliveryView,
    CompleteDeliveryView,
    CurrentDeliveryView,
    DeliveryHistoryView,
    ToggleDutyView,
    DeliveryProfileView,
)

urlpatterns = [
    path(
        'available',
        AvailableDeliveriesView.as_view(),
        name='available_deliveries'
    ),
    path(
        'current',
        CurrentDeliveryView.as_view(),
        name='current_delivery'
    ),
    path(
        'history',
        DeliveryHistoryView.as_view(),
        name='delivery_history'
    ),
    path(
        'toggle-duty',
        ToggleDutyView.as_view(),
        name='toggle_duty'
    ),
    path(
        'profile',
        DeliveryProfileView.as_view(),
        name='delivery_profile'
    ),
    path(
        'orders/<int:order_id>/accept',
        AcceptDeliveryView.as_view(),
        name='accept_delivery'
    ),
    path(
        'orders/<int:order_id>/complete',
        CompleteDeliveryView.as_view(),
        name='complete_delivery'
    ),
]