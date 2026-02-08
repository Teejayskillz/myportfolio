from django.shortcuts import render
from projects.models import Project 
from django.db.models import Q
from blog.models import Post
from marketplace.models import Product

def home_view(request):
    latest_posts = (
        Post.objects.filter(status='published')
        .order_by('-publish')[:10]
    )

    featured_products = (
        Product.objects.filter(is_active=True)
        .order_by('-id')[:12]
    )

    return render(request, 'pages/home.html', {
        'latest_posts': latest_posts,
        'featured_products': featured_products,
    })

def about_view(request):
    """
    REnders the about page
    """
    return render(request, 'pages/about.html')

def home(request):
    # Fetch projects marked as featured (or your preferred logic)
    # Ensure you are fetching enough projects for your desired display (e.g., 3, 6, etc.)
    featured_projects = Project.objects.filter(is_featured=True).order_by('?') # Or .order_by('-created_at')

    # Add the delay attribute to each project
    projects_with_delay = []
    for index, project in enumerate(featured_projects):
        project.aos_delay = index * 150 # Calculate delay: 0, 150, 300, ...
        projects_with_delay.append(project)

    context = {
        'featured_projects': projects_with_delay # Pass the modified list/queryset
    }
    return render(request, 'home.html', context)
