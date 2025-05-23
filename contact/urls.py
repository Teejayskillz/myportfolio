# contact/urls.py

from django.urls import path
from . import views

app_name = 'contact' # Namespace for URLs

urlpatterns = [
    path('', views.contact_view, name='contact_page'), # Maps '/' (within the contact app's scope) to contact_view.
]