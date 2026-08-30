from rest_framework import serializers
from django.db import transaction
from .models import Category, MenuItem, MenuItemVariant


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'image']


# ============================================================
# 🌟 VARIANT SERIALIZER (Quantity Removed from Output)
# ============================================================
class MenuItemVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuItemVariant
        fields = ['id', 'size_name', 'actual_price', 'offer_price', 'is_available']


# ============================================================
# 🌟 MAIN MENU ITEM SERIALIZER
# ============================================================
class MenuItemSerializer(serializers.ModelSerializer):
    # This keeps the category name visible in responses
    category_name = serializers.ReadOnlyField(source='category.name') 
    
    # Grabs all related variants and attaches them to the main item
    variants = MenuItemVariantSerializer(many=True, required=False)

    class Meta:
        model = MenuItem
        fields = [
            'id',
            'category',
            'category_name',
            'section',
            'name',
            'description',
            'image',
            'banner_image',
            'dietary_preference',
            'has_variants',
            'actual_price',
            'offer_price',
            'is_available',
            'created_at',
            'variants',
        ]

    # ============================================================
    # 🛑 CUSTOM VALIDATION FOR PRICES & SECTION LIMITS
    # ============================================================
    def validate(self, data):
        section = data.get('section')
        has_variants = data.get('has_variants', getattr(self.instance, 'has_variants', False))

        # 🌟 1. Price Auto-Clean: If product has variants, clear main item prices automatically
        if has_variants:
            data['actual_price'] = None
            data['offer_price'] = None
        else:
            # If no variants, price must be provided for the main item
            actual_price = data.get('actual_price', getattr(self.instance, 'actual_price', None))
            offer_price = data.get('offer_price', getattr(self.instance, 'offer_price', None))
            if actual_price is None and offer_price is None:
                raise serializers.ValidationError({
                    "actual_price": "Price is required for items without variants."
                })

        # 🌟 2. Section Limits Validation
        SECTION_LIMITS = {
            'BEST SELLER': 10,
            'BANNER': 4,
            'COMBO MENU': 9,
            "TODAY'S SPECIAL": 6,
        }

        if section in SECTION_LIMITS:
            limit = SECTION_LIMITS[section]
            
            is_new_item = self.instance is None
            is_changing_section = not is_new_item and self.instance.section != section

            if is_new_item or is_changing_section:
                current_count = MenuItem.objects.filter(section=section).count()
                
                if current_count >= limit:
                    raise serializers.ValidationError({
                        "section": f"Limit exceeded! You can only add up to {limit} products in the '{section}' section."
                    })
        
        return data

    # ============================================================
    # 🌟 CUSTOM CREATE
    # ============================================================
    @transaction.atomic
    def create(self, validated_data):
        variants_data = validated_data.pop('variants', [])
        menu_item = MenuItem.objects.create(**validated_data)
        
        for variant_data in variants_data:
            MenuItemVariant.objects.create(menu_item=menu_item, **variant_data)
            
        return menu_item

    # ============================================================
    # 🌟 CUSTOM UPDATE
    # ============================================================
    @transaction.atomic
    def update(self, instance, validated_data):
        variants_data = validated_data.pop('variants', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if variants_data is not None:
            instance.variants.all().delete()
            for variant_data in variants_data:
                MenuItemVariant.objects.create(menu_item=instance, **variant_data)

        return instance