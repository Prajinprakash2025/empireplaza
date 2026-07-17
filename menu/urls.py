from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, FoodItemViewSet

router = DefaultRouter()
router.register(r'categories', CategoryViewSet)
router.register(r'food-items', FoodItemViewSet)

urlpatterns = [
    path('', include(router.urls)),
]