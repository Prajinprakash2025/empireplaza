from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import FAQViewSet


router = DefaultRouter(trailing_slash=False)
router.register('faqs', FAQViewSet, basename='faq')


urlpatterns = [
    path('', include(router.urls)),
    path('faqs/', FAQViewSet.as_view({'get': 'list', 'post': 'create'})),
    path('faqs/<int:pk>/', FAQViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'})),
]