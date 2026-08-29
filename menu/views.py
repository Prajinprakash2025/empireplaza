from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q  

# Direct import of our original permission guards
from accounts.permissions import IsAdmin, IsEmployee 
from .models import Category, MenuItem
from .serializers import CategorySerializer, MenuItemSerializer

# ==========================================
# CUSTOM PAGINATION
# ==========================================
class AdminPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

# ==========================================
# CATEGORY VIEWS
# ==========================================
class CategoryListCreateView(generics.ListCreateAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsEmployee]


class CategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsEmployee]

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        return Response({
            "status": True,
            "message": "Category updated successfully!",
            "data": response.data
        }, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({
            "status": True,
            "message": "Category deleted successfully!"
        }, status=status.HTTP_200_OK)

class PublicCategoryListView(generics.ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    pagination_class = None  


# ==========================================
# MENU ITEM VIEWS
# ==========================================
class PublicMenuItemListView(generics.ListAPIView):
    serializer_class = MenuItemSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        queryset = (
            MenuItem.objects
            .prefetch_related('variants')
            .filter(is_available=True)
            .order_by('-created_at')
        )

        search_query = self.request.query_params.get('search', '')
        category_id = self.request.query_params.get('category', '')
        section_name = self.request.query_params.get('section', '')
        diet_pref = self.request.query_params.get('diet', '')

        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(category__name__icontains=search_query)
            )

        if category_id and str(category_id).upper() != 'ALL':
            queryset = queryset.filter(category_id=category_id)

        if section_name and str(section_name).upper() != 'ALL':
            queryset = queryset.filter(section__iexact=section_name)

        if diet_pref and str(diet_pref).upper() != 'ALL':
            queryset = queryset.filter(
                dietary_preference__iexact=diet_pref
            )

        return queryset


class AdminMenuItemListCreateView(generics.ListCreateAPIView):
    serializer_class = MenuItemSerializer
    permission_classes = [IsEmployee]
    pagination_class = AdminPagination

    def get_queryset(self):
        queryset = (
            MenuItem.objects
            .prefetch_related('variants')
            .all()
            .order_by('-created_at')
        )

        search_query = self.request.query_params.get('search', '')
        category_id = self.request.query_params.get('category', '')
        section_name = self.request.query_params.get('section', '')
        low_stock = self.request.query_params.get('low_stock', '')
        is_available_param = self.request.query_params.get('available', '')

        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(category__name__icontains=search_query)
            )

        if category_id and str(category_id).upper() != 'ALL':
            queryset = queryset.filter(category_id=category_id)

        if section_name and str(section_name).upper() != 'ALL':
            queryset = queryset.filter(section__iexact=section_name)

        if low_stock and str(low_stock).lower() == 'true':
            queryset = queryset.filter(
                Q(has_variants=False, quantity__lt=10) |
                Q(has_variants=True, variants__quantity__lt=10)
            ).distinct()

        if is_available_param:
            if str(is_available_param).lower() == 'true':
                queryset = queryset.filter(is_available=True)

            elif str(is_available_param).lower() == 'false':
                queryset = queryset.filter(is_available=False)

        return queryset


class MenuItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = MenuItem.objects.prefetch_related('variants').all()
    serializer_class = MenuItemSerializer
    permission_classes = [IsEmployee]

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)

        return Response({
            "status": True,
            "message": "Menu Item updated successfully!",
            "data": response.data
        }, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)

        return Response({
            "status": True,
            "message": "Menu Item deleted successfully!"
        }, status=status.HTTP_200_OK)


from rest_framework.views import APIView

# ==========================================
# 🌟 HOME PAGE SINGLE COMPOSITE API
# ==========================================
class PublicHomeDataView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        # 1. Fetch All Categories
        categories = Category.objects.all()

        # 2. Base Queryset for Available Menu Items (with variants prefetched for fast performance)
        available_items = (
            MenuItem.objects
            .filter(is_available=True)
            .select_related('category')
            .prefetch_related('variants')
            .order_by('-created_at')
        )

        # 3. Filter by Sections
        banners = available_items.filter(section='BANNER')
        best_sellers = available_items.filter(section='BEST SELLER')
        combo_menu = available_items.filter(section='COMBO MENU')
        todays_special = available_items.filter(section="TODAY'S SPECIAL")

        # 4. Context passing for Full Image URLs (e.g. http://127.0.0.1:8000/media/...)
        context = {'request': request}

        # 5. Return all data in a single clean JSON Response
        return Response({
            "status": True,
            "data": {
                "banners": MenuItemSerializer(banners, many=True, context=context).data,
                "categories": CategorySerializer(categories, many=True, context=context).data,
                "best_sellers": MenuItemSerializer(best_sellers, many=True, context=context).data,
                "combo_menu": MenuItemSerializer(combo_menu, many=True, context=context).data,
                "todays_special": MenuItemSerializer(todays_special, many=True, context=context).data,
            }
        }, status=status.HTTP_200_OK)