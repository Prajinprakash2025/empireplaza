# from django.db import models
# from django.conf import settings
# from orders.models import Order

# class Delivery(models.Model):
#     STATUS_CHOICES = (
#         ('assigned', 'Assigned'),
#         ('picked_up', 'Picked Up'),
#         ('delivered', 'Delivered'),
#     )

#     order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='delivery_details')
#     delivery_boy = models.ForeignKey(
#         settings.AUTH_USER_MODEL, 
#         on_delete=models.CASCADE, 
#         limit_choices_to={'role': 'delivery_boy'},
#         related_name='deliveries'
#     )
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='assigned')
#     assigned_at = models.DateTimeField(auto_now_add=True)
#     delivered_at = models.DateTimeField(blank=True, null=True)

#     def __str__(self):
#         return f"Delivery for Order {self.order.id} - Status: {self.status}"