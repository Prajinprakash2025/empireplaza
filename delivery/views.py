from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsDeliveryBoy
from orders.models import Order
from orders.serializers import OrderReadSerializer
from .models import Delivery
from .serializers import DeliverySerializer


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

        # Delivery boy must be on duty
        if not profile.is_on_duty:
            return Response(
                {"error": "You are currently off duty."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Delivery boy cannot accept another order while busy
        if profile.is_busy:
            return Response(
                {"error": "You already have an active delivery."},
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

        # Mark delivery boy as busy
        profile.is_busy = True
        profile.save(update_fields=['is_busy'])

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

        # Mark delivery boy as available again
        try:
            profile = request.user.delivery_profile
            profile.is_busy = False
            profile.save(update_fields=['is_busy'])
        except Exception:
            pass

        return Response(DeliverySerializer(delivery).data)


class CurrentDeliveryView(APIView):
    """
    Get the currently active delivery assigned to the logged-in delivery boy.
    """
    permission_classes = [IsDeliveryBoy]

    def get(self, request):
        delivery = Delivery.objects.filter(
            delivery_boy=request.user,
            status='assigned'
        ).select_related('order').first()

        if not delivery:
            return Response({"active_delivery": None})

        return Response({
            "active_delivery": DeliverySerializer(delivery).data
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

        if profile.is_busy and profile.is_on_duty:
            return Response(
                {"error": "Cannot go offline while you have an active delivery in progress!"},
                status=status.HTTP_400_BAD_REQUEST
            )

        profile.is_on_duty = not profile.is_on_duty
        profile.save(update_fields=['is_on_duty'])

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