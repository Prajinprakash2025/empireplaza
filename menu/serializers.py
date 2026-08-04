from rest_framework import serializers
from django.db import transaction
from .models import Category, MenuItem, MenuItemVariant # 🌟 Added MenuItemVariant

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'image']

# ============================================================
# 🌟 NEW: VARIANT SERIALIZER
# ============================================================
class MenuItemVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuItemVariant
        fields = ['id', 'size_name', 'actual_price', 'offer_price', 'quantity', 'is_available']

class MenuItemSerializer(serializers.ModelSerializer):
    # This keeps the category name visible
    category_name = serializers.ReadOnlyField(source='category.name') 
    
    # 🌟 NEW: This grabs all related variants and attaches them to the main item
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
            'quantity',
            'is_available',
            'created_at',
            'variants',
        ]

    # ============================================================
    # 🛑 CUSTOM VALIDATION FOR SECTION LIMITS (Kept exactly as you wrote it!)
    # ============================================================
    def validate(self, data):
        section = data.get('section')
        
        # You can define limits for any section here
        SECTION_LIMITS = {
            'BEST SELLER': 10,
            'BANNER': 4,
            'COMBO MENU': 9,
            "TODAY'S SPECIAL": 6,
        }

        if section in SECTION_LIMITS:
            limit = SECTION_LIMITS[section]
            
            # Check if we are creating a new item, or updating an existing item to a restricted section
            is_new_item = self.instance is None
            is_changing_section = not is_new_item and self.instance.section != section

            if is_new_item or is_changing_section:
                # Count how many items currently exist in this section
                current_count = MenuItem.objects.filter(section=section).count()
                
                if current_count >= limit:
                    raise serializers.ValidationError({
                        "section": f"Limit exceeded! You can only add up to {limit} products in the '{section}' section."
                    })
        
        return data

    # ============================================================
    # 🌟 NEW: CUSTOM CREATE TO SAVE ITEM AND VARIANTS TOGETHER
    # ============================================================
    @transaction.atomic
    def create(self, validated_data):
        # 1. Pull the variants list out of the request data
        variants_data = validated_data.pop('variants', [])
        
        # 2. Create the main product (e.g., "Chicken Biryani")
        menu_item = MenuItem.objects.create(**validated_data)
        
        # 3. Loop through and create the variants (e.g., "Full", "Half") linked to this item
        for variant_data in variants_data:
            MenuItemVariant.objects.create(menu_item=menu_item, **variant_data)
            
        return menu_item

    # ============================================================
    # 🌟 NEW: CUSTOM UPDATE TO HANDLE EDITING VARIANTS
    # ============================================================
    @transaction.atomic
    def update(self, instance, validated_data):
        # 1. Pull the variants list out (use None as default to check if it was provided)
        variants_data = validated_data.pop('variants', None)
        
        # 2. Update the main item details (Name, Image, Category, etc.)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # 3. If variants were sent from React, update them
        if variants_data is not None:
            # The cleanest way to update variants is to delete the old ones and save the new ones
            instance.variants.all().delete()
            for variant_data in variants_data:
                MenuItemVariant.objects.create(menu_item=instance, **variant_data)

        return instance
