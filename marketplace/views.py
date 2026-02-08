import uuid
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import HttpResponse, Http404
import os
from django.utils import timezone
from datetime import timedelta, date
from django.core.mail import send_mail
from django.urls import reverse
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from .models import (
    Product,
    HostingPlan,
    PurchaseRequest,
    DownloadToken,
    Rental,
    RentalInvoice,
    MagicLinkToken
)           
from .forms import (
    CheckoutOptionsForm,
    BuyerDetailsForm,
    ReceiptUploadForm
)


def product_list(request):
    products = Product.objects.filter(is_active=True)
    return render(request, 'marketplace/product_list.html', {
        'products': products
    })


def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    return render(request, 'marketplace/product_detail.html', {
        'product': product
    })


def checkout_options(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)

    if request.method == 'POST':
        form = CheckoutOptionsForm(request.POST, product=product)

        if form.is_valid():
            delivery_type = form.cleaned_data['delivery_type']
            hosting_plan = form.cleaned_data.get('hosting_plan')

            # 🔐 SERVER-SIDE PRICE CALCULATION
            amount = Decimal('0.00')

            if delivery_type in ['hosted', 'both']:
                if not hosting_plan:
                    messages.error(request, "Please select a hosting plan.")
                    return redirect(request.path)
                amount += product.rental_setup_fee
                amount += hosting_plan.monthly_price

            if delivery_type in ['source', 'both']:
                source_option = getattr(product, 'source_option', None)
                if not source_option:
                    messages.error(request, "Source code not available for this product.")
                    return redirect(request.path)
                amount += source_option.price

            checkout_id = str(uuid.uuid4())

            checkouts = request.session.get('checkouts', {})
            checkouts[checkout_id] = {
                'product_id': product.id,
                'delivery_type': delivery_type,
                'hosting_plan_id': hosting_plan.id if hosting_plan else None,
                'amount': str(amount),
                'buyer': {}
            }

            request.session['checkouts'] = checkouts
            return redirect('marketplace:checkout_details', checkout_id=checkout_id)

    else:
        form = CheckoutOptionsForm(product=product)

    return render(request, 'marketplace/checkout/options.html', {
        'product': product,
        'form': form,
        'step': 1
    })


def checkout_details(request, checkout_id):
    checkouts = request.session.get('checkouts', {})
    checkout = checkouts.get(checkout_id)

    if not checkout:
        messages.error(request, "Checkout session expired.")
        return redirect('marketplace:product_list')

    product = get_object_or_404(Product, id=checkout["product_id"])

    if request.method == 'POST':
        form = BuyerDetailsForm(request.POST)
        if form.is_valid():
            checkout['buyer'] = {
                'name': form.cleaned_data['buyer_name'],
                'email': form.cleaned_data['buyer_email'],
                'whatsapp': form.cleaned_data['whatsapp_number'],
                'note': form.cleaned_data.get('note', '')
            }
            checkouts[checkout_id] = checkout
            request.session['checkouts'] = checkouts
            return redirect('marketplace:checkout_summary', checkout_id=checkout_id)
    else:
        form = BuyerDetailsForm()

    return render(request, 'marketplace/checkout/details.html', {
        'form': form,
        'checkout': checkout,
        'step': 2,
        'product': product
    })


def checkout_summary(request, checkout_id):
    checkouts = request.session.get('checkouts', {})
    checkout = checkouts.get(checkout_id)

    if not checkout:
        messages.error(request, "Checkout session expired.")
        return redirect('marketplace:product_list')

    # Get the product object
    from .models import Product, HostingPlan
    product = Product.objects.get(id=checkout['product_id'])

    hosting_plan = None
    if checkout.get('hosting_plan_id'):
        hosting_plan = HostingPlan.objects.get(id=checkout['hosting_plan_id'])

    # Pre-fill the receipt form if needed
    from .forms import ReceiptUploadForm
    form = ReceiptUploadForm()

    return render(request, 'marketplace/checkout/summary.html', {
        'checkout': checkout,
        'checkout_id': checkout_id,
        'product': product,
        'hosting_plan': hosting_plan,
        'form': form,
        'step': 3  
    })


