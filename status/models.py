from django.db import models


class Subscriber(models.Model):
    """Someone who wants email updates from a company's status page."""

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="subscribers",
    )
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "email"], name="unique_subscriber"
            )
        ]
