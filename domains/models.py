from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

hostname = RegexValidator(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$")


def not_one_of_ours(host):
    ours = settings.APP_DOMAIN  # "statuspage.com"
    if host == ours or host.endswith("." + ours):
        raise ValidationError("Can't be one of our own domains.")


class CustomDomain(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        ACTIVE = "active"

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="custom_domains",
    )
    host = models.CharField(
        max_length=253,
        unique=True,
        validators=[hostname, not_one_of_ours],
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    # Set by the tls_certificate_issued webhook.
    https_ready = models.BooleanField(default=False)
    # The domain's UUID at SaaS Custom Domains, to check and remove it.
    provider_uuid = models.CharField(
        max_length=36, unique=True, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.host

    def save(self, *args, **kwargs):
        self.host = self.host.strip().lower().rstrip(".")
        super().save(*args, **kwargs)

    @property
    def label(self):
        if self.status != self.Status.ACTIVE:
            return "Waiting for DNS"
        if self.https_ready:
            return "Live"
        return "DNS OK, waiting for HTTPS"
