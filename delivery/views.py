# from django.utils import timezone
# from rest_framework import status, permissions
# from rest_framework.response import Response
# from rest_framework.views import APIView
# from accounts.permissions import IsDeliveryBoy
# # from orders.models import Order
# from orders.serializers import OrderReadSerializer
# from .models import Delivery
# from .serializers import DeliverySerializer

# class AvailableDeliveriesView(APIView):
#     """
#     Delivery boys can view orders that are ready for pickup.
#     """
#     permission_classes = [IsDeliveryBoy]

#     def get(self, request):
#         orders = Order.objects.filter(status='ready_for_pickup').order_by('created_at')
#         serializer = OrderReadSerializer(orders, many=True)
#         return Response(serializer.data)

# class AcceptDeliveryView(APIView):
#     """
#     Delivery boy accepts an order and changes status to Out for Delivery.
#     """
#     permission_classes = [IsDeliveryBoy]

#     def post(self, request, order_id):
#         try:
#             order = Order.objects.get(pk=order_id, status='ready_for_pickup')
#         except Order.DoesNotExist:
#             return Response({"error": "Order not available for delivery"}, status=status.HTTP_400_BAD_REQUEST)

#         # Update order status
#         order.status = 'out_for_delivery'
#         order.save()

#         # Create or update Delivery entry
#         delivery, created = Delivery.objects.get_or_create(
#             order=order,
#             defaults={
#                 'delivery_boy': request.user,
#                 'status': 'assigned'
#             }
#         )
#         if not created:
#             delivery.delivery_boy = request.user
#             delivery.status = 'assigned'
#             delivery.save()

#         return Response(DeliverySerializer(delivery).data, status=status.HTTP_201_CREATED)

# class CompleteDeliveryView(APIView):
#     """
#     Delivery boy marks order as Delivered.
#     """
#     permission_classes = [IsDeliveryBoy]

#     def post(self, request, delivery_id):
#         try:
#             delivery = Delivery.objects.get(pk=delivery_id, delivery_boy=request.user, status='assigned')
#         except Delivery.DoesNotExist:
#             return Response({"error": "Active delivery assignment not found"}, status=status.HTTP_404_NOT_FOUND)

#         # Update delivery status
#         delivery.status = 'delivered'
#         delivery.delivered_at = timezone.now()
#         delivery.save()

#         # Update corresponding order status
#         order = delivery.order
#         order.status = 'delivered'
#         order.payment_status = 'completed'  # Assuming Cash on Delivery completed
#         order.save()

#         return Response(DeliverySerializer(delivery).data)