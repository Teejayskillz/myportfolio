from django.db import models
from django.utils.text import slugify
import uuid
from django.utils import timezone
from datetime import timedelta
import secrets
from ckeditor.fields import RichTextField
from django.db import models
from ckeditor.fields import RichTextField
from django.utils.text import slugify

class HostingPlan(models.Model):
    PLAN_CHOICES = [
            ('Basic', 'Basic (Low Traffic)'),
            ('Pro', 'Pro (Medium Traffic)'),
            ('Enterprise', 'Enterprise (High Traffic/Company)'),
        ]
    name = models.CharField(max_length=100, choices=PLAN_CHOICES)
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2)
    features = models.TextField(help_text="Separate features with commas")
    is_active = models.BooleanField(default=True) 

    def __str__(self):
        return f"{self.name} - ₦{self.monthly_price}/mo"
        

class Product(models.Model):
    CATEGORY_CHOICES = (
        ('script', 'Script'),
        ('tool', 'Tool'),
        ('plugin', 'Plugin'),
        ('template', 'Template'),
    )

    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    short_description = models.TextField(blank=True)
    description = RichTextField(blank=True, help_text="Detailed product writeup / documentation")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    tech_stack = models.CharField(max_length=255, help_text="e.g. Django, Laravel, WordPress")
    version = models.CharField(max_length=50, default="1.0.0")
    is_active = models.BooleanField(default=True)

    # Images
    main_image = models.ImageField(upload_to="marketplace/products/", blank=True, null=True)
    

    # Source file (optional, to be used after payment)
    source_file = models.FileField(upload_to="marketplace/products/source/", blank=True, null=True)

    # Price
    price_full_ownership = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="One-time price for full source code ownership"
    )

    rental_setup_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="One-time setup fee for managed/rental version"
    )

    # Hosting options
    available_hosting_plans = models.ManyToManyField(
        'marketplace.HostingPlan',
        blank=True
    )
    @property
    def starting_monthly_price(self):
        plans = self.available_hosting_plans.filter(is_active=True)
        return plans.order_by('monthly_price').first()
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


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
    whatsapp_number = models.CharField(max_length=30) 

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
