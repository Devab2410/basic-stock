"""
Grocery app – 100% function-based views, raw request.POST (no Django Forms).
Every view requires login + a staff profile on the active store.
"""
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum, F
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from .models import (
    GroceryCategory, GroceryBrand, GroceryUnit,
    GroceryProduct, GroceryStock,
    GroceryStockAdjustment, GroceryStockTransfer,
    GrocerySupplier, GroceryCustomer,
    GroceryOffer,
    GroceryPurchase, GroceryPurchaseItem,
    GrocerySale, GrocerySaleItem,
    GrocerySaleReturn, GrocerySaleReturnItem,
    STATUS_PURCHASE,
)
from .utils import generate_purchase_no, generate_sale_no, get_dashboard_stats


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def _get_store(request):
    profile = getattr(request.user, 'profile', None)
    return profile.store if profile else None


def _require_store(view_fn):
    """Decorator: ensure user has an active store."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        store = _get_store(request)
        if not store:
            messages.error(request, 'No active store. Contact administrator.')
            return redirect('core:dashboard')
        return view_fn(request, *args, **kwargs)
    wrapper.__name__ = view_fn.__name__
    return wrapper


def _to_decimal(val, default=0):
    try:
        return Decimal(str(val))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(str(default))


def _to_int(val, default=0):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


# ──────────────────────────────────────────────────────────────────
# DASHBOARD
# ──────────────────────────────────────────────────────────────────

@_require_store
def dashboard(request):
    store = _get_store(request)
    ctx = get_dashboard_stats(store)
    return render(request, 'grocery/dashboard.html', ctx)


# ──────────────────────────────────────────────────────────────────
# CATEGORY
# ──────────────────────────────────────────────────────────────────

@_require_store
def categories(request):
    store = _get_store(request)
    all_categories = GroceryCategory.objects.filter(store=store).select_related('parent').order_by('name')
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create':
            name = request.POST.get('name', '').strip()
            parent_id = request.POST.get('parent') or None
            if not name:
                messages.error(request, 'Name is required.')
            else:
                parent = None
                if parent_id:
                    parent = get_object_or_404(GroceryCategory, pk=parent_id, store=store)
                GroceryCategory.objects.create(store=store, name=name, parent=parent,
                                               is_active=request.POST.get('is_active') == 'on')
                messages.success(request, 'Category created.')
        elif action == 'update':
            cat = get_object_or_404(GroceryCategory, pk=request.POST.get('id'), store=store)
            name = request.POST.get('name', '').strip()
            parent_id = request.POST.get('parent') or None
            if not name:
                messages.error(request, 'Name is required.')
            else:
                parent = None
                if parent_id and int(parent_id) != cat.pk:
                    parent = get_object_or_404(GroceryCategory, pk=parent_id, store=store)
                cat.name = name
                cat.parent = parent
                cat.is_active = request.POST.get('is_active') == 'on'
                cat.save()
                messages.success(request, 'Category updated.')
        elif action == 'delete':
            GroceryCategory.objects.filter(pk=request.POST.get('id'), store=store).delete()
            messages.success(request, 'Category deleted.')
        return redirect('grocery:categories')
    parents = GroceryCategory.objects.filter(store=store, parent=None)
    return render(request, 'grocery/categories.html', {
        'categories': all_categories, 'parents': parents,
    })


def category_list(request):
    return categories(request)


# ──────────────────────────────────────────────────────────────────
# BRAND
# ──────────────────────────────────────────────────────────────────

@_require_store
def brands(request):
    store = _get_store(request)
    all_brands = GroceryBrand.objects.filter(store=store).order_by('name')
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create':
            name = request.POST.get('name', '').strip()
            if not name:
                messages.error(request, 'Brand name is required.')
            else:
                GroceryBrand.objects.get_or_create(store=store, name=name)
                messages.success(request, 'Brand created.')
        elif action == 'update':
            brand = get_object_or_404(GroceryBrand, pk=request.POST.get('id'), store=store)
            brand.name = request.POST.get('name', '').strip()
            brand.is_active = request.POST.get('is_active') == 'on'
            brand.save()
            messages.success(request, 'Brand updated.')
        elif action == 'delete':
            GroceryBrand.objects.filter(pk=request.POST.get('id'), store=store).delete()
            messages.success(request, 'Brand deleted.')
        return redirect('grocery:brands')
    return render(request, 'grocery/brands.html', {'brands': all_brands})


def brand_list(request):
    return brands(request)


# ──────────────────────────────────────────────────────────────────
# UNIT
# ──────────────────────────────────────────────────────────────────

@_require_store
def units(request):
    store = _get_store(request)
    all_units = GroceryUnit.objects.filter(store=store).order_by('name')
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create':
            name = request.POST.get('name', '').strip()
            if not name:
                messages.error(request, 'Unit name is required.')
            else:
                GroceryUnit.objects.get_or_create(store=store, name=name,
                                                  defaults={'short_name': request.POST.get('short_name', '').strip()})
                messages.success(request, 'Unit created.')
        elif action == 'update':
            unit = get_object_or_404(GroceryUnit, pk=request.POST.get('id'), store=store)
            unit.name = request.POST.get('name', '').strip()
            unit.short_name = request.POST.get('short_name', '').strip()
            unit.save()
            messages.success(request, 'Unit updated.')
        elif action == 'delete':
            GroceryUnit.objects.filter(pk=request.POST.get('id'), store=store).delete()
            messages.success(request, 'Unit deleted.')
        return redirect('grocery:units')
    return render(request, 'grocery/units.html', {'units': all_units})


def unit_list(request):
    return units(request)


# ──────────────────────────────────────────────────────────────────
# PRODUCT
# ──────────────────────────────────────────────────────────────────

@_require_store
def product_list(request):
    store = _get_store(request)
    qs = GroceryProduct.objects.filter(store=store, is_active=True).select_related('category', 'brand', 'unit')
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(sku__icontains=q) | Q(barcode__icontains=q))
    paginator = Paginator(qs.order_by('name'), 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'grocery/product_list.html', {'page_obj': page_obj, 'q': q})


@_require_store
def product_detail(request, pk):
    store = _get_store(request)
    product = get_object_or_404(
        GroceryProduct.objects.select_related('category', 'brand', 'unit'),
        pk=pk, store=store
    )
    stocks = product.stocks.filter(store=store).order_by('expiry_date')
    return render(request, 'grocery/product_detail.html', {'product': product, 'stocks': stocks})


@_require_store
def product_create(request):
    store = _get_store(request)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Product name is required.')
        else:
            GroceryProduct.objects.create(
                store=store,
                name=name,
                sku=request.POST.get('sku', '').strip(),
                barcode=request.POST.get('barcode', '').strip(),
                description=request.POST.get('description', '').strip(),
                hsn_code=request.POST.get('hsn_code', '').strip(),
                purchase_price=_to_decimal(request.POST.get('purchase_price'), 0),
                selling_price=_to_decimal(request.POST.get('selling_price'), 0),
                tax_rate=_to_decimal(request.POST.get('tax_rate'), 0),
                weight=_to_decimal(request.POST.get('weight'), 0),
                is_perishable=request.POST.get('is_perishable') == 'on',
                shelf_life_days=_to_int(request.POST.get('shelf_life_days'), 0) or None,
                category_id=request.POST.get('category') or None,
                brand_id=request.POST.get('brand') or None,
                unit_id=request.POST.get('unit') or None,
            )
            messages.success(request, 'Product created.')
            return redirect('grocery:product_list')
    ctx = {
        'categories': GroceryCategory.objects.filter(store=store, is_active=True),
        'brands': GroceryBrand.objects.filter(store=store, is_active=True),
        'units': GroceryUnit.objects.filter(store=store),
        'action': 'Create',
    }
    return render(request, 'grocery/product_form.html', ctx)


@_require_store
def product_edit(request, pk):
    store = _get_store(request)
    product = get_object_or_404(GroceryProduct, pk=pk, store=store)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Product name is required.')
        else:
            product.name = name
            product.sku = request.POST.get('sku', '').strip()
            product.barcode = request.POST.get('barcode', '').strip()
            product.description = request.POST.get('description', '').strip()
            product.hsn_code = request.POST.get('hsn_code', '').strip()
            product.purchase_price = _to_decimal(request.POST.get('purchase_price'), 0)
            product.selling_price = _to_decimal(request.POST.get('selling_price'), 0)
            product.tax_rate = _to_decimal(request.POST.get('tax_rate'), 0)
            product.weight = _to_decimal(request.POST.get('weight'), 0)
            product.is_perishable = request.POST.get('is_perishable') == 'on'
            product.shelf_life_days = _to_int(request.POST.get('shelf_life_days'), 0) or None
            product.category_id = request.POST.get('category') or None
            product.brand_id = request.POST.get('brand') or None
            product.unit_id = request.POST.get('unit') or None
            product.save()
            messages.success(request, 'Product updated.')
            return redirect('grocery:product_list')
    ctx = {
        'product': product,
        'categories': GroceryCategory.objects.filter(store=store, is_active=True),
        'brands': GroceryBrand.objects.filter(store=store, is_active=True),
        'units': GroceryUnit.objects.filter(store=store),
        'action': 'Edit',
    }
    return render(request, 'grocery/product_form.html', ctx)


@_require_store
@require_POST
def product_delete(request, pk):
    store = _get_store(request)
    product = get_object_or_404(GroceryProduct, pk=pk, store=store)
    product.is_active = False
    product.save(update_fields=['is_active'])
    messages.success(request, 'Product deactivated.')
    return redirect('grocery:product_list')


# ──────────────────────────────────────────────────────────────────
# STOCK VIEWS
# ──────────────────────────────────────────────────────────────────

@_require_store
def manage_stock(request):
    """Manage Stock — list + CRUD via POST."""
    store = _get_store(request)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            product_id = request.POST.get('product')
            if not product_id:
                messages.error(request, 'Product is required.')
            else:
                GroceryStock.objects.create(
                    product_id=product_id,
                    store=store,
                    batch_no=request.POST.get('batch_no', '').strip(),
                    quantity=_to_decimal(request.POST.get('quantity'), 0),
                    min_quantity=_to_decimal(request.POST.get('min_quantity'), 10),
                    warehouse=request.POST.get('warehouse', '').strip(),
                    rack_location=request.POST.get('rack_location', '').strip(),
                    manufacturing_date=request.POST.get('manufacturing_date') or None,
                    expiry_date=request.POST.get('expiry_date') or None,
                )
                messages.success(request, 'Stock record created.')

        elif action == 'update':
            stock = get_object_or_404(GroceryStock, pk=request.POST.get('id'), store=store)
            stock.batch_no = request.POST.get('batch_no', '').strip()
            stock.quantity = _to_decimal(request.POST.get('quantity'), stock.quantity)
            stock.min_quantity = _to_decimal(request.POST.get('min_quantity'), stock.min_quantity)
            stock.warehouse = request.POST.get('warehouse', '').strip()
            stock.rack_location = request.POST.get('rack_location', '').strip()
            stock.manufacturing_date = request.POST.get('manufacturing_date') or None
            stock.expiry_date = request.POST.get('expiry_date') or None
            stock.save()
            messages.success(request, 'Stock updated.')

        elif action == 'delete':
            GroceryStock.objects.filter(pk=request.POST.get('id'), store=store).delete()
            messages.success(request, 'Stock record deleted.')

        return redirect('grocery:manage_stock')

    stocks = GroceryStock.objects.for_store(store).select_related('product').order_by('product__name')
    products = GroceryProduct.objects.filter(store=store, is_active=True)
    return render(request, 'grocery/manage_stock.html', {
        'stocks': stocks,
        'products': products,
    })


@_require_store
def low_stocks(request):
    store = _get_store(request)
    stocks = GroceryStock.objects.for_store(store).low_stock().select_related('product')
    return render(request, 'grocery/low_stocks.html', {'stocks': stocks})


@_require_store
def expired_products(request):
    store = _get_store(request)
    stocks = GroceryStock.objects.for_store(store).expired().select_related('product')
    return render(request, 'grocery/expired_products.html', {'stocks': stocks})


@_require_store
def near_expiry(request):
    store = _get_store(request)
    stocks = GroceryStock.objects.for_store(store).near_expiry(5).select_related('product')
    return render(request, 'grocery/near_expiry.html', {'stocks': stocks})


# ──────────────────────────────────────────────────────────────────
# STOCK ADJUSTMENT  (now updates stock.quantity!)
# ──────────────────────────────────────────────────────────────────

@_require_store
def stock_adjustment_list(request):
    store = _get_store(request)
    adjustments = (
        GroceryStockAdjustment.objects
        .filter(stock__store=store)
        .select_related('stock__product', 'adjusted_by')
        .order_by('-date')
    )
    return render(request, 'grocery/stock_adjustment_list.html', {'adjustments': adjustments})


@_require_store
def stock_adjustment_create(request):
    store = _get_store(request)
    if request.method == 'POST':
        stock_id = request.POST.get('stock')
        adj_type = request.POST.get('adjustment_type', 'add')
        qty = _to_decimal(request.POST.get('quantity'), 0)
        reason = request.POST.get('reason', '').strip()
        notes = request.POST.get('notes', '').strip()
        if not stock_id or qty <= 0:
            messages.error(request, 'Valid stock and quantity are required.')
        else:
            with transaction.atomic():
                stock = get_object_or_404(GroceryStock, pk=stock_id, store=store)
                GroceryStockAdjustment.objects.create(
                    stock=stock,
                    adjustment_type=adj_type,
                    quantity=qty,
                    reason=reason,
                    notes=notes,
                    adjusted_by=request.user,
                )
                # ── Actually update the stock quantity ──
                if adj_type == 'add':
                    stock.quantity += qty
                elif adj_type == 'return':
                    stock.quantity += qty
                else:  # remove, damage, expired
                    stock.quantity = max(stock.quantity - qty, Decimal('0'))
                stock.save(update_fields=['quantity'])
            messages.success(request, 'Stock adjusted.')
            return redirect('grocery:stock_adjustment_list')
    stocks = GroceryStock.objects.for_store(store).select_related('product')
    adj_types = [('add', 'Add'), ('remove', 'Remove'), ('damage', 'Damage/Loss'),
                 ('expired', 'Expired'), ('return', 'Return')]
    return render(request, 'grocery/stock_adjustment_form.html', {
        'stocks': stocks, 'adjustment_types': adj_types, 'action': 'Create'
    })


# ──────────────────────────────────────────────────────────────────
# STOCK TRANSFER  (now actually moves stock!)
# ──────────────────────────────────────────────────────────────────

@_require_store
def stock_transfer_list(request):
    store = _get_store(request)
    transfers = (
        GroceryStockTransfer.objects
        .filter(Q(from_store=store) | Q(to_store=store))
        .select_related('product', 'from_store', 'to_store', 'transferred_by')
        .order_by('-date')
    )
    return render(request, 'grocery/stock_transfer_list.html', {'transfers': transfers})


@_require_store
def stock_transfer_create(request):
    from core.models import Store
    store = _get_store(request)
    if request.method == 'POST':
        product_id = request.POST.get('product')
        to_store_id = request.POST.get('to_store')
        qty = _to_decimal(request.POST.get('quantity'), 0)
        batch_no = request.POST.get('batch_no', '').strip()
        if not product_id or not to_store_id or qty <= 0:
            messages.error(request, 'Product, destination store and quantity are required.')
        else:
            product = get_object_or_404(GroceryProduct, pk=product_id, store=store)
            to_store = get_object_or_404(Store, pk=to_store_id)
            GroceryStockTransfer.objects.create(
                product=product,
                from_store=store,
                to_store=to_store,
                quantity=qty,
                batch_no=batch_no,
                transferred_by=request.user,
            )
            messages.success(request, 'Transfer created.')
            return redirect('grocery:stock_transfer_list')
    ctx = {
        'products': GroceryProduct.objects.filter(store=store, is_active=True),
        'stores': Store.objects.exclude(pk=store.pk),
        'action': 'Create',
    }
    return render(request, 'grocery/stock_transfer_form.html', ctx)


@_require_store
@require_POST
def stock_transfer_complete(request, pk):
    """Mark transfer as completed and move stock between stores."""
    store = _get_store(request)
    transfer = get_object_or_404(GroceryStockTransfer, pk=pk, from_store=store, status='pending')

    with transaction.atomic():
        # Deduct from source store
        source_stocks = GroceryStock.objects.filter(
            product=transfer.product, store=transfer.from_store
        ).order_by('expiry_date')  # FIFO

        remaining = transfer.quantity
        for s in source_stocks:
            if remaining <= 0:
                break
            deduct = min(s.quantity, remaining)
            s.quantity -= deduct
            s.save(update_fields=['quantity'])
            remaining -= deduct

        # Add to destination store
        dest_stock, created = GroceryStock.objects.get_or_create(
            product=transfer.product,
            store=transfer.to_store,
            batch_no=transfer.batch_no,
            defaults={'quantity': 0, 'min_quantity': 10},
        )
        dest_stock.quantity += transfer.quantity
        dest_stock.save(update_fields=['quantity'])

        transfer.status = 'completed'
        transfer.save(update_fields=['status'])

    messages.success(request, 'Transfer completed. Stock moved.')
    return redirect('grocery:stock_transfer_list')


# ──────────────────────────────────────────────────────────────────
# SUPPLIER
# ──────────────────────────────────────────────────────────────────

@_require_store
def suppliers(request):
    store = _get_store(request)
    all_suppliers = GrocerySupplier.objects.filter(store=store).order_by('name')
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create':
            name = request.POST.get('name', '').strip()
            if not name:
                messages.error(request, 'Supplier name is required.')
            else:
                GrocerySupplier.objects.create(
                    store=store, name=name,
                    phone=request.POST.get('phone', '').strip(),
                    email=request.POST.get('email', '').strip(),
                    address=request.POST.get('address', '').strip(),
                    gstin=request.POST.get('gstin', '').strip(),
                )
                messages.success(request, 'Supplier created.')
        elif action == 'update':
            sup = get_object_or_404(GrocerySupplier, pk=request.POST.get('id'), store=store)
            sup.name = request.POST.get('name', '').strip()
            sup.phone = request.POST.get('phone', '').strip()
            sup.email = request.POST.get('email', '').strip()
            sup.address = request.POST.get('address', '').strip()
            sup.gstin = request.POST.get('gstin', '').strip()
            sup.is_active = request.POST.get('is_active') == 'on'
            sup.save()
            messages.success(request, 'Supplier updated.')
        elif action == 'delete':
            GrocerySupplier.objects.filter(pk=request.POST.get('id'), store=store).delete()
            messages.success(request, 'Supplier deleted.')
        return redirect('grocery:suppliers')
    return render(request, 'grocery/suppliers.html', {'suppliers': all_suppliers})


def supplier_list(request):
    return suppliers(request)


# ──────────────────────────────────────────────────────────────────
# CUSTOMER
# ──────────────────────────────────────────────────────────────────

@_require_store
def customers(request):
    store = _get_store(request)
    all_customers = GroceryCustomer.objects.filter(store=store).order_by('name')
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create':
            name = request.POST.get('name', '').strip()
            phone = request.POST.get('phone', '').strip()
            if not phone:
                messages.error(request, 'Phone is required.')
            else:
                GroceryCustomer.objects.get_or_create(
                    store=store, phone=phone,
                    defaults={
                        'name': name,
                        'email': request.POST.get('email', '').strip(),
                        'address': request.POST.get('address', '').strip(),
                    }
                )
                messages.success(request, 'Customer created.')
        elif action == 'update':
            cust = get_object_or_404(GroceryCustomer, pk=request.POST.get('id'), store=store)
            cust.name = request.POST.get('name', '').strip()
            cust.phone = request.POST.get('phone', '').strip()
            cust.email = request.POST.get('email', '').strip()
            cust.address = request.POST.get('address', '').strip()
            cust.is_active = request.POST.get('is_active') == 'on'
            cust.save()
            messages.success(request, 'Customer updated.')
        elif action == 'delete':
            GroceryCustomer.objects.filter(pk=request.POST.get('id'), store=store).delete()
            messages.success(request, 'Customer deleted.')
        return redirect('grocery:customers')
    return render(request, 'grocery/customers.html', {'customers': all_customers})


def customer_list(request):
    return customers(request)


# ──────────────────────────────────────────────────────────────────
# OFFERS / PROMOTIONS
# ──────────────────────────────────────────────────────────────────

@_require_store
def offer_list(request):
    store = _get_store(request)
    offers = (
        GroceryOffer.objects.filter(store=store)
        .select_related('product')
        .order_by('-start_date')
    )
    return render(request, 'grocery/offer_list.html', {'offers': offers})


@_require_store
def offer_create(request):
    store = _get_store(request)
    if request.method == 'POST':
        product_id = request.POST.get('product')
        offer_type = request.POST.get('offer_type', 'flat')
        value = _to_decimal(request.POST.get('value'), 0)
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        if not product_id or not start_date or not end_date or value <= 0:
            messages.error(request, 'Product, dates and value are required.')
        else:
            GroceryOffer.objects.create(
                store=store,
                product_id=product_id,
                offer_type=offer_type,
                value=value,
                x_quantity=_to_int(request.POST.get('x_quantity'), 1),
                y_quantity=_to_int(request.POST.get('y_quantity'), 1),
                start_date=start_date,
                end_date=end_date,
            )
            messages.success(request, 'Offer created.')
            return redirect('grocery:offer_list')
    ctx = {
        'products': GroceryProduct.objects.filter(store=store, is_active=True),
        'offer_types': [('flat', 'Flat Discount'), ('percent', 'Percentage (%)'), ('buy_x_get_y', 'Buy X Get Y')],
        'action': 'Create',
    }
    return render(request, 'grocery/offer_form.html', ctx)


@_require_store
def offer_edit(request, pk):
    store = _get_store(request)
    offer = get_object_or_404(GroceryOffer, pk=pk, store=store)
    if request.method == 'POST':
        value = _to_decimal(request.POST.get('value'), 0)
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        if not start_date or not end_date or value <= 0:
            messages.error(request, 'Dates and value are required.')
        else:
            offer.value = value
            offer.start_date = start_date
            offer.end_date = end_date
            offer.is_active = request.POST.get('is_active') == 'on'
            offer.save()
            messages.success(request, 'Offer updated.')
            return redirect('grocery:offer_list')
    ctx = {
        'offer': offer,
        'offer_types': [('flat', 'Flat Discount'), ('percent', 'Percentage (%)'), ('buy_x_get_y', 'Buy X Get Y')],
        'action': 'Edit',
    }
    return render(request, 'grocery/offer_form.html', ctx)


@_require_store
@require_POST
def offer_delete(request, pk):
    store = _get_store(request)
    offer = get_object_or_404(GroceryOffer, pk=pk, store=store)
    offer.delete()
    messages.success(request, 'Offer removed.')
    return redirect('grocery:offer_list')


# ──────────────────────────────────────────────────────────────────
# PURCHASE
# ──────────────────────────────────────────────────────────────────

@_require_store
def purchase_list(request):
    store = _get_store(request)
    purchases = (
        GroceryPurchase.objects.filter(store=store)
        .select_related('supplier')
        .order_by('-purchase_date')
    )
    suppliers_qs = GrocerySupplier.objects.filter(store=store, is_active=True)
    products = GroceryProduct.objects.filter(store=store, is_active=True).select_related('unit')
    status_choices = STATUS_PURCHASE
    return render(request, 'grocery/purchase_list.html', {
        'purchases': purchases,
        'suppliers': suppliers_qs,
        'products': products,
        'status': status_choices,
    })


@_require_store
def purchase_create(request):
    store = _get_store(request)
    if request.method == 'POST':
        supplier_id = request.POST.get('supplier')
        purchase_date_val = request.POST.get('purchase_date') or date.today().isoformat()
        supplier_invoice_no = request.POST.get('supplier_invoice_no', '').strip()
        notes = request.POST.get('notes', '').strip()
        discount = _to_decimal(request.POST.get('discount'), 0)

        products = request.POST.getlist('product_id')
        quantities = request.POST.getlist('quantity')
        unit_prices = request.POST.getlist('unit_price')
        batch_nos = request.POST.getlist('batch_no')
        expiry_dates = request.POST.getlist('expiry_date')
        tax_rates = request.POST.getlist('tax_rate')

        if not supplier_id or not products:
            messages.error(request, 'Supplier and at least one item are required.')
        else:
            with transaction.atomic():
                purchase = GroceryPurchase.objects.create(
                    store=store,
                    supplier_id=supplier_id,
                    purchase_no=generate_purchase_no(store),
                    purchase_date=purchase_date_val,
                    supplier_invoice_no=supplier_invoice_no,
                    notes=notes,
                    discount=discount,
                    created_by=request.user,
                )
                subtotal = Decimal('0')
                tax_total = Decimal('0')
                for i, prod_id in enumerate(products):
                    if not prod_id:
                        continue
                    qty = _to_decimal(quantities[i] if i < len(quantities) else 0, 0)
                    u_price = _to_decimal(unit_prices[i] if i < len(unit_prices) else 0, 0)
                    batch = batch_nos[i].strip() if i < len(batch_nos) else ''
                    exp_date = expiry_dates[i] if i < len(expiry_dates) else None
                    t_rate = _to_decimal(tax_rates[i] if i < len(tax_rates) else 0, 0)

                    item = GroceryPurchaseItem.objects.create(
                        purchase=purchase,
                        product_id=prod_id,
                        quantity=qty,
                        unit_price=u_price,
                        batch_no=batch,
                        expiry_date=exp_date or None,
                        tax_rate=t_rate,
                    )
                    subtotal += (u_price * qty)
                    tax_total += item.tax_amount

                purchase.subtotal = subtotal
                purchase.tax_amount = tax_total
                purchase.total = subtotal + tax_total - discount
                purchase.save(update_fields=['subtotal', 'tax_amount', 'total'])
            messages.success(request, f'Purchase {purchase.purchase_no} created.')
            return redirect('grocery:purchase_detail', pk=purchase.pk)

    ctx = {
        'suppliers': GrocerySupplier.objects.filter(store=store, is_active=True),
        'products': GroceryProduct.objects.filter(store=store, is_active=True).select_related('unit'),
    }
    return render(request, 'grocery/purchase_form.html', ctx)


@_require_store
def purchase_detail(request, pk):
    store = _get_store(request)
    purchase = get_object_or_404(
        GroceryPurchase.objects.select_related('supplier', 'created_by').prefetch_related('items__product'),
        pk=pk, store=store
    )
    status_choices = STATUS_PURCHASE
    return render(request, 'grocery/purchase_detail.html', {
        'purchase': purchase,
        'status': status_choices,
    })


@_require_store
@require_POST
def purchase_receive(request, pk):
    """Change purchase status and create/reverse stock accordingly."""
    store = _get_store(request)
    purchase = get_object_or_404(GroceryPurchase, pk=pk, store=store)
    old_status = purchase.status
    new_status = request.POST.get('status', 'received')

    purchase.status = new_status
    purchase.save(update_fields=['status'])

    # ── Add stock when purchase is received (from draft) ──
    if new_status in ('received', 'partial') and old_status not in ('received', 'partial'):
        with transaction.atomic():
            for item in purchase.items.select_related('product').all():
                stock, created = GroceryStock.objects.get_or_create(
                    product=item.product,
                    store=store,
                    batch_no=item.batch_no or '',
                    defaults={
                        'quantity': 0,
                        'min_quantity': 10,
                        'expiry_date': item.expiry_date,
                    }
                )
                stock.quantity += item.received_qty or item.quantity
                if item.expiry_date and (not stock.expiry_date or item.expiry_date < stock.expiry_date):
                    stock.expiry_date = item.expiry_date
                stock.save(update_fields=['quantity', 'expiry_date'])

    # ── Reverse stock when going back to draft or cancelled ──
    elif new_status in ('draft', 'cancelled') and old_status in ('received', 'partial'):
        with transaction.atomic():
            for item in purchase.items.select_related('product').all():
                try:
                    stock = GroceryStock.objects.get(
                        product=item.product,
                        store=store,
                        batch_no=item.batch_no or '',
                    )
                    stock.quantity = max(stock.quantity - (item.received_qty or item.quantity), Decimal('0'))
                    stock.save(update_fields=['quantity'])
                except GroceryStock.DoesNotExist:
                    pass

    messages.success(request, f'Purchase {purchase.purchase_no} marked as {purchase.get_status_display()}.')
    return redirect('grocery:purchase_detail', pk=pk)


@_require_store
@require_POST
def purchase_delete(request, pk):
    """Delete a purchase. Reverse stock if it was received."""
    store = _get_store(request)
    purchase = get_object_or_404(GroceryPurchase, pk=pk, store=store)

    # If purchase was received, reverse the stock
    if purchase.status in ('received', 'partial'):
        with transaction.atomic():
            for item in purchase.items.select_related('product').all():
                try:
                    stock = GroceryStock.objects.get(
                        product=item.product,
                        store=store,
                        batch_no=item.batch_no or '',
                    )
                    stock.quantity = max(stock.quantity - (item.received_qty or item.quantity), Decimal('0'))
                    stock.save(update_fields=['quantity'])
                except GroceryStock.DoesNotExist:
                    pass

    purchase.delete()
    messages.success(request, 'Purchase deleted.')
    return redirect('grocery:purchase_list')


# ──────────────────────────────────────────────────────────────────
# SALE / POS
# ──────────────────────────────────────────────────────────────────

@_require_store
def sale_list(request):
    store = _get_store(request)
    sales = (
        GrocerySale.objects.filter(store=store)
        .select_related('customer', 'biller')
        .order_by('-sale_date')
    )
    return render(request, 'grocery/sale_list.html', {'sales': sales})


@_require_store
def sale_detail(request, pk):
    store = _get_store(request)
    sale = get_object_or_404(
        GrocerySale.objects.select_related('customer', 'biller').prefetch_related('items__product'),
        pk=pk, store=store
    )
    return render(request, 'grocery/sale_detail.html', {'sale': sale})


@_require_store
def pos(request):
    """POS View – GET renders terminal; POST creates sale with FIFO stock deduction."""
    store = _get_store(request)
    if request.method == 'POST':
        customer_id = request.POST.get('customer') or None
        payment_method = request.POST.get('payment_method', 'cash')
        discount_total = _to_decimal(request.POST.get('discount', 0), 0)
        product_ids = request.POST.getlist('product_id')
        quantities = request.POST.getlist('sale_qty')
        unit_prices = request.POST.getlist('sale_price')

        if not product_ids:
            messages.error(request, 'Add at least one item.')
        else:
            with transaction.atomic():
                sale = GrocerySale.objects.create(
                    store=store,
                    customer_id=customer_id,
                    biller=request.user,
                    sale_no=generate_sale_no(store),
                    payment_method=payment_method,
                    discount=discount_total,
                )
                subtotal = Decimal('0')
                tax_total = Decimal('0')

                for i, prod_id in enumerate(product_ids):
                    if not prod_id:
                        continue
                    qty = _to_decimal(quantities[i] if i < len(quantities) else 1, 1)
                    u_price = _to_decimal(unit_prices[i] if i < len(unit_prices) else 0, 0)

                    product = GroceryProduct.objects.get(pk=prod_id)
                    tax_rate = product.tax_rate

                    item = GrocerySaleItem.objects.create(
                        sale=sale,
                        product_id=prod_id,
                        quantity=qty,
                        unit_price=u_price,
                        tax_rate=tax_rate,
                    )
                    subtotal += (u_price * qty)
                    tax_total += item.tax_amount

                    # ── FIFO stock deduction ──
                    remaining = qty
                    stock_batches = GroceryStock.objects.filter(
                        product_id=prod_id, store=store, quantity__gt=0
                    ).order_by('expiry_date', 'created_at')

                    for stock in stock_batches:
                        if remaining <= 0:
                            break
                        deduct = min(stock.quantity, remaining)
                        stock.quantity -= deduct
                        stock.save(update_fields=['quantity'])
                        remaining -= deduct

                sale.subtotal = subtotal
                sale.tax_amount = tax_total
                sale.total = subtotal + tax_total - discount_total
                sale.save(update_fields=['subtotal', 'tax_amount', 'total'])
            messages.success(request, f'Sale {sale.sale_no} completed.')
            return redirect('grocery:sale_detail', pk=sale.pk)

    ctx = {
        'products': GroceryProduct.objects.filter(store=store, is_active=True).select_related('unit'),
        'customers': GroceryCustomer.objects.filter(store=store, is_active=True),
        'payment_methods': [('cash', 'Cash'), ('card', 'Card'), ('upi', 'UPI'),
                            ('wallet', 'Wallet'), ('credit', 'Credit')],
    }
    return render(request, 'grocery/pos.html', ctx)


# ──────────────────────────────────────────────────────────────────
# AJAX / API endpoints
# ──────────────────────────────────────────────────────────────────

@_require_store
def product_search_api(request):
    store = _get_store(request)
    q = request.GET.get('q', '').strip()
    products = GroceryProduct.objects.filter(store=store, is_active=True)
    if q:
        products = products.filter(Q(name__icontains=q) | Q(sku__icontains=q) | Q(barcode__icontains=q))
    data = [
        {
            'id': p.id,
            'name': p.name,
            'sku': p.sku,
            'barcode': p.barcode,
            'selling_price': float(p.selling_price),
            'purchase_price': float(p.purchase_price),
            'tax_rate': float(p.tax_rate),
            'stock': float(p.current_stock),
            'unit': str(p.unit) if p.unit else '',
        }
        for p in products[:20]
    ]
    return JsonResponse({'results': data})


# ──────────────────────────────────────────────────────────────────
# REPORTS
# ──────────────────────────────────────────────────────────────────

@_require_store
def report_sales(request):
    store = _get_store(request)
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    sales = GrocerySale.objects.filter(store=store)
    if date_from:
        sales = sales.filter(sale_date__date__gte=date_from)
    if date_to:
        sales = sales.filter(sale_date__date__lte=date_to)
    total = sales.aggregate(total=Sum('total'))['total'] or 0
    return render(request, 'grocery/reports/sales_report.html', {
        'sales': sales.order_by('-sale_date'),
        'total_sales': total,
        'date_from': date_from or '',
        'date_to': date_to or '',
    })


@_require_store
def report_purchases(request):
    store = _get_store(request)
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    purchases = GroceryPurchase.objects.filter(store=store)
    if date_from:
        purchases = purchases.filter(purchase_date__gte=date_from)
    if date_to:
        purchases = purchases.filter(purchase_date__lte=date_to)
    total = purchases.aggregate(total=Sum('total'))['total'] or 0
    return render(request, 'grocery/reports/purchase_report.html', {
        'purchases': purchases.order_by('-purchase_date'),
        'total_purchases': total,
        'date_from': date_from or '',
        'date_to': date_to or '',
    })


@_require_store
def report_inventory(request):
    store = _get_store(request)
    stocks = GroceryStock.objects.for_store(store).select_related('product')
    return render(request, 'grocery/reports/inventory_report.html', {'stocks': stocks})


@_require_store
def report_expiry(request):
    store = _get_store(request)
    days = _to_int(request.GET.get('days'), 7)
    stocks = GroceryStock.objects.for_store(store).near_expiry(days).select_related('product')
    return render(request, 'grocery/reports/expiry_report.html', {'stocks': stocks, 'days': days})
