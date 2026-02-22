import uuid
import os
from decimal import Decimal
from datetime import timedelta, date

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import HttpResponse, Http404, HttpResponseBadRequest
from django.utils import timezone
from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.views.decorators.csrf import csrf_exempt

from dateutil.relativedelta import relativedelta
import requests
import hmac
import hashlib
import json

from .models import (
    Product,
    HostingPlan,
    PurchaseRequest,
    DownloadToken,
    Rental,
    RentalInvoice,
    MagicLinkToken,
    PaymentTransaction,
)
from .forms import (
    CheckoutOptionsForm,
    BuyerDetailsForm,
    ReceiptUploadForm
)
from .emails import send_purchase_pending_emails, send_rental_invoice_pending_emails
from .services import fulfill_purchase, fulfill_invoice


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

    if request.method == "POST":
        form = CheckoutOptionsForm(request.POST, product=product)

        if form.is_valid():
            delivery_type = form.cleaned_data["delivery_type"]  # full_ownership | rent_own
            hosting_plan = form.cleaned_data.get("hosting_plan")

            # 🔐 SERVER-SIDE PRICE CALCULATION
            if delivery_type == "rent_own":
                if not hosting_plan:
                    messages.error(request, "Please select a hosting plan.")
                    return redirect(request.path)

                amount = (product.rental_setup_fee or Decimal("0.00")) + hosting_plan.monthly_price

            elif delivery_type == "full_ownership":
                amount = product.price_full_ownership
                hosting_plan = None  # safety: ownership shouldn't carry a plan

            else:
                messages.error(request, "Invalid option selected.")
                return redirect(request.path)

            checkout_id = str(uuid.uuid4())

            checkouts = request.session.get("checkouts", {})
            checkouts[checkout_id] = {
                "product_id": product.id,
                "delivery_type": delivery_type,
                "hosting_plan_id": hosting_plan.id if hosting_plan else None,
                "amount": str(amount),
                "buyer": {},
            }

            request.session["checkouts"] = checkouts
            return redirect("marketplace:checkout_details", checkout_id=checkout_id)

    else:
        form = CheckoutOptionsForm(product=product)

    return render(request, "marketplace/checkout/options.html", {
        "product": product,
        "form": form,
        "step": 1
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
                'note': form.cleaned_data.get('note', ''),

                # ✅ domain fields (new)
                'domain_option': form.cleaned_data.get('domain_option', 'none'),
                'domain_name': (form.cleaned_data.get('domain_name') or '').strip().lower(),
            }
            checkouts[checkout_id] = checkout
            request.session['checkouts'] = checkouts
            return redirect('marketplace:checkout_summary', checkout_id=checkout_id)

    else:
        # ✅ prefill if user goes back
        initial = {}
        buyer = checkout.get('buyer') or {}
        if buyer:
            initial = {
                'buyer_name': buyer.get('name', ''),
                'buyer_email': buyer.get('email', ''),
                'whatsapp_number': buyer.get('whatsapp', ''),
                'note': buyer.get('note', ''),
                'domain_option': buyer.get('domain_option', 'none'),
                'domain_name': buyer.get('domain_name', ''),
            }
        form = BuyerDetailsForm(initial=initial)

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

    product = Product.objects.get(id=checkout['product_id'])

    hosting_plan = None
    if checkout.get('hosting_plan_id'):
        hosting_plan = HostingPlan.objects.get(id=checkout['hosting_plan_id'])

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
    checkouts = request.session.get('checkouts', {})
    checkout = checkouts.get(checkout_id)

    if not checkout:
        messages.error(request, "Checkout session expired.")
        return redirect('marketplace:product_list')

    product = get_object_or_404(Product, id=checkout['product_id'])

    hosting_plan = None
    if checkout.get('hosting_plan_id'):
        hosting_plan = get_object_or_404(HostingPlan, id=checkout['hosting_plan_id'])

    if request.method == 'POST':
        form = ReceiptUploadForm(request.POST, request.FILES)
        if form.is_valid():
            buyer = checkout.get('buyer') or {}

            purchase = PurchaseRequest.objects.create(
                product=product,
                hosting_plan=hosting_plan,
                delivery_type=checkout['delivery_type'],  # full_ownership | rent_own
                buyer_name=buyer.get('name', ''),
                buyer_email=buyer.get('email', ''),
                whatsapp_number=buyer.get('whatsapp', ''),

                # ✅ domain fields (new)
                domain_option=buyer.get('domain_option', 'none'),
                domain_name=(buyer.get('domain_name') or '').strip().lower(),

                # NOTE: only keep this if your model has it
                domain_status="unchecked",

                amount=Decimal(checkout['amount']),
                receipt=form.cleaned_data['receipt'],
                status='pending'
            )

            send_purchase_pending_emails(request=request, purchase=purchase)

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
        'step': 3
    })


