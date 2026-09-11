from django.urls import path
from .views import (
    AvailableDeliveriesView,
    AcceptDeliveryView,
    CompleteDeliveryView,
)

urlpatterns = [
    path(
        'available',
        AvailableDeliveriesView.as_view(),
        name='available_deliveries'
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