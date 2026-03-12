from django import forms
from django.forms import inlineformset_factory

from .models import (
    PharmacyProduct, PharmacyCategory, PharmacyBrand, PharmacyUnit,
    PharmacyStock, PharmacyStockAdjustment, PharmacyStockTransfer,
    PharmacySupplier, PharmacyCustomer,
    PharmacyPurchase, PharmacyPurchaseItem,
    PharmacySale, PharmacySaleItem, PharmacySaleReturn
)


class ProductForm(forms.ModelForm):
    class Meta:
        model = PharmacyProduct
        fields = [
            'name', 'category', 'brand', 'unit', 'barcode', 'sku', 'description', 'image',
            'purchase_price', 'selling_price', 'tax_rate', 'hsn_code',
            'requires_prescription', 'schedule_type', 'is_active'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, store=None, **kwargs):
        super().__init__(*args, **kwargs)
        if store:
            self.fields['category'].queryset = PharmacyCategory.objects.filter(
                store=store, is_active=True)
            self.fields['brand'].queryset = PharmacyBrand.objects.filter(store=store, is_active=True)
            self.fields['unit'].queryset = PharmacyUnit.objects.filter(store=store)


class CategoryForm(forms.ModelForm):
    class Meta:
        model = PharmacyCategory
        fields = ['name', 'parent', 'is_active']

    def __init__(self, *args, store=None, **kwargs):
        super().__init__(*args, **kwargs)
        if store:
            self.fields['parent'].queryset = PharmacyCategory.objects.filter(
                store=store, parent__isnull=True, is_active=True)


class BrandForm(forms.ModelForm):
    class Meta:
        model = PharmacyBrand
        fields = ['name', 'is_active']


class UnitForm(forms.ModelForm):
    class Meta:
        model = PharmacyUnit
        fields = ['name', 'short_name']


class StockAdjustmentForm(forms.ModelForm):
    class Meta:
        model = PharmacyStockAdjustment
        fields = ['stock', 'adjustment_type', 'quantity', 'reason', 'notes']

    def __init__(self, *args, store=None, **kwargs):
        super().__init__(*args, **kwargs)
        if store:
            self.fields['stock'].queryset = PharmacyStock.objects.filter(
                store=store
            ).select_related('product')


class StockTransferForm(forms.ModelForm):
    class Meta:
        model = PharmacyStockTransfer
        fields = ['product', 'to_store', 'quantity', 'notes']

    def __init__(self, *args, store=None, **kwargs):
        super().__init__(*args, **kwargs)
        if store:
            from core.models import Store
            self.fields['product'].queryset = PharmacyProduct.objects.filter(
                store=store, is_active=True)
            self.fields['to_store'].queryset = Store.objects.filter(
                company=store.company,
                business_type=store.business_type,
                is_active=True
            ).exclude(pk=store.pk)


class SupplierForm(forms.ModelForm):
    class Meta:
        model = PharmacySupplier
        fields = [
            'name', 'contact_person', 'email', 'phone', 'address', 'city',
            'gstin', 'drug_license_no', 'is_active'
        ]


class CustomerForm(forms.ModelForm):
    class Meta:
        model = PharmacyCustomer
        fields = ['name', 'phone', 'email', 'address', 'dob', 'is_active']
        widgets = {
            'dob': forms.DateInput(attrs={'type': 'date'}),
        }


class PurchaseForm(forms.ModelForm):
    class Meta:
        model = PharmacyPurchase
        fields = ['supplier', 'supplier_invoice_no', 'purchase_date', 'discount', 'status', 'notes']
        widgets = {
            'purchase_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, store=None, **kwargs):
        super().__init__(*args, **kwargs)
        if store:
            self.fields['supplier'].queryset = PharmacySupplier.objects.filter(
                store=store, is_active=True)


class PurchaseItemForm(forms.ModelForm):
    class Meta:
        model = PharmacyPurchaseItem
        fields = ['product', 'quantity', 'received_qty', 'unit_price', 'tax_rate', 'batch_no', 'expiry_date']
        widgets = {
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, store=None, **kwargs):
        super().__init__(*args, **kwargs)
        if store:
            self.fields['product'].queryset = PharmacyProduct.objects.filter(
                store=store, is_active=True)


def PurchaseItemFormSet(store=None, **kwargs):
    FormSet = inlineformset_factory(
        PharmacyPurchase, PharmacyPurchaseItem,
        form=PurchaseItemForm,
        extra=3, can_delete=True
    )
    class _FormSet(FormSet):
        def __init__(self, *args, **kw):
            super().__init__(*args, **kw)
            for form in self.forms:
                form.fields['product'].queryset = PharmacyProduct.objects.filter(
                    store=store, is_active=True)
    return _FormSet(**kwargs)


class SaleForm(forms.ModelForm):
    class Meta:
        model = PharmacySale
        fields = ['customer', 'discount', 'payment_method', 'amount_paid', 'notes']

    def __init__(self, *args, store=None, **kwargs):
        super().__init__(*args, **kwargs)
        if store:
            self.fields['customer'].queryset = PharmacyCustomer.objects.filter(
                store=store, is_active=True)


class SaleItemForm(forms.ModelForm):
    class Meta:
        model = PharmacySaleItem
        fields = ['product', 'quantity', 'unit_price', 'tax_rate']


def SaleItemFormSet(store=None, **kwargs):
    FormSet = inlineformset_factory(
        PharmacySale, PharmacySaleItem,
        form=SaleItemForm,
        extra=5, can_delete=True
    )
    class _FormSet(FormSet):
        def __init__(self, *args, **kw):
            super().__init__(*args, **kw)
            for form in self.forms:
                form.fields['product'].queryset = PharmacyProduct.objects.filter(
                    store=store, is_active=True)
    return _FormSet(**kwargs)


class SaleReturnForm(forms.ModelForm):
    class Meta:
        model = PharmacySaleReturn
        fields = ['reason', 'refund_method']
