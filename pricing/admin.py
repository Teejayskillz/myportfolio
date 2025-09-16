# pricing/admin.py
from django.contrib import admin
from .models import PricingPlan

@admin.register(PricingPlan)
class PricingPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'is_premium', 'order', 'button_text', 'note')  
    list_editable = ('price', 'is_premium', 'order', 'button_text', 'note')  
    search_fields = ('name', 'note')  
    list_filter = ('is_premium',)  

    fieldsets = (
        (None, {
            'fields': ('name', 'price', 'is_premium', 'order', 'button_text', 'button_url_name')
        }),
        ('Content', {
            'fields': ('features', 'note'),
            'description': "Features (newline separated) and optional note for marketing (e.g. 'Best for enterprises, startups...')"
        }),
    )
