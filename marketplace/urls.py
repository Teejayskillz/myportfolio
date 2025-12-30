from django.urls import path
from . import views

app_name = "marketplace"

urlpatterns = [
    path("", views.product_list, name="product_list"),
    path("<slug:slug>/", views.product_detail, name="product_detail"),
    path("checkout/<slug:slug>/", views.checkout_view, name="checkout"),
    path('checkout/<int:product_id>/', views.checkout_view, name='checkout'),
    
]
    