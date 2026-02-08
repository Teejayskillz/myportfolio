# marketplace/admin.py

from datetime import timedelta
from django.conf import settings
from django.contrib import admin, messages
from django.core.mail import EmailMessage
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import (
    Product,
    HostingPlan,
    PurchaseRequest,
    License,
    DownloadToken,
    Rental,
    RentalInvoice,
    MagicLinkToken,
)

def _send_hosted_activation_email(request, purchase, rental):
    access_url = request.build_absolute_uri(
        reverse("marketplace:rentals_access_request")
    )

    hosted_url_line = f"Hosted URL: {rental.hosted_url}\n" if rental.hosted_url else ""

    EmailMessage(
        subject=f"Your Hosted Rental is Active: {purchase.product.title}",
        body=(
            f"Hi {purchase.buyer_name},\n\n"
            f"Your hosted rental has been activated.\n\n"
            f"Product: {purchase.product.title}\n"
            f"Plan: {purchase.hosting_plan}\n"
            f"Status: {rental.status}\n"
            f"Active until: {rental.expires_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"{hosted_url_line}\n"
            f"To view your rental details and renew later, use the rentals access page:\n"
            f"{access_url}\n\n"
            f"Thanks!"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[purchase.buyer_email],
    ).send()


def _add_one_month(dt):
    """
    Adds ~1 month safely.
    If python-dateutil is installed, uses calendar months.
    Otherwise falls back to 30 days.
    """
    try:
        from dateutil.relativedelta import relativedelta
        return dt + relativedelta(months=1)
    except Exception:
        return dt + timedelta(days=30)


# -------------------------
# PRODUCT + PLANS
# -------------------------
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "version", "is_active", "created_at")
    prepopulated_fields = {"slug": ("title",)}
    list_filter = ("category", "is_active")
    search_fields = ("title", "tech_stack")


@admin.register(HostingPlan)
class HostingPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "monthly_price", "is_active")
    list_filter = ("name", "is_active")


