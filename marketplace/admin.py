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


def _send_hosted_activation_email(request, purchase, rental) -> int:
    access_url = request.build_absolute_uri(reverse("marketplace:rentals_access_request"))
    hosted_url_line = f"Hosted URL: {rental.hosted_url}\n" if rental.hosted_url else ""

    msg = EmailMessage(
        subject=f"Your Hosted Rental is Active: {purchase.product.title}",
        body=(
            f"Hi {purchase.buyer_name},\n\n"
            f"Your hosted rental has been activated.\n\n"
            f"Product: {purchase.product.title}\n"
            f"Plan: {purchase.hosting_plan}\n"
            f"Status: {rental.status}\n"
            f"Active until: {rental.expires_at:%Y-%m-%d %H:%M:%S}\n"
            f"{hosted_url_line}\n"
            f"To view your rental details and renew later, use the rentals access page:\n"
            f"{access_url}\n\n"
            f"Thanks!"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[purchase.buyer_email],
    )
    return msg.send(fail_silently=False)


def _send_ownership_email(request, purchase, license_obj, token_obj) -> int:
    download_url = request.build_absolute_uri(
        reverse("marketplace:download_product", kwargs={"token": token_obj.token})
    )

    msg = EmailMessage(
        subject=f"Your Purchase: {purchase.product.title}",
        body=(
            f"Thank you {purchase.buyer_name}!\n\n"
            f"Your license key: {license_obj.license_key}\n"
            f"Download your product here: {download_url}\n\n"
            f"License expires: {license_obj.expires_at:%Y-%m-%d %H:%M:%S}"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[purchase.buyer_email],
    )
    return msg.send(fail_silently=False)


def _add_one_month(dt):
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
    list_display_links = ("id", "product")
    list_filter = ("status", "delivery_type", "created_at")
    search_fields = ("buyer_email", "buyer_name", "whatsapp_number", "product__title")
    readonly_fields = ("created_at",)

    fieldsets = (
        ("Customer Info", {"fields": ("buyer_name", "buyer_email", "whatsapp_number")}),
        ("Purchase Details", {"fields": ("product", "delivery_type", "hosting_plan", "amount")}),
        ("Payment", {"fields": ("receipt", "status")}),
        ("Admin", {"fields": ("admin_note",)}),
    )

    actions = ["approve_and_fulfill_all", "resend_fulfillment_emails", "reject_purchase"]

    def _fulfill_one(self, request, purchase, now):
        """
        Fulfill and email based on delivery_type.
        Returns tuple: (source_sent, rent_sent, skipped, email_failed)
        """
        source_sent = 0
        rent_sent = 0
        skipped = 0
        email_failed = 0

        # OWNERSHIP (new + old alias)
        if purchase.delivery_type in ("full_ownership", "source"):
            license_obj, _ = License.objects.get_or_create(
                purchase=purchase,
                defaults={
                    "product": purchase.product,
                    "expires_at": now + timedelta(days=365),
                },
            )
            token_obj, _ = DownloadToken.objects.get_or_create(
                license=license_obj,
                defaults={"expires_at": now + timedelta(days=7), "max_downloads": 3},
            )

            try:
                sent = _send_ownership_email(request, purchase, license_obj, token_obj)
                if sent == 0:
                    email_failed += 1
                    self.message_user(
                        request,
                        f"❌ Ownership email reported 0 sent for Purchase #{purchase.id} ({purchase.buyer_email}).",
                        level=messages.ERROR,
                    )
                else:
                    source_sent += 1
            except Exception as e:
                email_failed += 1
                self.message_user(
                    request,
                    f"❌ Ownership email failed for Purchase #{purchase.id} ({purchase.buyer_email}): "
                    f"{type(e).__name__}: {e}",
                    level=messages.ERROR,
                )

        # RENT/HOST (new + old alias)
        if purchase.delivery_type in ("rent_own", "hosted"):
            if not purchase.hosting_plan:
                skipped += 1
                self.message_user(
                    request,
                    f"⚠️ Purchase #{purchase.id} skipped for rent: missing hosting_plan.",
                    level=messages.WARNING,
                )
                return source_sent, rent_sent, skipped, email_failed

            existing_rental = Rental.objects.filter(
                product=purchase.product,
                buyer_email__iexact=purchase.buyer_email,
            ).order_by("-created_at").first()

            if existing_rental:
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
                    sent = _send_hosted_activation_email(request, purchase, existing_rental)
                    if sent == 0:
                        email_failed += 1
                        self.message_user(
                            request,
                            f"❌ Rent email reported 0 sent for Purchase #{purchase.id} ({purchase.buyer_email}).",
                            level=messages.ERROR,
                        )
                    else:
                        rent_sent += 1
                except Exception as e:
                    email_failed += 1
                    self.message_user(
                        request,
                        f"❌ Rent email failed for Purchase #{purchase.id} ({purchase.buyer_email}): "
                        f"{type(e).__name__}: {e}",
                        level=messages.ERROR,
                    )
                return source_sent, rent_sent, skipped, email_failed

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

            RentalInvoice.objects.create(
                rental=rental,
                period_start=now.date(),
                period_end=_add_one_month(now).date(),
                amount=purchase.hosting_plan.monthly_price,
                status="approved",
                admin_note=f"Initial month auto-approved from PurchaseRequest #{purchase.id}.",
            )

            try:
                sent = _send_hosted_activation_email(request, purchase, rental)
                if sent == 0:
                    email_failed += 1
                    self.message_user(
                        request,
                        f"❌ Rent email reported 0 sent for Purchase #{purchase.id} ({purchase.buyer_email}).",
                        level=messages.ERROR,
                    )
                else:
                    rent_sent += 1
            except Exception as e:
                email_failed += 1
                self.message_user(
                    request,
                    f"❌ Rent email failed for Purchase #{purchase.id} ({purchase.buyer_email}): "
                    f"{type(e).__name__}: {e}",
                    level=messages.ERROR,
                )

        return source_sent, rent_sent, skipped, email_failed

    @admin.action(description="Approve & fulfill (send emails + create license/rental)")
    def approve_and_fulfill_all(self, request, queryset):
        approved_count = 0
        source_fulfilled = 0
        hosted_fulfilled = 0
        skipped = 0
        email_failed = 0

        with transaction.atomic():
            purchases = queryset.select_for_update().select_related("product", "hosting_plan")

            for purchase in purchases:
                if purchase.status != "pending":
                    skipped += 1
                    continue

                now = timezone.now()

                # Fulfill + email first (so we can see errors)
                s_sent, r_sent, sk, e_failed = self._fulfill_one(request, purchase, now)
                source_fulfilled += s_sent
                hosted_fulfilled += r_sent
                skipped += sk
                email_failed += e_failed

                # Mark approved regardless (you can change this if you want)
                purchase.status = "approved"
                purchase.admin_note = (purchase.admin_note or "") + f"\nApproved on {now:%Y-%m-%d %H:%M} by admin."
                purchase.save(update_fields=["status", "admin_note"])
                approved_count += 1

        if approved_count:
            self.message_user(request, f"✅ Approved {approved_count} purchase(s).", level=messages.SUCCESS)
        if source_fulfilled:
            self.message_user(request, f"📦 Sent {source_fulfilled} ownership email(s).", level=messages.SUCCESS)
        if hosted_fulfilled:
            self.message_user(request, f"🏠 Sent {hosted_fulfilled} rent email(s).", level=messages.SUCCESS)
        if email_failed:
            self.message_user(request, f"⚠️ {email_failed} email(s) failed (see red errors above).", level=messages.WARNING)
        if skipped:
            self.message_user(request, f"⚠️ Skipped {skipped} item(s).", level=messages.WARNING)

    @admin.action(description="Resend fulfillment email(s) (works for approved too)")
    def resend_fulfillment_emails(self, request, queryset):
        resent_ownership = 0
        resent_rent = 0
        skipped = 0
        email_failed = 0

        purchases = queryset.select_related("product", "hosting_plan")
        now = timezone.now()

        for purchase in purchases:
            s_sent, r_sent, sk, e_failed = self._fulfill_one(request, purchase, now)
            resent_ownership += s_sent
            resent_rent += r_sent
            skipped += sk
            email_failed += e_failed

        if resent_ownership:
            self.message_user(request, f"📨 Resent {resent_ownership} ownership email(s).", level=messages.SUCCESS)
        if resent_rent:
            self.message_user(request, f"📨 Resent {resent_rent} rent email(s).", level=messages.SUCCESS)
        if email_failed:
            self.message_user(request, f"⚠️ {email_failed} email(s) failed (see red errors).", level=messages.WARNING)
        if skipped:
            self.message_user(request, f"⚠️ Skipped {skipped} item(s).", level=messages.WARNING)

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
                if inv.status == "approved" or inv.status != "pending":
                    skipped_count += 1
                    continue

                rental = inv.rental
                now = timezone.now()
                base = rental.expires_at if rental.expires_at and rental.expires_at > now else now

                rental.expires_at = _add_one_month(base)
                rental.status = "active"
                rental.save(update_fields=["expires_at", "status"])

                inv.status = "approved"
                inv.admin_note = (inv.admin_note or "") + f"\nApproved on {now:%Y-%m-%d %H:%M} by admin."
                inv.save(update_fields=["status", "admin_note"])

                approved_count += 1

        if approved_count:
            self.message_user(request, f"✅ Approved {approved_count} invoice(s) and extended rentals.", level=messages.SUCCESS)
        if skipped_count:
            self.message_user(request, f"⚠️ Skipped {skipped_count} invoice(s).", level=messages.WARNING)

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
