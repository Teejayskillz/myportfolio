
from django.shortcuts import render, get_object_or_404, redirect
from .forms import CheckoutForm
from django.contrib import messages
from .models import Product, Order, PaymentGateway




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

    # Get all active payment gateways
    active_gateways = PaymentGateway.objects.filter(is_active=True)

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            buyer_name = form.cleaned_data['buyer_name']
            buyer_email = form.cleaned_data['buyer_email']

            order = Order.objects.create(
                product=product,
                buyer_name=buyer_name,
                buyer_email=buyer_email,
                status='pending'
            )

            # Pass order ID to payment page
            request.session['order_id'] = order.id
            messages.success(request, f'Thank you {buyer_name}, proceed to payment!')
            return redirect('payment_page')  # You can make this dynamic based on selected gateway

    else:
        form = CheckoutForm()

    return render(request, 'marketplace/checkout.html', {
        'product': product,
        'form': form,
        'active_gateways': active_gateways,
    })
