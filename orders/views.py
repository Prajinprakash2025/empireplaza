from django.db.models import Prefetch, Q
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

from accounts.permissions import IsEmployee

from .models import Cart, CartItem, Order
from .serializers import (
    CartItemAddSerializer,
    CartItemQuantitySerializer,
    CartItemReadSerializer,
    CartReadSerializer,
    CheckoutSerializer,
    OrderReadSerializer,
    OrderStatusUpdateSerializer,
)


class OrderPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


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

        return Response(
            {
                'status': True,
                'message': 'Order placed successfully.',
                'data': OrderReadSerializer(
                    order,
                    context={'request': request},
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )


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

        return Response({
            'status': True,
            'message': 'Order cancelled successfully.',
            'data': OrderReadSerializer(
                updated_order,
                context={'request': request},
            ).data,
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
            .select_related('user')
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

        return Response({
            'status': True,
            'message': 'Order status updated successfully.',
            'data': OrderReadSerializer(
                updated_order,
                context={'request': request},
            ).data,
        })