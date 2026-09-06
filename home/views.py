from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.parsers import MultiPartParser, FormParser

from .models import Banner
from .serializers import BannerSerializer
from accounts.permissions import IsAdminRole


class BannerViewSet(viewsets.ModelViewSet):
    queryset = Banner.objects.all().order_by('-created_at')
    serializer_class = BannerSerializer
    permission_classes = [IsAdminRole]
    parser_classes = [MultiPartParser, FormParser]
