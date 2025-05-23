from django.shortcuts import render

# Create your views here.
def home_view(request):
    """
    Renders homepage
    """

    return render(request, 'pages/home.html')

def about_view(request):
    """
    REnders the about page
    """
    return render(request, 'pages/about.html')
