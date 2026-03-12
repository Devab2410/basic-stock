from django.contrib import admin
from .models import (
    GroceryCategory, GroceryBrand, GroceryUnit, GroceryProduct,
    GroceryStock, GroceryStockAdjustment, GrocerySupplier, GroceryCustomer,
    GroceryPurchase, GroceryPurchaseItem, GrocerySale, GrocerySaleItem, GroceryOffer
)

@admin.register(GroceryCategory)
class GroceryCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'parent', 'is_active')
    list_filter = ('store', 'is_active')

@admin.register(GroceryBrand)
class GroceryBrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'is_active')

@admin.register(GroceryUnit)
class GroceryUnitAdmin(admin.ModelAdmin):
    list_display = ('name', 'short_name', 'store')

@admin.register(GroceryProduct)
class GroceryProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'category', 'selling_price', 'weight', 'is_perishable', 'is_active')
    list_filter = ('store', 'is_perishable', 'is_active')
    search_fields = ('name', 'barcode', 'sku')

@admin.register(GroceryStock)
class GroceryStockAdmin(admin.ModelAdmin):
    list_display = ('product', 'store', 'batch_no', 'quantity', 'expiry_date')
    list_filter = ('store',)
    search_fields = ('product__name', 'batch_no')

@admin.register(GrocerySupplier)
class GrocerySupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'phone', 'is_active')

@admin.register(GroceryCustomer)
class GroceryCustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'store', 'loyalty_points', 'is_active')

@admin.register(GroceryOffer)
class GroceryOfferAdmin(admin.ModelAdmin):
    list_display = ('product', 'store', 'offer_type', 'value', 'end_date', 'is_active')
    list_filter = ('store', 'offer_type', 'is_active')
