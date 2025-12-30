from django.db import models
from django.utils.text import slugify
import uuid
import secrets
from django.utils import timezone
from datetime import timedelta

class PaymentGateway(models.Model):
    name = models.CharField(max_length=50)  # e.g., "Flutterwave", "Paystack"
    is_active = models.BooleanField(default=False)
    public_key = models.CharField(max_length=255, blank=True, null=True)
    secret_key = models.CharField(max_length=255, blank=True, null=True)
    callback_url = models.URLField(blank=True, null=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    CATEGORY_CHOICES = (
        ('script', 'Script'),
        ('tool', 'Tool'),
        ('plugin', 'Plugin'),
        ('template', 'Template'),
    )

    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    short_description = models.CharField(max_length=300)
    description = models.TextField()

    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES
    )

    tech_stack = models.CharField(
        max_length=255,
        help_text="e.g. Django, PHP, WordPress"
    )

    version = models.CharField(max_length=50, default="1.0.0")
    price = models.DecimalField(max_digits=10, decimal_places=2)

    product_file = models.FileField(
        upload_to="marketplace/products/"
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

class Order(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='orders'
    )

    email = models.EmailField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    reference = models.CharField(
        max_length=100,
        unique=True,
        editable=False
    )

    payment_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = str(uuid.uuid4())
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.title} - {self.email}"



class DownloadToken(models.Model):
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='download_token'
    )

    token = models.CharField(
        max_length=64,
        unique=True,
        editable=False
    )

    expires_at = models.DateTimeField()
    download_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)

        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=48)

        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"Download for {self.order.email}"
