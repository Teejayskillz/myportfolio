from django.db import models
from django.forms import ValidationError
from django.utils.text import slugify
import uuid
from django.utils import timezone
from datetime import timedelta
import secrets
from ckeditor.fields import RichTextField
import logging
from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
logger = logging.getLogger("marketplace")



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
        help_text="One-time price for full source code ownership",
        null=True,
        blank=True
    )

    rental_setup_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="One-time setup fee for managed/rental version",
        null=True,
        blank=True
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
    ("full_ownership", "Full Ownership (Source Code + Docs)"),
    ("rent_own", "Rent & Host (Setup + Monthly)"),
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

    DOMAIN_OPTION_CHOICES = (
        ("none", "No domain"),
        ("have_domain", "I already have a domain"),
        ("need_domain", "I want Sleekpedia to register a domain"),
    )

    domain_option = models.CharField(
        max_length=20,
        choices=DOMAIN_OPTION_CHOICES,
        default="none"
    )
    domain_name = models.CharField(max_length=253, blank=True)  # domains max ~253 chars
    domain_status = models.CharField(
        max_length=20,
        default="unchecked",
        blank=True
    )

    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    from django.core.exceptions import ValidationError

    def clean(self):
       super().clean()
       if self.delivery_type == "rent_own" and not self.hosting_plan:
            raise ValidationError({"hosting_plan": "Hosting plan is required for Rent & Own."})
       if self.delivery_type == "full_ownership":
            self.hosting_plan = None
       if self.domain_option in ("have_domain", "need_domain") and not self.domain_name:
            raise ValidationError({"domain_name": "Please enter a domain name."})
        
 
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

class Rental(models.Model):
    STATUS_CHOICES = (
        ("active", "Active"),
        ("expired", "Expired"),
        ("cancelled", "Cancelled"),
    )

    product = models.ForeignKey("marketplace.Product", on_delete=models.CASCADE)
    hosting_plan = models.ForeignKey("marketplace.HostingPlan", on_delete=models.PROTECT)

    buyer_name = models.CharField(max_length=255)
    buyer_email = models.EmailField(db_index=True)
    whatsapp_number = models.CharField(max_length=30)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    started_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()

    # optional: admin can store hosted URL or notes
    hosted_url = models.URLField(blank=True)
    admin_note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.expires_at:
            # default: 30 days rental after activation
            self.expires_at = timezone.now() + timedelta(days=30)
        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.expires_at
    

    def __str__(self):
        return f"{self.product.title} ({self.buyer_email}) - {self.status}"


class RentalInvoice(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )

    rental = models.ForeignKey(Rental, on_delete=models.CASCADE, related_name="invoices")

    # What payment covers
    period_start = models.DateField()
    period_end = models.DateField()

    amount = models.DecimalField(max_digits=10, decimal_places=2)

    receipt = models.FileField(upload_to="marketplace/rental_receipts/", blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    admin_note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Invoice #{self.id} - {self.rental.buyer_email} - {self.status}"


class MagicLinkToken(models.Model):
    email = models.EmailField(db_index=True)
    token = models.CharField(max_length=64, unique=True, editable=False)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def is_valid(self):
        return self.used_at is None and timezone.now() < self.expires_at

    def __str__(self):
        return f"{self.email} - valid={self.is_valid()}"


def _safe_send_mail(*, subject: str, message: str, to: list[str]) -> int:
    """
    Sends email and LOGS success/failure.
    - In DEBUG=True: raises errors so you can see them immediately.
    - In production: logs the exception but won't break checkout.
    """
    try:
        sent = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=to,
            fail_silently=False,
        )
        logger.info("EMAIL SENT=%s subject=%s to=%s", sent, subject, to)
        return sent
    except Exception:
        logger.exception("EMAIL FAILED subject=%s to=%s", subject, to)
        if getattr(settings, "DEBUG", False):
            raise
        return 0


