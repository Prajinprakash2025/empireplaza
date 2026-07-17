from rest_framework import serializers
from .models import Order, OrderItem
from menu.models import FoodItem
from menu.serializers import FoodItemSerializer

class OrderItemWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['food_item', 'quantity']

class OrderItemReadSerializer(serializers.ModelSerializer):
    food_item = FoodItemSerializer(read_only=True)
    
    class Meta:
        model = OrderItem
        fields = ['id', 'food_item', 'quantity', 'price']

class OrderWriteSerializer(serializers.ModelSerializer):
    items = OrderItemWriteSerializer(many=True)

    class Meta:
        model = Order
        fields = ['delivery_address', 'items']

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        user = self.context['request'].user
        
        # Calculate total price
        total_price = 0
        order_items_to_create = []
        
        for item in items_data:
            food_item = item['food_item']
            quantity = item['quantity']
            price = food_item.price * quantity
            total_price += price
            order_items_to_create.append((food_item, quantity, food_item.price))

        # Create Order
        order = Order.objects.create(
            user=user,
            total_price=total_price,
            delivery_address=validated_data['delivery_address']
        )
        
        # Create Order Items
        for food_item, qty, item_price in order_items_to_create:
            OrderItem.objects.create(
                order=order,
                food_item=food_item,
                quantity=qty,
                price=item_price
            )
            
        return order

class OrderReadSerializer(serializers.ModelSerializer):
    items = OrderItemReadSerializer(many=True, read_only=True)
    user_phone = serializers.ReadOnlyField(source='user.phone_number')

    class Meta:
        model = Order
        fields = ['id', 'user_phone', 'total_price', 'status', 'payment_status', 'delivery_address', 'created_at', 'items']