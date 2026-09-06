from rest_framework import serializers
from .models import Banner


class BannerSerializer(serializers.ModelSerializer):

    class Meta:
        model = Banner
        fields = [
            'id',
            'subtitle',
            'title',
            'description',
            'image',
            'button_text',
            'button_link',
            'is_active',
            'created_at',
            'updated_at',
        ]