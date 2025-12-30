from django.urls import path
from . import views

app_name = "marketplace"

urlpatterns = [
    path("", views.product_list, name="product_list"),
    path("checkout/<slug:slug>/", views.checkout_view, name="checkout"),
    path('payment/', views.payment_page, name='payment_page'),
    path("<slug:slug>/", views.product_detail, name="product_detail"),
    path('payment/callback/', views.payment_callback, name='payment_callback'),
    path('download/<uuid:token>/', views.download_product, name='download_product'),
]
    