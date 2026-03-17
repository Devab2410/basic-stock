"""
Pharmacy app – 100% function-based views, raw request.POST (no Django Forms).
Every view requires login + a staff profile on the active store.
Simple CRUD pages (category, brand, unit, supplier, customer) use the
business_types single-page pattern: one URL, action = create | update | delete.
"""
import InventoryHub
import InventoryHub
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum, Prefetch, Count, F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from datetime import date, timedelta

from .models import (
    PharmacyBrand,
    PharmacyCategory,
    PharmacyCustomer,
    PharmacyProduct,
    PharmacyPurchase,
    PharmacyPurchaseItem,
    PharmacySale,
    PharmacySaleItem,
    PharmacySaleReturn,
    PharmacySaleReturnItem,
    PharmacyStock,
    PharmacyStockAdjustment,
    PharmacyStockTransfer,
    PharmacySupplier,
    PharmacyUnit,
    PharmacyProductImage,
)
from .utils import generate_purchase_no, generate_sale_no, generate_return_no, get_dashboard_stats


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def _get_store(request):
    """Return the active store for the logged-in user."""
    return request.user.active_store


def _require_store(view_fn):
    """Decorator: ensure the user has an active store before entering a view."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        store = _get_store(request)
        if not store:
            messages.error(request, 'No active store. Contact administrator.')
            # return redirect('core:dashboard') 
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

def get_dashboard_stats1(store):
    today = date.today()
    month_start = today.replace(day=1)
    last_month_start = (month_start - timedelta(days=1)).replace(day=1)
    last_month_end = month_start - timedelta(days=1)
    thirty_days_ago = today - timedelta(days=30)

    # ── Sales totals ─────────────────────────────────────────
    sales_qs = PharmacySale.objects.filter(store=store)

    total_sales = sales_qs.filter(
        status__in=['paid', 'partial']
    ).aggregate(total=Sum('total'))['total'] or 0

    this_month_sales = sales_qs.filter(
        sale_date__date__gte=month_start,
        status__in=['paid', 'partial']
    ).aggregate(total=Sum('total'))['total'] or 0

    last_month_sales = sales_qs.filter(
        sale_date__date__gte=last_month_start,
        sale_date__date__lte=last_month_end,
        status__in=['paid', 'partial']
    ).aggregate(total=Sum('total'))['total'] or 0

    sales_change = 0
    if last_month_sales:
        sales_change = round(
            ((this_month_sales - last_month_sales) / last_month_sales) * 100, 1
        )

    today_sales = sales_qs.filter(
        sale_date__date=today
    ).aggregate(total=Sum('total'))['total'] or 0

    today_order_count = sales_qs.filter(sale_date__date=today).count()

    # ── Sale Returns ─────────────────────────────────────────
    from .models import PharmacySaleReturn
    total_sale_returns = PharmacySaleReturn.objects.filter(
        sale__store=store
    ).aggregate(total=Sum('total_refund'))['total'] or 0

    # ── Purchase totals ───────────────────────────────────────
    purchase_qs = PharmacyPurchase.objects.filter(store=store)

    total_purchase = purchase_qs.filter(
        status__in=['received', 'partial']
    ).aggregate(total=Sum('total'))['total'] or 0

    this_month_purchase = purchase_qs.filter(
        purchase_date__gte=month_start,
        status__in=['received', 'partial']
    ).aggregate(total=Sum('total'))['total'] or 0

    last_month_purchase = purchase_qs.filter(
        purchase_date__gte=last_month_start,
        purchase_date__lte=last_month_end,
        status__in=['received', 'partial']
    ).aggregate(total=Sum('total'))['total'] or 0

    purchase_change = 0
    if last_month_purchase:
        purchase_change = round(
            ((this_month_purchase - last_month_purchase) / last_month_purchase) * 100, 1
        )

    # ── Profit ────────────────────────────────────────────────
    # Approximate profit: sales revenue - purchase cost for sold items
    sold_items = PharmacySaleItem.objects.filter(
        sale__store=store,
        sale__status__in=['paid', 'partial'],
        sale__sale_date__date__gte=month_start,
    ).select_related('product')

    revenue = sum(item.subtotal for item in sold_items)
    cogs = sum(
        item.product.purchase_price * item.quantity for item in sold_items
    )
    profit = float(revenue) - float(cogs)

    # ── Counts ────────────────────────────────────────────────
    total_customers = PharmacyCustomer.objects.filter(store=store, is_active=True).count()
    total_suppliers = PharmacySupplier.objects.filter(store=store, is_active=True).count()
    total_products = PharmacyProduct.objects.filter(store=store, is_active=True).count()
    total_categories = PharmacyCategory.objects.filter(store=store, is_active=True).count()

    # ── Low stock ─────────────────────────────────────────────
    low_stock_items = (
        PharmacyStock.objects
        .for_store(store)
        .low_stock()
        .select_related('product', 'product__category')
        .order_by('quantity')[:10]
    )

    # ── Near-expiry & expired ─────────────────────────────────
    near_expiry_items = (
        PharmacyStock.objects
        .for_store(store)
        .near_expiry(days=30)
        .select_related('product')
        .order_by('expiry_date')[:10]
    )

    expired_count = PharmacyStock.objects.for_store(store).expired().count()

    # ── Recent sales ──────────────────────────────────────────
    recent_sales = (
        sales_qs
        .select_related('customer', 'biller')
        .prefetch_related('items__product')
        .order_by('-sale_date')[:10]
    )

    # ── Recent purchases ──────────────────────────────────────
    recent_purchases = (
        purchase_qs
        .select_related('supplier', 'created_by')
        .order_by('-purchase_date')[:10]
    )

    # ── Top selling products (last 30 days) ───────────────────
    top_products = (
        PharmacySaleItem.objects
        .filter(
            sale__store=store,
            sale__sale_date__date__gte=thirty_days_ago,
        )
        .values('product__id', 'product__name')
        .annotate(
            total_qty=Sum('quantity'),
            total_revenue=Sum('subtotal'),
        )
        .order_by('-total_qty')[:5]
    )

    # ── Top customers (last 30 days) ──────────────────────────
    top_customers = (
        sales_qs
        .filter(
            sale_date__date__gte=thirty_days_ago,
            customer__isnull=False,
            status__in=['paid', 'partial'],
        )
        .values('customer__id', 'customer__name', 'customer__phone')
        .annotate(
            order_count=Count('id'),
            total_spent=Sum('total'),
        )
        .order_by('-total_spent')[:5]
    )

    # ── Monthly sales chart data (last 6 months) ──────────────
    monthly_sales = []
    monthly_purchases = []
    month_labels = []

    for i in range(5, -1, -1):
        # Calculate month boundaries
        first_of_current = today.replace(day=1)
        target_month = first_of_current - timedelta(days=i * 30)
        m_start = target_month.replace(day=1)
        if m_start.month == 12:
            m_end = m_start.replace(year=m_start.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            m_end = m_start.replace(month=m_start.month + 1, day=1) - timedelta(days=1)

        sale_total = sales_qs.filter(
            sale_date__date__gte=m_start,
            sale_date__date__lte=m_end,
            status__in=['paid', 'partial'],
        ).aggregate(total=Sum('total'))['total'] or 0

        purch_total = purchase_qs.filter(
            purchase_date__gte=m_start,
            purchase_date__lte=m_end,
            status__in=['received', 'partial'],
        ).aggregate(total=Sum('total'))['total'] or 0

        monthly_sales.append(float(sale_total))
        monthly_purchases.append(float(purch_total))
        month_labels.append(m_start.strftime('%b %Y'))

    # ── Top categories ────────────────────────────────────────
    top_categories = (
        PharmacySaleItem.objects
        .filter(
            sale__store=store,
            sale__sale_date__date__gte=thirty_days_ago,
            product__category__isnull=False,
        )
        .values('product__category__id', 'product__category__name')
        .annotate(
            total_qty=Sum('quantity'),
            total_revenue=Sum('subtotal'),
        )
        .order_by('-total_qty')[:5]
    )

    # ── Invoice dues (sales with pending/partial status) ──────
    invoice_due = sales_qs.filter(
        status__in=['pending', 'partial']
    ).aggregate(
        total_due=Sum(F('total') - F('amount_paid'))
    )['total_due'] or 0

    # ── Today's order count for alert ─────────────────────────
    alert_low_stock = (
        PharmacyStock.objects
        .for_store(store)
        .low_stock()
        .select_related('product')
        .first()
    )

    return {
        # Summary cards
        'total_sales': total_sales,
        'total_sale_returns': total_sale_returns,
        'total_purchase': total_purchase,
        'invoice_due': invoice_due,
        'profit': profit,
        'sales_change': sales_change,
        'purchase_change': purchase_change,

        # Today
        'today_sales': today_sales,
        'today_order_count': today_order_count,

        # Counts
        'total_customers': total_customers,
        'total_suppliers': total_suppliers,
        'total_products': total_products,
        'total_categories': total_categories,

        # Stock alerts
        'low_stock_items': low_stock_items,
        'near_expiry_items': near_expiry_items,
        'expired_count': expired_count,
        'alert_low_stock': alert_low_stock,  # For the top alert banner

        # Lists
        'recent_sales': recent_sales,
        'recent_purchases': recent_purchases,
        'top_products': top_products,
        'top_customers': top_customers,
        'top_categories': top_categories,

        # Chart data (JSON-serializable)
        'chart_month_labels': month_labels,
        'chart_monthly_sales': monthly_sales,
        'chart_monthly_purchases': monthly_purchases,
    }




@_require_store
def dashboard(request):
    store = _get_store(request)
    ctx = get_dashboard_stats1(store)
    return render(request, 'pharmacy/dashboard.html', ctx)


# ──────────────────────────────────────────────────────────────────
# CATEGORY  (single-page pattern)
# ──────────────────────────────────────────────────────────────────

@_require_store
def categories(request):
    store = _get_store(request)
    all_categories = PharmacyCategory.objects.filter(store=store).select_related('parent').order_by('name')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            name = request.POST.get('name', '').strip()
            parent_id = request.POST.get('parent') or None
            is_active = request.POST.get('is_active') == 'on'
            image = request.FILES.get('image')
            if not name:
                messages.error(request, 'Name is required.')
            else:
                parent = None
                if parent_id:
                    parent = get_object_or_404(PharmacyCategory, pk=parent_id, store=store)
                PharmacyCategory.objects.create(store=store, name=name, parent=parent, is_active=is_active, image=image)
                messages.success(request, 'Category created successfully.')

        elif action == 'update':
            cat = get_object_or_404(PharmacyCategory, pk=request.POST.get('id'), store=store)
            name = request.POST.get('name', '').strip()
            parent_id = request.POST.get('parent') or None
            image = request.FILES.get('image')
            if not name:
                messages.error(request, 'Name is required.')
            else:
                parent = None
                if parent_id and int(parent_id) != cat.pk:
                    parent = get_object_or_404(PharmacyCategory, pk=parent_id, store=store)
                cat.name = name
                cat.parent = parent
                cat.is_active = request.POST.get('is_active') == 'on'
                cat.image = image if image else cat.image
                cat.save()
                messages.success(request, 'Category updated successfully.')

        elif action == 'delete':
            PharmacyCategory.objects.filter(pk=request.POST.get('id'), store=store).delete()
            messages.success(request, 'Category deleted successfully.')

        return redirect('pharmacy:categories')

    parents = PharmacyCategory.objects.filter(store=store, parent=None)
    return render(request, 'pharmacy/categories.html', {
        'categories': all_categories,
        'parents': parents,
    })



# ──────────────────────────────────────────────────────────────────
# BRAND  (single-page pattern)
# ──────────────────────────────────────────────────────────────────

@_require_store
def brands(request):
    store = _get_store(request)
    all_brands = PharmacyBrand.objects.filter(store=store).order_by('name')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            name = request.POST.get('name', '').strip()
            image = request.FILES.get('image')
            if not name:
                messages.error(request, 'Brand name is required.')
            else:
                PharmacyBrand.objects.get_or_create(store=store, name=name, image=image)
                messages.success(request, 'Brand created successfully.')

        elif action == 'update':
            brand = get_object_or_404(PharmacyBrand, pk=request.POST.get('id'), store=store)
            name = request.POST.get('name', '').strip()
            image = request.FILES.get('image')
            if not name:
                messages.error(request, 'Brand name is required.')
            else:
                brand.name = name
                brand.image = image
                brand.is_active = request.POST.get('is_active') == 'on'
                brand.save()
                messages.success(request, 'Brand updated successfully.')

        elif action == 'delete':
            PharmacyBrand.objects.filter(pk=request.POST.get('id'), store=store).delete()
            messages.success(request, 'Brand deleted successfully.')

        return redirect('pharmacy:brands')

    return render(request, 'pharmacy/brands.html', {'brands': all_brands})



# ──────────────────────────────────────────────────────────────────
# UNIT  (single-page pattern)
# ──────────────────────────────────────────────────────────────────

@_require_store
def units(request):
    store = _get_store(request)
    all_units = PharmacyUnit.objects.filter(store=store).order_by('name')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            name = request.POST.get('name', '').strip()
            short_name = request.POST.get('short_name', '').strip()
            if not name:
                messages.error(request, 'Unit name is required.')
            else:
                PharmacyUnit.objects.get_or_create(store=store, name=name, defaults={'short_name': short_name})
                messages.success(request, 'Unit created successfully.')

        elif action == 'update':
            unit = get_object_or_404(PharmacyUnit, pk=request.POST.get('id'), store=store)
            unit.name = request.POST.get('name', '').strip()
            unit.short_name = request.POST.get('short_name', '').strip()
            unit.save()
            messages.success(request, 'Unit updated successfully.')

        elif action == 'delete':
            PharmacyUnit.objects.filter(pk=request.POST.get('id'), store=store).delete()
            messages.success(request, 'Unit deleted successfully.')

        return redirect('pharmacy:units')

    return render(request, 'pharmacy/units.html', {'units': all_units})


# ──────────────────────────────────────────────────────────────────
# SUPPLIER  (single-page pattern)
# ──────────────────────────────────────────────────────────────────

@_require_store
def suppliers(request):
    store = _get_store(request)
    all_suppliers = PharmacySupplier.objects.filter(store=store).order_by('name')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            name = request.POST.get('name', '').strip()
            if not name:
                messages.error(request, 'Supplier name is required.')
            else:
                PharmacySupplier.objects.create(
                    store=store,
                    name=name,
                    contact_person=request.POST.get('contact_person', '').strip(),
                    email=request.POST.get('email', '').strip(),
                    phone=request.POST.get('phone', '').strip(),
                    address=request.POST.get('address', '').strip(),
                    city=request.POST.get('city', '').strip(),
                    gstin=request.POST.get('gstin', '').strip(),
                    drug_license_no=request.POST.get('drug_license_no', '').strip(),
                )
                messages.success(request, 'Supplier created successfully.')

        elif action == 'update':
            sup = get_object_or_404(PharmacySupplier, pk=request.POST.get('id'), store=store)
            sup.name = request.POST.get('name', '').strip()
            sup.contact_person = request.POST.get('contact_person', '').strip()
            sup.email = request.POST.get('email', '').strip()
            sup.phone = request.POST.get('phone', '').strip()
            sup.address = request.POST.get('address', '').strip()
            sup.city = request.POST.get('city', '').strip()
            sup.gstin = request.POST.get('gstin', '').strip()
            sup.drug_license_no = request.POST.get('drug_license_no', '').strip()
            sup.is_active = request.POST.get('is_active') == 'on'
            sup.save()
            messages.success(request, 'Supplier updated successfully.')

        elif action == 'delete':
            PharmacySupplier.objects.filter(pk=request.POST.get('id'), store=store).delete()
            messages.success(request, 'Supplier deleted successfully.')

        return redirect('pharmacy:suppliers')

    return render(request, 'pharmacy/suppliers.html', {'suppliers': all_suppliers})


# ──────────────────────────────────────────────────────────────────
# CUSTOMER  (single-page pattern)
# ──────────────────────────────────────────────────────────────────

@_require_store
def customers(request):
    store = _get_store(request)
    all_customers = PharmacyCustomer.objects.filter(store=store).order_by('name')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            name = request.POST.get('name', '').strip()
            phone = request.POST.get('phone', '').strip()
            if not name or not phone:
                messages.error(request, 'Name and phone are required.')
            else:
                PharmacyCustomer.objects.get_or_create(
                    store=store, phone=phone,
                    defaults={
                        'name': name,
                        'email': request.POST.get('email', '').strip(),
                        'address': request.POST.get('address', '').strip(),
                        'dob': request.POST.get('dob') or None,
                    }
                )
                messages.success(request, 'Customer created successfully.')

        elif action == 'update':
            cust = get_object_or_404(PharmacyCustomer, pk=request.POST.get('id'), store=store)
            cust.name = request.POST.get('name', '').strip()
            cust.phone = request.POST.get('phone', '').strip()
            cust.email = request.POST.get('email', '').strip()
            cust.address = request.POST.get('address', '').strip()
            cust.dob = request.POST.get('dob') or None
            cust.is_active = request.POST.get('is_active') == 'on'
            cust.save()
            messages.success(request, 'Customer updated successfully.')

        elif action == 'delete':
            PharmacyCustomer.objects.filter(pk=request.POST.get('id'), store=store).delete()
            messages.success(request, 'Customer deleted successfully.')

        return redirect('pharmacy:customers')

    return render(request, 'pharmacy/customers.html', {'customers': all_customers})


# ──────────────────────────────────────────────────────────────────
# PRODUCT
# ──────────────────────────────────────────────────────────────────

def product_list(request):
    store = _get_store(request)

    categories = PharmacyCategory.objects.filter(
        store=store, is_active=True
    ).order_by('name')

    brands = PharmacyBrand.objects.filter(
        store=store, is_active=True
    ).order_by('name')

    units = PharmacyUnit.objects.filter(
        store=store
    ).order_by('name')

    schedules = PharmacyProduct.SCHEDULE_CHOICES

    # Prefetch primary images only
    primary_images = PharmacyProductImage.objects.filter(is_primary=True)

    qs = (
        PharmacyProduct.objects
        .filter(store=store, is_active=True)
        .select_related('category', 'brand', 'unit')
        .prefetch_related(
            Prefetch(
                'images',
                queryset=primary_images,
                to_attr='primary_images'
            )
        )
    )

    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q) |
            Q(sku__icontains=q) |
            Q(barcode__icontains=q)
        )

    paginator = Paginator(qs.order_by('name'), 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'q': q,
        'categories': categories,
        'brands': brands,
        'units': units,
        'schedules': schedules,
    }

    return render(request, 'pharmacy/product_list.html', context)


@_require_store
def product_detail(request, pk):
    store = _get_store(request)

    product = get_object_or_404(
        PharmacyProduct.objects.select_related('category', 'brand', 'unit'),
        pk=pk,
        store=store
    )

    images = [
        {
            "id": img.id,
            "url": img.image.url,
            "is_primary": img.is_primary
        }
        for img in product.images.all()
    ]

    # AJAX request
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({
            "id": product.id,
            "name": product.name,
            "category": product.category_id,
            "brand": product.brand_id,
            "unit": product.unit_id,
            "sku": product.sku,
            "barcode": product.barcode,
            "purchase_price": str(product.purchase_price),
            "selling_price": str(product.selling_price),
            "schedule_type": product.schedule_type,
            "requires_prescription": str(product.requires_prescription),
            "tax_rate": str(product.tax_rate),
            "description": product.description,
            "hsn_code": product.hsn_code,
            "images": images,
        })

    return render(request, 'pharmacy/product_detail.html', {'product': product})


@_require_store
def pharmacy_customer_shop(request):
    """Customer-facing pharmacy product catalog — search, browse by category."""
    store = _get_store(request)

    categories = PharmacyCategory.objects.filter(
        store=store, is_active=True
    ).order_by('name')

    q = request.GET.get('q', '').strip()
    cat_id = request.GET.get('category', '').strip()

    products_qs = (
        PharmacyProduct.objects
        .filter(store=store, is_active=True)
        .select_related('category', 'brand', 'unit')
        .prefetch_related('images')
        .order_by('name')
    )

    if q:
        products_qs = products_qs.filter(
            Q(name__icontains=q) |
            Q(brand__name__icontains=q) |
            Q(description__icontains=q)
        )
    if cat_id:
        products_qs = products_qs.filter(category_id=cat_id)

    selected_category = None
    if cat_id:
        selected_category = PharmacyCategory.objects.filter(pk=cat_id, store=store).first()

    total_count = products_qs.count()
    paginator = Paginator(products_qs, 12)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Build per-product display data (MRP, discount, stock)
    product_data = []
    for p in page_obj:
        sp = p.selling_price or Decimal('0')
        tax = p.tax_rate or Decimal('0')
        if tax > 0:
            mrp = (sp * (Decimal('1') + tax / Decimal('100'))).quantize(Decimal('0.01'))
            disc = int(((mrp - sp) / mrp) * 100)
        else:
            mrp = (sp * Decimal('1.12')).quantize(Decimal('0.01'))
            disc = 12
        stock_qty = p.current_stock
        # primary image
        primary_img = None
        for img in p.images.all():
            if img.is_primary:
                primary_img = img
                break
        if not primary_img:
            imgs = list(p.images.all())
            primary_img = imgs[0] if imgs else None
        product_data.append({
            'product': p,
            'mrp': mrp,
            'discount_pct': disc,
            'in_stock': stock_qty > 0,
            'stock_qty': stock_qty,
            'primary_img': primary_img,
        })

    context = {
        'categories': categories,
        'page_obj': page_obj,
        'product_data': product_data,
        'q': q,
        'cat_id': cat_id,
        'selected_category': selected_category,
        'total_count': total_count,
    }
    return render(request, 'pharmacy/shop.html', context)


@_require_store
def product_detail_modern(request, pk):
    """Customer-facing product detail page with full dynamic data."""
    from datetime import date as today_date
    store = _get_store(request)
    product = get_object_or_404(
        PharmacyProduct.objects.select_related('category', 'brand', 'unit'),
        pk=pk,
        store=store
    )

    # ── Stock batches ──────────────────────────────────────────
    stock_batches = PharmacyStock.objects.filter(
        product=product, store=store
    ).order_by('expiry_date')
    total_stock = stock_batches.aggregate(total=Sum('quantity'))['total'] or 0
    nearest_expiry_batch = stock_batches.filter(
        quantity__gt=0, expiry_date__isnull=False
    ).order_by('expiry_date').first()

    # ── Related products (same category) ──────────────────────
    related_products = []
    if product.category:
        related_products = list(
            PharmacyProduct.objects.filter(
                store=store, category=product.category, is_active=True
            ).exclude(pk=pk).select_related('brand')[:6]
        )

    # ── Sales history for this product ────────────────────────
    recent_sale_items = (
        PharmacySaleItem.objects
        .filter(product=product, sale__store=store)
        .select_related('sale', 'sale__customer')
        .order_by('-sale__sale_date')[:10]
    )
    total_units_sold = (
        PharmacySaleItem.objects
        .filter(product=product, sale__store=store)
        .aggregate(total=Sum('quantity'))['total'] or 0
    )

    # ── MRP & discount (dynamic via tax rate) ─────────────────
    sp = product.selling_price or Decimal('0')
    tax_rate = product.tax_rate or Decimal('0')
    if tax_rate > 0:
        mrp = (sp * (Decimal('1') + tax_rate / Decimal('100'))).quantize(Decimal('0.01'))
        discount_pct = int(((mrp - sp) / mrp) * 100)
    else:
        mrp = (sp * Decimal('1.12')).quantize(Decimal('0.01'))
        discount_pct = 12

    # ── Breadcrumbs ───────────────────────────────────────────
    breadcrumbs = [
        {'name': 'Home', 'url': '/'},
        {'name': 'Pharmacy', 'url': '/pharmacy/'},
    ]
    if product.category:
        breadcrumbs.append({'name': product.category.name, 'url': '#'})
    breadcrumbs.append({'name': product.name, 'url': '#'})

    context = {
        'product': product,
        'breadcrumbs': breadcrumbs,
        'images': product.images.all(),
        'stock_batches': stock_batches,
        'total_stock': total_stock,
        'in_stock': total_stock > 0,
        'nearest_expiry_batch': nearest_expiry_batch,
        'related_products': related_products,
        'recent_sale_items': recent_sale_items,
        'total_units_sold': total_units_sold,
        'mrp': mrp,
        'discount_pct': discount_pct,
        'today': today_date.today(),
    }
    return render(request, 'pharmacy/product_detail_modern.html', context)

@_require_store
def product_create(request):
    store = _get_store(request)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Product name is required.')
        else:
            product = PharmacyProduct.objects.create(
                category_id=request.POST.get('category') or None,
                brand_id=request.POST.get('brand') or None,
                store=store,
                name=name,
                sku=request.POST.get('sku', '').strip(),
                barcode=request.POST.get('barcode', '').strip(),
                purchase_price=_to_decimal(request.POST.get('purchase_price'), 0),
                selling_price=_to_decimal(request.POST.get('selling_price'), 0),
                schedule_type=request.POST.get('schedule_type', 'OTC'),
                description=request.POST.get('description', '').strip(),
                hsn_code=request.POST.get('hsn_code', '').strip(),
                tax_rate=_to_decimal(request.POST.get('tax_rate'), 0),
                requires_prescription=request.POST.get('requires_prescription') == 'on',
                unit_id=request.POST.get('unit') or None,
            )
            images = request.FILES.getlist("images")
            primary_index = request.POST.get('primary_image')

            for index, img in enumerate(images):
                PharmacyProductImage.objects.create(
                product=product,
                image=img,
                is_primary=(str(index) == primary_index)
            )
            
            messages.success(request, 'Product created.')
            return redirect('pharmacy:product_list')
    
    return redirect('pharmacy:product_list')


@_require_store
def product_edit(request):
    store = _get_store(request)
    if request.method == 'POST':
        pk = request.POST.get('id')
        product = get_object_or_404(PharmacyProduct, pk=pk, store=store)
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
            product.requires_prescription = request.POST.get('requires_prescription')
            product.schedule_type = request.POST.get('schedule_type', 'OTC')
            product.category_id = request.POST.get('category') or None
            product.brand_id = request.POST.get('brand') or None
            product.unit_id = request.POST.get('unit') or None
            product.save()

            images = request.FILES.getlist("images")
            primary_image = request.POST.get("primary_image")

            # new uploads
            for img in images:
                PharmacyProductImage.objects.create(
                    product=product,
                    image=img
                )

            # update primary image
            if primary_image:
                PharmacyProductImage.objects.filter(product=product).update(is_primary=False)
                PharmacyProductImage.objects.filter(id=primary_image).update(is_primary=True)


            messages.success(request, 'Product updated.')
            return redirect('pharmacy:product_list')
    
    return redirect('pharmacy:product_list')

@_require_store
def product_image_delete(request, pk):
    store = _get_store(request)
    image = get_object_or_404(PharmacyProductImage, pk=pk, product__store=store)

    image.delete()

    return JsonResponse({"success": True})


@_require_store
@require_POST
def product_delete(request, pk):
    store = _get_store(request)
    product = get_object_or_404(PharmacyProduct, pk=pk, store=store)
    product.is_active = False
    product.save(update_fields=['is_active'])
    messages.success(request, 'Product deactivated.')
    return redirect('pharmacy:product_list')


# ──────────────────────────────────────────────────────────────────
# STOCK VIEWS
# ──────────────────────────────────────────────────────────────────

@_require_store
def manage_stock(request):
    store = _get_store(request)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            product_id = request.POST.get('product')
            batch_no = request.POST.get('batch_no', '').strip()
            quantity = _to_int(request.POST.get('quantity'), 0)
            min_quantity = _to_int(request.POST.get('min_quantity'), 10)
            warehouse = request.POST.get('warehouse', '').strip()
            rack_location = request.POST.get('rack_location', '').strip()
            manufacturing_date = request.POST.get('manufacturing_date') or None
            expiry_date = request.POST.get('expiry_date') or None
            if not product_id or quantity <= 0:
                messages.error(request, 'Product and quantity are required.')
            else:
                PharmacyStock.objects.create(
                    product_id=product_id,
                    store=store,
                    batch_no=batch_no,
                    quantity=quantity,
                    min_quantity=min_quantity,
                    warehouse=warehouse,
                    rack_location=rack_location,
                    manufacturing_date=manufacturing_date,
                    expiry_date=expiry_date,
                )
                messages.success(request, 'Stock added successfully.')

        elif action == 'update':
            stock = get_object_or_404(PharmacyStock, pk=request.POST.get('id'), store=store)
            stock.batch_no = request.POST.get('batch_no', '').strip()
            stock.quantity = _to_int(request.POST.get('quantity'), stock.quantity)
            stock.min_quantity = _to_int(request.POST.get('min_quantity'), stock.min_quantity)
            stock.warehouse = request.POST.get('warehouse', '').strip()
            stock.rack_location = request.POST.get('rack_location', '').strip()
            stock.manufacturing_date = request.POST.get('manufacturing_date') or None
            stock.expiry_date = request.POST.get('expiry_date') or None
            stock.save()
            messages.success(request, 'Stock updated successfully.')

        elif action == 'delete':
            PharmacyStock.objects.filter(pk=request.POST.get('id'), store=store).delete()
            messages.success(request, 'Stock deleted successfully.')

        return redirect('pharmacy:manage_stock')

    stocks = PharmacyStock.objects.for_store(store).select_related('product').order_by('product__name')
    products = PharmacyProduct.objects.filter(store=store, is_active=True).order_by('name')
    return render(request, 'pharmacy/manage_stock.html', {
        'stocks': stocks,
        'products': products,
    })


@_require_store
def low_stocks(request):
    store = _get_store(request)
    stocks = PharmacyStock.objects.for_store(store).low_stock().select_related('product')
    return render(request, 'pharmacy/low_stocks.html', {'stocks': stocks})


@_require_store
def expired_products(request):
    store = _get_store(request)
    stocks = PharmacyStock.objects.for_store(store).expired().select_related('product')
    return render(request, 'pharmacy/expired_products.html', {'stocks': stocks})


@_require_store
def near_expiry(request):
    store = _get_store(request)
    stocks = PharmacyStock.objects.for_store(store).near_expiry(30).select_related('product')
    return render(request, 'pharmacy/near_expiry.html', {'stocks': stocks})


# ──────────────────────────────────────────────────────────────────
# STOCK ADJUSTMENT
# ──────────────────────────────────────────────────────────────────

@_require_store
def stock_adjustment_list(request):
    store = _get_store(request)
    adjustments = (
        PharmacyStockAdjustment.objects
        .filter(stock__store=store)
        .select_related('stock__product', 'adjusted_by')
        .order_by('-date')
    )
    return render(request, 'pharmacy/stock_adjustment_list.html', {'adjustments': adjustments})


@_require_store
def stock_adjustment_create(request):
    store = _get_store(request)
    if request.method == 'POST':
        stock_id = request.POST.get('stock')
        adj_type = request.POST.get('adjustment_type', 'add')
        qty = _to_int(request.POST.get('quantity'), 0)
        reason = request.POST.get('reason', '').strip()
        notes = request.POST.get('notes', '').strip()
        if not stock_id or qty <= 0:
            messages.error(request, 'Valid stock and quantity are required.')
        else:
            stock = get_object_or_404(PharmacyStock, pk=stock_id, store=store)
            with transaction.atomic():
                PharmacyStockAdjustment.objects.create(
                    stock=stock,
                    adjustment_type=adj_type,
                    quantity=qty,
                    reason=reason,
                    notes=notes,
                    adjusted_by=request.user,
                )
                # ── Apply the adjustment to actual stock quantity ──────────────
                if adj_type == 'add':
                    stock.quantity += qty
                elif adj_type in ('remove', 'damage', 'expired', 'return'):
                    stock.quantity = max(0, stock.quantity - qty)
                stock.save(update_fields=['quantity'])
            messages.success(request, 'Stock adjusted.')
            return redirect('pharmacy:stock_adjustment_list')
    stocks = PharmacyStock.objects.for_store(store).select_related('product')
    ctx = {
        'stocks': stocks,
        'adjustment_types': PharmacyStockAdjustment.TYPE_CHOICES,
        'action': 'Create',
    }
    return render(request, 'pharmacy/stock_adjustment_list.html', ctx)


# ──────────────────────────────────────────────────────────────────
# STOCK TRANSFER
# ──────────────────────────────────────────────────────────────────

@_require_store
def stock_transfer_list(request):
    store = _get_store(request)
    transfers = (
        PharmacyStockTransfer.objects
        .filter(Q(from_store=store) | Q(to_store=store))
        .select_related('product', 'from_store', 'to_store', 'transferred_by')
        .order_by('-date')
    )
    return render(request, 'pharmacy/stock_transfer_list.html', {'transfers': transfers})


@_require_store
def stock_transfer_create(request):
    from core.models import Store
    store = _get_store(request)
    if request.method == 'POST':
        product_id = request.POST.get('product')
        to_store_id = request.POST.get('to_store')
        qty = _to_int(request.POST.get('quantity'), 0)
        notes = request.POST.get('notes', '').strip()
        if not product_id or not to_store_id or qty <= 0:
            messages.error(request, 'Product, destination store and quantity are required.')
        else:
            product = get_object_or_404(PharmacyProduct, pk=product_id, store=store)
            to_store = get_object_or_404(Store, pk=to_store_id)
            PharmacyStockTransfer.objects.create(
                product=product,
                from_store=store,
                to_store=to_store,
                quantity=qty,
                transferred_by=request.user,
                notes=notes,
            )
            messages.success(request, 'Transfer created.')
            return redirect('pharmacy:stock_transfer_list')
    ctx = {
        'products': PharmacyProduct.objects.filter(store=store, is_active=True),
        'stores': Store.objects.exclude(pk=store.pk),
        'action': 'Create',
    }
    return render(request, 'pharmacy/stock_transfer_list.html', ctx)


@_require_store
@require_POST
def stock_transfer_complete(request, pk):
    store = _get_store(request)
    transfer = get_object_or_404(PharmacyStockTransfer, pk=pk, from_store=store)
    transfer.status = 'completed'
    transfer.save(update_fields=['status'])
    messages.success(request, 'Transfer marked as completed.')
    return redirect('pharmacy:stock_transfer_list')


# ──────────────────────────────────────────────────────────────────
# PURCHASE
# ──────────────────────────────────────────────────────────────────

@_require_store
def purchase_list(request):
    store = _get_store(request)
    purchases = PharmacyPurchase.objects.filter(store=store).select_related('supplier', 'created_by').order_by('-purchase_date')
    status = PharmacyPurchase.STATUS_CHOICES
    ctx = {
        'purchases': purchases,
        'suppliers': PharmacySupplier.objects.filter(store=store, is_active=True),
        'products': PharmacyProduct.objects.filter(store=store, is_active=True).select_related('unit'),
        'status': status,
    }
    return render(request, 'pharmacy/purchase_list.html', ctx)


@_require_store
def purchase_create(request):
    store = _get_store(request)
    if request.method == 'POST':

        supplier_id = request.POST.get('supplier')
        date_str = request.POST.get('purchase_date') or date.today().isoformat()
        discount = _to_decimal(request.POST.get('discount'), 0)
        notes = request.POST.get('notes', '').strip()
        supplier_invoice = request.POST.get('supplier_invoice_no', '').strip()

        products = request.POST.getlist('product_id')
        quantities = request.POST.getlist('quantity')
        unit_prices = request.POST.getlist('unit_price')
        tax_rates = request.POST.getlist('item_tax_rate')
        batches = request.POST.getlist('batch_no')
        expiry_dates = request.POST.getlist('expiry_date')
        status = request.POST.get('status')

        if date_str:
            purchase_date = datetime.strptime(date_str, "%d-%m-%Y").date()
        else:
            purchase_date = date.today()

        if not supplier_id or not products:
            messages.error(request, 'Supplier and at least one item are required.')
        else:
            with transaction.atomic():
                purchase = PharmacyPurchase.objects.create(
                    store=store,
                    supplier_id=supplier_id,
                    purchase_no=generate_purchase_no(store),
                    supplier_invoice_no=supplier_invoice,
                    purchase_date=purchase_date,
                    discount=discount,
                    notes=notes,
                    created_by=request.user,
                    status=status,
                )
                for i, prod_id in enumerate(products):
                    if not prod_id:
                        continue
                    qty = _to_int(quantities[i] if i < len(quantities) else 0, 0)
                    u_price = _to_decimal(unit_prices[i] if i < len(unit_prices) else 0, 0)
                    t_rate = _to_decimal(tax_rates[i] if i < len(tax_rates) else 0, 0)
                    batch = batches[i].strip() if i < len(batches) else ''
                    exp_date = expiry_dates[i] if i < len(expiry_dates) else None
                    PharmacyPurchaseItem.objects.create(
                        purchase=purchase,
                        product_id=prod_id,
                        quantity=qty,
                        received_qty=qty,
                        unit_price=u_price,
                        tax_rate=t_rate,
                        batch_no=batch,
                        expiry_date=exp_date or None,
                    )
                purchase.recalculate_totals()
            messages.success(request, f'Purchase {purchase.purchase_no} created.')
            return redirect('pharmacy:purchase_list')

    return redirect('pharmacy:purchase_list')

@_require_store
def purchase_detail(request, pk):
    store = _get_store(request)
    purchase = get_object_or_404(
        PharmacyPurchase.objects.select_related('supplier', 'created_by').prefetch_related('items__product'),
        pk=pk, store=store
    )
    return render(request, 'pharmacy/purchase_detail.html', {'purchase': purchase})


@_require_store
@require_POST
def purchase_receive(request):
    store = _get_store(request)
    pk = request.POST.get('pk')
    purchase = get_object_or_404(PharmacyPurchase, pk=pk, store=store)
    new_status = request.POST.get('status') or purchase.status
    old_status = purchase.status
    purchase.status = new_status
    purchase.save()

    # ── Update PharmacyStock when purchase is received (fully or partially) ──
    if new_status in ('received', 'partial') and old_status not in ('received', 'partial'):
        with transaction.atomic():
            for item in purchase.items.select_related('product').all():
                # Each PurchaseItem is a unique batch → get_or_create by batch
                stock, created = PharmacyStock.objects.get_or_create(
                    product=item.product,
                    store=store,
                    batch_no=item.batch_no or '',
                    defaults={
                        'quantity': 0,
                        'expiry_date': item.expiry_date,
                    }
                )
                # Add received quantity to existing stock
                stock.quantity += item.received_qty
                if item.expiry_date:
                    stock.expiry_date = item.expiry_date
                stock.save(update_fields=['quantity', 'expiry_date'])

    # ── Reverse stock when purchase goes back to draft or cancelled (was previously received) ──
    elif new_status in ('draft', 'cancelled') and old_status in ('received', 'partial'):
        with transaction.atomic():
            for item in purchase.items.select_related('product').all():
                try:
                    stock = PharmacyStock.objects.get(
                        product=item.product,
                        store=store,
                        batch_no=item.batch_no or '',
                    )
                    stock.quantity = max(0, stock.quantity - item.received_qty)
                    stock.save(update_fields=['quantity'])
                except PharmacyStock.DoesNotExist:
                    pass  # stock was already removed or never existed

    messages.success(request, f'Purchase {purchase.purchase_no} marked as {purchase.status}.')
    return redirect('pharmacy:purchase_list')

@require_POST
@_require_store
def purchase_delete(request):
    store = _get_store(request)
    pk = request.POST.get('pk')
    purchase = get_object_or_404(PharmacyPurchase, pk=pk, store=store)
    purchase.delete()
    messages.success(request, f'Purchase {purchase.purchase_no} deleted.')
    return redirect('pharmacy:purchase_list')


# ──────────────────────────────────────────────────────────────────
# SALE / POS
# ──────────────────────────────────────────────────────────────────

@_require_store
def sale_list(request):
    store = _get_store(request)
    sales = PharmacySale.objects.filter(store=store).select_related('customer', 'biller').order_by('-sale_date')
    return render(request, 'pharmacy/sale_list.html', {'sales': sales})


@_require_store
def sale_detail(request, pk):
    store = _get_store(request)
    sale = get_object_or_404(
        PharmacySale.objects.select_related('customer', 'biller').prefetch_related('items__product'),
        pk=pk, store=store
    )

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        items_data = [
            {
                'name': item.product.name,
                'price': float(item.unit_price),
                'qty': item.quantity,
                'tax': float(item.tax_rate),
                'total': float(item.subtotal + item.tax_amount)
            }
            for item in sale.items.all()
        ]
        return JsonResponse({
            'success': True,
            'sale': {
                'id': sale.id,
                'sale_no': sale.sale_no,
                'customer': sale.customer.name if sale.customer else 'Walk-in Customer',
                'date': sale.sale_date.strftime("%d-%m-%Y %H:%M"),
                'subtotal': float(sale.subtotal),
                'discount': float(sale.discount),
                'tax_amount': float(sale.tax_amount),
                'total': float(sale.total),
                'amount_paid': float(sale.amount_paid),
                'balance_due': float(sale.balance_due),
                'items': items_data
            }
        })

    return render(request, 'pharmacy/sale_detail.html', {'sale': sale})


# views.py  — updated pos() view
# Add 'categories' to the context so the template can render category pills.

@_require_store
def pos(request):
    """POS View – GET renders the POS terminal; POST creates the sale."""
    store = _get_store(request)

    if request.method == 'POST':
        customer_id    = request.POST.get('customer') or None
        discount       = _to_decimal(request.POST.get('discount'), 0)
        payment_method = request.POST.get('payment_method', 'cash')
        amount_paid    = _to_decimal(request.POST.get('amount_paid'), 0)
        notes          = request.POST.get('notes', '').strip()

        product_ids = request.POST.getlist('product_id')
        quantities  = request.POST.getlist('sale_qty')
        unit_prices = request.POST.getlist('sale_price')
        tax_rates   = request.POST.getlist('sale_tax_rate')

        if not product_ids:
            messages.error(request, 'Add at least one item.')
        else:
            with transaction.atomic():
                sale = PharmacySale.objects.create(
                    store=store,
                    customer_id=customer_id,
                    biller=request.user,
                    sale_no=generate_sale_no(store),
                    discount=discount,
                    payment_method=payment_method,
                    amount_paid=amount_paid,
                    notes=notes,
                )
                for i, prod_id in enumerate(product_ids):
                    if not prod_id:
                        continue
                    qty     = _to_int(quantities[i] if i < len(quantities) else 1, 1)
                    u_price = _to_decimal(unit_prices[i] if i < len(unit_prices) else 0, 0)
                    t_rate  = _to_decimal(tax_rates[i] if i < len(tax_rates) else 0, 0)

                    # FIFO stock deduction
                    batches = (
                        PharmacyStock.objects
                        .filter(product_id=prod_id, store=store, quantity__gt=0)
                        .order_by('expiry_date', 'created_at')
                    )
                    remaining   = qty
                    first_stock = None
                    for batch in batches:
                        if remaining <= 0:
                            break
                        deduct = min(batch.quantity, remaining)
                        batch.quantity -= deduct
                        batch.save(update_fields=['quantity'])
                        remaining -= deduct
                        if first_stock is None:
                            first_stock = batch

                    PharmacySaleItem.objects.create(
                        sale=sale,
                        product_id=prod_id,
                        stock=first_stock,
                        quantity=qty,
                        unit_price=u_price,
                        tax_rate=t_rate,
                    )

                sale.recalculate_totals()
                sale.status = 'paid' if amount_paid >= sale.total else 'partial'
                sale.save(update_fields=['status'])

            messages.success(request, f'Sale {sale.sale_no} completed.')
            return redirect('pharmacy:sale_detail', pk=sale.pk)

    # ── GET: build context ──────────────────────────────────────────────────
    products = (
        PharmacyProduct.objects
        .filter(store=store, is_active=True)
        .select_related('unit', 'brand', 'category')
        .prefetch_related('images', 'stocks')
        .order_by('name')
    )

    # Top-level (parent=None) active categories that have at least one product
    categories = (
        PharmacyCategory.objects
        .filter(store=store, is_active=True, parent=None)
        .prefetch_related('children__products')
        .order_by('name')
    )

    print("children", categories)
    for category in categories:
        print("category", category.children.all())

        for child in category.children.all():
            print("child", child)
            for product in child.products.all():
                print("product", product)

    ctx = {
        'products':        products,
        'categories':      categories,
        'customers':       PharmacyCustomer.objects.filter(store=store, is_active=True),
        'payment_methods': PharmacySale.PAYMENT_METHOD_CHOICES,
    }
    return render(request, 'pharmacy/pos.html', ctx)


# @_require_store
# def pos(request):
#     """POS View – GET renders the POS terminal; POST creates the sale."""
#     store = _get_store(request)
#     if request.method == 'POST':
#         customer_id = request.POST.get('customer') or None
#         discount = _to_decimal(request.POST.get('discount'), 0)
#         payment_method = request.POST.get('payment_method', 'cash')
#         amount_paid = _to_decimal(request.POST.get('amount_paid'), 0)
#         notes = request.POST.get('notes', '').strip()

#         product_ids = request.POST.getlist('product_id')
#         quantities = request.POST.getlist('sale_qty')
#         unit_prices = request.POST.getlist('sale_price')
#         tax_rates = request.POST.getlist('sale_tax_rate')

#         if not product_ids:
#             messages.error(request, 'Add at least one item.')
#         else:
#             with transaction.atomic():
#                 sale = PharmacySale.objects.create(
#                     store=store,
#                     customer_id=customer_id,
#                     biller=request.user,
#                     sale_no=generate_sale_no(store),
#                     discount=discount,
#                     payment_method=payment_method,
#                     amount_paid=amount_paid,
#                     notes=notes,
#                 )
#                 for i, prod_id in enumerate(product_ids):
#                     if not prod_id:
#                         continue
#                     qty = _to_int(quantities[i] if i < len(quantities) else 1, 1)
#                     u_price = _to_decimal(unit_prices[i] if i < len(unit_prices) else 0, 0)
#                     t_rate = _to_decimal(tax_rates[i] if i < len(tax_rates) else 0, 0)

#                     # ── FIFO stock deduction ───────────────────────────────────
#                     # Pick batches ordered by earliest expiry_date first (FIFO)
#                     # then by oldest creation first for batches without expiry
#                     batches = (
#                         PharmacyStock.objects
#                         .filter(product_id=prod_id, store=store, quantity__gt=0)
#                         .order_by('expiry_date', 'created_at')
#                     )
#                     remaining = qty
#                     first_stock = None  # track first batch used for SaleItem FK
#                     for batch in batches:
#                         if remaining <= 0:
#                             break
#                         deduct = min(batch.quantity, remaining)
#                         batch.quantity -= deduct
#                         batch.save(update_fields=['quantity'])
#                         remaining -= deduct
#                         if first_stock is None:
#                             first_stock = batch
#                     # ─────────────────────────────────────────────────────────

#                     PharmacySaleItem.objects.create(
#                         sale=sale,
#                         product_id=prod_id,
#                         stock=first_stock,   # link to first FIFO batch used
#                         quantity=qty,
#                         unit_price=u_price,
#                         tax_rate=t_rate,
#                     )
#                 sale.recalculate_totals()
#                 sale.status = 'paid' if amount_paid >= sale.total else 'partial'
#                 sale.save(update_fields=['status'])
#             messages.success(request, f'Sale {sale.sale_no} completed.')
#             return redirect('pharmacy:sale_detail', pk=sale.pk)

#     ctx = {
#         'products': PharmacyProduct.objects.filter(store=store, is_active=True).select_related('unit'),
#         'customers': PharmacyCustomer.objects.filter(store=store, is_active=True),
#         'payment_methods': PharmacySale.PAYMENT_METHOD_CHOICES,
#     }
#     return render(request, 'pharmacy/pos.html', ctx)


# ──────────────────────────────────────────────────────────────────
# SALE RETURN
# ──────────────────────────────────────────────────────────────────

@_require_store
def sale_return_create(request, sale_pk):
    store = _get_store(request)
    sale = get_object_or_404(PharmacySale, pk=sale_pk, store=store)
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        refund_method = request.POST.get('refund_method', 'cash')
        product_ids = request.POST.getlist('return_product_id')
        quantities = request.POST.getlist('return_qty')
        unit_prices = request.POST.getlist('return_unit_price')
        if not product_ids or not reason:
            messages.error(request, 'Reason and items are required.')
        else:
            with transaction.atomic():
                sale_return = PharmacySaleReturn.objects.create(
                    sale=sale,
                    return_no=generate_return_no(store),
                    reason=reason,
                    refund_method=refund_method,
                    processed_by=request.user,
                )
                total = Decimal('0')
                for i, prod_id in enumerate(product_ids):
                    if not prod_id:
                        continue
                    qty = _to_int(quantities[i] if i < len(quantities) else 0, 0)
                    price = _to_decimal(unit_prices[i] if i < len(unit_prices) else 0, 0)
                    item = PharmacySaleReturnItem.objects.create(
                        sale_return=sale_return,
                        product_id=prod_id,
                        quantity=qty,
                        unit_price=price,
                    )
                    total += item.subtotal
                sale_return.total_refund = total
                sale_return.save(update_fields=['total_refund'])
            messages.success(request, f'Return {sale_return.return_no} created.')
            return redirect('pharmacy:sale_detail', pk=sale_pk)
    ctx = {
        'sale': sale,
        'refund_methods': PharmacySaleReturn.REFUND_METHOD_CHOICES,
    }
    return render(request, 'pharmacy/sale_list.html', ctx)


# ──────────────────────────────────────────────────────────────────
# AJAX / API endpoints
# ──────────────────────────────────────────────────────────────────

@_require_store
def product_search_api(request):
    store = _get_store(request)
    q = request.GET.get('q', '').strip()
    products = PharmacyProduct.objects.filter(store=store, is_active=True)
    if q:
        products = products.filter(Q(name__icontains=q) | Q(sku__icontains=q) | Q(barcode__icontains=q))
    data = [
        {
            'id': p.id,
            'name': p.name,
            'sku': p.sku,
            'selling_price': float(p.selling_price),
            'tax_rate': float(p.tax_rate),
            'stock': p.current_stock,
        }
        for p in products[:20]
    ]
    return JsonResponse({'results': data})


@_require_store
def stock_check_api(request):
    store = _get_store(request)
    product_id = request.GET.get('product_id')
    if not product_id:
        return JsonResponse({'error': 'product_id is required'}, status=400)
    product = get_object_or_404(PharmacyProduct, pk=product_id, store=store)
    return JsonResponse({'product_id': product.id, 'stock': product.current_stock})


# ──────────────────────────────────────────────────────────────────
# REPORTS
# ──────────────────────────────────────────────────────────────────

@_require_store
def report_sales(request):
    store = _get_store(request)
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    sales = PharmacySale.objects.filter(store=store)
    if date_from:
        sales = sales.filter(sale_date__date__gte=date_from)
    if date_to:
        sales = sales.filter(sale_date__date__lte=date_to)
    total = sales.aggregate(total=Sum('total'))['total'] or 0
    return render(request, 'pharmacy/reports/sales_report.html', {
        'sales': sales.order_by('-sale_date'),
        'total_sales': total,
    })


@_require_store
def report_purchases(request):
    store = _get_store(request)
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    purchases = PharmacyPurchase.objects.filter(store=store)
    if date_from:
        purchases = purchases.filter(purchase_date__gte=date_from)
    if date_to:
        purchases = purchases.filter(purchase_date__lte=date_to)
    total = purchases.aggregate(total=Sum('total'))['total'] or 0
    return render(request, 'pharmacy/reports/purchase_report.html', {
        'purchases': purchases.order_by('-purchase_date'),
        'total_purchases': total,
    })


@_require_store
def report_inventory(request):
    store = _get_store(request)
    stocks = PharmacyStock.objects.for_store(store).select_related('product')
    return render(request, 'pharmacy/reports/inventory_report.html', {'stocks': stocks})


@_require_store
def report_expiry(request):
    store = _get_store(request)
    days = _to_int(request.GET.get('days'), 90)
    stocks = PharmacyStock.objects.for_store(store).near_expiry(days).select_related('product')
    return render(request, 'pharmacy/reports/expiry_report.html', {'stocks': stocks, 'days': days})


@_require_store
def report_stock_history(request):
    store = _get_store(request)
    adjustments = (
        PharmacyStockAdjustment.objects
        .filter(stock__store=store)
        .select_related('stock__product', 'adjusted_by')
        .order_by('-date')
    )
    return render(request, 'pharmacy/reports/stock_history.html', {'adjustments': adjustments})