# -------------------------
# PURCHASE REQUESTS
# -------------------------
@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "product",
        "buyer_name",
        "buyer_email",
        "whatsapp_number",
        "delivery_type",
        "hosting_plan",
        "amount",
        "status",
        "created_at",
    )
    list_filter = ("status", "delivery_type", "created_at")
    search_fields = ("buyer_email", "buyer_name", "whatsapp_number", "product__title")
    readonly_fields = ("created_at",)

    fieldsets = (
        ("Customer Info", {"fields": ("buyer_name", "buyer_email", "whatsapp_number")}),
        ("Purchase Details", {"fields": ("product", "delivery_type", "hosting_plan", "amount")}),
        ("Payment", {"fields": ("receipt", "status")}),
        ("Admin", {"fields": ("admin_note",)}),
    )

    actions = ["approve_and_fulfill_all", "reject_purchase"]

    @admin.action(description="Approve & fulfill (source license + hosted rental)")
    def approve_and_fulfill_all(self, request, queryset):
        """
        - Approves pending PurchaseRequests.
        - If delivery_type includes source: creates License + DownloadToken + sends email.
        - If delivery_type includes hosted: creates Rental (if not exists) + creates initial approved invoice.
        - Prevents duplicate rentals.
        """
        approved_count = 0
        source_fulfilled = 0
        hosted_fulfilled = 0
        skipped = 0
        email_failed = 0

        with transaction.atomic():
            purchases = queryset.select_for_update().select_related("product", "hosting_plan")

            for purchase in purchases:
                # Only handle pending (avoid double-processing)
                if purchase.status != "pending":
                    skipped += 1
                    continue

                now = timezone.now()

                # ✅ Approve purchase
                purchase.status = "approved"
                purchase.admin_note = (purchase.admin_note or "") + f"\nApproved on {now:%Y-%m-%d %H:%M} by admin."
                purchase.save(update_fields=["status", "admin_note"])
                approved_count += 1

                # -------------------------
                # SOURCE / BOTH: LICENSE + TOKEN + EMAIL
                # -------------------------
                if purchase.delivery_type in ("source", "both"):
                    license_obj, _ = License.objects.get_or_create(
                        purchase=purchase,
                        defaults={
                            "product": purchase.product,
                            "expires_at": now + timedelta(days=365),
                        },
                    )

                    token_obj, _ = DownloadToken.objects.get_or_create(
                        license=license_obj,
                        defaults={
                            "expires_at": now + timedelta(days=7),
                            "max_downloads": 3,
                        },
                    )

                    download_url = request.build_absolute_uri(
                        reverse("marketplace:download_product", kwargs={"token": token_obj.token})
                    )

                    try:
                        EmailMessage(
                            subject=f"Your Purchase: {purchase.product.title}",
                            body=(
                                f"Thank you {purchase.buyer_name}!\n\n"
                                f"Your license key: {license_obj.license_key}\n"
                                f"Download your product here: {download_url}\n\n"
                                f"License expires: {license_obj.expires_at.strftime('%Y-%m-%d %H:%M:%S')}"
                            ),
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            to=[purchase.buyer_email],
                        ).send()
                    except Exception:
                        # Optional: log if you want
                        email_failed += 1

                    source_fulfilled += 1

                # -------------------------
                # HOSTED / BOTH: CREATE RENTAL + INITIAL INVOICE
                # -------------------------
                if purchase.delivery_type in ("hosted", "both"):
                    if not purchase.hosting_plan:
                        skipped += 1
                        self.message_user(
                            request,
                            f"⚠️ Purchase #{purchase.id} skipped for hosted: missing hosting_plan.",
                            level=messages.WARNING,
                        )
                        continue

                    # Prevent duplicate rental creation for same product + email
                    existing_rental = Rental.objects.filter(
                        product=purchase.product,
                        buyer_email__iexact=purchase.buyer_email,
                    ).order_by("-created_at").first()

                    if existing_rental:
                        # If rental exists, you might want to activate it instead of creating a new one
                        # We'll just ensure it's active and set a fresh expiry if it's expired/cancelled.
                        base = existing_rental.expires_at if existing_rental.expires_at and existing_rental.expires_at > now else now
                        existing_rental.hosting_plan = purchase.hosting_plan
                        existing_rental.buyer_name = purchase.buyer_name
                        existing_rental.whatsapp_number = purchase.whatsapp_number
                        existing_rental.status = "active"
                        existing_rental.started_at = existing_rental.started_at or now
                        existing_rental.expires_at = _add_one_month(base)
                        existing_rental.admin_note = (existing_rental.admin_note or "") + f"\nRe-activated from PurchaseRequest #{purchase.id}."
                        existing_rental.save()

                        try:
                            _send_hosted_activation_email(request, purchase, existing_rental)
                        except Exception:
                            email_failed += 1

                        hosted_fulfilled += 1
                        continue

                    # Create new rental
                    rental = Rental.objects.create(
                        product=purchase.product,
                        hosting_plan=purchase.hosting_plan,
                        buyer_name=purchase.buyer_name,
                        buyer_email=purchase.buyer_email,
                        whatsapp_number=purchase.whatsapp_number,
                        status="active",
                        started_at=now,
                        expires_at=_add_one_month(now),
                        admin_note=f"Auto-created from PurchaseRequest #{purchase.id}. Setup fee included in PurchaseRequest amount.",
                    )

                    # Create initial invoice as approved (first month already paid with setup fee + first month)
                    RentalInvoice.objects.create(
                        rental=rental,
                        period_start=now.date(),
                        period_end=_add_one_month(now).date(),
                        amount=purchase.hosting_plan.monthly_price,
                        status="approved",
                        admin_note=f"Initial month auto-approved from PurchaseRequest #{purchase.id}. Setup fee is separate in PurchaseRequest amount.",
                    )

                    try:
                        _send_hosted_activation_email(request, purchase, rental)
                    except Exception:
                        email_failed += 1

                    hosted_fulfilled += 1
        # Summary messages
        if approved_count:
            self.message_user(request, f"✅ Approved {approved_count} purchase(s).", level=messages.SUCCESS)
        if source_fulfilled:
            self.message_user(request, f"📦 Fulfilled {source_fulfilled} source/both purchase(s) (license + download link).", level=messages.SUCCESS)
        if hosted_fulfilled:
            self.message_user(request, f"🏠 Fulfilled {hosted_fulfilled} hosted/both purchase(s) (rental created/activated).", level=messages.SUCCESS)
        if email_failed:
            self.message_user(request, f"⚠️ {email_failed} email(s) failed to send (check email settings/logs).", level=messages.WARNING)
        if skipped:
            self.message_user(request, f"⚠️ Skipped {skipped} item(s) (not pending / missing plan / etc).", level=messages.WARNING)

    @admin.action(description="Reject purchase request(s)")
    def reject_purchase(self, request, queryset):
        updated = queryset.exclude(status="approved").update(status="rejected")
        self.message_user(request, f"Rejected {updated} purchase request(s).", level=messages.WARNING)


