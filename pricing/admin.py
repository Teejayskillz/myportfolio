from django.contrib import admin

# Register your models here.
# pricing/admin.py

from .models import PricingPlan

@admin.register(PricingPlan)
class PricingPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'is_premium', 'order', 'button_text')
    list_editable = ('price', 'is_premium', 'order', 'button_text')
    search_fields = ('name',)