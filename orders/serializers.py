from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from menu.models import MenuItem, MenuItemVariant
from .models import Cart, CartItem, Order, OrderItem
from accounts.models import Address


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
            'packing_charge',
            'is_available',
        ]

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if instance.image:
            from menu.serializers import resolve_media_url
            ret['image'] = resolve_media_url(self.context.get('request'), instance.image)
        return ret


class CartVariantMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuItemVariant
        fields = [
            'id',
            'size_name',
            'actual_price',
            'offer_price',
            'packing_charge',
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
    total_packing_charge = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = [
            'id',
            'items',
            'total_items',
            'total_price',
            'total_packing_charge',
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

    def get_total_packing_charge(self, obj):
        total = Decimal('0.00')
        for item in obj.items.all():
            pkg = Decimal('0.00')
            if item.variant and item.variant.packing_charge is not None and item.variant.packing_charge > 0:
                pkg = Decimal(str(item.variant.packing_charge))
            elif item.menu_item and item.menu_item.packing_charge:
                pkg = Decimal(str(item.menu_item.packing_charge))
            total += pkg * item.quantity
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
    delivery_boy = serializers.SerializerMethodField()
    packing_duration_mins = serializers.SerializerMethodField()

    def get_delivery_boy(self, obj):
        try:
            if hasattr(obj, 'delivery_details') and obj.delivery_details:
                boy = obj.delivery_details.delivery_boy
                profile = getattr(boy, 'delivery_profile', None)
                name = (boy.get_full_name() or boy.username or boy.phone_number).strip()
                return {
                    'id': boy.id,
                    'name': name,
                    'phone': boy.phone_number,
                    'employee_id': getattr(boy, 'employee_id', None),
                    'status': obj.delivery_details.status,
                    'latitude': profile.current_latitude if profile else None,
                    'longitude': profile.current_longitude if profile else None,
                }
        except Exception:
            pass
        return None

    def get_packing_duration_mins(self, obj):
        if obj.packed_at and obj.created_at:
            diff_secs = (obj.packed_at - obj.created_at).total_seconds()
            return max(1, round(diff_secs / 60))
        return None

    class Meta:
        model = Order
        fields = [
            'id',
            'customer_name',
            'customer_phone',
            'delivery_address',
            'special_instructions',
            'total_price',
            'delivery_fee',
            'delivery_distance_km',
            'status',
            'payment_status',
            'items',
            'delivery_boy',
            'created_at',
            'updated_at',
            'packed_at',
            'packing_duration_mins',
        ]


class OrderStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ['status', 'payment_status', 'packed_at']

    def update(self, instance, validated_data):
        new_status = validated_data.get('status')
        if new_status in ['ready_for_pickup', 'out_for_delivery', 'delivered'] and not instance.packed_at:
            instance.packed_at = timezone.now()
        return super().update(instance, validated_data)


from decimal import Decimal
from django.db import transaction
from rest_framework import serializers

from accounts.models import Address
from menu.models import MenuItem, MenuItemVariant
from settings.models import SiteSetting
from .distance_utils import calculate_haversine_distance_km, calculate_delivery_fee
from .models import Cart, CartItem, Order, OrderItem


class CheckoutSerializer(serializers.Serializer):

    address_id = serializers.IntegerField()

    special_instructions = serializers.CharField(
        required=False,
        allow_blank=True,
        default=''
    )

    payment_method = serializers.CharField(
        required=False,
        allow_blank=True,
        default='online'
    )

    def validate(self, attrs):

        user = self.context['request'].user

        # -----------------------------------------
        # 1. CHECK SELECTED ADDRESS
        # -----------------------------------------

        try:
            address = Address.objects.get(
                id=attrs['address_id'],
                user=user
            )
        except Address.DoesNotExist:
            raise serializers.ValidationError({
                'address_id': 'Invalid address selected.'
            })

        # -----------------------------------------
        # 2. GET USER CART
        # -----------------------------------------

        cart = Cart.objects.filter(
            user=user
        ).prefetch_related(
            'items__menu_item',
            'items__variant'
        ).first()

        if not cart or not cart.items.exists():
            raise serializers.ValidationError(
                "Your cart is empty. Please add items before checkout."
            )

        # -----------------------------------------
        # 3. CHECK STORE STATUS & DELIVERY RADIUS
        # -----------------------------------------

        site_settings = SiteSetting.objects.first()
        if site_settings and not site_settings.is_open:
            raise serializers.ValidationError(
                "Empire Plaza is currently closed for online orders. Browsing is permitted, but new orders are paused until opening hours."
            )

        if site_settings and site_settings.delivery_radius and float(site_settings.delivery_radius) > 0:
            max_radius = float(site_settings.delivery_radius)
            cust_lat = address.latitude
            cust_lng = address.longitude

            # If address has no coordinates, attempt fallback geocoding
            if not cust_lat or not cust_lng or (cust_lat == 0 and cust_lng == 0):
                from .distance_utils import geocode_address
                g_lat, g_lng = geocode_address(address.address_line, address.city, address.pincode)
                if g_lat and g_lng:
                    cust_lat, cust_lng = g_lat, g_lng
                    address.latitude = g_lat
                    address.longitude = g_lng
                    address.save(update_fields=['latitude', 'longitude'])

            if cust_lat and cust_lng and site_settings.latitude and site_settings.longitude:
                distance_km = calculate_haversine_distance_km(
                    site_settings.latitude,
                    site_settings.longitude,
                    cust_lat,
                    cust_lng,
                )
                if distance_km > max_radius:
                    raise serializers.ValidationError(
                        f"Delivery unavailable: Your address is {distance_km:.1f} KM away, exceeding our maximum delivery radius of {max_radius:.1f} KM."
                    )
            elif site_settings.latitude and site_settings.longitude:
                raise serializers.ValidationError(
                    f"Delivery location coordinates required. Please ensure your delivery address has a pin on the map within {max_radius:.1f} KM of Empire Plaza."
                )

        # -----------------------------------------
        # 4. CHECK PAYMENT METHOD & SECURITY
        # -----------------------------------------
        payment_method = attrs.get('payment_method', 'online')
        if payment_method == 'cod':
            if site_settings and not site_settings.is_cod_enabled:
                raise serializers.ValidationError(
                    "Cash on Delivery is currently disabled by Empire Plaza. Please choose an online payment method."
                )
        elif payment_method != 'cod' and not self.context.get('verified_online_payment'):
            raise serializers.ValidationError(
                "Direct checkout is only permitted for Cash on Delivery. Online payments must be verified via Razorpay."
            )

        # -----------------------------------------
        # 5. CHECK ITEM AVAILABILITY
        # -----------------------------------------

        for item in cart.items.all():

            menu_item = item.menu_item

            if not menu_item.is_available:
                raise serializers.ValidationError(
                    f"'{menu_item.name}' is currently unavailable."
                )

            if item.variant:

                if not item.variant.is_available:
                    raise serializers.ValidationError(
                        f"'{menu_item.name} - "
                        f"{item.variant.size_name}' "
                        "is currently unavailable."
                    )

        attrs['address'] = address
        attrs['cart'] = cart

        return attrs

    @transaction.atomic
    def create(self, validated_data):

        user = self.context['request'].user

        cart = validated_data.pop('cart')
        address = validated_data.pop('address')

        special_instructions = validated_data.get(
            'special_instructions',
            ''
        )

        # -----------------------------------------
        # 4. CREATE ADDRESS SNAPSHOT
        # -----------------------------------------

        customer_name = address.full_name
        customer_phone = address.phone_number

        delivery_address = (
            f"{address.full_name}, "
            f"{address.address_line}, "
            f"{address.city}, "
            f"{address.state} - "
            f"{address.pincode}"
        )

        # -----------------------------------------
        # 5. CALCULATE TOTAL
        # -----------------------------------------

        total_price = Decimal('0.00')

        order_items_to_create = []

        for item in cart.items.select_related(
            'menu_item',
            'variant'
        ).all():

            menu_item = item.menu_item
            variant = item.variant

            if variant:
                unit_price = (
                    variant.offer_price
                    if variant.offer_price is not None
                    else variant.actual_price
                )

                variant_name = variant.size_name

            else:
                unit_price = (
                    menu_item.offer_price
                    if menu_item.offer_price is not None
                    else menu_item.actual_price
                )

                variant_name = ''

            unit_price = Decimal(str(unit_price))

            line_total = unit_price * item.quantity

            total_price += line_total

            # Variant packing charge or base item fallback
            pkg = Decimal('0.00')
            if variant and variant.packing_charge is not None and variant.packing_charge > 0:
                pkg = Decimal(str(variant.packing_charge))
            elif menu_item and menu_item.packing_charge:
                pkg = Decimal(str(menu_item.packing_charge))
            total_price += pkg * item.quantity

            order_items_to_create.append({
                'menu_item': menu_item,
                'variant': variant,
                'item_name': menu_item.name,
                'variant_name': variant_name,
                'quantity': item.quantity,
                'unit_price': unit_price,
                'line_total': line_total,
            })

        # -----------------------------------------
        # 5.1 CALCULATE DYNAMIC DISTANCE & DELIVERY FEE
        # -----------------------------------------
        site_settings = SiteSetting.objects.first()
        distance_km = 0.0
        if site_settings and address.latitude and address.longitude:
            distance_km = calculate_haversine_distance_km(
                site_settings.latitude,
                site_settings.longitude,
                address.latitude,
                address.longitude,
            )

        delivery_fee = Decimal('0.00')
        if order_items_to_create:
            delivery_fee = calculate_delivery_fee(distance_km, total_price, site_settings)
            total_price += delivery_fee

        # -----------------------------------------
        # 6. CREATE ORDER
        # -----------------------------------------

        payment_method = self.validated_data.get('payment_method', 'online')
        initial_payment_status = (
            'pending'
            if (payment_method == 'cod' and site_settings and site_settings.is_cod_enabled)
            else 'completed'
        )

        order = Order.objects.create(
            user=user,
            customer_name=customer_name,
            customer_phone=customer_phone,
            delivery_address=delivery_address,
            special_instructions=special_instructions,
            total_price=total_price,
            delivery_fee=delivery_fee,
            delivery_distance_km=distance_km,
            status='preparing',
            payment_status=initial_payment_status,
        )

        # -----------------------------------------
        # 7. CREATE ORDER ITEMS
        # -----------------------------------------

        for item_data in order_items_to_create:

            OrderItem.objects.create(
                order=order,
                **item_data
            )

        # -----------------------------------------
        # 8. CLEAR CART
        # -----------------------------------------

        cart.items.all().delete()

        cart.save(
            update_fields=['updated_at']
        )

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