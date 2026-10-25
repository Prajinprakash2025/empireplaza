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

    def get_authenticators(self):
        # Anyone can view settings without requiring valid JWT cookies
        if self.request.method == 'GET':
            return []
        return super().get_authenticators()

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
        # Check if caller is authenticated admin or requesting fresh data
        is_admin = (
            request.user 
            and request.user.is_authenticated 
            and getattr(request.user, 'role', '') == 'admin'
        )
        force_fresh = (
            request.query_params.get('fresh') == 'true' 
            or request.query_params.get('_t') is not None
            or request.headers.get('Cache-Control') == 'no-cache'
        )

        # High-traffic safe: Serve cached response for public visitors unless fresh data requested
        if not is_admin and not force_fresh:
            cached_data = cache.get(SITE_SETTINGS_CACHE_KEY)
            if cached_data is not None:
                return Response(cached_data)

        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        # Keep cache populated with the latest settings
        cache.set(SITE_SETTINGS_CACHE_KEY, data, timeout=CACHE_TIMEOUT_SECONDS)
        return Response(data)

    def perform_update(self, serializer):
        instance = serializer.save()
        # Invalidate cache immediately on admin update
        cache.delete(SITE_SETTINGS_CACHE_KEY)
        # Pre-populate cache with fresh data
        fresh_data = self.get_serializer(instance).data
        cache.set(SITE_SETTINGS_CACHE_KEY, fresh_data, timeout=CACHE_TIMEOUT_SECONDS)
