# blog/urls.py
from django.urls import path
from . import views

app_name = 'blog' # Don't forget the app_name for namespacing!

urlpatterns = [
    # Post list view
    path('', views.post_list, name='post_list'),
    path('category/<slug:category_slug>/', views.post_list, name='post_list_by_category'),
    # Post detail view (using year/month/day/slug for SEO friendly URLs)
    path('<int:year>/<int:month>/<int:day>/<slug:post_slug>/',
         views.post_detail,
         name='post_detail'),
]