"""
Ecommerce app – 100% function-based views, raw request.POST (no Django Forms).
Every view requires login + a staff profile on the active store.
"""
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum, Avg
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import (
    EcommerceBrand,
    EcommerceCart,
    EcommerceCartItem,
    EcommerceCategory,
    EcommerceCustomer,
    EcommerceOrder,
    EcommerceOrderItem,
    EcommerceProduct,
    EcommerceProductImage,
    EcommerceProductVariant,
    EcommerceReview,
)
from .utils import generate_order_no, get_dashboard_stats


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def _get_store(request):
    return request.user.active_store


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
    return render(request, 'ecommerce/dashboard.html', ctx)


# ──────────────────────────────────────────────────────────────────
# CATEGORY
# ──────────────────────────────────────────────────────────────────

@_require_store
def categories(request):
    store = _get_store(request)
    all_categories = EcommerceCategory.objects.filter(store=store).select_related('parent').order_by('name')
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
                    parent = get_object_or_404(EcommerceCategory, pk=parent_id, store=store)
                EcommerceCategory.objects.create(store=store, name=name, parent=parent,
                                                 is_active=request.POST.get('is_active') == 'on')
                messages.success(request, 'Category created.')
        elif action == 'update':
            cat = get_object_or_404(EcommerceCategory, pk=request.POST.get('id'), store=store)
            name = request.POST.get('name', '').strip()
            parent_id = request.POST.get('parent') or None
            if not name:
                messages.error(request, 'Name is required.')
            else:
                parent = None
                if parent_id and int(parent_id) != cat.pk:
                    parent = get_object_or_404(EcommerceCategory, pk=parent_id, store=store)
                cat.name = name
                cat.parent = parent
                cat.is_active = request.POST.get('is_active') == 'on'
                cat.save()
                messages.success(request, 'Category updated.')
        elif action == 'delete':
            EcommerceCategory.objects.filter(pk=request.POST.get('id'), store=store).delete()
            messages.success(request, 'Category deleted.')
        return redirect('ecommerce:categories')
    parents = EcommerceCategory.objects.filter(store=store, parent=None)
    return render(request, 'ecommerce/categories.html', {
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
    all_brands = EcommerceBrand.objects.filter(store=store).order_by('name')
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create':
            name = request.POST.get('name', '').strip()
            if not name:
                messages.error(request, 'Brand name is required.')
            else:
                EcommerceBrand.objects.get_or_create(store=store, name=name)
                messages.success(request, 'Brand created.')
        elif action == 'update':
            brand = get_object_or_404(EcommerceBrand, pk=request.POST.get('id'), store=store)
            brand.name = request.POST.get('name', '').strip()
            brand.is_active = request.POST.get('is_active') == 'on'
            brand.save()
            messages.success(request, 'Brand updated.')
        elif action == 'delete':
            EcommerceBrand.objects.filter(pk=request.POST.get('id'), store=store).delete()
            messages.success(request, 'Brand deleted.')
        return redirect('ecommerce:brands')
    return render(request, 'ecommerce/brands.html', {'brands': all_brands})


def brand_list(request):
    return brands(request)


# ──────────────────────────────────────────────────────────────────
# PRODUCT
# ──────────────────────────────────────────────────────────────────

@_require_store
def product_list(request):
    store = _get_store(request)
    qs = EcommerceProduct.objects.filter(store=store, is_active=True).select_related('category', 'brand')
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(sku__icontains=q))
    featured_only = request.GET.get('featured')
    if featured_only:
        qs = qs.filter(is_featured=True)
    paginator = Paginator(qs.order_by('name'), 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'ecommerce/product_list.html', {'page_obj': page_obj, 'q': q})


@_require_store
def product_detail(request, pk):
    store = _get_store(request)
    product = get_object_or_404(
        EcommerceProduct.objects.select_related('category', 'brand')
                                .prefetch_related('variants', 'images', 'reviews'),
        pk=pk, store=store
    )
    avg_rating = product.reviews.filter(is_approved=True).aggregate(avg=Avg('rating'))['avg']
    return render(request, 'ecommerce/product_detail.html', {'product': product, 'avg_rating': avg_rating})


@_require_store
def product_create(request):
    store = _get_store(request)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Product name is required.')
        else:
            product = EcommerceProduct.objects.create(
                store=store,
                name=name,
                sku=request.POST.get('sku', '').strip(),
                description=request.POST.get('description', '').strip(),
                purchase_price=_to_decimal(request.POST.get('purchase_price'), 0),
                selling_price=_to_decimal(request.POST.get('selling_price'), 0),
                compare_price=_to_decimal(request.POST.get('compare_price'), 0),
                tax_rate=_to_decimal(request.POST.get('tax_rate'), 0),
                is_featured=request.POST.get('is_featured') == 'on',
                meta_title=request.POST.get('meta_title', '').strip(),
                meta_description=request.POST.get('meta_description', '').strip(),
                category_id=request.POST.get('category') or None,
                brand_id=request.POST.get('brand') or None,
            )
            messages.success(request, 'Product created.')
            return redirect('ecommerce:product_detail', pk=product.pk)
    ctx = {
        'categories': EcommerceCategory.objects.filter(store=store, is_active=True),
        'brands': EcommerceBrand.objects.filter(store=store, is_active=True),
        'action': 'Create',
    }
    return render(request, 'ecommerce/product_form.html', ctx)


@_require_store
def product_edit(request, pk):
    store = _get_store(request)
    product = get_object_or_404(EcommerceProduct, pk=pk, store=store)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Product name is required.')
        else:
            product.name = name
            product.sku = request.POST.get('sku', '').strip()
            product.description = request.POST.get('description', '').strip()
            product.purchase_price = _to_decimal(request.POST.get('purchase_price'), 0)
            product.selling_price = _to_decimal(request.POST.get('selling_price'), 0)
            product.compare_price = _to_decimal(request.POST.get('compare_price'), 0)
            product.tax_rate = _to_decimal(request.POST.get('tax_rate'), 0)
            product.is_featured = request.POST.get('is_featured') == 'on'
            product.meta_title = request.POST.get('meta_title', '').strip()
            product.meta_description = request.POST.get('meta_description', '').strip()
            product.category_id = request.POST.get('category') or None
            product.brand_id = request.POST.get('brand') or None
            product.save()
            messages.success(request, 'Product updated.')
            return redirect('ecommerce:product_detail', pk=product.pk)
    ctx = {
        'product': product,
        'categories': EcommerceCategory.objects.filter(store=store, is_active=True),
        'brands': EcommerceBrand.objects.filter(store=store, is_active=True),
        'action': 'Edit',
    }
    return render(request, 'ecommerce/product_form.html', ctx)


@_require_store
@require_POST
def product_delete(request, pk):
    store = _get_store(request)
    product = get_object_or_404(EcommerceProduct, pk=pk, store=store)
    product.is_active = False
    product.save(update_fields=['is_active'])
    messages.success(request, 'Product deactivated.')
    return redirect('ecommerce:product_list')


# ──────────────────────────────────────────────────────────────────
# PRODUCT VARIANTS
# ──────────────────────────────────────────────────────────────────

@_require_store
def variant_create(request, product_pk):
    store = _get_store(request)
    product = get_object_or_404(EcommerceProduct, pk=product_pk, store=store)
    if request.method == 'POST':
        sku = request.POST.get('sku', '').strip()
        attr_name = request.POST.get('attribute_name', '').strip()
        attr_value = request.POST.get('attribute_value', '').strip()
        if not sku or not attr_name or not attr_value:
            messages.error(request, 'SKU, attribute name and value are required.')
        else:
            EcommerceProductVariant.objects.create(
                product=product,
                sku=sku,
                attribute_name=attr_name,
                attribute_value=attr_value,
                price_modifier=_to_decimal(request.POST.get('price_modifier'), 0),
                stock=_to_int(request.POST.get('stock'), 0),
            )
            messages.success(request, 'Variant added.')
            return redirect('ecommerce:product_detail', pk=product_pk)
    return render(request, 'ecommerce/variant_form.html', {'product': product, 'action': 'Create'})


@_require_store
def variant_edit(request, pk):
    store = _get_store(request)
    variant = get_object_or_404(EcommerceProductVariant, pk=pk, product__store=store)
    product = variant.product
    if request.method == 'POST':
        attr_value = request.POST.get('attribute_value', '').strip()
        if not attr_value:
            messages.error(request, 'Attribute value is required.')
        else:
            variant.attribute_value = attr_value
            variant.price_modifier = _to_decimal(request.POST.get('price_modifier'), 0)
            variant.stock = _to_int(request.POST.get('stock'), 0)
            variant.save()
            messages.success(request, 'Variant updated.')
            return redirect('ecommerce:product_detail', pk=product.pk)
    return render(request, 'ecommerce/variant_form.html', {'product': product, 'variant': variant, 'action': 'Edit'})


@_require_store
@require_POST
def variant_delete(request, pk):
    store = _get_store(request)
    variant = get_object_or_404(EcommerceProductVariant, pk=pk, product__store=store)
    product_pk = variant.product_id
    variant.delete()
    messages.success(request, 'Variant removed.')
    return redirect('ecommerce:product_detail', pk=product_pk)


# ──────────────────────────────────────────────────────────────────
# ORDERS
# ──────────────────────────────────────────────────────────────────

@_require_store
def order_list(request):
    store = _get_store(request)
    qs = EcommerceOrder.objects.filter(store=store).select_related('customer').order_by('-created_at')
    status_filter = request.GET.get('status')
    if status_filter:
        qs = qs.filter(status=status_filter)
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'ecommerce/order_list.html', {
        'page_obj': page_obj,
        'status_choices': EcommerceOrder.STATUS_CHOICES,
        'current_status': status_filter,
    })


