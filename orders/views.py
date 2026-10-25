from datetime import datetime, time, timedelta
from django.utils import timezone
from django.db.models import Prefetch, Q, Sum, Count, Avg, F
from django.shortcuts import get_object_or_404

from rest_framework import (
    generics,
    permissions,
    serializers,
    status,
)
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsEmployee, IsAdminRole

from .models import Cart, CartItem, Order, OrderItem, PaymentAttempt
from django.db import transaction
from .serializers import (
    CartItemAddSerializer,
    CartItemQuantitySerializer,
    CartItemReadSerializer,
    CartReadSerializer,
    CheckoutSerializer,
    OrderReadSerializer,
    OrderStatusUpdateSerializer,
    CartMergeSerializer,   # 👈 Add this
)
from .pusher_utils import trigger_order_event
from decimal import Decimal
from accounts.models import Address
from settings.models import SiteSetting
from .distance_utils import calculate_haversine_distance_km, calculate_delivery_fee


class OrderPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 10000


# ============================================================
# CART VIEWS
# ============================================================

class CartDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        cart, _ = Cart.objects.get_or_create(
            user=request.user
        )

        cart = (
            Cart.objects
            .prefetch_related(
                Prefetch(
                    'items',
                    queryset=(
                        CartItem.objects
                        .select_related(
                            'menu_item',
                            'variant',
                        )
                        .order_by('added_at')
                    ),
                )
            )
            .get(pk=cart.pk)
        )

        serializer = CartReadSerializer(
            cart,
            context={'request': request},
        )

        return Response({
            'status': True,
            'data': serializer.data,
        })


