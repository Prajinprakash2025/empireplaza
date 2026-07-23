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
        # Auto-generate employee_id if not present for Staff roles
        if not self.employee_id:
            if self.role == 'employee':
                count = CustomUser.objects.filter(role='employee').count() + 1
                self.employee_id = f"EMP-{count:03d}"  # Generates EMP-001, EMP-002, etc.
            elif self.role == 'delivery_boy':
                count = CustomUser.objects.filter(role='delivery_boy').count() + 1
                self.employee_id = f"DB-{count:03d}"   # Generates DB-001, DB-002, etc.

        super().save(*args, **kwargs)