@_require_store
def order_detail(request, pk):
    store = _get_store(request)
    order = get_object_or_404(
        EcommerceOrder.objects.select_related('customer')
                              .prefetch_related('items__product', 'items__variant'),
        pk=pk, store=store
    )
    return render(request, 'ecommerce/order_detail.html', {'order': order})


@_require_store
def order_create(request):
    """Manual order creation by staff."""
    store = _get_store(request)
    if request.method == 'POST':
        customer_id = request.POST.get('customer') or None
        shipping_address = request.POST.get('shipping_address', '').strip()
        billing_address = request.POST.get('billing_address', '').strip()
        payment_method = request.POST.get('payment_method', 'cod')
        shipping_fee = _to_decimal(request.POST.get('shipping_fee'), 0)
        discount = _to_decimal(request.POST.get('discount'), 0)

        product_ids = request.POST.getlist('product_id')
        variant_ids = request.POST.getlist('variant_id')
        quantities = request.POST.getlist('quantity')
        unit_prices = request.POST.getlist('unit_price')

        if not product_ids or not shipping_address:
            messages.error(request, 'Shipping address and at least one product are required.')
        else:
            with transaction.atomic():
                order = EcommerceOrder.objects.create(
                    store=store,
                    customer_id=customer_id,
                    order_no=generate_order_no(store),
                    shipping_address=shipping_address,
                    billing_address=billing_address or shipping_address,
                    payment_method=payment_method,
                    shipping_fee=shipping_fee,
                    discount=discount,
                )
                subtotal = Decimal('0')
                for i, prod_id in enumerate(product_ids):
                    if not prod_id:
                        continue
                    qty = _to_int(quantities[i] if i < len(quantities) else 1, 1)
                    u_price = _to_decimal(unit_prices[i] if i < len(unit_prices) else 0, 0)
                    variant_id = variant_ids[i] if i < len(variant_ids) else ''
                    item = EcommerceOrderItem.objects.create(
                        order=order,
                        product_id=prod_id,
                        variant_id=variant_id or None,
                        quantity=qty,
                        unit_price=u_price,
                    )
                    subtotal += item.subtotal
                tax_rate = _to_decimal(request.POST.get('tax_rate'), 0)
                tax_amount = (subtotal * tax_rate / 100).quantize(Decimal('0.01'))
                order.subtotal = subtotal
                order.tax_amount = tax_amount
                order.total = subtotal + tax_amount + shipping_fee - discount
                order.save(update_fields=['subtotal', 'tax_amount', 'total'])
            messages.success(request, f'Order {order.order_no} created.')
            return redirect('ecommerce:order_detail', pk=order.pk)

    ctx = {
        'products': EcommerceProduct.objects.filter(store=store, is_active=True)
                                            .prefetch_related('variants'),
        'customers': EcommerceCustomer.objects.filter(store=store),
    }
    return render(request, 'ecommerce/order_form.html', ctx)


