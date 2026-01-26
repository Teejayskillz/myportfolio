from django.shortcuts import render, get_object_or_404, redirect
from .forms import CheckoutForm
from django.contrib import messages
from .models import Product, Order, PaymentGateway, DownloadToken
import requests
import time
from django.core.mail import EmailMessage
from django.conf import settings
from django.http import HttpResponse, Http404
from django.urls import reverse
import os
from django.views.decorators.csrf import csrf_exempt



def product_list(request):
    products = Product.objects.filter(is_active=True)
    return render(request, "marketplace/product_list.html", {"products": products})


def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    return render(request, "marketplace/product_detail.html", {"product": product})

def checkout_view(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    active_gateways = PaymentGateway.objects.filter(is_active=True)

    if request.method == 'POST':
        form = CheckoutForm(request.POST)

        if form.is_valid():
            selected_gateway_name = request.POST.get('gateway')

            if not selected_gateway_name:
                messages.error(request, "Please select a payment method.")
                return render(request, 'marketplace/checkout.html', {
                    'product': product,
                    'form': form,
                    'active_gateways': active_gateways,
                })

            gateway = active_gateways.filter(name=selected_gateway_name).first()
            if not gateway:
                messages.error(request, "Selected payment method is not available.")
                return render(request, 'marketplace/checkout.html', {
                    'product': product,
                    'form': form,
                    'active_gateways': active_gateways,
                })

            order = Order.objects.create(
                product=product,
                buyer_name=form.cleaned_data['buyer_name'],
                buyer_email=form.cleaned_data['buyer_email'],
                amount=product.price,
                payment_status='pending',
                gateway_name=gateway.name,
            )

            request.session['order_id'] = order.id
            messages.success(request, f"Thank you {order.buyer_name}! Proceeding to payment...")
            return redirect('marketplace:payment_page', order_id=order.id)  # <-- FIXED

        messages.error(request, "Please correct the errors below.")

    else:
        form = CheckoutForm()

    return render(request, 'marketplace/checkout.html', {
        'product': product,
        'form': form,
        'active_gateways': active_gateways,
    })


def payment_page(request, order_id):
    order = get_object_or_404(Order, id=order_id, payment_status='pending')
    gateway = get_object_or_404(
        PaymentGateway,
        name=order.gateway_name,
        is_active=True
    )

    if request.method == 'POST':
        reference = f"order-{order.id}-{int(time.time())}"

        payload = {
            "email": order.buyer_email,
            "amount": int(order.amount * 100),
            "reference": reference,
            "callback_url": request.build_absolute_uri(
                reverse('marketplace:payment_callback')
            ),
            "metadata": {
                "order_id": order.id,
                "product": order.product.title,
            },
        }

        headers = {
            "Authorization": f"Bearer {gateway.secret_key}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            "https://api.paystack.co/transaction/initialize",
            json=payload,
            headers=headers,
            timeout=30
        )

        if response.status_code != 200:
            messages.error(request, "Paystack server error.")
            return redirect('marketplace:checkout', slug=order.product.slug)

        resp_data = response.json()

        if resp_data.get("status"):
            order.reference = reference
            order.save(update_fields=['reference'])
            return redirect(resp_data["data"]["authorization_url"])

        messages.error(
            request,
            resp_data.get("message", "Payment initialization failed.")
        )

    return render(request, 'marketplace/payment.html', {
        'order': order,
        'gateway': gateway,
    })


def payment_callback(request):
    reference = request.GET.get('reference') or request.GET.get('trxref')
    if not reference:
        messages.error(request, "Invalid payment reference.")
        return redirect('marketplace:product_list')

    # 🔐 Verify payment with Paystack FIRST
    gateway = PaymentGateway.objects.filter(
        name='paystack',
        is_active=True
    ).first()

    if not gateway:
        messages.error(request, "Payment gateway not configured.")
        return redirect('marketplace:product_list')

    headers = {
        "Authorization": f"Bearer {gateway.secret_key}",
    }

    verify_url = f"https://api.paystack.co/transaction/verify/{reference}"
    response = requests.get(verify_url, headers=headers, timeout=20)

    if response.status_code != 200:
        messages.error(request, "Unable to verify payment.")
        return redirect('marketplace:product_list')

    resp_data = response.json()
    if not resp_data.get("status"):
        messages.error(request, "Verification failed.")
        return redirect('marketplace:product_list')

    data = resp_data["data"]
    metadata = data.get("metadata", {})

    order_id = metadata.get("order_id")
    if not order_id:
        messages.error(request, "Order metadata missing.")
        return redirect('marketplace:product_list')

    order = get_object_or_404(Order, id=order_id)

    # 🔐 CRITICAL: Reference must match
    if order.reference != reference:
        messages.error(request, "Payment reference mismatch.")
        return redirect('marketplace:product_list')

    # ✅ Final validation
    if (
        data["status"] == "success"
        and int(data["amount"]) == int(order.amount * 100)
    ):
        if order.payment_status != 'paid':
            order.payment_status = 'paid'
            order.save(update_fields=['payment_status'])

        request.session.pop('order_id', None)
        return redirect('marketplace:payment_success', order_id=order.id)

    order.payment_status = 'failed'
    order.save(update_fields=['payment_status'])
    messages.error(request, "Payment failed.")
    return redirect('marketplace:checkout', slug=order.product.slug)

@csrf_exempt
def paystack_webhook(request):
    signature = request.headers.get('x-paystack-signature')
    computed_signature = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode(),
        request.body,
        hashlib.sha512
    ).hexdigest()

    if signature != computed_signature:
        return HttpResponse(status=400)

    payload = json.loads(request.body)
    event = payload.get('event')
    data = payload.get('data', {})

    if event == 'charge.success':
        reference = data.get('reference')

        try:
            order = Order.objects.get(reference=reference)

            # ✅ Idempotent update (safe if webhook fires twice)
            if order.payment_status != 'paid':
                order.payment_status = 'paid'
                order.save(update_fields=['payment_status'])

        except Order.DoesNotExist:
            pass

    return HttpResponse(status=200)

def payment_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, payment_status='paid')
    token, _ = DownloadToken.objects.get_or_create(order=order)

    download_url = request.build_absolute_uri(
        reverse('marketplace:download_product', kwargs={'token': str(token.token)})
    )

    try:
        EmailMessage(
            subject=f"Your Purchase: {order.product.title}",
            body=f"Download your product here:\n\n{download_url}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[order.buyer_email],
        ).send()
    except Exception as e:
        messages.error(request, f"Email failed: {e}")

    return render(request, 'marketplace/success.html', {"order": order})

def download_product(request, token):
    download_token = get_object_or_404(DownloadToken, token=token)

    if not download_token.is_valid():
        raise Http404("Invalid or expired download link.")

    download_token.increment_use()
    file_path = download_token.order.product.file.path
    file_name = os.path.basename(file_path)

    response = HttpResponse()
    response['Content-Disposition'] = f'attachment; filename="{file_name}"'
    response['X-Sendfile'] = file_path

    if not settings.DEBUG:
        return response

    with open(file_path, 'rb') as f:
        stream_response = HttpResponse(
            f.read(),
            content_type='application/octet-stream'
        )
        stream_response['Content-Disposition'] = f'attachment; filename="{file_name}"'
        return stream_response
