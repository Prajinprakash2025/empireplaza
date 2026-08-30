from decimal import Decimal
from django.db import transaction
from rest_framework import serializers

from menu.models import MenuItem, MenuItemVariant
from .models import Cart, CartItem, Order, OrderItem


# ============================================================
# ⚙️ RESTAURANT CART LIMITS (Spam / Fake Order Protection)
# ============================================================
MAX_QUANTITY_PER_ITEM = 20   # Single item max 20 (e.g. Max 20 Biryani)
MAX_TOTAL_CART_ITEMS = 50    # Cart-il total max 50 items

# ============================================================
# 🛒 CART ITEM SERIALIZERS
# ============================================================

class CartMenuItemMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuItem
        fields = [
            'id',
            'name',
            'image',
            'dietary_preference',
            'has_variants',
            'actual_price',
            'offer_price',
            'is_available',
        ]


class CartVariantMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuItemVariant
        fields = [
            'id',
            'size_name',
            'actual_price',
            'offer_price',
            'is_available',
        ]


class CartItemReadSerializer(serializers.ModelSerializer):
    menu_item = CartMenuItemMinimalSerializer(read_only=True)
    variant = CartVariantMinimalSerializer(read_only=True)
    unit_price = serializers.SerializerMethodField()
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            'id',
            'menu_item',
            'variant',
            'quantity',
            'unit_price',
            'line_total',
            'added_at',
            'updated_at',
        ]

    def get_unit_price(self, obj):
        if obj.variant:
            price = obj.variant.offer_price if obj.variant.offer_price is not None else obj.variant.actual_price
        else:
            price = obj.menu_item.offer_price if obj.menu_item.offer_price is not None else obj.menu_item.actual_price
        return str(price) if price is not None else "0.00"

    def get_line_total(self, obj):
        unit_price = Decimal(self.get_unit_price(obj))
        return str(unit_price * obj.quantity)


class CartReadSerializer(serializers.ModelSerializer):
    items = CartItemReadSerializer(many=True, read_only=True)
    total_items = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = [
            'id',
            'items',
            'total_items',
            'total_price',
            'created_at',
            'updated_at',
        ]

    def get_total_items(self, obj):
        return sum(item.quantity for item in obj.items.all())

    def get_total_price(self, obj):
        total = Decimal('0.00')
        for item in obj.items.all():
            if item.variant:
                price = item.variant.offer_price if item.variant.offer_price is not None else item.variant.actual_price
            else:
                price = item.menu_item.offer_price if item.menu_item.offer_price is not None else item.menu_item.actual_price
            if price is not None:
                total += Decimal(str(price)) * item.quantity
        return str(total)


class CartItemAddSerializer(serializers.Serializer):
    menu_item_id = serializers.IntegerField()
    variant_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    quantity = serializers.IntegerField(
        default=1, 
        min_value=1, 
        max_value=MAX_QUANTITY_PER_ITEM,
        error_messages={
            "max_value": f"You can only add up to {MAX_QUANTITY_PER_ITEM} items of this product."
        }
    )

    def validate(self, attrs):
        menu_item_id = attrs.get('menu_item_id')
        variant_id = attrs.get('variant_id')
        quantity = attrs.get('quantity', 1)

        try:
            menu_item = MenuItem.objects.get(pk=menu_item_id)
        except MenuItem.DoesNotExist:
            raise serializers.ValidationError({"menu_item_id": "Menu item not found."})

        if not menu_item.is_available:
            raise serializers.ValidationError({"menu_item_id": "This item is currently unavailable."})

        variant = None
        if menu_item.has_variants:
            if not variant_id:
                raise serializers.ValidationError({"variant_id": "Please select a size/variant for this item."})
            try:
                variant = MenuItemVariant.objects.get(pk=variant_id, menu_item=menu_item)
            except MenuItemVariant.DoesNotExist:
                raise serializers.ValidationError({"variant_id": "Invalid variant selected for this item."})

            if not variant.is_available:
                raise serializers.ValidationError({"variant_id": "This size/variant is currently unavailable."})
        else:
            if variant_id:
                raise serializers.ValidationError({"variant_id": "This item does not have variants."})

        attrs['menu_item'] = menu_item
        attrs['variant'] = variant
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        cart, _ = Cart.objects.get_or_create(user=user)
        
        menu_item = validated_data['menu_item']
        variant = validated_data.get('variant')
        quantity = validated_data.get('quantity', 1)

        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            menu_item=menu_item,
            variant=variant,
            defaults={'quantity': quantity}
        )

        if not created:
            # 🛡️ Limit Check: Max quantity per item check
            new_quantity = cart_item.quantity + quantity
            if new_quantity > MAX_QUANTITY_PER_ITEM:
                raise serializers.ValidationError({
                    "quantity": f"Maximum limit reached! You can only add up to {MAX_QUANTITY_PER_ITEM} of this item."
                })
            cart_item.quantity = new_quantity
            cart_item.save(update_fields=['quantity', 'updated_at'])

        cart.save(update_fields=['updated_at'])
        return cart_item


class CartItemQuantitySerializer(serializers.ModelSerializer):
    quantity = serializers.IntegerField(
        min_value=1, 
        max_value=MAX_QUANTITY_PER_ITEM,
        error_messages={
            "max_value": f"Maximum limit reached! You can only order up to {MAX_QUANTITY_PER_ITEM} of this item."
        }
    )

    class Meta:
        model = CartItem
        fields = ['quantity']

    def validate_quantity(self, value):
        return value


# ============================================================
# 📦 ORDER SERIALIZERS
# ============================================================

class OrderItemReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = [
            'id',
            'menu_item',
            'variant',
            'item_name',
            'variant_name',
            'quantity',
            'unit_price',
            'line_total',
        ]


