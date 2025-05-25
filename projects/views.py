from django.shortcuts import render, get_object_or_404
from .models import Project 

# Create your views here.

def project_list_view(request):
    """"
    Display a list of projects.
    """
    projects = Project.objects.all()
    context = {
        'projects': projects,
    }
    return render(request, 'projects/project_list.html', context )

def project_detail_view(request, slug): # NOW ACCEPTS 'slug'
    """
    Display details of a single project
    """
    project = get_object_or_404(Project, slug=slug) # NOW QUERIES BY 'slug'
    context = {
        'project': project
    }
    return render(request, 'projects/project_detail.html', context)