def checkout_payment(request, checkout_id):
    # Get all active checkouts from session
    checkouts = request.session.get('checkouts', {})
    checkout = checkouts.get(checkout_id)

    if not checkout:
        messages.error(request, "Checkout session expired.")
        return redirect('marketplace:product_list')

    # Fetch product object
    product = get_object_or_404(Product, id=checkout['product_id'])

    # Optional: fetch hosting plan if selected
    hosting_plan = None
    if checkout.get('hosting_plan_id'):
        hosting_plan = get_object_or_404(HostingPlan, id=checkout['hosting_plan_id'])

    if request.method == 'POST':
        form = ReceiptUploadForm(request.POST, request.FILES)
        if form.is_valid():
            # Create PurchaseRequest
            purchase = PurchaseRequest.objects.create(
                product=product,
                hosting_plan=hosting_plan,
                delivery_type=checkout['delivery_type'],
                buyer_name=checkout['buyer']['name'],
                buyer_email=checkout['buyer']['email'],
                whatsapp_number=checkout['buyer']['whatsapp'],
                amount=Decimal(checkout['amount']),
                receipt=form.cleaned_data['receipt'],
                status='pending'  # Default status
            )
            from .emails import send_purchase_pending_emails
            send_purchase_pending_emails(request=request, purchase=purchase)

            # Remove this checkout from session
            del checkouts[checkout_id]
            request.session['checkouts'] = checkouts

            messages.success(request, "Your order has been submitted! Admin will review your payment.")
            return redirect('marketplace:product_list')

    else:
        form = ReceiptUploadForm()

    return render(request, 'marketplace/checkout/summary.html', {
        'checkout': checkout,
        'checkout_id': checkout_id,
        'product': product,
        'hosting_plan': hosting_plan,
        'form': form,
        'step': 3  # Step indicator
    })


