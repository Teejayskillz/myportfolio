# marketplace/urls.py
from django.urls import path
from . import views

app_name = 'marketplace'

urlpatterns = [
    path('', views.product_list, name='product_list'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),

    # Checkout steps
    path('checkout/<slug:slug>/buy/', views.buy_now, name='buy_now'),
    path('checkout/<int:purchase_id>/upload-receipt/', views.buy_now_receipt, name='buy_now_receipt'),
    path('checkout/<int:purchase_id>/summary/', views.buy_now_summary, name='buy_now_summary'),
    path('checkout/<slug:slug>/options/', views.checkout_options, name='checkout_options'),
    path('checkout/details/', views.checkout_details, name='checkout_details'),
    path('checkout/payment/', views.checkout_payment, name='checkout_payment'),

    path("rent/<slug:slug>/", views.rent_start, name="rent_start"),
    path("rent/<int:purchase_id>/upload-receipt/", views.rent_receipt, name="rent_receipt"),
    path("rent/<int:purchase_id>/confirmed/", views.rent_confirmed, name="rent_confirmed"),

    # magic link
    path("rentals/access/", views.rentals_access_request, name="rentals_access_request"),
    path("rentals/magic/<str:token>/", views.rentals_magic_login, name="rentals_magic_login"),
    path("rentals/dashboard/", views.rentals_dashboard, name="rentals_dashboard"),

    # renew
    path("rentals/<int:rental_id>/renew/", views.rental_generate_renew_invoice, name="rental_generate_renew_invoice"),
    path("rentals/invoice/<int:invoice_id>/upload/", views.rental_invoice_upload, name="rental_invoice_upload"),
    
    path("download/<str:token>/", views.download_product, name="download_product"),

]

