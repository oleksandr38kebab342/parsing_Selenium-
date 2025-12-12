from django.db import models


class Product(models.Model):
    name = models.CharField(max_length=512)
    url = models.URLField()  # Removed unique constraint to allow duplicates across categories
    sku = models.CharField(max_length=64)  # Removed unique constraint to allow duplicates across categories
    mpn = models.CharField(max_length=64, blank=True, null=True)
    manufacturer = models.CharField(max_length=128, blank=True, null=True)
    color = models.CharField(max_length=128, blank=True, null=True)
    memory = models.CharField(max_length=128, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=8, default="UAH")
    images = models.JSONField(default=list, blank=True)
    rating = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    review_count = models.PositiveIntegerField(default=0)
    screen_size = models.CharField(max_length=64, blank=True, null=True)
    resolution = models.CharField(max_length=64, blank=True, null=True)
    characteristics = models.JSONField(default=dict, blank=True)
    missing_fields = models.JSONField(default=list, blank=True)
    raw_jsonld = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.sku})"
