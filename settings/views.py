from django.shortcuts import render, get_object_or_404
from django.core.cache import cache
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.views import APIView

from .models import SiteSetting, OfferBanner
from .serializers import SiteSettingSerializer, OfferBannerSerializer
from accounts.permissions import IsAdminRole

SITE_SETTINGS_CACHE_KEY = 'site_settings_public_data'
CACHE_TIMEOUT_SECONDS = 30


class SiteSettingRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    serializer_class = SiteSettingSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

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

    def get_throttles(self):
        # Public GET requests for site settings should never be throttled
        if self.request.method == 'GET':
            return []
        return super().get_throttles()

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


class OfferBannerListCreateView(generics.ListCreateAPIView):
    queryset = OfferBanner.objects.all().order_by('-created_at')
    serializer_class = OfferBannerSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_authenticators(self):
        if self.request.method == 'GET':
            return []
        return super().get_authenticators()

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAdminRole()]

    def perform_create(self, serializer):
        is_active = self.request.data.get('is_active') in ['true', 'True', True]
        if is_active:
            OfferBanner.objects.all().update(is_active=False)
        serializer.save(is_active=is_active)
        cache.delete(SITE_SETTINGS_CACHE_KEY)


class OfferBannerDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = OfferBanner.objects.all()
    serializer_class = OfferBannerSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_authenticators(self):
        if self.request.method == 'GET':
            return []
        return super().get_authenticators()

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAdminRole()]

    def perform_update(self, serializer):
        is_active = serializer.validated_data.get('is_active')
        if is_active:
            OfferBanner.objects.exclude(pk=self.get_object().pk).update(is_active=False)
        serializer.save()
        cache.delete(SITE_SETTINGS_CACHE_KEY)

    def perform_destroy(self, instance):
        instance.delete()
        cache.delete(SITE_SETTINGS_CACHE_KEY)


class OfferBannerActivateView(APIView):
    """
    Single-click activation: Set this banner active and all others inactive.
    """
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        return [IsAdminRole()]

    def post(self, request, pk):
        banner = get_object_or_404(OfferBanner, pk=pk)

        action = request.data.get('action', 'activate') # 'activate' or 'toggle' or 'deactivate'
        if action == 'deactivate':
            banner.is_active = False
        elif action == 'toggle':
            banner.is_active = not banner.is_active
            if banner.is_active:
                OfferBanner.objects.exclude(pk=banner.pk).update(is_active=False)
        else:
            OfferBanner.objects.exclude(pk=banner.pk).update(is_active=False)
            banner.is_active = True

        banner.save()
        cache.delete(SITE_SETTINGS_CACHE_KEY)

        serializer = OfferBannerSerializer(banner, context={'request': request})
        return Response({
            "message": f"Banner '{banner.title}' is now {'ACTIVE' if banner.is_active else 'INACTIVE'}",
            "banner": serializer.data
        }, status=status.HTTP_200_OK)