@_require_store
@require_POST
def order_update_status(request, pk):
    store = _get_store(request)
    order = get_object_or_404(EcommerceOrder, pk=pk, store=store)
    new_status = request.POST.get('status')
    valid = [s[0] for s in EcommerceOrder.STATUS_CHOICES]
    if new_status not in valid:
        messages.error(request, 'Invalid status.')
    else:
        order.status = new_status
        tracking_no = request.POST.get('tracking_no', '').strip()
        if tracking_no:
            order.tracking_no = tracking_no
        order.save()
        messages.success(request, f'Order status updated to {new_status}.')
    return redirect('ecommerce:order_detail', pk=pk)


@_require_store
@require_POST
def order_update_payment(request, pk):
    store = _get_store(request)
    order = get_object_or_404(EcommerceOrder, pk=pk, store=store)
    payment_status = request.POST.get('payment_status')
    if payment_status in ('pending', 'paid', 'failed'):
        order.payment_status = payment_status
        order.save(update_fields=['payment_status'])
        messages.success(request, f'Payment status updated to {payment_status}.')
    else:
        messages.error(request, 'Invalid payment status.')
    return redirect('ecommerce:order_detail', pk=pk)


# ──────────────────────────────────────────────────────────────────
# CUSTOMERS
# ──────────────────────────────────────────────────────────────────

