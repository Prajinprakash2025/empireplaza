from django.db import models

# 1. CATEGORY MODEL
class Category(models.Model):
    name = models.CharField(max_length=100) # e.g., "Burger"
    image = models.ImageField(upload_to='category_images/', blank=True, null=True) 
    
    def __str__(self):
        return self.name

# 2. MENU ITEM / PRODUCT MODEL
class MenuItem(models.Model):
    # --- Dietary Choices ---
    DIETARY_CHOICES = [
        ('VEG', 'Veg'),
        ('NON-VEG', 'Non-Veg'),
    ]

    # --- Section Choices ---
    SECTION_CHOICES = [
        ('ALL', 'All'),
        ('BANNER', 'Banner'),
        ('COMBO MENU', 'Combo Menu'),
        ('BEST SELLER', 'Best Seller'),
        ("TODAY'S SPECIAL", "Today's Special"),
        ('OTHERS', 'Others'),
    ]

    # --- Relationships & Choices ---
    category = models.ForeignKey(Category, related_name='menu_items', on_delete=models.CASCADE)
    section = models.CharField(max_length=50, choices=SECTION_CHOICES, default='ALL')
    
    # --- Core Details ---
    name = models.CharField(max_length=255, verbose_name="Product Name")
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='menu_images/', blank=True, null=True, verbose_name="Product Image")
    banner_image = models.ImageField(upload_to='banner_images/', blank=True, null=True, verbose_name="Banner Image")
    dietary_preference = models.CharField(max_length=10, choices=DIETARY_CHOICES, default='VEG')
    
    # 🌟 NEW FIELD: Sizes undo illayo ennu ariyikkan
    has_variants = models.BooleanField(default=False, verbose_name="Has Sizes/Variants?")
    
    # --- Pricing & Inventory ---
    # 🌟 CHANGED: Size ulla items-nu direct price aavashyamilla, athukondu blank/null aakki
    actual_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Actual ₹", blank=True, null=True)
    offer_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Offer ₹")
    quantity = models.PositiveIntegerField(default=0, verbose_name="Qty")
    
    # --- Metadata ---
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# 3. 🌟 NEW MODEL: MENU ITEM VARIANT (Sizes, Prices & Stock)
class MenuItemVariant(models.Model):
    menu_item = models.ForeignKey(MenuItem, related_name='variants', on_delete=models.CASCADE)
    size_name = models.CharField(max_length=50) # e.g., 'Small', 'Half', 'Full'
    
    actual_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Actual ₹")
    offer_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Offer ₹")
    quantity = models.PositiveIntegerField(default=0, verbose_name="Qty / Stock")
    
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.menu_item.name} - {self.size_name}"