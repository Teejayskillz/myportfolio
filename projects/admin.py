from django.contrib import admin
from .models import Project

# Register your models here.

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'description', 'technologies' , 'github_url', 'live_demo_url' )
    search_fields = ('title', 'description', 'technologies')

    