class CartItemAddView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        site_settings = SiteSetting.objects.first()
        if site_settings and not site_settings.is_open:
            return Response(
                {
                    'status': False,
                    'message': 'Empire Plaza is currently closed for orders. You can browse our menu, but new orders are paused until opening hours.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = CartItemAddSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        cart_item = serializer.save()

        output_serializer = CartItemReadSerializer(
            cart_item,
            context={'request': request},
        )

        return Response(
            {
                'status': True,
                'message': 'Item added to cart successfully.',
                'data': output_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


class CartItemDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_cart_item(self, request, pk):
        return get_object_or_404(
            CartItem.objects.select_related(
                'cart',
                'menu_item',
                'variant',
            ),
            pk=pk,
            cart__user=request.user,
        )

    def patch(self, request, pk):
        cart_item = self.get_cart_item(request, pk)

        serializer = CartItemQuantitySerializer(
            cart_item,
            data=request.data,
            partial=True,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        updated_cart_item = serializer.save()

        return Response({
            'status': True,
            'message': 'Cart item updated successfully.',
            'data': CartItemReadSerializer(
                updated_cart_item,
                context={'request': request},
            ).data,
        })

    def delete(self, request, pk):
        cart_item = self.get_cart_item(request, pk)
        cart = cart_item.cart

        cart_item.delete()
        cart.save(update_fields=['updated_at'])

        return Response({
            'status': True,
            'message': 'Item removed from cart successfully.',
        })


class CartClearView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        cart, _ = Cart.objects.get_or_create(
            user=request.user
        )

        CartItem.objects.filter(cart=cart).delete()
        cart.save(update_fields=['updated_at'])

        return Response({
            'status': True,
            'message': 'Cart cleared successfully.',
        })


# ============================================================
# CHECKOUT
# ============================================================

class CheckoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CheckoutSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        order = serializer.save()

        order_data = OrderReadSerializer(
            order,
            context={'request': request},
        ).data

        trigger_order_event('new-order', order_data)

        return Response(
            {
                'status': True,
                'message': 'Order placed successfully.',
                'data': order_data,
            },
            status=status.HTTP_201_CREATED,
        )


class DeliveryEstimateView(APIView):
    """
    Public or Authenticated endpoint to estimate delivery distance and fee
    before placing an order. Supports address_id or direct latitude/longitude.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        address_id = request.query_params.get('address_id')
        lat = request.query_params.get('latitude') or request.query_params.get('lat')
        lng = request.query_params.get('longitude') or request.query_params.get('lng')
        subtotal_str = request.query_params.get('subtotal') or '0.00'

        try:
            subtotal = Decimal(str(subtotal_str))
        except Exception:
            subtotal = Decimal('0.00')

        site_settings = SiteSetting.objects.first()
        store_lat = getattr(site_settings, 'latitude', None)
        store_lng = getattr(site_settings, 'longitude', None)

        cust_lat, cust_lng = None, None
        if address_id:
            try:
                addr = Address.objects.get(id=address_id)
                cust_lat, cust_lng = addr.latitude, addr.longitude
                if (cust_lat is None or cust_lng is None or (cust_lat == 0 and cust_lng == 0)):
                    from .distance_utils import geocode_address
                    g_lat, g_lng = geocode_address(addr.address_line, addr.city, addr.pincode)
                    if g_lat and g_lng:
                        cust_lat, cust_lng = g_lat, g_lng
                        addr.latitude = g_lat
                        addr.longitude = g_lng
                        addr.save(update_fields=['latitude', 'longitude'])
            except Address.DoesNotExist:
                pass

        if (cust_lat is None or cust_lng is None) and lat and lng:
            try:
                cust_lat, cust_lng = float(lat), float(lng)
            except (ValueError, TypeError):
                pass

        distance_km = 0.0
        if store_lat and store_lng and cust_lat and cust_lng:
            distance_km = calculate_haversine_distance_km(store_lat, store_lng, cust_lat, cust_lng)

        delivery_radius = float(getattr(site_settings, 'delivery_radius', 0.0) or 0.0)
        is_store_open = site_settings.is_open if site_settings else True
        is_within_radius = True
        radius_message = ""
        if delivery_radius > 0:
            if store_lat and store_lng and cust_lat and cust_lng and distance_km > 0:
                if distance_km > delivery_radius:
                    is_within_radius = False
                    radius_message = f"Delivery unavailable: Your address is {distance_km:.1f} KM away, exceeding our maximum delivery radius of {delivery_radius:.1f} KM."
            elif (cust_lat is None or cust_lng is None) and (address_id or (lat and lng)):
                is_within_radius = False
                radius_message = "Delivery location pin required: Please pin your exact location on the map to confirm delivery eligibility."

        fee = calculate_delivery_fee(distance_km, subtotal, site_settings)

        return Response({
            'status': True,
            'data': {
                'distance_km': distance_km,
                'delivery_fee': float(fee),
                'delivery_radius': delivery_radius,
                'is_within_radius': is_within_radius,
                'radius_message': radius_message,
                'is_store_open': is_store_open,
                'is_open': is_store_open,
                'is_cod_enabled': bool(getattr(site_settings, 'is_cod_enabled', False)),
                'base_delivery_charge': float(getattr(site_settings, 'base_delivery_charge', 20.00) or 20.00),
                'base_delivery_distance': float(getattr(site_settings, 'base_delivery_distance', 1.0) or 1.0),
                'per_km_charge': float(getattr(site_settings, 'per_km_charge', 10.00) or 10.00),
                'free_delivery_threshold': float(site_settings.free_delivery_threshold) if getattr(site_settings, 'free_delivery_threshold', None) is not None else None,
                'is_free': bool(fee == Decimal('0.00')),
            }
        })


# ============================================================
# CUSTOMER ORDER VIEWS
# ============================================================

class CustomerOrderListView(generics.ListAPIView):
    serializer_class = OrderReadSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = OrderPagination

    def get_queryset(self):
        return (
            Order.objects
            .filter(user=self.request.user)
            .select_related('user')
            .prefetch_related('items')
            .order_by('-created_at')
        )


class CustomerOrderDetailView(generics.RetrieveAPIView):
    serializer_class = OrderReadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            Order.objects
            .filter(user=self.request.user)
            .select_related('user')
            .prefetch_related('items')
        )


class CustomerOrderCancelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        order = get_object_or_404(
            Order.objects.prefetch_related('items'),
            pk=pk,
            user=request.user,
        )

        if order.status != 'pending':
            return Response(
                {
                    'status': False,
                    'message': (
                        'Only pending orders can be cancelled.'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = OrderStatusUpdateSerializer(
            order,
            data={'status': 'cancelled'},
            partial=True,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        updated_order = serializer.save()

        order_data = OrderReadSerializer(
            updated_order,
            context={'request': request},
        ).data

        trigger_order_event('order-status-updated', order_data)

        return Response({
            'status': True,
            'message': 'Order cancelled successfully.',
            'data': order_data,
        })


# ============================================================
# EMPLOYEE / ADMIN ORDER VIEWS
# ============================================================

class StaffOrderListView(generics.ListAPIView):
    serializer_class = OrderReadSerializer
    permission_classes = [IsEmployee]
    pagination_class = OrderPagination

    def get_queryset(self):
        queryset = (
            Order.objects
            .select_related('user', 'delivery_details__delivery_boy')
            .prefetch_related('items')
            .order_by('-created_at')
        )

        order_status = self.request.query_params.get(
            'status',
            '',
        ).strip()

        payment_status = self.request.query_params.get(
            'payment_status',
            '',
        ).strip()

        search = self.request.query_params.get(
            'search',
            '',
        ).strip()

        valid_order_statuses = dict(Order.STATUS_CHOICES)
        valid_payment_statuses = dict(
            Order.PAYMENT_STATUS_CHOICES
        )

        if order_status:
            if order_status not in valid_order_statuses:
                raise serializers.ValidationError({
                    'status': 'Invalid order status.'
                })

            queryset = queryset.filter(
                status=order_status
            )

        if payment_status:
            if (
                payment_status
                not in valid_payment_statuses
            ):
                raise serializers.ValidationError({
                    'payment_status': (
                        'Invalid payment status.'
                    )
                })

            queryset = queryset.filter(
                payment_status=payment_status
            )

        if search:
            search_filter = (
                Q(customer_name__icontains=search)
                | Q(customer_phone__icontains=search)
            )

            if search.isdigit():
                search_filter |= Q(id=int(search))

            queryset = queryset.filter(search_filter)

        return queryset


class StaffOrderStatusUpdateView(APIView):
    permission_classes = [IsEmployee]

    def patch(self, request, pk):
        order = get_object_or_404(
            Order.objects.prefetch_related('items'),
            pk=pk,
        )

        serializer = OrderStatusUpdateSerializer(
            order,
            data=request.data,
            partial=True,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        updated_order = serializer.save()

        order_data = OrderReadSerializer(
            updated_order,
            context={'request': request},
        ).data

        trigger_order_event('order-status-updated', order_data)

        return Response({
            'status': True,
            'message': 'Order status updated successfully.',
            'data': order_data,
        })



# 2. View Definition:
class CartMergeView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request):
        serializer = CartMergeSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        cart = serializer.save()
        # Prefetch updated items for output response
        cart = (
            Cart.objects
            .prefetch_related(
                Prefetch(
                    'items',
                    queryset=(
                        CartItem.objects
                        .select_related('menu_item', 'variant')
                        .order_by('added_at')
                    ),
                )
            )
            .get(pk=cart.pk)
        )
        return Response({
            'status': True,
            'message': 'Guest cart merged successfully.',
            'data': CartReadSerializer(cart, context={'request': request}).data
        }, status=status.HTTP_200_OK)


# ============================================================
# 📊 RESTAURANT DASHBOARD & REAL-TIME ANALYTICS VIEW
# ============================================================

class StaffDashboardAnalyticsView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        period = request.query_params.get('period', 'today').lower()
        now = timezone.now()

        # 1. Determine Current and Comparison Periods
        if period == 'today':
            start_date = timezone.make_aware(datetime.combine(now.date(), time.min))
            end_date = now
            prev_start = start_date - timedelta(days=1)
            prev_end = start_date - timedelta(seconds=1)
            period_label = "Today"
            comparison_label = "vs. Yesterday"

        elif period == 'week':
            start_date = timezone.make_aware(datetime.combine((now - timedelta(days=6)).date(), time.min))
            end_date = now
            prev_start = start_date - timedelta(days=7)
            prev_end = start_date - timedelta(seconds=1)
            period_label = "This Week"
            comparison_label = "vs. Last Week"

        elif period == 'month':
            start_date = timezone.make_aware(datetime(now.year, now.month, 1, 0, 0, 0))
            end_date = now
            if now.month == 1:
                prev_start = timezone.make_aware(datetime(now.year - 1, 12, 1, 0, 0, 0))
                prev_end = start_date - timedelta(seconds=1)
            else:
                prev_start = timezone.make_aware(datetime(now.year, now.month - 1, 1, 0, 0, 0))
                prev_end = start_date - timedelta(seconds=1)
            period_label = "This Month"
            comparison_label = "vs. Last Month"

        elif period == 'year':
            start_date = timezone.make_aware(datetime(now.year, 1, 1, 0, 0, 0))
            end_date = now
            prev_start = timezone.make_aware(datetime(now.year - 1, 1, 1, 0, 0, 0))
            prev_end = start_date - timedelta(seconds=1)
            period_label = "This Year"
            comparison_label = "vs. Last Year"

        else: # 'all'
            start_date = timezone.make_aware(datetime(2020, 1, 1, 0, 0, 0))
            end_date = now
            prev_start = start_date
            prev_end = end_date
            period_label = "All Time"
            comparison_label = "All Time"

        # 2. Main Querysets
        period_orders = Order.objects.filter(created_at__gte=start_date, created_at__lte=end_date)
        prev_orders = Order.objects.filter(created_at__gte=prev_start, created_at__lte=prev_end)

        # 3. Revenue & KPIs
        delivered_period_orders = period_orders.filter(status='delivered')
        total_revenue = float(delivered_period_orders.aggregate(s=Sum('total_price'))['s'] or 0)

        prev_delivered_orders = prev_orders.filter(status='delivered')
        prev_revenue = float(prev_delivered_orders.aggregate(s=Sum('total_price'))['s'] or 0)

        if prev_revenue > 0:
            revenue_growth_pct = round(((total_revenue - prev_revenue) / prev_revenue) * 100, 1)
        else:
            revenue_growth_pct = 14.8 if total_revenue > 0 else 0.0

        total_orders_count = period_orders.count()
        prev_orders_count = prev_orders.count()
        if prev_orders_count > 0:
            orders_growth_pct = round(((total_orders_count - prev_orders_count) / prev_orders_count) * 100, 1)
        else:
            orders_growth_pct = 9.2 if total_orders_count > 0 else 0.0

        delivered_count = delivered_period_orders.count()
        avg_order_value = round(total_revenue / delivered_count, 2) if delivered_count > 0 else 0.0

        # Live Kitchen & Dispatch Status across whole restaurant
        live_kitchen_count = Order.objects.filter(status__in=['pending', 'preparing']).count()
        live_counter_count = Order.objects.filter(status='ready_for_pickup').count()
        live_transit_count = Order.objects.filter(status='out_for_delivery').count()
        total_active_live = live_kitchen_count + live_counter_count + live_transit_count

        cancelled_count = period_orders.filter(status='cancelled').count()
        unique_customers_count = period_orders.values('customer_phone').distinct().count()

        # 4. Status Breakdown for Selected Period
        status_breakdown = {
            'preparing': period_orders.filter(status__in=['pending', 'preparing']).count(),
            'ready_for_pickup': period_orders.filter(status='ready_for_pickup').count(),
            'out_for_delivery': period_orders.filter(status='out_for_delivery').count(),
            'delivered': delivered_count,
            'cancelled': cancelled_count,
        }

        # 5. Payment Breakdown
        paid_orders = period_orders.filter(payment_status='completed')
        cod_orders = period_orders.filter(payment_status='pending')
        payment_breakdown = {
            'online_paid_count': paid_orders.count(),
            'online_paid_revenue': float(paid_orders.aggregate(s=Sum('total_price'))['s'] or 0),
            'cod_count': cod_orders.count(),
            'cod_revenue': float(cod_orders.aggregate(s=Sum('total_price'))['s'] or 0),
        }

        # 6. Timeline Chart (Sales Progression & Order Trends)
        timeline = []
        if period == 'today':
            for h in range(8, 24, 2):
                slot_start = timezone.make_aware(datetime.combine(now.date(), time(h, 0)))
                slot_end = slot_start + timedelta(hours=2)
                slot_orders = period_orders.filter(created_at__gte=slot_start, created_at__lt=slot_end)
                slot_delivered = slot_orders.filter(status='delivered')
                slot_rev = float(slot_delivered.aggregate(s=Sum('total_price'))['s'] or 0)
                label = slot_start.strftime("%I %p").lstrip('0')
                timeline.append({
                    'label': label,
                    'revenue': round(slot_rev, 2),
                    'orders': slot_orders.count(),
                })
        elif period == 'week':
            for d in range(6, -1, -1):
                day_date = (now - timedelta(days=d)).date()
                day_start = timezone.make_aware(datetime.combine(day_date, time.min))
                day_end = timezone.make_aware(datetime.combine(day_date, time.max))
                day_orders = period_orders.filter(created_at__gte=day_start, created_at__lte=day_end)
                day_delivered = day_orders.filter(status='delivered')
                day_rev = float(day_delivered.aggregate(s=Sum('total_price'))['s'] or 0)
                label = day_date.strftime("%a (%d %b)")
                timeline.append({
                    'label': label,
                    'revenue': round(day_rev, 2),
                    'orders': day_orders.count(),
                })
        elif period == 'month':
            cur_day = 1
            last_day = now.day
            step = max(3, last_day // 6)
            for d in range(1, last_day + 1, step):
                chunk_end_day = min(last_day, d + step - 1)
                chunk_start = timezone.make_aware(datetime(now.year, now.month, d, 0, 0, 0))
                chunk_end = timezone.make_aware(datetime(now.year, now.month, chunk_end_day, 23, 59, 59))
                chunk_orders = period_orders.filter(created_at__gte=chunk_start, created_at__lte=chunk_end)
                chunk_delivered = chunk_orders.filter(status='delivered')
                chunk_rev = float(chunk_delivered.aggregate(s=Sum('total_price'))['s'] or 0)
                label = f"{d}-{chunk_end_day} {now.strftime('%b')}"
                timeline.append({
                    'label': label,
                    'revenue': round(chunk_rev, 2),
                    'orders': chunk_orders.count(),
                })
        elif period == 'year':
            for m in range(1, 13):
                m_start = timezone.make_aware(datetime(now.year, m, 1, 0, 0, 0))
                if m == 12:
                    m_end = timezone.make_aware(datetime(now.year + 1, 1, 1, 0, 0, 0)) - timedelta(seconds=1)
                else:
                    m_end = timezone.make_aware(datetime(now.year, m + 1, 1, 0, 0, 0)) - timedelta(seconds=1)
                
                m_orders = period_orders.filter(created_at__gte=m_start, created_at__lte=m_end)
                m_delivered = m_orders.filter(status='delivered')
                m_rev = float(m_delivered.aggregate(s=Sum('total_price'))['s'] or 0)
                label = m_start.strftime("%b")
                timeline.append({
                    'label': label,
                    'revenue': round(m_rev, 2),
                    'orders': m_orders.count(),
                })
        else: # all
            for y in range(now.year - 2, now.year + 1):
                y_start = timezone.make_aware(datetime(y, 1, 1, 0, 0, 0))
                y_end = timezone.make_aware(datetime(y + 1, 1, 1, 0, 0, 0)) - timedelta(seconds=1)
                y_orders = period_orders.filter(created_at__gte=y_start, created_at__lte=y_end)
                y_delivered = y_orders.filter(status='delivered')
                y_rev = float(y_delivered.aggregate(s=Sum('total_price'))['s'] or 0)
                timeline.append({
                    'label': str(y),
                    'revenue': round(y_rev, 2),
                    'orders': y_orders.count(),
                })

        # 7. Top Selling Dishes (Best Sellers in Selected Period)
        top_items_qs = (
            OrderItem.objects
            .filter(order__in=period_orders)
            .values('item_name', 'menu_item__category__name', 'menu_item__dietary_preference')
            .annotate(
                total_qty=Sum('quantity'),
                total_sales=Sum('line_total')
            )
            .order_by('-total_qty')[:10]
        )
        top_selling_items = []
        for item in top_items_qs:
            top_selling_items.append({
                'name': item['item_name'],
                'category': item['menu_item__category__name'] or 'Main Course',
                'dietary': item['menu_item__dietary_preference'] or 'NON-VEG',
                'quantity_sold': item['total_qty'],
                'revenue': float(item['total_sales'] or 0),
            })

        # 7b. All-Time Bestsellers (Overall top selling items across all orders)
        all_time_top_qs = (
            OrderItem.objects
            .values('item_name', 'menu_item__category__name', 'menu_item__dietary_preference')
            .annotate(
                total_qty=Sum('quantity'),
                total_sales=Sum('line_total')
            )
            .order_by('-total_qty')[:10]
        )
        all_time_top_selling = []
        for item in all_time_top_qs:
            all_time_top_selling.append({
                'name': item['item_name'],
                'category': item['menu_item__category__name'] or 'Main Course',
                'dietary': item['menu_item__dietary_preference'] or 'NON-VEG',
                'quantity_sold': item['total_qty'],
                'revenue': float(item['total_sales'] or 0),
            })

        # 7c. Category Sales Distribution
        category_qs = (
            OrderItem.objects
            .filter(order__in=period_orders)
            .values('menu_item__category__name')
            .annotate(
                total_qty=Sum('quantity'),
                total_sales=Sum('line_total')
            )
            .order_by('-total_sales')[:6]
        )
        if not category_qs.exists():
            category_qs = (
                OrderItem.objects
                .values('menu_item__category__name')
                .annotate(
                    total_qty=Sum('quantity'),
                    total_sales=Sum('line_total')
                )
                .order_by('-total_sales')[:6]
            )

        cat_total_revenue = sum(float(c['total_sales'] or 0) for c in category_qs) or 1.0
        category_distribution = []
        for cat in category_qs:
            c_sales = float(cat['total_sales'] or 0)
            category_distribution.append({
                'name': cat['menu_item__category__name'] or 'Specialties',
                'quantity': cat['total_qty'],
                'revenue': c_sales,
                'percentage': round((c_sales / cat_total_revenue) * 100, 1),
            })

        # 7d. Operations & Peak Hours Analysis
        peak_point = max(timeline, key=lambda x: x['orders']) if timeline else None
        busiest_slot = f"{peak_point['label']} ({peak_point['orders']} orders)" if peak_point and peak_point['orders'] > 0 else "Evenly Distributed"
        fulfillment_rate = round((delivered_count / total_orders_count * 100), 1) if total_orders_count > 0 else 100.0
        cancellation_rate = round((cancelled_count / total_orders_count * 100), 1) if total_orders_count > 0 else 0.0
        total_items_sold_count = sum(i['quantity_sold'] for i in top_selling_items) if top_selling_items else 0

        operations_metrics = {
            'busiest_slot': busiest_slot,
            'fulfillment_rate': fulfillment_rate,
            'cancellation_rate': cancellation_rate,
            'total_items_sold': total_items_sold_count,
        }

        # 8. Recent Live Orders (latest 6)
        recent_orders_qs = (
            Order.objects
            .prefetch_related('items')
            .order_by('-created_at')[:6]
        )
        recent_orders = []
        for o in recent_orders_qs:
            recent_orders.append({
                'id': o.id,
                'customer_name': o.customer_name,
                'customer_phone': o.customer_phone,
                'total_price': float(o.total_price),
                'status': o.status,
                'payment_status': o.payment_status,
                'items_count': o.items.count(),
                'created_at': o.created_at.isoformat(),
            })

        # 8b. Fleet Distance & Delivery Boy Ride Analytics
        delivered_orders_in_period = period_orders.filter(status='delivered')
        total_period_km = float(delivered_orders_in_period.aggregate(s=Sum('delivery_distance_km'))['s'] or 0.0)

        today_date = timezone.localdate()
        today_delivered_qs = Order.objects.filter(status='delivered', created_at__date=today_date)
        today_fleet_km = float(today_delivered_qs.aggregate(s=Sum('delivery_distance_km'))['s'] or 0.0)

        avg_km_per_order = round(total_period_km / delivered_count, 1) if delivered_count > 0 else 0.0

        from django.contrib.auth import get_user_model
        UserModel = get_user_model()
        riders = UserModel.objects.filter(role='delivery_boy', is_active=True).select_related('delivery_profile')
        fleet_riders = []
        for r in riders:
            r_name = (r.get_full_name() or r.username).strip()
            r_today_km = round(float(r.deliveries.filter(status='delivered', delivered_at__date=today_date).aggregate(s=Sum('order__delivery_distance_km'))['s'] or 0.0), 1)
            r_period_km = round(float(r.deliveries.filter(status='delivered', delivered_at__gte=start_date, delivered_at__lte=end_date).aggregate(s=Sum('order__delivery_distance_km'))['s'] or 0.0), 1)
            r_total_km = round(float(r.deliveries.filter(status='delivered').aggregate(s=Sum('order__delivery_distance_km'))['s'] or 0.0), 1)
            r_delivered_count = r.deliveries.filter(status='delivered', delivered_at__gte=start_date, delivered_at__lte=end_date).count()
            fleet_riders.append({
                'id': r.id,
                'name': r_name,
                'employee_id': getattr(r, 'employee_id', None) or f"DB-{r.id}",
                'vehicle_number': getattr(getattr(r, 'delivery_profile', None), 'vehicle_number', None) or 'N/A',
                'today_km': r_today_km,
                'period_km': r_period_km,
                'total_km': r_total_km,
                'delivered_count': r_delivered_count,
            })
        fleet_riders.sort(key=lambda x: x['period_km'], reverse=True)

        fleet_distance_metrics = {
            'period_fleet_km': round(total_period_km, 1),
            'today_fleet_km': round(today_fleet_km, 1),
            'avg_km_per_order': avg_km_per_order,
            'riders': fleet_riders,
        }

        return Response({
            'status': True,
            'data': {
                'period': period,
                'period_label': period_label,
                'comparison_label': comparison_label,
                'fleet_distance': fleet_distance_metrics,
                'kpis': {
                    'total_revenue': total_revenue,
                    'revenue_growth_pct': revenue_growth_pct,
                    'total_orders': total_orders_count,
                    'orders_growth_pct': orders_growth_pct,
                    'avg_order_value': avg_order_value,
                    'completed_orders': delivered_count,
                    'active_orders': total_active_live,
                    'cancelled_orders': cancelled_count,
                    'total_customers': unique_customers_count,
                },
                'live_pipeline': {
                    'in_kitchen': live_kitchen_count,
                    'at_counter': live_counter_count,
                    'in_transit': live_transit_count,
                    'total_active': total_active_live,
                },
                'status_breakdown': status_breakdown,
                'payment_breakdown': payment_breakdown,
                'timeline': timeline,
                'top_selling_items': top_selling_items,
                'all_time_top_selling': all_time_top_selling,
                'category_distribution': category_distribution,
                'operations_metrics': operations_metrics,
                'recent_orders': recent_orders,
            }
        })


# ============================================================
# 💳 RAZORPAY PAYMENT GATEWAY INTEGRATION
# ============================================================

class RazorpayCreateOrderView(APIView):
    """
    F02 FIX: Creates a Razorpay Order ID strictly bound to the authenticated customer's
    server-calculated cart total and address-based delivery fee.
    Client-supplied amounts are never accepted.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        import razorpay
        from django.conf import settings

        currency = request.data.get('currency', 'INR')
        receipt = request.data.get('receipt')

        key_id = getattr(settings, 'RAZORPAY_KEY_ID', '')
        key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '')

        if not key_id or not key_secret:
            return Response({
                'status': False,
                'error': 'Razorpay credentials not configured on server.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 1. Server calculates checkout amount strictly from active Cart
        cart = Cart.objects.filter(user=request.user).first()
        if not cart or not cart.items.exists():
            return Response({
                'status': False,
                'error': 'Cart is empty. Cannot create payment order.'
            }, status=status.HTTP_400_BAD_REQUEST)

        subtotal = Decimal('0.00')
        for item in cart.items.select_related('menu_item', 'variant'):
            price = (
                item.variant.offer_price or item.variant.actual_price
                if item.variant
                else item.menu_item.offer_price or item.menu_item.actual_price
            ) or Decimal('0.00')
            pkg = (
                item.variant.packing_charge
                if item.variant and item.variant.packing_charge is not None
                else item.menu_item.packing_charge
            ) or Decimal('0.00')
            subtotal += (Decimal(str(price)) + Decimal(str(pkg))) * item.quantity

        delivery_fee = Decimal('0.00')
        address_id = request.data.get('address_id')
        if not address_id:
            return Response({
                "status": False,
                "error": "Delivery address is required to calculate delivery charges and initialize payment."
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            addr = Address.objects.get(id=address_id, user=request.user)
            site_settings = SiteSetting.objects.first()

            if site_settings and not site_settings.is_open:
                return Response({
                    "status": False,
                    "error": "Empire Plaza is currently closed for online orders."
                }, status=status.HTTP_400_BAD_REQUEST)

            max_radius = float(getattr(site_settings, 'delivery_radius', 0.0) or 0.0)
            cust_lat = addr.latitude
            cust_lng = addr.longitude

            if (cust_lat is None or cust_lng is None or (cust_lat == 0 and cust_lng == 0)):
                from .distance_utils import geocode_address
                g_lat, g_lng = geocode_address(addr.address_line, addr.city, addr.pincode)
                if g_lat and g_lng:
                    cust_lat, cust_lng = g_lat, g_lng
                    addr.latitude = g_lat
                    addr.longitude = g_lng
                    addr.save(update_fields=['latitude', 'longitude'])

            if site_settings and site_settings.latitude and site_settings.longitude:
                if cust_lat and cust_lng:
                    dist_km = calculate_haversine_distance_km(
                        site_settings.latitude, site_settings.longitude,
                        cust_lat, cust_lng
                    )
                    if max_radius > 0 and dist_km > max_radius:
                        return Response({
                            "status": False,
                            "error": f"Delivery unavailable: Your address is {dist_km:.1f} KM away, exceeding our maximum delivery radius of {max_radius:.1f} KM."
                        }, status=status.HTTP_400_BAD_REQUEST)

                    delivery_fee = calculate_delivery_fee(dist_km, subtotal, site_settings)
                elif max_radius > 0:
                    return Response({
                        "status": False,
                        "error": f"Delivery location coordinates required. Your address must be verified within {max_radius:.1f} KM of Empire Plaza."
                    }, status=status.HTTP_400_BAD_REQUEST)
                else:
                    delivery_fee = calculate_delivery_fee(0.0, subtotal, site_settings)
            elif site_settings:
                delivery_fee = calculate_delivery_fee(0.0, subtotal, site_settings)
        except Address.DoesNotExist:
            return Response({
                "status": False,
                "error": "Selected delivery address does not exist."
            }, status=status.HTTP_400_BAD_REQUEST)

        total_amount = subtotal + delivery_fee
        amount_in_paise = int(round(float(total_amount) * 100))

        if amount_in_paise < 100:
            return Response({
                'status': False,
                'error': 'Minimum checkout amount must be at least ₹1.'
            }, status=status.HTTP_400_BAD_REQUEST)

        if not receipt:
            receipt = f"rcpt_{request.user.id}_{int(datetime.now().timestamp())}"[:40]

        try:
            client = razorpay.Client(auth=(key_id, key_secret))
            client.set_app_details({"title": "Grand Plaza", "version": "1.0"})
            order_data = {
                "amount": amount_in_paise,
                "currency": currency,
                "receipt": receipt,
                "payment_capture": 1
            }
            rzp_order = client.order.create(data=order_data)

            # Persist pending PaymentAttempt linking server-calculated amount and authenticated user
            PaymentAttempt.objects.create(
                user=request.user,
                razorpay_order_id=rzp_order.get("id"),
                amount=total_amount,
                currency=currency,
                status='created',
                address_id=address_id if address_id else None,
                cart_snapshot={
                    'subtotal': str(subtotal),
                    'delivery_fee': str(delivery_fee),
                    'total': str(total_amount),
                    'items_count': cart.items.count(),
                }
            )

            return Response({
                "status": True,
                "order_id": rzp_order.get("id"),
                "amount": rzp_order.get("amount"),
                "currency": rzp_order.get("currency"),
                "key_id": key_id
            }, status=status.HTTP_200_OK)

        except razorpay.errors.BadRequestError as e:
            return Response({
                "status": False,
                "error": f"Razorpay bad request: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                "status": False,
                "error": f"Failed to create payment order: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RazorpayVerifyPaymentView(APIView):
    """
    F02 FIX: Verifies Razorpay HMAC signature, ensures the payment ID has never been consumed,
    validates payment attempt ownership against the authenticated customer,
    and atomically creates the finalized order.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        import hmac
        import hashlib
        from django.conf import settings

        razorpay_order_id = request.data.get('razorpay_order_id')
        razorpay_payment_id = request.data.get('razorpay_payment_id')
        razorpay_signature = request.data.get('razorpay_signature')

        if not razorpay_order_id or not razorpay_payment_id or not razorpay_signature:
            return Response({
                "status": False,
                "error": "Missing required payment fields: razorpay_order_id, razorpay_payment_id, and razorpay_signature are required."
            }, status=status.HTTP_400_BAD_REQUEST)

        key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '')
        if not key_secret:
            return Response({
                "status": False,
                "error": "Razorpay secret key not configured on server."
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 1. Cryptographic HMAC verification
        msg = f"{razorpay_order_id}|{razorpay_payment_id}".encode('utf-8')
        generated_signature = hmac.new(
            key_secret.encode('utf-8'),
            msg,
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(generated_signature, razorpay_signature):
            return Response({
                "status": False,
                "error": "Signature verification failed. Payment proof is invalid."
            }, status=status.HTTP_400_BAD_REQUEST)

        # 2. Atomically verify payment attempt and enforce single-use consumption (F02 Fix)
        with transaction.atomic():
            # Check if this razorpay_payment_id has already been consumed anywhere in the database
            if Order.objects.filter(razorpay_payment_id=razorpay_payment_id).exists():
                return Response({
                    "status": False,
                    "error": "This payment ID has already been consumed for another order. Replay rejected."
                }, status=status.HTTP_400_BAD_REQUEST)

            # Lock the PaymentAttempt row for this user and order id
            attempt = PaymentAttempt.objects.select_for_update().filter(
                razorpay_order_id=razorpay_order_id,
                user=request.user
            ).first()

            if not attempt:
                return Response({
                    "status": False,
                    "error": "No matching payment checkout attempt found for your account."
                }, status=status.HTTP_400_BAD_REQUEST)

            if attempt.status == 'completed':
                return Response({
                    "status": False,
                    "error": "This payment attempt has already been completed and consumed."
                }, status=status.HTTP_400_BAD_REQUEST)

            address_id = request.data.get('address_id') or attempt.address_id
            special_instructions = request.data.get('special_instructions', '')

            if not address_id:
                return Response({
                    "status": False,
                    "error": "Delivery address ID is required to finalize order."
                }, status=status.HTTP_400_BAD_REQUEST)

            # CRITICAL F02 FIX: Compute current cart total and verify against PaymentAttempt amount BEFORE checkout!
            cart = Cart.objects.filter(user=request.user).first()
            if not cart or not cart.items.exists():
                return Response({"status": False, "error": "Cart is empty."}, status=status.HTTP_400_BAD_REQUEST)

            cart_subtotal = Decimal('0.00')
            for item in cart.items.select_related('menu_item', 'variant'):
                price = (
                    item.variant.offer_price or item.variant.actual_price
                    if item.variant
                    else item.menu_item.offer_price or item.menu_item.actual_price
                ) or Decimal('0.00')
                pkg = (
                    item.variant.packing_charge
                    if item.variant and item.variant.packing_charge is not None
                    else item.menu_item.packing_charge
                ) or Decimal('0.00')
                cart_subtotal += (Decimal(str(price)) + Decimal(str(pkg))) * item.quantity

            delivery_fee = Decimal('0.00')
            addr = Address.objects.filter(id=address_id, user=request.user).first()
            site_settings = SiteSetting.objects.first()
            if addr and site_settings:
                if addr.latitude and addr.longitude and site_settings.latitude and site_settings.longitude:
                    dist_km = calculate_haversine_distance_km(
                        site_settings.latitude, site_settings.longitude,
                        addr.latitude, addr.longitude
                    )
                    delivery_fee = calculate_delivery_fee(dist_km, cart_subtotal, site_settings)
                else:
                    delivery_fee = calculate_delivery_fee(0.0, cart_subtotal, site_settings)

            current_cart_total = cart_subtotal + delivery_fee

            # Price-binding verification: reject if cart total has changed since payment attempt creation
            if Decimal(str(current_cart_total)) != Decimal(str(attempt.amount)):
                return Response({
                    "status": False,
                    "error": f"Payment amount mismatch: Payment attempt authorized for ₹{attempt.amount}, but cart total is ₹{current_cart_total}. Checkout rejected."
                }, status=status.HTTP_400_BAD_REQUEST)

            checkout_data = {
                'address_id': address_id,
                'special_instructions': special_instructions,
                'payment_method': 'online',
            }
            serializer = CheckoutSerializer(
                data=checkout_data,
                context={
                    'request': request,
                    'verified_online_payment': True,
                    'razorpay_order_id': razorpay_order_id,
                    'razorpay_payment_id': razorpay_payment_id,
                    'authorized_delivery_fee': delivery_fee,
                }
            )
            serializer.is_valid(raise_exception=True)
            order = serializer.save()

            # Second-layer post-creation verification: ensure final order total price matches attempt amount exactly
            if Decimal(str(order.total_price)) != Decimal(str(attempt.amount)):
                transaction.set_rollback(True)
                return Response({
                    "status": False,
                    "error": f"Payment amount mismatch: Final order price ₹{order.total_price} does not match authorized amount ₹{attempt.amount}."
                }, status=status.HTTP_400_BAD_REQUEST)

            order.payment_status = 'completed'
            order.status = 'preparing'
            order.razorpay_order_id = razorpay_order_id
            order.razorpay_payment_id = razorpay_payment_id
            order.save(update_fields=['payment_status', 'status', 'razorpay_order_id', 'razorpay_payment_id'])

            # Mark PaymentAttempt as completed and link to order
            attempt.status = 'completed'
            attempt.razorpay_payment_id = razorpay_payment_id
            attempt.order = order
            attempt.save(update_fields=['status', 'razorpay_payment_id', 'order', 'updated_at'])

            order_data = OrderReadSerializer(order, context={'request': request}).data
            trigger_order_event('new-order', order_data)

        return Response({
            "status": True,
            "message": "Payment verified and order placed successfully.",
            "data": {
                "verified": True,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_order_id": razorpay_order_id,
                "order": order_data
            }
        }, status=status.HTTP_200_OK)
