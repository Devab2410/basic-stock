"""
Ecommerce app – utility helpers.
"""
from datetime import date
from decimal import Decimal

from django.db.models import Sum


def generate_order_no(store):
    """Generate sequential order number: ECO-{store_code}-{year}-{seq:05d}"""
    from .models import EcommerceOrder
    year = date.today().year
    prefix = f"ECO-{store.store_code}-{year}-"
    last = (
        EcommerceOrder.objects.filter(order_no__startswith=prefix)
        .order_by('-order_no')
        .values_list('order_no', flat=True)
        .first()
    )
    seq = 1
    if last:
        try:
            seq = int(last.split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    return f"{prefix}{seq:05d}"


def get_dashboard_stats(store):
    """Return KPI dict for ecommerce dashboard."""
    from .models import EcommerceProduct, EcommerceOrder, EcommerceReview
    today = date.today()
    stats = {
        'total_products': EcommerceProduct.objects.filter(store=store, is_active=True).count(),
        'featured_products': EcommerceProduct.objects.filter(store=store, is_featured=True, is_active=True).count(),
        'total_orders': EcommerceOrder.objects.filter(store=store).count(),
        'pending_orders': EcommerceOrder.objects.filter(store=store, status='pending').count(),
        'processing_orders': EcommerceOrder.objects.filter(store=store, status='processing').count(),
        'today_revenue': (
            EcommerceOrder.objects.filter(store=store, created_at__date=today, payment_status='paid')
            .aggregate(t=Sum('total'))['t'] or Decimal('0')
        ),
        'pending_reviews': EcommerceReview.objects.filter(store=store, is_approved=False).count(),
    }
    return stats