def send_purchase_pending_emails(*, request, purchase) -> None:
    """
    purchase = PurchaseRequest (pending)
    Sends:
      - customer confirmation
      - admin notification
    """
    brand = getattr(settings, "MARKETPLACE_BRAND_NAME", "Marketplace")
    admin_emails = getattr(settings, "MARKETPLACE_ADMIN_EMAILS", [])

    # Customer email
    customer_subject = f"{brand}: Order received (pending verification)"
    customer_message = (
        f"Hi {purchase.buyer_name},\n\n"
        f"We received your order for: {purchase.product.title}\n"
        f"Delivery type: {purchase.delivery_type}\n"
        f"Amount: ₦{purchase.amount}\n"
        f"Status: Pending verification\n\n"
        f"Next step: We will verify your payment and email you once approved.\n\n"
        f"Thanks,\n{brand}"
    )
    _safe_send_mail(subject=customer_subject, message=customer_message, to=[purchase.buyer_email])

    # Admin email + admin link
    if admin_emails:
        admin_url = request.build_absolute_uri(
            reverse("admin:marketplace_purchaserequest_change", args=[purchase.id])
        )
        admin_subject = f"{brand}: New order submitted (#{purchase.id})"
        admin_message = (
            f"New PurchaseRequest submitted.\n\n"
            f"ID: {purchase.id}\n"
            f"Product: {purchase.product.title}\n"
            f"Delivery: {purchase.delivery_type}\n"
            f"Hosting plan: {purchase.hosting_plan or '—'}\n"
            f"Amount: ₦{purchase.amount}\n"
            f"Buyer: {purchase.buyer_name} ({purchase.buyer_email})\n"
            f"WhatsApp: {purchase.whatsapp_number}\n"
            f"Receipt uploaded: {'YES' if purchase.receipt else 'NO'}\n\n"
            f"Review in admin: {admin_url}\n"
        )
        _safe_send_mail(subject=admin_subject, message=admin_message, to=admin_emails)


def send_rental_invoice_pending_emails(*, request, invoice) -> None:
    """
    invoice = RentalInvoice (pending)
    Sends:
      - customer confirmation
      - admin notification
    """
    brand = getattr(settings, "MARKETPLACE_BRAND_NAME", "Marketplace")
    admin_emails = getattr(settings, "MARKETPLACE_ADMIN_EMAILS", [])

    email = invoice.rental.buyer_email
    name = invoice.rental.buyer_name

    # Customer email
    customer_subject = f"{brand}: Renewal receipt received (pending verification)"
    customer_message = (
        f"Hi {name},\n\n"
        f"We received your renewal receipt for: {invoice.rental.product.title}\n"
        f"Period: {invoice.period_start} → {invoice.period_end}\n"
        f"Amount: ₦{invoice.amount}\n"
        f"Status: Pending verification\n\n"
        f"We’ll verify and update your rental status.\n\n"
        f"Thanks,\n{brand}"
    )
    _safe_send_mail(subject=customer_subject, message=customer_message, to=[email])

    # Admin email + admin link
    if admin_emails:
        admin_url = request.build_absolute_uri(
            reverse("admin:marketplace_rentalinvoice_change", args=[invoice.id])
        )
        admin_subject = f"{brand}: Renewal receipt submitted (Invoice #{invoice.id})"
        admin_message = (
            f"New renewal invoice receipt submitted.\n\n"
            f"Invoice ID: {invoice.id}\n"
            f"Product: {invoice.rental.product.title}\n"
            f"Buyer: {name} ({email})\n"
            f"Period: {invoice.period_start} → {invoice.period_end}\n"
            f"Amount: ₦{invoice.amount}\n"
            f"Receipt uploaded: {'YES' if invoice.receipt else 'NO'}\n\n"
            f"Review in admin: {admin_url}\n"
        )
        _safe_send_mail(subject=admin_subject, message=admin_message, to=admin_emails)

class PaymentTransaction(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("success", "Success"),
        ("failed", "Failed"),
    )

    provider = models.CharField(max_length=20, default="paystack")
    reference = models.CharField(max_length=80, unique=True, db_index=True)

    email = models.EmailField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)  # Naira
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Links to PurchaseRequest OR RentalInvoice
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    paystack_payload = models.JSONField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.provider}:{self.reference} ({self.status})"
    
    def clean(self):
        return super().clean()
