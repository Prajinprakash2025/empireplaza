from django.conf import settings
from django.db import models

from menu.models import MenuItem, MenuItemVariant


class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='cart',)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart - {self.user.phone_number}"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart,on_delete=models.CASCADE,related_name='items',)
    menu_item = models.ForeignKey(MenuItem,on_delete=models.CASCADE,related_name='cart_items',)
    variant = models.ForeignKey(MenuItemVariant,on_delete=models.CASCADE,null=True,blank=True,related_name='cart_items',)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['added_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1),
                name='cart_item_quantity_gte_1',
            ),
            models.UniqueConstraint(
                fields=['cart', 'menu_item'],
                condition=models.Q(variant__isnull=True),
                name='unique_cart_menu_without_variant',
            ),
            models.UniqueConstraint(
                fields=['cart', 'menu_item', 'variant'],
                condition=models.Q(variant__isnull=False),
                name='unique_cart_menu_with_variant',
            ),
        ]

    def __str__(self):
        variant_name = (
            f" - {self.variant.size_name}"
            if self.variant
            else ''
        )
        return (
            f"{self.quantity} x "
            f"{self.menu_item.name}{variant_name}"
        )


class Order(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('preparing', 'Preparing'),
        ('ready_for_pickup', 'Ready for Pickup'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    )

    PAYMENT_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('refunded', 'Refunded'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='orders',
    )

    customer_name = models.CharField(max_length=150)
    customer_phone = models.CharField(max_length=15)

    delivery_address = models.TextField()
    special_instructions = models.TextField(
        blank=True,
        default='',
    )

    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending',
        db_index=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.pk} - {self.customer_phone}"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
    )

    # Menu item delete ചെയ്താലും order history നഷ്ടപ്പെടില്ല.
    menu_item = models.ForeignKey(
        MenuItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_items',
    )

    variant = models.ForeignKey(
        MenuItemVariant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_items',
    )

    # Product snapshots
    item_name = models.CharField(max_length=255)
    variant_name = models.CharField(
        max_length=50,
        blank=True,
        default='',
    )

    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )
    line_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    class Meta:
        ordering = ['id']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1),
                name='order_item_quantity_gte_1',
            ),
        ]

    def save(self, *args, **kwargs):
        self.line_total = self.unit_price * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        variant_name = (
            f" ({self.variant_name})"
            if self.variant_name
            else ''
        )
        return (
            f"{self.quantity} x "
            f"{self.item_name}{variant_name}"
        )