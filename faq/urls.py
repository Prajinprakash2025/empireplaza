from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import FAQViewSet


router = DefaultRouter(trailing_slash=False)
router.register('faqs', FAQViewSet, basename='faq')


urlpatterns = [
    path('', include(router.urls)),
]