def download_product(request, token):
    download_token = get_object_or_404(DownloadToken, token=token)

    if download_token.download_count >= download_token.max_downloads:
        raise Http404("Download limit reached.")

    if timezone.now() > download_token.expires_at:
        raise Http404("Download link expired.")

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
            request.session['buy_now'] = {
                'product_id': product.id,
                'buyer_name': form.cleaned_data['buyer_name'],
                'buyer_email': form.cleaned_data['buyer_email'],
                'whatsapp_number': form.cleaned_data['whatsapp_number'],

                # ✅ domain fields (new)
                'domain_option': form.cleaned_data.get('domain_option', 'none'),
                'domain_name': (form.cleaned_data.get('domain_name') or '').strip().lower(),

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
            purchase = PurchaseRequest.objects.create(
                product=product,
                delivery_type='full_ownership',
                buyer_name=session_data['buyer_name'],
                buyer_email=session_data['buyer_email'],
                whatsapp_number=session_data['whatsapp_number'],

                # ✅ domain fields (new)
                domain_option=session_data.get('domain_option', 'none'),
                domain_name=(session_data.get('domain_name') or '').strip().lower(),

                # NOTE: only keep this if your model has it
                domain_status="unchecked",

                amount=Decimal(session_data['amount']),
                receipt=form.cleaned_data['receipt'],
                status='pending'
            )

            send_purchase_pending_emails(request=request, purchase=purchase)

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

        # ✅ Domain fields (new)
        domain_option = (request.POST.get("domain_option") or "none").strip()
        domain_name = (request.POST.get("domain_name") or "").strip().lower()

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

        # ✅ Validate domain only when needed
        if domain_option in ("have_domain", "need_domain") and not domain_name:
            messages.error(request, "Please enter your domain name.")
            return redirect("marketplace:rent_start", slug=product.slug)

        amount = (product.rental_setup_fee or Decimal("0.00")) + plan.monthly_price

        purchase = PurchaseRequest.objects.create(
            product=product,
            hosting_plan=plan,
            delivery_type="rent_own",
            buyer_name=buyer_name,
            buyer_email=buyer_email,
            whatsapp_number=whatsapp_number,
            amount=amount,
            status="pending",

            # ✅ Save domain choice
            domain_option=domain_option,
            domain_name=domain_name,

            # NOTE: only keep this if your model has it
            domain_status="unchecked",
        )

        return redirect("marketplace:rent_receipt", purchase_id=purchase.id)

    return render(request, "marketplace/rent_start.html", {
        "product": product,
        "plans": plans,
        "setup_fee": product.rental_setup_fee,
    })


def rent_receipt(request, purchase_id):
    purchase = get_object_or_404(PurchaseRequest, id=purchase_id, delivery_type="rent_own")

    if request.method == "POST":
        receipt = request.FILES.get("receipt")
        if not receipt:
            messages.error(request, "Please upload a receipt.")
            return redirect("marketplace:rent_receipt", purchase_id=purchase.id)

        purchase.receipt = receipt
        purchase.status = "pending"
        purchase.save()

        send_purchase_pending_emails(request=request, purchase=purchase)

        return redirect("marketplace:rent_confirmed", purchase_id=purchase.id)

    return render(request, "marketplace/rent_receipt.html", {"purchase": purchase})


def rent_confirmed(request, purchase_id):
    purchase = get_object_or_404(PurchaseRequest, id=purchase_id, delivery_type="rent_own")
    return render(request, "marketplace/rent_confirmed.html", {"purchase": purchase})


# -------------------------
# MAGIC LINK ACCESS
# -------------------------
def rentals_access_request(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()

        has_rentals = Rental.objects.filter(buyer_email__iexact=email).exists()

        if has_rentals:
            token_obj = MagicLinkToken.objects.create(
                email=email,
                expires_at=timezone.now() + timedelta(minutes=15),
            )
            link = request.build_absolute_uri(
                reverse("marketplace:rentals_magic_login", args=[token_obj.token])
            )

            send_mail(
                subject="Your Rentals Access Link",
                message=f"Use this link to access your rentals (expires in 15 minutes):\n\n{link}",
                from_email=None,  # uses DEFAULT_FROM_EMAIL
                recipient_list=[email],
                fail_silently=False,
            )

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

    request.session["rentals_email"] = token_obj.email
    request.session.set_expiry(60 * 30)

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
# -------------------------
def rental_generate_renew_invoice(request, rental_id):
    email = request.session.get("rentals_email")
    if not email:
        messages.error(request, "Session expired. Please request a new access link.")
        return redirect("marketplace:rentals_access_request")

    rental = get_object_or_404(Rental, id=rental_id, buyer_email__iexact=email)

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
    base_dt = rental.expires_at if rental.expires_at and rental.expires_at > now else now

    period_start = (base_dt + timedelta(days=1)).date()
    period_end = (base_dt + relativedelta(months=1)).date()

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

        send_rental_invoice_pending_emails(request=request, invoice=invoice)

        messages.success(request, "Receipt submitted. Verification usually takes 1–24 hours.")
        return redirect("marketplace:rentals_dashboard")

    return render(request, "marketplace/rental_invoice_upload.html", {"invoice": invoice})


def _paystack_init(*, email, amount_naira, reference, callback_url):
    url = "https://api.paystack.co/transaction/initialize"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "email": email,
        "amount": int(amount_naira * 100),
        "reference": reference,
        "callback_url": callback_url,
    }

    r = requests.post(url, json=payload, headers=headers, timeout=30)
    return r.json()


def paystack_start_purchase(request, purchase_id):
    purchase = get_object_or_404(PurchaseRequest, id=purchase_id)

    if purchase.status == "approved":
        return redirect("marketplace:product_list")

    reference = f"PR-{purchase.id}-{uuid.uuid4().hex[:10]}"

    tx = PaymentTransaction.objects.create(
        reference=reference,
        email=purchase.buyer_email,
        amount=purchase.amount,
        content_type=ContentType.objects.get_for_model(PurchaseRequest),
        object_id=purchase.id,
        status="pending",
    )

    callback_url = request.build_absolute_uri(reverse("marketplace:paystack_callback"))

    res = _paystack_init(
        email=purchase.buyer_email,
        amount_naira=purchase.amount,
        reference=reference,
        callback_url=callback_url,
    )

    if not res.get("status"):
        tx.status = "failed"
        tx.paystack_payload = res
        tx.save(update_fields=["status", "paystack_payload"])
        return HttpResponseBadRequest("Unable to initialize payment.")

    tx.paystack_payload = res
    tx.save(update_fields=["paystack_payload"])

    return redirect(res["data"]["authorization_url"])


def paystack_start_invoice(request, invoice_id):
    invoice = get_object_or_404(RentalInvoice, id=invoice_id)

    if invoice.status == "approved":
        return redirect("marketplace:rentals_dashboard")

    reference = f"INV-{invoice.id}-{uuid.uuid4().hex[:10]}"

    tx = PaymentTransaction.objects.create(
        reference=reference,
        email=invoice.rental.buyer_email,
        amount=invoice.amount,
        content_type=ContentType.objects.get_for_model(RentalInvoice),
        object_id=invoice.id,
        status="pending",
    )

    callback_url = request.build_absolute_uri(reverse("marketplace:paystack_callback"))

    res = _paystack_init(
        email=invoice.rental.buyer_email,
        amount_naira=invoice.amount,
        reference=reference,
        callback_url=callback_url,
    )

    if not res.get("status"):
        tx.status = "failed"
        tx.paystack_payload = res
        tx.save(update_fields=["status", "paystack_payload"])
        return HttpResponseBadRequest("Unable to initialize payment.")

    tx.paystack_payload = res
    tx.save(update_fields=["paystack_payload"])

    return redirect(res["data"]["authorization_url"])


def paystack_callback(request):
    return redirect("marketplace:product_list")


def _paystack_verify(reference: str):
    url = f"https://api.paystack.co/transaction/verify/{reference}"
    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
    r = requests.get(url, headers=headers, timeout=30)
    return r.json()


@csrf_exempt
def paystack_webhook(request):
    signature = request.headers.get("x-paystack-signature")
    if not signature:
        return HttpResponse(status=400)

    body = request.body
    computed = hmac.new(
        key=settings.PAYSTACK_SECRET_KEY.encode(),
        msg=body,
        digestmod=hashlib.sha512
    ).hexdigest()

    if not hmac.compare_digest(computed, signature):
        return HttpResponse(status=401)

    event = json.loads(body.decode("utf-8"))
    event_type = event.get("event")
    data = event.get("data", {})
    reference = data.get("reference")

    if not reference:
        return HttpResponse(status=400)

    if event_type not in ("charge.success",):
        return HttpResponse(status=200)

    tx = PaymentTransaction.objects.filter(reference=reference).select_related("content_type").first()
    if not tx:
        return HttpResponse(status=200)

    if tx.status == "success":
        return HttpResponse(status=200)

    verify = _paystack_verify(reference)
    if not verify.get("status"):
        return HttpResponse(status=200)

    vdata = verify.get("data", {})
    if vdata.get("status") != "success":
        tx.status = "failed"
        tx.paystack_payload = verify
        tx.save(update_fields=["status", "paystack_payload"])
        return HttpResponse(status=200)

    paid_amount_kobo = int(vdata.get("amount", 0))
    paid_amount_naira = paid_amount_kobo / 100

    if float(tx.amount) != float(paid_amount_naira):
        tx.status = "failed"
        tx.paystack_payload = verify
        tx.save(update_fields=["status", "paystack_payload"])
        return HttpResponse(status=200)

    tx.status = "success"
    tx.paid_at = timezone.now()
    tx.paystack_payload = verify
    tx.save(update_fields=["status", "paid_at", "paystack_payload"])

    obj = tx.content_object

    if isinstance(obj, PurchaseRequest):
        fulfill_purchase(request=request, purchase=obj)
    elif isinstance(obj, RentalInvoice):
        fulfill_invoice(invoice=obj)

    return HttpResponse(status=200)