# -------------------------
# LICENSE + DOWNLOAD TOKEN
# -------------------------
@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    list_display = ("product", "license_key", "expires_at", "is_active")
    readonly_fields = ("license_key", "issued_at")


@admin.register(DownloadToken)
class DownloadTokenAdmin(admin.ModelAdmin):
    list_display = ("license", "download_count", "max_downloads", "expires_at")


# -------------------------
# RENTALS + INVOICES
# -------------------------
@admin.register(Rental)
class RentalAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "buyer_email", "hosting_plan", "status", "expires_at", "hosted_url", "created_at")
    list_filter = ("status", "hosting_plan")
    search_fields = ("buyer_email", "buyer_name", "product__title")
    readonly_fields = ("created_at",)


@admin.register(RentalInvoice)
class RentalInvoiceAdmin(admin.ModelAdmin):
    list_display = ("id", "buyer_email", "product_title", "status", "amount", "period_start", "period_end", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("rental__buyer_email", "rental__buyer_name", "rental__product__title")
    readonly_fields = ("created_at",)

    actions = ["approve_selected_invoices", "reject_selected_invoices"]

    def buyer_email(self, obj):
        return obj.rental.buyer_email
    buyer_email.short_description = "Buyer Email"

    def product_title(self, obj):
        return obj.rental.product.title
    product_title.short_description = "Product"

    @admin.action(description="Approve selected invoices (extend rental + activate)")
    def approve_selected_invoices(self, request, queryset):
        approved_count = 0
        skipped_count = 0

        with transaction.atomic():
            invoices = queryset.select_for_update().select_related("rental", "rental__hosting_plan")

            for inv in invoices:
                if inv.status == "approved":
                    skipped_count += 1
                    continue
                if inv.status != "pending":
                    skipped_count += 1
                    continue

                rental = inv.rental
                now = timezone.now()
                base = rental.expires_at if rental.expires_at and rental.expires_at > now else now

                # Extend rental 1 month
                rental.expires_at = _add_one_month(base)
                rental.status = "active"
                rental.save(update_fields=["expires_at", "status"])

                # Approve invoice
                inv.status = "approved"
                inv.admin_note = (inv.admin_note or "") + f"\nApproved on {now:%Y-%m-%d %H:%M} by admin."
                inv.save(update_fields=["status", "admin_note"])

                approved_count += 1

        if approved_count:
            self.message_user(
                request,
                f"✅ Approved {approved_count} invoice(s) and extended rentals.",
                level=messages.SUCCESS,
            )
        if skipped_count:
            self.message_user(
                request,
                f"⚠️ Skipped {skipped_count} invoice(s) (already approved or not pending).",
                level=messages.WARNING,
            )

    @admin.action(description="Reject selected invoices")
    def reject_selected_invoices(self, request, queryset):
        updated = queryset.exclude(status="approved").update(status="rejected")
        self.message_user(request, f"Rejected {updated} invoice(s).", level=messages.WARNING)


# -------------------------
# MAGIC LINK TOKENS
# -------------------------
@admin.register(MagicLinkToken)
class MagicLinkTokenAdmin(admin.ModelAdmin):
    list_display = ("email", "token", "expires_at", "used_at", "created_at", "is_valid_display")
    search_fields = ("email", "token")
    list_filter = ("created_at",)
    readonly_fields = ("created_at", "token")

    def is_valid_display(self, obj):
        return obj.is_valid()
    is_valid_display.short_description = "Valid?"
