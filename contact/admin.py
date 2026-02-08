from django.contrib import admin
from .models import ContactMessage

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("created_at", "name", "email", "project_type", "is_read")
    list_filter = ("is_read", "project_type", "created_at")
    search_fields = ("name", "email", "phone", "message")
    list_editable = ("is_read",)
