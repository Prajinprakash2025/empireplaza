from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.permissions import IsEmployee
from .models import Order
from .serializers import OrderWriteSerializer, OrderReadSerializer

class UserOrderView(APIView):
    """
    Users can place order (POST) and view their order history (GET).
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        orders = Order.objects.filter(user=request.user).order_by('-created_at')
        serializer = OrderReadSerializer(orders, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = OrderWriteSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            order = serializer.save()
            return Response(OrderReadSerializer(order).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class KitchenOrderView(APIView):
    """
    Employees can view pending/preparing kitchen orders and update status.
    """
    permission_classes = [IsEmployee]

    def get(self, request):
        # Get active kitchen orders
        orders = Order.objects.filter(status__in=['pending', 'preparing', 'ready_for_pickup']).order_by('created_at')
        serializer = OrderReadSerializer(orders, many=True)
        return Response(serializer.data)

    def patch(self, request, pk):
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)
            
        new_status = request.data.get('status')
        if new_status not in ['preparing', 'ready_for_pickup', 'cancelled']:
            return Response({"error": "Invalid status for kitchen"}, status=status.HTTP_400_BAD_REQUEST)
            
        order.status = new_status
        order.save()
        return Response(OrderReadSerializer(order).data)