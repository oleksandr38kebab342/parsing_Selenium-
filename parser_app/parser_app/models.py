from django.db import models


class Product(models.Model):
    name = models.CharField(max_length=512)
    url = models.URLField(unique=True)
    sku = models.CharField(max_length=64, unique=True)
    mpn = models.CharField(max_length=64, blank=True)
    manufacturer = models.CharField(max_length=128, blank=True)
    color = models.CharField(max_length=128, blank=True)
    memory = models.CharField(max_length=128, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=8, default="UAH")
    images = models.JSONField(default=list, blank=True)
    rating = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    review_count = models.PositiveIntegerField(default=0)
    screen_size = models.CharField(max_length=64, blank=True)
    resolution = models.CharField(max_length=64, blank=True)
    characteristics = models.JSONField(default=dict, blank=True)
    missing_fields = models.JSONField(default=list, blank=True)
    raw_jsonld = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.sku})"
