import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

logger = logging.getLogger("marketplace")


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
