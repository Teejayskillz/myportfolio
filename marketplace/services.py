from datetime import timedelta
from django.db import transaction
from django.utils import timezone

from .models import License, DownloadToken, Rental, RentalInvoice

def add_one_month(dt):
    try:
        from dateutil.relativedelta import relativedelta
        return dt + relativedelta(months=1)
    except Exception:
        return dt + timedelta(days=30)

@transaction.atomic
def fulfill_purchase(*, request, purchase):
    """
    purchase = PurchaseRequest
    Creates license/download OR rental + invoice and sends email.
    Returns: dict info about what happened.
    """
    now = timezone.now()
    result = {"ownership": False, "rental": False}

    # FULL OWNERSHIP
    if purchase.delivery_type in ("full_ownership", "source"):
        license_obj, _ = License.objects.get_or_create(
            purchase=purchase,
            defaults={"product": purchase.product, "expires_at": now + timedelta(days=365)},
        )
        token_obj, _ = DownloadToken.objects.get_or_create(
            license=license_obj,
            defaults={"expires_at": now + timedelta(days=7), "max_downloads": 3},
        )

        # reuse your admin email logic safely by importing helper
        from .admin import _send_ownership_email
        _send_ownership_email(request, purchase, license_obj, token_obj)

        result["ownership"] = True

    # RENT & HOST
    if purchase.delivery_type in ("rent_own", "hosted"):
        if not purchase.hosting_plan:
            raise ValueError("hosting_plan required for rent_own")

        existing_rental = (
            Rental.objects.filter(product=purchase.product, buyer_email__iexact=purchase.buyer_email)
            .order_by("-created_at")
            .first()
        )

        if existing_rental:
            base = existing_rental.expires_at if existing_rental.expires_at and existing_rental.expires_at > now else now
            existing_rental.hosting_plan = purchase.hosting_plan
            existing_rental.buyer_name = purchase.buyer_name
            existing_rental.whatsapp_number = purchase.whatsapp_number
            existing_rental.status = "active"
            existing_rental.expires_at = add_one_month(base)
            existing_rental.save()
            rental = existing_rental
        else:
            rental = Rental.objects.create(
                product=purchase.product,
                hosting_plan=purchase.hosting_plan,
                buyer_name=purchase.buyer_name,
                buyer_email=purchase.buyer_email,
                whatsapp_number=purchase.whatsapp_number,
                status="active",
                started_at=now,
                expires_at=add_one_month(now),
                admin_note=f"Auto-created from PurchaseRequest #{purchase.id}.",
            )

            RentalInvoice.objects.create(
                rental=rental,
                period_start=now.date(),
                period_end=add_one_month(now).date(),
                amount=purchase.hosting_plan.monthly_price,
                status="approved",
                admin_note=f"Initial month auto-approved from PurchaseRequest #{purchase.id}.",
            )

        from .admin import _send_hosted_activation_email
        _send_hosted_activation_email(request, purchase, rental)

        result["rental"] = True

    # mark purchase approved
    purchase.status = "approved"
    purchase.admin_note = (purchase.admin_note or "") + f"\nAuto-approved via Paystack on {now:%Y-%m-%d %H:%M}."
    purchase.save(update_fields=["status", "admin_note"])

    return result


@transaction.atomic
def fulfill_invoice(*, invoice):
    """
    invoice = RentalInvoice
    Extends rental by 1 month and marks invoice approved.
    """
    now = timezone.now()
    rental = invoice.rental
    base = rental.expires_at if rental.expires_at and rental.expires_at > now else now

    rental.expires_at = add_one_month(base)
    rental.status = "active"
    rental.save(update_fields=["expires_at", "status"])

    invoice.status = "approved"
    invoice.admin_note = (invoice.admin_note or "") + f"\nAuto-approved via Paystack on {now:%Y-%m-%d %H:%M}."
    invoice.save(update_fields=["status", "admin_note"])
