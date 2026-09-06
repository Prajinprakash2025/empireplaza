from django.db import models


class Banner(models.Model):
    subtitle = models.CharField(max_length=200)
    title = models.CharField(max_length=255)
    description = models.TextField()

    image = models.ImageField(
        upload_to='banners/'
    )

    button_text = models.CharField(
        max_length=100,
        default='ORDER NOW'
    )

    button_link = models.CharField(
        max_length=255,
        blank=True
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title
