from django.contrib import admin
from django.core.mail import EmailMessage
from django.urls import reverse
from django.conf import settings
from django.utils.html import format_html
from .models import PurchaseRequest, License, DownloadToken
from django.utils import timezone
from datetime import timedelta
import secrets

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


@admin.action(description="Approve & Fulfill Selected Purchases")
def approve_and_fulfill(modeladmin, request, queryset):
    for purchase in queryset.filter(status='pending'):
        purchase.status = 'approved'
        purchase.save(update_fields=['status'])

        # Create License if source code purchased
        if purchase.delivery_type in ['source', 'both']:
            license_obj, created = License.objects.get_or_create(
                purchase=purchase,
                defaults={
                    'product': purchase.product,
                    'expires_at': timezone.now() + timedelta(days=365)
                }
            )

            # Create Download Token
            DownloadToken.objects.get_or_create(
                license=license_obj,
                defaults={
                    'expires_at': timezone.now() + timedelta(days=7),  # token valid for 7 days
                    'max_downloads': 3
                }
            )

            # Send email with license + download link
            token = license_obj.download_token
            download_url = request.build_absolute_uri(
                reverse('marketplace:download_product', kwargs={'token': token.token})
            )

            try:
                EmailMessage(
                    subject=f"Your Purchase: {purchase.product.title}",
                    body=f"Thank you {purchase.buyer_name}!\n\n"
                         f"Your license key: {license_obj.license_key}\n"
                         f"Download your product here: {download_url}\n\n"
                         f"Expires: {license_obj.expires_at.strftime('%Y-%m-%d %H:%M:%S')}",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[purchase.buyer_email]
                ).send()
            except Exception as e:
                # optional: log error
                print(f"Email failed for {purchase.buyer_email}: {e}")


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

    actions = [approve_and_fulfill]

    fieldsets = (
        ('Customer Info', {
            'fields': ('buyer_name', 'buyer_email', 'whatsapp_number')
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


