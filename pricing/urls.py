# pricing/urls.py
from django.urls import path
from . import views

app_name = 'pricing'

urlpatterns = [
    path('', views.pricing_page_view, name='pricing_page'),
]