from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import BannerViewSet


router = DefaultRouter()
router.register('banners', BannerViewSet, basename='banner')

urlpatterns = [
    path('', include(router.urls)),
]