from django.db import models
from django.utils.text import slugify
import uuid
from django.utils import timezone
from datetime import timedelta
import secrets


class Product(models.Model):
    CATEGORY_CHOICES = (
        ('script', 'Script'),
        ('tool', 'Tool'),
        ('plugin', 'Plugin'),
        ('template', 'Template'),
    )

    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)

    tech_stack = models.CharField(
        max_length=255,
        help_text="e.g. Django, Laravel, WordPress"
    )

    version = models.CharField(max_length=50, default="1.0.0")
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

class SourceCodeOption(models.Model):
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name='source_option'
    )

    price = models.DecimalField(max_digits=10, decimal_places=2)
    update_duration_months = models.PositiveIntegerField(default=12)

    def __str__(self):
        return f"{self.product.title} – Source Code"


class HostingPlan(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='hosting_plans'
    )

    name = models.CharField(max_length=100)  # Basic, Pro, Enterprise
    price_per_month = models.DecimalField(max_digits=10, decimal_places=2)

    features = models.TextField(
        help_text="Describe limits, features, support level"
    )

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.product.title} – {self.name}"

class PurchaseRequest(models.Model):
    DELIVERY_CHOICES = (
        ('hosted', 'Hosted'),
        ('source', 'Source Code'),
        ('both', 'Hosted + Source Code'),
    )

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('active', 'Active'),
        ('expired', 'Expired'),
    )

    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    hosting_plan = models.ForeignKey(
        HostingPlan,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    delivery_type = models.CharField(max_length=20, choices=DELIVERY_CHOICES)

    buyer_name = models.CharField(max_length=255)
    buyer_email = models.EmailField()

    amount = models.DecimalField(max_digits=10, decimal_places=2)

    receipt = models.FileField(
        upload_to='marketplace/receipts/',
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product.title} – {self.buyer_email}"

class License(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    purchase = models.OneToOneField(PurchaseRequest, on_delete=models.CASCADE)

    license_key = models.CharField(max_length=50, unique=True, editable=False)

    issued_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.license_key:
            self.license_key = str(uuid.uuid4()).upper()
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=365)
        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"{self.product.title} – {self.license_key}"


class DownloadToken(models.Model):
    license = models.OneToOneField(License, on_delete=models.CASCADE)

    token = models.CharField(max_length=64, unique=True, editable=False)
    expires_at = models.DateTimeField()
    download_count = models.PositiveIntegerField(default=0)
    max_downloads = models.PositiveIntegerField(default=3)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def is_valid(self):
        return self.download_count < self.max_downloads
