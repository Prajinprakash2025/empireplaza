from django.shortcuts import render
from django.core.cache import cache
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from .models import SiteSetting
from .serializers import SiteSettingSerializer
from accounts.permissions import IsAdminRole

SITE_SETTINGS_CACHE_KEY = 'site_settings_public_data'
CACHE_TIMEOUT_SECONDS = 30


class SiteSettingRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    serializer_class = SiteSettingSerializer

    def get_permissions(self):
        # Anyone can view settings
        if self.request.method == 'GET':
            return [AllowAny()]

        # Only Admin can update settings
        return [IsAdminRole()]

    def get_object(self):
        # Get the single settings object
        obj, created = SiteSetting.objects.get_or_create(pk=1)
        return obj

    def retrieve(self, request, *args, **kwargs):
        # High-traffic safe: Cache response for 30s to prevent database contention
        cached_data = cache.get(SITE_SETTINGS_CACHE_KEY)
        if cached_data is not None:
            return Response(cached_data)

        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        cache.set(SITE_SETTINGS_CACHE_KEY, data, timeout=CACHE_TIMEOUT_SECONDS)
        return Response(data)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        # Invalidate cache immediately on admin update
        cache.delete(SITE_SETTINGS_CACHE_KEY)
