from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from .models import FAQ
from .serializers import FAQSerializer
from accounts.permissions import IsAdminRole


class FAQViewSet(viewsets.ModelViewSet):
    serializer_class = FAQSerializer

    def get_queryset(self):
        user = self.request.user

        if user.is_authenticated and (
            user.role == 'admin' or user.is_superuser
        ):
            return FAQ.objects.all()

        return FAQ.objects.filter(is_active=True)

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAdminRole()]