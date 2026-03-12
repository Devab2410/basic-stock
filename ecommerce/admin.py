from django.contrib import admin
from .models import (
    EcommerceCategory, EcommerceBrand, EcommerceProduct, EcommerceProductVariant,
    EcommerceProductImage, EcommerceCustomer, EcommerceOrder, EcommerceOrderItem,
    EcommerceReview
)

@admin.register(EcommerceCategory)
class EcommerceCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'parent', 'is_active')

@admin.register(EcommerceBrand)
class EcommerceBrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'is_active')

class VariantInline(admin.TabularInline):
    model = EcommerceProductVariant
    extra = 1

class ImageInline(admin.TabularInline):
    model = EcommerceProductImage
    extra = 1

@admin.register(EcommerceProduct)
class EcommerceProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'selling_price', 'is_featured', 'is_active')
    list_filter = ('store', 'is_active', 'is_featured')
    search_fields = ('name', 'sku')
    inlines = [VariantInline, ImageInline]

class OrderItemInline(admin.TabularInline):
    model = EcommerceOrderItem
    extra = 0
    readonly_fields = ('subtotal',)

@admin.register(EcommerceOrder)
class EcommerceOrderAdmin(admin.ModelAdmin):
    list_display = ('order_no', 'store', 'customer', 'status', 'payment_status', 'total', 'created_at')
    list_filter = ('store', 'status', 'payment_status')
    search_fields = ('order_no', 'customer__user__username')
    inlines = [OrderItemInline]

@admin.register(EcommerceReview)
class EcommerceReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'customer', 'rating', 'is_approved', 'created_at')
    list_filter = ('store', 'is_approved', 'rating')
