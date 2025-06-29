from django.contrib import admin
from django.utils.html import format_html # Import format_html for safe HTML rendering
from .models import Project

# Register your models here.

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'display_truncated_description', 'technologies' , 'github_url', 'live_demo_url' )
    search_fields = ('title', 'description', 'technologies')

    # New method to display the description safely and truncated
    def display_truncated_description(self, obj):
        # Truncate the description to, say, 100 characters
        # Ensure that the truncation doesn't break HTML tags in an odd way,
        # though for display purposes in admin, a raw string slice is often sufficient.
        truncated_text = obj.description[:100]
        # Use format_html to mark the string as safe HTML.
        # This will render the HTML tags within the truncated text.
        return format_html(truncated_text)

    # Optional: Set a more user-friendly column header
    display_truncated_description.short_description = 'Description'