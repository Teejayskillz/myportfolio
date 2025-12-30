from django.contrib import admin
from .models import Product, Order, DownloadToken, PaymentGateway



@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'price', 'is_active', 'created_at')
    prepopulated_fields = {"slug": ("title",)}
    list_filter = ('category', 'is_active')
    search_fields = ('title', 'tech_stack')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('product', 'buyer_name', 'buyer_email', 'amount', 'payment_status', 'created_at')
    list_filter = ('payment_status',)
    search_fields = ('email', 'reference')
    readonly_fields = ('reference', 'created_at')

@admin.register(DownloadToken)
class DownloadTokenAdmin(admin.ModelAdmin):
    # These names must match the model fields exactly
    list_display = ('order', 'expires_at', 'download_count', 'created_at')
    readonly_fields = ('token', 'created_at')

@admin.register(PaymentGateway)
class PaymentGatewayAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'public_key')
    list_editable = ('is_active',)
