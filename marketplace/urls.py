# marketplace/urls.py
from django.urls import path
from . import views

app_name = 'marketplace'

urlpatterns = [
    path('', views.product_list, name='product_list'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),

    # Checkout steps
    path('checkout/<slug:slug>/options/', views.checkout_options, name='checkout_options'),
    path('checkout/details/', views.checkout_details, name='checkout_details'),
    path('checkout/payment/', views.checkout_payment, name='checkout_payment'),
]
