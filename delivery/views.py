from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsDeliveryBoy
from orders.models import Order
from orders.serializers import OrderReadSerializer
from orders.pusher_utils import trigger_order_event
from .models import Delivery
from .serializers import DeliverySerializer

def verify_rider_device_session(request, profile):
    """
    Enforces strict single-device session check for delivery riders (F11 fix).
    If rider profile has an active session token, the request MUST provide 
    a matching session token via X-Device-Session header or delivery_session_token cookie.
    Omission of the token is strictly rejected.
    """
    if not profile or not profile.active_session_token:
        return None

    device_token = request.headers.get('X-Device-Session') or request.COOKIES.get('delivery_session_token')
    if not device_token:
        return Response(
            {"error": "Device session token required. Please login again."},
            status=status.HTTP_401_UNAUTHORIZED
        )

    if profile.active_session_token != device_token:
        return Response(
            {"error": "Session expired. Your account was logged in on another device."},
            status=status.HTTP_401_UNAUTHORIZED
        )
    return None



class AvailableDeliveriesView(APIView):
    """
    Delivery boys can view orders that are ready for pickup.
    """
    permission_classes = [IsDeliveryBoy]

    def get(self, request):
        orders = Order.objects.filter(
            status='ready_for_pickup'
        ).order_by('created_at')

        serializer = OrderReadSerializer(orders, many=True)
        return Response(serializer.data)


