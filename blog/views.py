
from django.shortcuts import render, get_object_or_404
from .models import Post, Category
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

def post_list(request, category_slug=None):
    object_list = Post.objects.filter(status='published')
    category = None
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        object_list = object_list.filter(categories=category)

    for i, post in enumerate(object_list):
        post.aos_delay = i * 100 # Calculate delay: 0, 100, 200, etc.    

    paginator = Paginator(object_list, 5) # 5 posts per page
    page = request.GET.get('page')
    try:
        posts = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer deliver first page
        posts = paginator.page(1)
    except EmptyPage:
        # If page is out of range deliver last page of results
        posts = paginator.page(paginator.num_pages)

    all_categories = Category.objects.all() # For sidebar/filter
    return render(request,
                  'blog/post_list.html',
                  {'page': page,
                   'posts': posts,
                   'category': category,
                   'all_categories': all_categories})

def post_detail(request, year, month, day, post_slug):
    post = get_object_or_404(Post, slug=post_slug,
                             status='published',
                             publish__year=year,
                             publish__month=month,
                             publish__day=day)
    return render(request,
                  'blog/post_detail.html',
                  {'post': post})