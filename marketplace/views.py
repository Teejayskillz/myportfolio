
from django.shortcuts import render, get_object_or_404, redirect
from .forms import CheckoutForm
from django.contrib import messages
from .models import Product, Order, PaymentGateway,DownloadToken
import requests
import time
from django.contrib import messages
from django.core.mail import EmailMessage
from django.conf import settings
from django.http import HttpResponse, Http404
from django.core.serving import sendfile  # For efficient large file serving (optional)
import reverse

def product_list(request):
    products = Product.objects.filter(is_active=True)

    context = {
        "products": products
    }

    return render(request, "marketplace/product_list.html", context)


def product_detail(request, slug):
    product = get_object_or_404(
        Product,
        slug=slug,
        is_active=True
    )

    context = {
        "product": product
    }

    return render(request, "marketplace/product_detail.html", context)



def checkout_view(request, slug):
    product = get_object_or_404(
        Product,
        slug=slug,
        is_active=True
    )

    # Get all currently active payment gateways
    active_gateways = PaymentGateway.objects.filter(is_active=True)

    if request.method == 'POST':
        form = CheckoutForm(request.POST)

        if form.is_valid():
            # Get selected gateway from form (very important!)
            selected_gateway_name = request.POST.get('gateway')

            if not selected_gateway_name:
                messages.error(request, "Please select a payment method.")
                # Re-render form with error (don't lose user input)
                return render(request, 'marketplace/checkout.html', {
                    'product': product,
                    'form': form,
                    'active_gateways': active_gateways,
                    'selected_gateway': selected_gateway_name,  # keep selection
                })

            if not active_gateways.filter(name=selected_gateway_name).exists():
                messages.error(request, "Selected payment method is not available.")
                return render(request, 'marketplace/checkout.html', {
                    'product': product,
                    'form': form,
                    'active_gateways': active_gateways,
                })

            # Create the order
            order = Order.objects.create(
                product=product,
                buyer_name=form.cleaned_data['buyer_name'],
                buyer_email=form.cleaned_data['buyer_email'],
                status='pending',
                # Important: store price at time of purchase (protect against price changes)
                amount=product.price,  # ← make sure Product has price field!
            )

            # Store critical data in session
            request.session['order_id'] = order.id
            request.session['selected_gateway'] = selected_gateway_name
            request.session.modified = True  # Ensure session is saved

            messages.success(
                request,
                f"Thank you {order.buyer_name}! Proceeding to payment..."
            )

            # Use correct named URL with namespace
            return redirect('marketplace:payment_page')

        # If form invalid → show errors
        else:
            messages.error(request, "Please correct the errors below.")

    else:
        form = CheckoutForm()

    return render(request, 'marketplace/checkout.html', {
        'product': product,
        'form': form,
        'active_gateways': active_gateways,
    })


def payment_page(request):
    """
    Initiates a Paystack payment:
    1. Retrieves pending order from session
    2. Gets selected gateway from session
    3. Calls Paystack Initialize Transaction API
    4. Redirects user to Paystack checkout page on success
    5. Shows error page if anything fails
    """
    # 1. Get order from session
    order_id = request.session.get('order_id')
    if not order_id:
        messages.error(request, "No active order found. Please start checkout again.")
        return redirect('marketplace_home')  # or your home/product list

    order = get_object_or_404(Order, id=order_id, status='pending')

    # 2. Get selected gateway from session (set in checkout_view)
    gateway_name = request.session.get('selected_gateway')
    if not gateway_name:
        messages.error(request, "No payment method was selected. Please try again.")
        return redirect('marketplace:checkout', slug=order.product.slug)

    gateway = get_object_or_404(PaymentGateway, name=gateway_name, is_active=True)

    # 3. Prepare Paystack payload
    # IMPORTANT REQUIREMENTS:
    # - amount must be in **kobo** (NGN * 100) → e.g. ₦5000 = 500000
    # - Make sure Order has 'amount' field (or use product.price)
    # - Reference should be unique (we use order.id + timestamp)
    payload = {
        "email": order.buyer_email,
        "amount": int(order.amount * 100),  # Convert to kobo (required!)
        "reference": f"order-{order.id}-{int(time.time())}",  # unique ref
        "currency": "NGN",  # change if using other supported currency
        "callback_url": request.build_absolute_uri(
            reverse('marketplace:payment_callback')
        ),
        "metadata": {
            "order_id": str(order.id),
            "product": order.product.title,
            # You can add more custom data here if needed
        },
        # Optional but recommended fields:
        # "channels": ["card", "bank", "ussd", "qr", "mobile_money"],
        # "bearer": "subaccount"  # or "account" depending on your setup
    }

    headers = {
        "Authorization": f"Bearer {gateway.secret_key}",
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
    }

    # 4. Send request to Paystack
    try:
        response = requests.post(
            "https://api.paystack.co/transaction/initialize",
            json=payload,
            headers=headers,
            timeout=30
        )

        resp_data = response.json()

        if resp_data.get("status") is True:  # Paystack uses True for success
            payment_url = resp_data["data"]["authorization_url"]
            
            # Optional: store reference for easier verification later
            order.transaction_ref = payload["reference"]
            order.save(update_fields=['transaction_ref'])

            return redirect(payment_url)

        else:
            error_message = resp_data.get('message', 'Payment initiation failed')
            messages.error(request, f"Paystack error: {error_message}")

    except requests.exceptions.RequestException as e:
        messages.error(request, f"Could not connect to Paystack: {str(e)}")
    except Exception as e:
        messages.error(request, f"Unexpected error: {str(e)}")

    # 5. Fallback: show error in template if initiation fails
    return render(request, 'marketplace/payment.html', {
        'order': order,
        'gateway': gateway,
        'error_message': "We couldn't start the payment process. Please try again or choose another method."
    })