class AcceptDeliveryView(APIView):
    """
    Delivery boy accepts an order and changes status to Out for Delivery.
    """
    permission_classes = [IsDeliveryBoy]

    def post(self, request, order_id):

        # Check delivery boy profile
        try:
            profile = request.user.delivery_profile
        except Exception:
            return Response(
                {"error": "Delivery boy profile not found."},
                status=status.HTTP_400_BAD_REQUEST
            )

        session_err = verify_rider_device_session(request, profile)
        if session_err:
            return session_err

        # Delivery boy must be on duty
        if not profile.is_on_duty:
            return Response(
                {"error": "You are currently off duty."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check maximum active deliveries limit (multi-order batching)
        MAX_ACTIVE_ORDERS = 4
        active_count = Delivery.objects.filter(
            delivery_boy=request.user,
            status='assigned'
        ).count()

        if active_count >= MAX_ACTIVE_ORDERS:
            return Response(
                {"error": f"You have reached the maximum active deliveries limit ({MAX_ACTIVE_ORDERS} orders)."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Atomically accept the order
        updated = Order.objects.filter(
            pk=order_id,
            status='ready_for_pickup'
        ).update(
            status='out_for_delivery'
        )

        if not updated:
            return Response(
                {
                    "error": "Order already accepted by another delivery partner or not available."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        order = Order.objects.get(pk=order_id)

        # Create delivery assignment
        delivery, created = Delivery.objects.get_or_create(
            order=order,
            defaults={
                'delivery_boy': request.user,
                'status': 'assigned'
            }
        )

        if not created:
            delivery.delivery_boy = request.user
            delivery.status = 'assigned'
            delivery.delivered_at = None
            delivery.save()

        # Update busy status (only busy if rider hits max capacity)
        new_active_count = active_count + 1
        profile.is_busy = (new_active_count >= MAX_ACTIVE_ORDERS)
        profile.save(update_fields=['is_busy'])

        # 🌟 Realtime Broadcast: Order status changed to Out for Delivery
        trigger_order_event('order-status-updated', OrderReadSerializer(order).data)

        return Response(
            DeliverySerializer(delivery).data,
            status=status.HTTP_201_CREATED
        )


class CompleteDeliveryView(APIView):
    """
    Delivery boy marks order as Delivered.
    """
    permission_classes = [IsDeliveryBoy]

    def post(self, request, order_id):
        profile = getattr(request.user, 'delivery_profile', None)
        session_err = verify_rider_device_session(request, profile)
        if session_err:
            return session_err

        try:
            delivery = Delivery.objects.get(
                order_id=order_id,
                delivery_boy=request.user,
                status='assigned'
            )
        except Delivery.DoesNotExist:
            return Response(
                {"error": "Active delivery assignment not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Update delivery status
        delivery.status = 'delivered'
        delivery.delivered_at = timezone.now()
        delivery.save()

        # Update corresponding order status
        order = delivery.order
        order.status = 'delivered'
        order.payment_status = 'completed'
        order.save()

        # Check remaining active deliveries for this rider
        remaining_active = Delivery.objects.filter(
            delivery_boy=request.user,
            status='assigned'
        ).exclude(id=delivery.id).count()

        try:
            profile = request.user.delivery_profile
            profile.is_busy = (remaining_active >= 4)
            profile.save(update_fields=['is_busy'])
        except Exception:
            pass

        # 🌟 Realtime Broadcast: Order status changed to Delivered
        trigger_order_event('order-status-updated', OrderReadSerializer(order).data)

        return Response(DeliverySerializer(delivery).data)


class CurrentDeliveryView(APIView):
    """
    Get the currently active deliveries assigned to the logged-in delivery boy.
    """
    permission_classes = [IsDeliveryBoy]

    def get(self, request):
        deliveries = Delivery.objects.filter(
            delivery_boy=request.user,
            status='assigned'
        ).select_related('order').order_by('order__created_at')

        deliveries_data = DeliverySerializer(deliveries, many=True).data

        return Response({
            "active_delivery": deliveries_data[0] if deliveries_data else None,
            "active_deliveries": deliveries_data,
            "active_count": len(deliveries_data)
        })


class DeliveryHistoryView(APIView):
    """
    Get past completed deliveries for the logged-in delivery boy.
    """
    permission_classes = [IsDeliveryBoy]

    def get(self, request):
        deliveries = Delivery.objects.filter(
            delivery_boy=request.user,
            status='delivered'
        ).select_related('order').order_by('-delivered_at')[:50]

        return Response(DeliverySerializer(deliveries, many=True).data)


class ToggleDutyView(APIView):
    """
    Toggle on/off duty status for the logged-in delivery boy.
    """
    permission_classes = [IsDeliveryBoy]

    def post(self, request):
        try:
            profile = request.user.delivery_profile
        except Exception:
            from accounts.models import DeliveryBoyProfile
            profile, _ = DeliveryBoyProfile.objects.get_or_create(user=request.user)

        session_err = verify_rider_device_session(request, profile)
        if session_err:
            return session_err

        if profile.is_busy and profile.is_on_duty:
            return Response(
                {"error": "Cannot go offline while you have an active delivery in progress!"},
                status=status.HTTP_400_BAD_REQUEST
            )

        profile.is_on_duty = not profile.is_on_duty
        if not profile.is_on_duty:
            profile.current_latitude = None
            profile.current_longitude = None
            profile.save(update_fields=['is_on_duty', 'current_latitude', 'current_longitude'])
        else:
            profile.save(update_fields=['is_on_duty'])

        # Broadcast real-time duty status (Online / Offline) to Admin Fleet Map & Customers
        trigger_order_event('delivery-duty-updated', {
            'delivery_boy_id': request.user.id,
            'is_on_duty': profile.is_on_duty,
            'latitude': profile.current_latitude,
            'longitude': profile.current_longitude,
            'is_gps_active': False if not profile.is_on_duty else None,
        })

        return Response({
            "status": True,
            "is_on_duty": profile.is_on_duty,
            "message": f"You are now {'ONLINE' if profile.is_on_duty else 'OFFLINE'}."
        })


class DeliveryProfileView(APIView):
    """
    Get profile information, vehicle info, and stats for the delivery boy.
    """
    permission_classes = [IsDeliveryBoy]

    def get(self, request):
        user = request.user
        try:
            profile = user.delivery_profile
        except Exception:
            from accounts.models import DeliveryBoyProfile
            profile, _ = DeliveryBoyProfile.objects.get_or_create(user=user)

        total_delivered = Delivery.objects.filter(delivery_boy=user, status='delivered').count()
        today = timezone.now().date()
        today_delivered = Delivery.objects.filter(
            delivery_boy=user,
            status='delivered',
            delivered_at__date=today
        ).count()

        return Response({
            "id": user.id,
            "employee_id": user.employee_id or f"DB-{user.id:03d}",
            "username": user.username,
            "name": user.get_full_name() or user.username,
            "phone_number": user.phone_number,
            "email": user.email or "",
            "vehicle_number": profile.vehicle_number or "Not Set",
            "is_on_duty": profile.is_on_duty,
            "is_busy": profile.is_busy,
            "total_delivered": total_delivered,
            "today_delivered": today_delivered,
        })


class UpdateLocationView(APIView):
    """
    Update delivery boy's live GPS coordinates and broadcast via Pusher.
    Supports clearing location when GPS is lost or turned off.
    """
    permission_classes = [IsDeliveryBoy]

    def post(self, request):
        gps_disabled = request.data.get('gps_disabled', False)
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')

        try:
            profile = request.user.delivery_profile
            session_err = verify_rider_device_session(request, profile)
            if session_err:
                return session_err
        except Exception:
            return Response({"error": "Delivery profile not found."}, status=status.HTTP_404_NOT_FOUND)

        active_order_ids = list(
            Delivery.objects.filter(
                delivery_boy=request.user,
                status='assigned'
            ).values_list('order_id', flat=True)
        )

        # Case 1: GPS turned off, permission revoked, or explicit location clear
        if gps_disabled or (latitude is None and longitude is None):
            profile.current_latitude = None
            profile.current_longitude = None
            profile.last_location_updated_at = timezone.now()
            profile.save(update_fields=['current_latitude', 'current_longitude', 'last_location_updated_at'])

            last_seen_iso = profile.last_location_updated_at.isoformat()

            trigger_order_event('delivery-location-lost', {
                'delivery_boy_id': request.user.id,
                'is_on_duty': profile.is_on_duty,
                'is_gps_active': False,
                'last_seen': last_seen_iso,
                'active_order_ids': active_order_ids
            })

            trigger_order_event('delivery-location-updated', {
                'delivery_boy_id': request.user.id,
                'latitude': None,
                'longitude': None,
                'is_on_duty': profile.is_on_duty,
                'is_busy': profile.is_busy,
                'is_gps_active': False,
                'last_seen': last_seen_iso,
                'active_order_ids': active_order_ids
            })

            return Response({
                "status": True,
                "is_gps_active": False,
                "message": "GPS location cleared."
            })

        # Case 2: Active GPS coordinates update
        accuracy = request.data.get('accuracy')
        accuracy_val = None
        if accuracy is not None:
            try:
                accuracy_val = float(accuracy)
                from django.core.cache import cache
                cache.set(f"rider_accuracy_{request.user.id}", accuracy_val, timeout=300)
            except Exception:
                pass

        try:
            profile.current_latitude = float(latitude)
            profile.current_longitude = float(longitude)
            profile.last_location_updated_at = timezone.now()
            profile.save(update_fields=['current_latitude', 'current_longitude', 'last_location_updated_at'])
        except (ValueError, TypeError):
            return Response({"error": "Invalid latitude or longitude format."}, status=status.HTTP_400_BAD_REQUEST)

        last_seen_iso = profile.last_location_updated_at.isoformat()

        trigger_order_event('delivery-location-updated', {
            'delivery_boy_id': request.user.id,
            'latitude': float(latitude),
            'longitude': float(longitude),
            'accuracy': accuracy_val,
            'is_on_duty': profile.is_on_duty,
            'is_busy': profile.is_busy,
            'is_gps_active': True,
            'last_seen': last_seen_iso,
            'active_order_ids': active_order_ids
        })

        return Response({
            "status": True, 
            "latitude": float(latitude), 
            "longitude": float(longitude),
            "accuracy": accuracy_val,
            "is_on_duty": profile.is_on_duty,
            "is_gps_active": True,
            "last_seen": last_seen_iso
        })
