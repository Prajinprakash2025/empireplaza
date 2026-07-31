from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('user', 'User'),
        ('employee', 'Employee'),
        ('delivery_boy', 'Delivery Boy'),
    )
    
    # Custom display ID (e.g. EMP-001, DB-001)
    employee_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    phone_number = models.CharField(max_length=15, unique=True, db_index=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')
    address = models.TextField(blank=True, null=True)
    
    otp = models.CharField(max_length=6, blank=True, null=True)
    otp_created_at = models.DateTimeField(blank=True, null=True)
    is_verified = models.BooleanField(default=False)

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['username']

    def save(self, *args, **kwargs):
        # Auto-generate unique employee_id safely without crashes on delete
        if not self.employee_id:
            if self.role == 'employee':
                last_user = CustomUser.objects.filter(role='employee', employee_id__startswith='EMP-').order_by('-id').first()
                if last_user and last_user.employee_id:
                    try:
                        last_num = int(last_user.employee_id.split('-')[1])
                        new_num = last_num + 1
                    except (IndexError, ValueError):
                        new_num = 1
                else:
                    new_num = 1
                self.employee_id = f"EMP-{new_num:03d}"

            elif self.role == 'delivery_boy':
                last_user = CustomUser.objects.filter(role='delivery_boy', employee_id__startswith='DB-').order_by('-id').first()
                if last_user and last_user.employee_id:
                    try:
                        last_num = int(last_user.employee_id.split('-')[1])
                        new_num = last_num + 1
                    except (IndexError, ValueError):
                        new_num = 1
                else:
                    new_num = 1
                self.employee_id = f"DB-{new_num:03d}"

        super().save(*args, **kwargs)

class DeliveryBoyProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='delivery_profile')
    vehicle_number = models.CharField(max_length=30, blank=True, null=True)
    is_on_duty = models.BooleanField(default=True)   # Online / Offline status
    is_busy = models.BooleanField(default=False)    # Free / Delivering an order status
    current_latitude = models.FloatField(blank=True, null=True)
    current_longitude = models.FloatField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} Profile ({self.user.employee_id})"