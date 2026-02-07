from django.contrib import admin
from .models import (
    Product,
    SourceCodeOption,
    HostingPlan,
    PurchaseRequest,
    License,
    DownloadToken,
)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'version', 'is_active', 'created_at')
    prepopulated_fields = {'slug': ('title',)}
    list_filter = ('category', 'is_active')
    search_fields = ('title', 'tech_stack')


@admin.register(SourceCodeOption)
class SourceCodeOptionAdmin(admin.ModelAdmin):
    list_display = ('product', 'price', 'update_duration_months')


@admin.register(HostingPlan)
class HostingPlanAdmin(admin.ModelAdmin):
    list_display = ('product', 'name', 'price_per_month', 'is_active')
    list_filter = ('product', 'is_active')


@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(admin.ModelAdmin):
    list_display = (
        'product',
        'buyer_email',
        'delivery_type',
        'hosting_plan',
        'amount',
        'status',
        'created_at',
    )

    list_filter = ('status', 'delivery_type')
    search_fields = ('buyer_email', 'buyer_name')
    readonly_fields = ('product', 'buyer_email', 'amount', 'created_at')

    fieldsets = (
        ('Customer Info', {
            'fields': ('buyer_name', 'buyer_email')
        }),
        ('Purchase Details', {
            'fields': ('product', 'delivery_type', 'hosting_plan', 'amount')
        }),
        ('Payment', {
            'fields': ('receipt', 'status')
        }),
        ('Admin', {
            'fields': ('admin_note',)
        }),
    )


@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    list_display = ('product', 'license_key', 'expires_at', 'is_active')
    readonly_fields = ('license_key', 'issued_at')


@admin.register(DownloadToken)
class DownloadTokenAdmin(admin.ModelAdmin):
    list_display = ('license', 'download_count', 'max_downloads', 'expires_at')


