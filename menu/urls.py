from django.urls import path
from . import views

urlpatterns = [
    # 🌟 NEW: Home Page Single API
    path('public/home-data', views.PublicHomeDataView.as_view(), name='public-home-data'),
    # --- CATEGORY URLS ---
    path('public/categories', views.PublicCategoryListView.as_view(), name='public-category-list'),
    path('admin/categories', views.CategoryListCreateView.as_view(), name='category-list'),
    path('admin/categories/<int:pk>', views.CategoryDetailView.as_view(), name='category-detail'),

    # --- MENU ITEM URLS ---
    path('public/menu-items', views.PublicMenuItemListView.as_view(), name='public-menu-list'),
    path('admin/menu-items', views.AdminMenuItemListCreateView.as_view(), name='admin-menu-list'),
    path('admin/menu-items/<int:pk>', views.MenuItemDetailView.as_view(), name='menu-item-detail'),
]