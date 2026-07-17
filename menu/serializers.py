from rest_framework import serializers
from .models import Category, FoodItem

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'image']

class FoodItemSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source='category.name')

    class Meta:
        model = FoodItem
        fields = ['id', 'category', 'category_name', 'name', 'description', 'price', 'image', 'is_available', 'created_at']