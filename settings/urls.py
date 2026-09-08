from django.urls import path
from .views import SiteSettingRetrieveUpdateView


urlpatterns = [
    path(
        'site-settings',
        SiteSettingRetrieveUpdateView.as_view(),
        name='site-settings'
    ),
]