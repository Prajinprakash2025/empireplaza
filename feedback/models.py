from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Review(models.Model):

    class RatingChoices(models.IntegerChoices):
        ONE_STAR = 1, 'Bad'
        TWO_STARS = 2, 'Below Average'
        THREE_STARS = 3, 'Average'
        FOUR_STARS = 4, 'Good'
        FIVE_STARS = 5, 'Excellent'

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reviews'
    )

    order = models.OneToOneField(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='review'
    )

    rating = models.IntegerField(
        choices=RatingChoices.choices,
        help_text="Rating from 1 to 5 stars"
    )

    comment = models.TextField()

    # Admin feedback approve/hide 
    is_approved = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"Review by {self.user.username} - "
            f"{self.rating} Stars ({self.get_rating_display()})"
        )