from django.shortcuts import render

from rest_framework import generics, status, filters
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination

from .models import Review
from .serializers import ReviewSerializer
from orders.models import Order
from accounts.permissions import IsAdminRole


class AdminReviewPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 50


class ReviewEligibilityCheckView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        delivered_orders = Order.objects.filter(
            user=user,
            status='delivered'
        ).order_by('-created_at')

        if not delivered_orders.exists():
            return Response({
                "is_eligible": False,
                "has_reviewed": False,
                "message": "Review option will unlock after your first order is delivered!"
            })

        # Delivered orders which are not reviewed yet
        unreviewed_orders = delivered_orders.exclude(
            review__isnull=False
        )

        if unreviewed_orders.exists():
            return Response({
                "is_eligible": True,
                "has_reviewed": False
            })

        return Response({
            "is_eligible": False,
            "has_reviewed": True,
            "message": "You have already submitted feedback for all delivered orders."
        })

class ReviewCreateView(generics.CreateAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        user = request.user

        order_id = request.data.get('order')

        if not order_id:
            return Response(
                {"error": "Order ID is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check whether this order belongs to the logged-in user
        try:
            order = Order.objects.get(
                id=order_id,
                user=user
            )
        except Order.DoesNotExist:
            return Response(
                {"error": "Invalid order."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Only delivered orders can be reviewed
        if order.status != 'delivered':
            return Response(
                {
                    "error": "You can only leave feedback for a delivered order."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # Prevent reviewing the same order twice
        if Review.objects.filter(order=order).exists():
            return Response(
                {
                    "error": "You have already submitted feedback for this order."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=user, order=order)

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )

class ReviewListView(generics.ListAPIView):
    # Public users can see only approved feedback
    queryset = Review.objects.filter(
        is_approved=True
    ).order_by('-created_at')

    serializer_class = ReviewSerializer
    permission_classes = [AllowAny]


class AdminReviewListView(generics.ListAPIView):
    # Admin can see both approved and unapproved feedback
    queryset = Review.objects.all().order_by('-created_at')

    serializer_class = ReviewSerializer
    permission_classes = [IsAdminRole]

    pagination_class = AdminReviewPagination

    filter_backends = [filters.SearchFilter]
    search_fields = [
        'user__first_name',
        'user__username'
    ]


class AdminReviewUpdateView(generics.UpdateAPIView):
    # Admin can approve or hide feedback
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [IsAdminRole]
