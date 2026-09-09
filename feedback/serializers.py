from rest_framework import serializers
from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(
        source='user.first_name',
        read_only=True
    )

    rating_display = serializers.CharField(
        source='get_rating_display',
        read_only=True
    )

    class Meta:
        model = Review

        fields = [
            'id',
            'order',
            'user_name',
            'rating',
            'rating_display',
            'comment',
            'is_approved',
            'created_at',
        ]

        read_only_fields = ['id', 'created_at']