import uuid
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import HttpResponse, Http404
import os
from django.utils import timezone
from .forms import ReceiptUploadForm

from .models import (
    Product,
    HostingPlan,
    SourceCodeOption,
    PurchaseRequest
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
                amount += hosting_plan.price_per_month

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
        'product': checkout['product_id'] 

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
                amount=checkout['amount'],
                receipt=form.cleaned_data['receipt'],
                status='pending'  # Default status
            )

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

    file_path = download_token.license.purchase.product.product_file.path
    file_name = os.path.basename(file_path)

    response = HttpResponse(open(file_path, 'rb'), content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{file_name}"'
    return response