@_require_store
def customer_list(request):
    store = _get_store(request)
    customers = EcommerceCustomer.objects.filter(store=store).select_related('user').order_by('user__username')
    return render(request, 'ecommerce/customer_list.html', {'customers': customers})


@_require_store
def customer_detail(request, pk):
    store = _get_store(request)
    customer = get_object_or_404(EcommerceCustomer, pk=pk, store=store)
    orders = EcommerceOrder.objects.filter(store=store, customer=customer).order_by('-created_at')
    return render(request, 'ecommerce/customer_detail.html', {'customer': customer, 'orders': orders})


# ──────────────────────────────────────────────────────────────────
# REVIEWS
# ──────────────────────────────────────────────────────────────────

@_require_store
def review_list(request):
    store = _get_store(request)
    approved_filter = request.GET.get('approved')
    reviews = (
        EcommerceReview.objects.filter(store=store)
        .select_related('product', 'customer__user')
        .order_by('-created_at')
    )
    if approved_filter == 'pending':
        reviews = reviews.filter(is_approved=False)
    elif approved_filter == 'approved':
        reviews = reviews.filter(is_approved=True)
    return render(request, 'ecommerce/review_list.html', {'reviews': reviews})


@_require_store
@require_POST
def review_approve(request, pk):
    store = _get_store(request)
    review = get_object_or_404(EcommerceReview, pk=pk, store=store)
    review.is_approved = True
    review.save(update_fields=['is_approved'])
    messages.success(request, 'Review approved.')
    return redirect('ecommerce:review_list')


@_require_store
@require_POST
def review_delete(request, pk):
    store = _get_store(request)
    review = get_object_or_404(EcommerceReview, pk=pk, store=store)
    review.delete()
    messages.success(request, 'Review deleted.')
    return redirect('ecommerce:review_list')


# ──────────────────────────────────────────────────────────────────
# AJAX / API endpoints
# ──────────────────────────────────────────────────────────────────

@_require_store
def product_search_api(request):
    store = _get_store(request)
    q = request.GET.get('q', '').strip()
    products = EcommerceProduct.objects.filter(store=store, is_active=True)
    if q:
        products = products.filter(Q(name__icontains=q) | Q(sku__icontains=q))
    data = [
        {
            'id': p.id,
            'name': p.name,
            'sku': p.sku,
            'selling_price': float(p.selling_price),
            'compare_price': float(p.compare_price),
            'tax_rate': float(p.tax_rate),
            'has_variants': p.variants.exists(),
        }
        for p in products[:20]
    ]
    return JsonResponse({'results': data})


@_require_store
def product_variants_api(request, pk):
    store = _get_store(request)
    product = get_object_or_404(EcommerceProduct, pk=pk, store=store)
    variants = list(product.variants.values('id', 'attribute_name', 'attribute_value', 'price_modifier', 'stock'))
    return JsonResponse({'variants': variants})


# ──────────────────────────────────────────────────────────────────
# REPORTS
# ──────────────────────────────────────────────────────────────────

@_require_store
def report_orders(request):
    store = _get_store(request)
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    orders = EcommerceOrder.objects.filter(store=store)
    if date_from:
        orders = orders.filter(created_at__date__gte=date_from)
    if date_to:
        orders = orders.filter(created_at__date__lte=date_to)
    total_revenue = orders.filter(payment_status='paid').aggregate(t=Sum('total'))['t'] or 0
    return render(request, 'ecommerce/reports/orders_report.html', {
        'orders': orders.order_by('-created_at'),
        'total_revenue': total_revenue,
    })


@_require_store
def report_inventory(request):
    store = _get_store(request)
    products = (
        EcommerceProduct.objects.filter(store=store, is_active=True)
        .prefetch_related('variants')
        .order_by('name')
    )
    return render(request, 'ecommerce/reports/inventory_report.html', {'products': products})


@_require_store
def report_reviews(request):
    store = _get_store(request)
    products = (
        EcommerceProduct.objects.filter(store=store, is_active=True)
        .annotate(avg_rating=Avg('reviews__rating'))
        .order_by('name')
    )
    return render(request, 'ecommerce/reports/reviews_report.html', {'products': products})
