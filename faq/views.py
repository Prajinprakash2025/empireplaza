from django.shortcuts import render

from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from .models import FAQ
from .serializers import FAQSerializer
from accounts.permissions import IsAdminRole


class FAQViewSet(viewsets.ModelViewSet):
    queryset = FAQ.objects.all()
    serializer_class = FAQSerializer

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAdminRole()]
