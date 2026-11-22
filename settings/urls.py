from django.urls import path
from .views import (
    SiteSettingRetrieveUpdateView,
    OfferBannerListCreateView,
    OfferBannerDetailView,
    OfferBannerActivateView,
)


urlpatterns = [
    path('site-settings', SiteSettingRetrieveUpdateView.as_view(), name='site-settings'),
    path('site-settings/', SiteSettingRetrieveUpdateView.as_view()),

    # Offer Banners Library APIs
    path('offer-banners', OfferBannerListCreateView.as_view(), name='offer-banners-list'),
    path('offer-banners/', OfferBannerListCreateView.as_view()),
    path('offer-banners/<int:pk>', OfferBannerDetailView.as_view(), name='offer-banners-detail'),
    path('offer-banners/<int:pk>/', OfferBannerDetailView.as_view()),
    path('offer-banners/<int:pk>/activate', OfferBannerActivateView.as_view(), name='offer-banners-activate'),
    path('offer-banners/<int:pk>/activate/', OfferBannerActivateView.as_view()),
]