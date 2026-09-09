from django.contrib import admin
from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'rating',
        'is_approved',
        'created_at',
    )

    list_filter = (
        'rating',
        'is_approved',
    )

    search_fields = (
        'user__username',
        'user__first_name',
    )