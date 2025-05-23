# pages/urls.py

from django.urls import path
from . import views

app_name = 'pages' # Namespace for URLs

urlpatterns = [
    path('', views.home_view, name='home'),
    path('about/', views.about_view, name='about'),
]