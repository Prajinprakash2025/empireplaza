from django.shortcuts import render
from rest_framework import generics
from rest_framework.permissions import AllowAny

from .models import SiteSetting
from .serializers import SiteSettingSerializer
from accounts.permissions import IsAdminRole


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
