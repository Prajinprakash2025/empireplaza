from django.db import models
from django.utils import timezone


class SiteSetting(models.Model):
    # Contact & Location
    restaurant_name = models.CharField(max_length=255, blank=True, null=True, default="")
    email_address = models.EmailField(blank=True, null=True, default="")
    phone_number = models.CharField(max_length=20, blank=True, null=True, default="")
    physical_address = models.TextField(blank=True, null=True, default="")
    address_type = models.TextField(blank=True, null=True, default="")

    # GPS
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6,
        null=True, blank=True, default=0.0
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6,
        null=True, blank=True, default=0.0
    )

    delivery_radius = models.FloatField(default=0.0, help_text="In KM")

    # Footer & Working Hours
    footer_description = models.TextField(blank=True, null=True, default="")
    working_hours_mon_sat = models.CharField(
        max_length=100, blank=True, null=True, default=""
    )
    working_hours_sunday = models.CharField(
        max_length=100, blank=True, null=True, default=""
    )

    # Automated Working Hours
    opening_time = models.TimeField(
        null=True, blank=True, help_text="Format: HH:MM:SS"
    )
    closing_time = models.TimeField(
        null=True, blank=True, help_text="Format: HH:MM:SS"
    )

    # Manual Open / Close
    is_manually_open = models.BooleanField(
        default=True,
        help_text="Turn OFF to manually close the restaurant immediately."
    )

    # Social Media
    instagram_url = models.URLField(
        max_length=500, blank=True, null=True, default=""
    )
    facebook_url = models.URLField(
        max_length=500, blank=True, null=True, default=""
    )
    twitter_url = models.URLField(
        max_length=500, blank=True, null=True, default=""
    )
    whatsapp_url = models.URLField(
        max_length=500, blank=True, null=True, default=""
    )

    @property
    def is_open(self):
        if not self.is_manually_open:
            return False

        if self.opening_time is None or self.closing_time is None:
            return True

        current_time = timezone.localtime().time()

        if self.opening_time < self.closing_time:
            return self.opening_time <= current_time <= self.closing_time
        else:
            return current_time >= self.opening_time or current_time <= self.closing_time

    # Singleton - only one settings row
    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    class Meta:
        verbose_name = "Site Setting"
        verbose_name_plural = "Site Settings"

    def __str__(self):
        return "Website Settings"
