from django.contrib import admin
from .models import Delivery


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'order',
        'delivery_boy',
        'status',
        'assigned_at',
        'delivered_at',
    )
    list_filter = ('status',)
    search_fields = (
        'order__id',
        'delivery_boy__username',
        'delivery_boy__phone_number',
    )