class OrderReadSerializer(serializers.ModelSerializer):
    items = OrderItemReadSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id',
            'customer_name',
            'customer_phone',
            'delivery_address',
            'special_instructions',
            'total_price',
            'status',
            'payment_status',
            'items',
            'created_at',
            'updated_at',
        ]


class OrderStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ['status', 'payment_status']


class CheckoutSerializer(serializers.Serializer):
    customer_name = serializers.CharField(max_length=150)
    customer_phone = serializers.CharField(max_length=15)
    delivery_address = serializers.CharField()
    special_instructions = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, attrs):
        user = self.context['request'].user
        cart = Cart.objects.filter(user=user).prefetch_related('items__menu_item', 'items__variant').first()

        if not cart or not cart.items.exists():
            raise serializers.ValidationError("Your cart is empty. Please add items before checkout.")

        # Availability verification (Only checking is_available toggle)
        for item in cart.items.all():
            menu_item = item.menu_item
            if not menu_item.is_available:
                raise serializers.ValidationError(f"'{menu_item.name}' is currently unavailable.")

            if item.variant:
                if not item.variant.is_available:
                    raise serializers.ValidationError(f"'{menu_item.name} - {item.variant.size_name}' is currently unavailable.")

                # -------------------------------------------------------------
                # 📦 OPTIONAL INVENTORY STOCK CHECK (Uncomment if needed)
                # -------------------------------------------------------------
                # if item.quantity > item.variant.quantity:
                #     raise serializers.ValidationError(f"Stock insufficient for '{menu_item.name}'. Available: {item.variant.quantity}")
            # else:
            #     if item.quantity > menu_item.quantity:
            #         raise serializers.ValidationError(f"Stock insufficient for '{menu_item.name}'. Available: {menu_item.quantity}")

        attrs['cart'] = cart
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user = self.context['request'].user
        cart = validated_data.pop('cart')

        customer_name = validated_data['customer_name']
        customer_phone = validated_data['customer_phone']
        delivery_address = validated_data['delivery_address']
        special_instructions = validated_data.get('special_instructions', '')

        # 1. Calculate Total & Prepare Order Items
        total_price = Decimal('0.00')
        order_items_to_create = []

        for item in cart.items.select_related('menu_item', 'variant').all():
            menu_item = item.menu_item
            variant = item.variant

            if variant:
                unit_price = variant.offer_price if variant.offer_price is not None else variant.actual_price
                variant_name = variant.size_name
            else:
                unit_price = menu_item.offer_price if menu_item.offer_price is not None else menu_item.actual_price
                variant_name = ''

            unit_price = Decimal(str(unit_price))
            line_total = unit_price * item.quantity
            total_price += line_total

            order_items_to_create.append({
                'menu_item': menu_item,
                'variant': variant,
                'item_name': menu_item.name,
                'variant_name': variant_name,
                'quantity': item.quantity,
                'unit_price': unit_price,
                'line_total': line_total,
            })

            # -------------------------------------------------------------
            # 📦 OPTIONAL INVENTORY STOCK DEDUCTION (Uncomment if needed)
            # -------------------------------------------------------------
            # if variant:
            #     variant.quantity -= item.quantity
            #     variant.save(update_fields=['quantity'])
            # else:
            #     menu_item.quantity -= item.quantity
            #     menu_item.save(update_fields=['quantity'])

        # 2. Create Main Order
        order = Order.objects.create(
            user=user,
            customer_name=customer_name,
            customer_phone=customer_phone,
            delivery_address=delivery_address,
            special_instructions=special_instructions,
            total_price=total_price,
            status='pending',
            payment_status='pending',
        )

        # 3. Create OrderItems
        for item_data in order_items_to_create:
            OrderItem.objects.create(
                order=order,
                **item_data
            )

        # 4. Clear Cart after successful order
        cart.items.all().delete()
        cart.save(update_fields=['updated_at'])

        return order


# ============================================================
# 🔄 GUEST CART TO USER CART MERGE SERIALIZER
# ============================================================

class GuestCartItemInputSerializer(serializers.Serializer):
    menu_item_id = serializers.IntegerField()
    variant_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    quantity = serializers.IntegerField(default=1, min_value=1)


class CartMergeSerializer(serializers.Serializer):
    items = GuestCartItemInputSerializer(many=True, required=False, default=[])

    def save(self):
        user = self.context['request'].user
        cart, _ = Cart.objects.get_or_create(user=user)
        items_data = self.validated_data.get('items', [])

        for item_data in items_data:
            menu_item_id = item_data.get('menu_item_id')
            variant_id = item_data.get('variant_id')
            qty = min(item_data.get('quantity', 1), MAX_QUANTITY_PER_ITEM) # 👈 Capped at MAX

            try:
                menu_item = MenuItem.objects.get(pk=menu_item_id, is_available=True)
            except MenuItem.DoesNotExist:
                continue

            variant = None
            if menu_item.has_variants:
                if not variant_id:
                    continue
                try:
                    variant = MenuItemVariant.objects.get(
                        pk=variant_id, 
                        menu_item=menu_item, 
                        is_available=True
                    )
                except MenuItemVariant.DoesNotExist:
                    continue
            else:
                variant = None

            cart_item = CartItem.objects.filter(
                cart=cart,
                menu_item=menu_item,
                variant=variant
            ).first()

            if cart_item:
                # 🛡️ Cap at max allowed limit
                cart_item.quantity = min(cart_item.quantity + qty, MAX_QUANTITY_PER_ITEM)
                cart_item.save(update_fields=['quantity', 'updated_at'])
            else:
                CartItem.objects.create(
                    cart=cart,
                    menu_item=menu_item,
                    variant=variant,
                    quantity=qty
                )

        cart.save(update_fields=['updated_at'])
        return cart