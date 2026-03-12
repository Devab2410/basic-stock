"""
Grocery app – utility helpers.
"""
from datetime import date
from decimal import Decimal

from django.db.models import Sum


def generate_purchase_no(store):
    """Generate sequential purchase number: GRO-{store_code}-{year}-{seq:05d}"""
    from .models import GroceryPurchase
    year = date.today().year
    prefix = f"GRO-{store.store_code}-{year}-"
    last = (
        GroceryPurchase.objects.filter(purchase_no__startswith=prefix)
        .order_by('-purchase_no')
        .values_list('purchase_no', flat=True)
        .first()
    )
    seq = 1
    if last:
        try:
            seq = int(last.split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    return f"{prefix}{seq:05d}"


def generate_sale_no(store):
    """Generate sequential sale number: GRO-SALE-{store_code}-{year}-{seq:05d}"""
    from .models import GrocerySale
    year = date.today().year
    prefix = f"GRO-{store.store_code}-{year}-"
    last = (
        GrocerySale.objects.filter(sale_no__startswith=prefix)
        .order_by('-sale_no')
        .values_list('sale_no', flat=True)
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
    """Return a dict of KPI values for the grocery dashboard."""
    from .models import GroceryProduct, GroceryStock, GroceryOffer, GrocerySale, GroceryPurchase
    from datetime import timedelta
    today = date.today()
    thirty_days_ago = today - timedelta(days=30)

    today_sales = GrocerySale.objects.filter(store=store, sale_date__date=today)
    month_sales = GrocerySale.objects.filter(store=store, sale_date__date__gte=thirty_days_ago)

    stats = {
        'total_products': GroceryProduct.objects.filter(store=store, is_active=True).count(),
        'low_stock_count': GroceryStock.objects.for_store(store).low_stock().count(),
        'expired_count': GroceryStock.objects.for_store(store).expired().count(),
        'near_expiry_count': GroceryStock.objects.for_store(store).near_expiry(5).count(),
        'active_offers': GroceryOffer.objects.filter(store=store, is_active=True, end_date__date__gte=today).count(),
        'today_sales_total': today_sales.aggregate(t=Sum('total'))['t'] or Decimal('0'),
        'today_sales_count': today_sales.count(),
        'month_sales_total': month_sales.aggregate(t=Sum('total'))['t'] or Decimal('0'),
        'today_purchase_total': (
            GroceryPurchase.objects.filter(store=store, purchase_date=today)
            .aggregate(t=Sum('total'))['t'] or Decimal('0')
        ),
    }
    return stats


def generate_return_no(store):
    """Generate sequential return number: GRR-{store_code}-{year}-{seq:05d}"""
    from .models import GrocerySaleReturn
    year = date.today().year
    prefix = f"GRR-{store.store_code}-{year}-"
    last = (
        GrocerySaleReturn.objects
        .filter(return_no__startswith=prefix)
        .order_by('-return_no')
        .values_list('return_no', flat=True)
        .first()
    )
    seq = 1
    if last:
        try:
            seq = int(last.split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    return f"{prefix}{seq:05d}"

