from django.urls import path
from . import views

urlpatterns = [
    # 🌟 Home Page Single API
    path('public/home-data', views.PublicHomeDataView.as_view(), name='public-home-data'),
    path('public/home-data/', views.PublicHomeDataView.as_view()),

    # --- CATEGORY URLS (Support both with and without trailing slash) ---
    path('public/categories', views.PublicCategoryListView.as_view(), name='public-category-list'),
    path('public/categories/', views.PublicCategoryListView.as_view()),
    path('admin/categories', views.CategoryListCreateView.as_view(), name='category-list'),
    path('admin/categories/', views.CategoryListCreateView.as_view()),
    path('admin/categories/<int:pk>', views.CategoryDetailView.as_view(), name='category-detail'),
    path('admin/categories/<int:pk>/', views.CategoryDetailView.as_view()),

    # --- MENU ITEM URLS (Support both with and without trailing slash) ---
    path('public/menu-items', views.PublicMenuItemListView.as_view(), name='public-menu-list'),
    path('public/menu-items/', views.PublicMenuItemListView.as_view()),
    path('admin/menu-items', views.AdminMenuItemListCreateView.as_view(), name='admin-menu-list'),
    path('admin/menu-items/', views.AdminMenuItemListCreateView.as_view()),
    path('admin/menu-items/<int:pk>', views.MenuItemDetailView.as_view(), name='menu-item-detail'),
    path('admin/menu-items/<int:pk>/', views.MenuItemDetailView.as_view()),
]