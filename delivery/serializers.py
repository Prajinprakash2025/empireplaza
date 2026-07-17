from rest_framework import serializers
from .models import Delivery
from orders.serializers import OrderReadSerializer

class DeliverySerializer(serializers.ModelSerializer):
    order_details = OrderReadSerializer(source='order', read_only=True)
    delivery_boy_phone = serializers.ReadOnlyField(source='delivery_boy.phone_number')

    class Meta:
        model = Delivery
        fields = ['id', 'order', 'order_details', 'delivery_boy_phone', 'status', 'assigned_at', 'delivered_at']