def payment_callback(request):
    """
    Paystack Callback Handler:
    - Paystack redirects user here after payment attempt
    - We receive reference in GET params
    - We MUST verify the transaction with Paystack API
    - Update order only if verification passes
    """
    # 1. Get the reference from Paystack callback
    reference = request.GET.get('reference') or request.GET.get('trxref')

    if not reference:
        messages.error(request, "Invalid payment response. No reference found.")
        return redirect('marketplace_home')  # or your fallback page

    # 2. We need to find the order using the reference
    #    (assuming you saved transaction_ref during payment initiation)
    order = Order.objects.filter(transaction_ref=reference).first()

    if not order:
        messages.error(request, "Order not found for this payment reference.")
        return redirect('marketplace_home')

    # 3. Get the gateway used for this order
    #    (We assume gateway_name was saved or we can get it from session/product)
    gateway_name = request.session.get('selected_gateway') or order.gateway_name  # adjust based on your model

    if not gateway_name:
        # Fallback: if you don't store it, get first active or raise error
        gateway = PaymentGateway.objects.filter(is_active=True).first()
        if not gateway:
            messages.error(request, "Payment gateway configuration missing.")
            return redirect('marketplace:checkout', slug=order.product.slug)
    else:
        gateway = get_object_or_404(PaymentGateway, name=gateway_name, is_active=True)

    # 4. Verify transaction with Paystack
    headers = {
        "Authorization": f"Bearer {gateway.secret_key}",
        "Cache-Control": "no-cache",
    }

    verify_url = f"https://api.paystack.co/transaction/verify/{reference}"

    try:
        response = requests.get(verify_url, headers=headers, timeout=15)
        resp_data = response.json()

        if resp_data.get("status") is True:
            transaction = resp_data["data"]

            # Important checks
            if (transaction["status"] == "success" and
                int(transaction["amount"]) == int(order.amount * 100) and  # in kobo
                transaction["currency"] == "NGN"):  # add more checks if needed

                # Payment is valid → update order
                order.status = 'paid'
                order.transaction_status = 'success'  # optional extra field
                order.save(update_fields=['status', 'transaction_status'])

                # Clear session
                for key in ['order_id', 'selected_gateway']:
                    request.session.pop(key, None)

                messages.success(request, "Payment verified successfully! Thank you.")
                return redirect('marketplace:payment_success', order_id=order.id)

            else:
                # Suspicious - amount/currency mismatch
                order.status = 'failed'  # or 'suspicious'
                order.save(update_fields=['status'])
                messages.error(request, "Payment verification failed (mismatch).")

        else:
            messages.error(request, f"Payment verification failed: {resp_data.get('message', 'Unknown error')}")

    except requests.exceptions.RequestException as e:
        messages.error(request, f"Could not verify payment: Network error - {str(e)}")
    except Exception as e:
        messages.error(request, f"Verification error: {str(e)}")

    # Default fallback - payment failed/cancelled/not verified
    order.status = 'failed'
    order.save(update_fields=['status'])

    return redirect('marketplace:checkout', slug=order.product.slug)


def payment_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, status='paid')

    # Create download token if not exists
    token, created = DownloadToken.objects.get_or_create(order=order)

    # Generate download URL
    download_url = request.build_absolute_uri(
        reverse('marketplace:download_product', kwargs={'token': str(token.token)})
    )

    # SEO & Site Promotion Links
    site_url = "https://yourwebsite.com" # Replace with your actual SEO site link
    
    # Send email with download link
    try:
        subject = f"Your Purchase: {order.product.title}"
        body = (
            f"Dear {order.buyer_name},\n\n"
            f"Thank you for your purchase! Your digital product is ready.\n\n"
            f"Download here: {download_url}\n\n"
            f"This link expires on {token.expiration.strftime('%Y-%m-%d %H:%M')} UTC.\n"
            f"You can download up to {token.max_uses} times.\n\n"
            f"For more high-quality products, visit our main site: {site_url}\n\n"
            f"Best regards,\nYour Marketplace Team"
        )
        
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[order.buyer_email],
        )
        email.content_subtype = 'html'
        email.send(fail_silently=False)
        messages.success(request, "Email sent with download instructions!")
        
    except Exception as e:
        messages.error(request, f"Email sending failed: {str(e)}. Please contact support.")

    return render(request, 'marketplace/success.html', {
        'order': order,
        'seo_tags': 'digital download, marketplace, secure payment, ' + order.product.title # SEO Tags
    })


def download_product(request, token):
    download_token = get_object_or_404(DownloadToken, token=token)

    if not download_token.is_valid():
        raise Http404("Invalid or expired download link.")

    # Increment use count
    download_token.increment_use()

    # Serve the file (assuming Product has a FileField named 'file')
    file_path = download_token.order.product.file.path

    # Simple streaming response (for small files)
    response = HttpResponse(content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{download_token.order.product.file.name}"'
    with open(file_path, 'rb') as f:
        response.write(f.read())

    # OR for large files: Use sendfile with Nginx/Apache
    # return sendfile(request, file_path, attachment=True)

    return response