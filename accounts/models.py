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
    
    # Phone number is unique and used for OTP authentication
    phone_number = models.CharField(max_length=15, unique=True, db_index=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')
    address = models.TextField(blank=True, null=True)
    
    # OTP specific fields
    otp = models.CharField(max_length=6, blank=True, null=True)
    otp_created_at = models.DateTimeField(blank=True, null=True)
    is_verified = models.BooleanField(default=False)

    # Use phone_number as login username field
    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['username']

    def is_otp_expired(self):
        if not self.otp_created_at:
            return True
        # OTP is valid for 5 minutes
        expiration_time = self.otp_created_at + timezone.timedelta(minutes=5)
        return timezone.now() > expiration_time

    def __str__(self):
        return f"{self.phone_number} ({self.role})"