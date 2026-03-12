from django.contrib import admin
from .models import (
    PharmacyCategory, PharmacyBrand, PharmacyUnit,
    PharmacyProduct, PharmacyStock, PharmacyStockAdjustment, PharmacyStockTransfer,
    PharmacySupplier, PharmacyCustomer,
    PharmacyPurchase, PharmacyPurchaseItem,
    PharmacySale, PharmacySaleItem, PharmacySaleReturn, PharmacySaleReturnItem
)


@admin.register(PharmacyCategory)
class PharmacyCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'parent', 'is_active')
    list_filter = ('store', 'is_active')
    search_fields = ('name',)


@admin.register(PharmacyBrand)
class PharmacyBrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'is_active')
    list_filter = ('store', 'is_active')


@admin.register(PharmacyUnit)
class PharmacyUnitAdmin(admin.ModelAdmin):
    list_display = ('name', 'short_name', 'store')


@admin.register(PharmacyProduct)
class PharmacyProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'category', 'brand', 'selling_price', 'schedule_type',
                    'requires_prescription', 'is_active')
    list_filter = ('store', 'schedule_type', 'requires_prescription', 'is_active')
    search_fields = ('name', 'barcode', 'sku', 'hsn_code')
    list_select_related = ('store', 'category', 'brand', 'unit')


class PharmacyStockAdjustmentInline(admin.TabularInline):
    model = PharmacyStockAdjustment
    extra = 0
    readonly_fields = ('date',)


@admin.register(PharmacyStock)
class PharmacyStockAdmin(admin.ModelAdmin):
    list_display = ('product', 'store', 'batch_no', 'quantity', 'min_quantity',
                    'expiry_date', 'is_low_stock_display', 'is_expired_display')
    list_filter = ('store',)
    search_fields = ('product__name', 'batch_no')
    inlines = [PharmacyStockAdjustmentInline]

    @admin.display(boolean=True, description='Low Stock')
    def is_low_stock_display(self, obj):
        return obj.is_low_stock

    @admin.display(boolean=True, description='Expired')
    def is_expired_display(self, obj):
        return obj.is_expired


@admin.register(PharmacySupplier)
class PharmacySupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'phone', 'drug_license_no', 'is_active')
    list_filter = ('store', 'is_active')
    search_fields = ('name', 'phone', 'drug_license_no', 'gstin')


@admin.register(PharmacyCustomer)
class PharmacyCustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'store', 'is_active')
    list_filter = ('store', 'is_active')
    search_fields = ('name', 'phone', 'email')


class PurchaseItemInline(admin.TabularInline):
    model = PharmacyPurchaseItem
    extra = 0
    fields = ('product', 'quantity', 'received_qty', 'unit_price', 'tax_rate', 'batch_no', 'expiry_date', 'subtotal')
    readonly_fields = ('subtotal',)


@admin.register(PharmacyPurchase)
class PharmacyPurchaseAdmin(admin.ModelAdmin):
    list_display = ('purchase_no', 'store', 'supplier', 'purchase_date', 'total', 'status')
    list_filter = ('store', 'status')
    search_fields = ('purchase_no', 'supplier_invoice_no', 'supplier__name')
    inlines = [PurchaseItemInline]
    readonly_fields = ('purchase_no', 'subtotal', 'tax_amount', 'total', 'created_at')


class SaleItemInline(admin.TabularInline):
    model = PharmacySaleItem
    extra = 0
    fields = ('product', 'quantity', 'unit_price', 'tax_rate', 'subtotal')
    readonly_fields = ('subtotal',)


@admin.register(PharmacySale)
class PharmacySaleAdmin(admin.ModelAdmin):
    list_display = ('sale_no', 'store', 'customer', 'biller', 'total', 'payment_method', 'status', 'sale_date')
    list_filter = ('store', 'status', 'payment_method')
    search_fields = ('sale_no', 'customer__name')
    inlines = [SaleItemInline]
    readonly_fields = ('sale_no', 'subtotal', 'tax_amount', 'total', 'created_at')
