# projects/urls.py

from django.urls import path
from . import views

app_name = 'projects' # Namespace for URLs

urlpatterns = [
    path('', views.project_list_view, name='project_list'),
    path('<int:pk>/', views.project_detail_view, name='project_detail'),
]