def download_product(request, token):
    download_token = get_object_or_404(DownloadToken, token=token)

    if download_token.download_count >= download_token.max_downloads:
        raise Http404("Download limit reached.")

    if timezone.now() > download_token.expires_at:
        raise Http404("Download link expired.")

    # Increment usage
    download_token.download_count += 1
    download_token.save(update_fields=['download_count'])
    file_path = download_token.license.purchase.product.source_file.path
    file_name = os.path.basename(file_path)

    response = HttpResponse(open(file_path, 'rb'), content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{file_name}"'
    return response

def buy_now(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)

    if request.method == 'POST':
        form = BuyerDetailsForm(request.POST)
        if form.is_valid():
            # Save buyer info in session temporarily
            request.session['buy_now'] = {
                'product_id': product.id,
                'buyer_name': form.cleaned_data['buyer_name'],
                'buyer_email': form.cleaned_data['buyer_email'],
                'whatsapp_number': form.cleaned_data['whatsapp_number'],
                'amount': str(product.price_full_ownership)
            }
            return redirect('marketplace:buy_now_receipt', purchase_id=product.id)
    else:
        form = BuyerDetailsForm()

    return render(request, 'marketplace/checkout/buy_now.html', {
        'form': form,
        'product': product,
        'step': 1
    })

def buy_now_receipt(request, purchase_id):
    session_data = request.session.get('buy_now')
    if not session_data or int(session_data['product_id']) != purchase_id:
        messages.error(request, "Session expired. Please start again.")
        return redirect('marketplace:product_list')

    product = get_object_or_404(Product, id=purchase_id)

    if request.method == 'POST':
        form = ReceiptUploadForm(request.POST, request.FILES)
        if form.is_valid():
            # Create PurchaseRequest
            purchase = PurchaseRequest.objects.create(
                product=product,
                delivery_type='source',
                buyer_name=session_data['buyer_name'],
                buyer_email=session_data['buyer_email'],
                whatsapp_number=session_data['whatsapp_number'],
                amount=Decimal(session_data['amount']),
                receipt=form.cleaned_data['receipt'],
                status='pending'
            )
            # Clear session
            del request.session['buy_now']
            return redirect('marketplace:buy_now_summary', purchase_id=purchase.id)
    else:
        form = ReceiptUploadForm()

    return render(request, 'marketplace/checkout/buy_now_receipt.html', {
        'form': form,
        'product': product,
        'step': 2
    })

def buy_now_summary(request, purchase_id):
    purchase = get_object_or_404(PurchaseRequest, id=purchase_id)

    return render(request, 'marketplace/checkout/buy_now_summary.html', {
        'purchase': purchase,
        'step': 3
    })

def rent_start(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    plans = product.available_hosting_plans.filter(is_active=True).order_by("monthly_price")

    if request.method == "POST":
        plan_id = request.POST.get("plan_id")
        buyer_name = request.POST.get("buyer_name", "").strip()
        buyer_email = request.POST.get("buyer_email", "").strip()
        whatsapp_number = request.POST.get("whatsapp_number", "").strip()

        plans = product.available_hosting_plans.filter(is_active=True).order_by("monthly_price")
        if not plans.exists():
            messages.error(request, "No hosting plans available for this product yet.")
            return redirect("marketplace:product_detail", slug=product.slug)

        plan = plans.filter(id=plan_id).first()
        if not plan:
            messages.error(request, "Please select a valid hosting plan.")
            return redirect("marketplace:rent_start", slug=product.slug)

        if not buyer_name or not buyer_email or not whatsapp_number:
            messages.error(request, "Please fill in all required fields.")
            return redirect("marketplace:rent_start", slug=product.slug)

        # First payment = setup fee + first month
        amount = product.rental_setup_fee + plan.monthly_price

        purchase = PurchaseRequest.objects.create(
            product=product,
            hosting_plan=plan,
            delivery_type="hosted",
            buyer_name=buyer_name,
            buyer_email=buyer_email,
            whatsapp_number=whatsapp_number,
            amount=amount,
            status="pending",
        )

        return redirect("marketplace:rent_receipt", purchase_id=purchase.id)

    return render(request, "marketplace/rent_start.html", {
        "product": product,
        "plans": plans,
        "setup_fee": product.rental_setup_fee,
    })


def rent_receipt(request, purchase_id):
    purchase = get_object_or_404(PurchaseRequest, id=purchase_id, delivery_type="hosted")

    if request.method == "POST":
        receipt = request.FILES.get("receipt")
        if not receipt:
            messages.error(request, "Please upload a receipt.")
            return redirect("marketplace:rent_receipt", purchase_id=purchase.id)

        purchase.receipt = receipt
        purchase.status = "pending"
        purchase.save()

        from .emails import send_purchase_pending_emails
        send_purchase_pending_emails(request=request, purchase=purchase)


        return redirect("marketplace:rent_confirmed", purchase_id=purchase.id)

    return render(request, "marketplace/rent_receipt.html", {"purchase": purchase})


def rent_confirmed(request, purchase_id):
    purchase = get_object_or_404(PurchaseRequest, id=purchase_id, delivery_type="hosted")
    return render(request, "marketplace/rent_confirmed.html", {"purchase": purchase})


# -------------------------
# MAGIC LINK ACCESS
# -------------------------
def rentals_access_request(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()

        # check if rentals exist for that email (any status)
        has_rentals = Rental.objects.filter(buyer_email__iexact=email).exists()

        if has_rentals:
            token_obj = MagicLinkToken.objects.create(
                email=email,
                expires_at=timezone.now() + timedelta(minutes=15),
            )
            link = request.build_absolute_uri(
                reverse("marketplace:rentals_magic_login", args=[token_obj.token])
            )

            # send email
            send_mail(
                subject="Your Rentals Access Link",
                message=f"Use this link to access your rentals (expires in 15 minutes):\n\n{link}",
                from_email=None,  # uses DEFAULT_FROM_EMAIL
                recipient_list=[email],
                fail_silently=False,
            )

        # ALWAYS show neutral message (your security choice)
        messages.success(request, "If we found rentals for this email, we sent a link.")
        return redirect("marketplace:rentals_access_request")

    return render(request, "marketplace/rentals_access_request.html")


def rentals_magic_login(request, token):
    token_obj = MagicLinkToken.objects.filter(token=token).first()
    if not token_obj or not token_obj.is_valid():
        messages.error(request, "This link is invalid or expired. Please request a new one.")
        return redirect("marketplace:rentals_access_request")

    token_obj.used_at = timezone.now()
    token_obj.save()

    # store email in session (simple + clean)
    request.session["rentals_email"] = token_obj.email
    request.session.set_expiry(60 * 30)  # 30 minutes session

    return redirect("marketplace:rentals_dashboard")


def rentals_dashboard(request):
    email = request.session.get("rentals_email")
    if not email:
        messages.error(request, "Session expired. Please request a new access link.")
        return redirect("marketplace:rentals_access_request")

    rentals = (
        Rental.objects
        .filter(buyer_email__iexact=email)
        .select_related("product", "hosting_plan")
        .prefetch_related("invoices")
        .order_by("-created_at")
    )

    # Auto-mark expired rentals (keeps UI truthful)
    now = timezone.now()
    for r in rentals:
        if r.status == "active" and r.expires_at and r.expires_at < now:
            r.status = "expired"
            r.save(update_fields=["status"])

    return render(request, "marketplace/rentals_dashboard.html", {
        "rentals": rentals,
        "email": email
    })


# -------------------------
# RENEWALS

def rental_generate_renew_invoice(request, rental_id):
    email = request.session.get("rentals_email")
    if not email:
        messages.error(request, "Session expired. Please request a new access link.")
        return redirect("marketplace:rentals_access_request")

    rental = get_object_or_404(Rental, id=rental_id, buyer_email__iexact=email)

    # Prevent multiple pending invoices
    existing = (
        RentalInvoice.objects
        .filter(rental=rental, status="pending")
        .order_by("-created_at")
        .first()
    )
    if existing:
        messages.info(request, f"You already have a pending invoice (#{existing.id}). Upload receipt to continue.")
        return redirect("marketplace:rental_invoice_upload", invoice_id=existing.id)

    now = timezone.now()

    # Base date:
    # - if rental still active and not expired -> start from expires_at (but avoid overlap)
    # - else -> start from now
    if rental.expires_at and rental.expires_at > now:
        base_dt = rental.expires_at
    else:
        base_dt = now

    # Start on the next day (avoids “double covering” the same day)
    period_start = (base_dt + timedelta(days=1)).date()
    period_end = (base_dt + relativedelta(months=1)).date()  # monthly cycle

    invoice = RentalInvoice.objects.create(
        rental=rental,
        period_start=period_start,
        period_end=period_end,
        amount=rental.hosting_plan.monthly_price,
        status="pending",
    )

    messages.success(request, f"Renewal invoice generated (#{invoice.id}). Upload your receipt to continue.")
    return redirect("marketplace:rental_invoice_upload", invoice_id=invoice.id)

def rental_invoice_upload(request, invoice_id):
    email = request.session.get("rentals_email")
    if not email:
        messages.error(request, "Session expired. Please request a new access link.")
        return redirect("marketplace:rentals_access_request")

    invoice = get_object_or_404(
        RentalInvoice,
        id=invoice_id,
        rental__buyer_email__iexact=email
    )

    if request.method == "POST":
        receipt = request.FILES.get("receipt")
        if not receipt:
            messages.error(request, "Please upload a receipt.")
            return redirect("marketplace:rental_invoice_upload", invoice_id=invoice.id)

        invoice.receipt = receipt
        invoice.status = "pending"
        invoice.save()

        from .emails import send_rental_invoice_pending_emails
        send_rental_invoice_pending_emails(request=request, invoice=invoice)

        messages.success(request, "Receipt submitted. Verification usually takes 1–24 hours.")
        return redirect("marketplace:rentals_dashboard")

    return render(request, "marketplace/rental_invoice_upload.html", {"invoice": invoice})
