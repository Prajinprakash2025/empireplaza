from django.urls import path
from .views import (
    ReviewEligibilityCheckView,
    ReviewCreateView,
    ReviewListView,
    AdminReviewListView,
    AdminReviewUpdateView,
)

urlpatterns = [
    # Customer
    path(
        'eligibility',
        ReviewEligibilityCheckView.as_view(),
        name='review-eligibility'
    ),
    path(
        'submit',
        ReviewCreateView.as_view(),
        name='review-submit'
    ),

    # Public
    path(
        '',
        ReviewListView.as_view(),
        name='review-list'
    ),

    # Admin
    path(
        'admin',
        AdminReviewListView.as_view(),
        name='admin-review-list'
    ),
    path(
        'admin/<int:pk>',
        AdminReviewUpdateView.as_view(),
        name='admin-review-update'
    ),
]