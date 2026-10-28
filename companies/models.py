from django.db import models


class Company(models.Model):
    """A customer of Statuspage. Each one gets a status page."""

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    # Whoever manages the company's DNS. Gets the records to add.
    dns_contact_email = models.EmailField(blank=True)
    # [{"name": "API", "status": "operational"}, ...]
    components = models.JSONField(default=list)

    class Meta:
        ordering = ["id"]
        verbose_name_plural = "companies"

    def __str__(self):
        return self.name

    def fetch_status_data(self):
        degraded = [
            c for c in self.components if c["status"] != "operational"
        ]
        return {
            "company": self,
            "components": self.components,
            "overall": (
                "Some systems are degraded"
                if degraded
                else "All systems operational"
            ),
        }
