"""
Utility functions for the pharmacy app.
"""
from django.db.models import Sum, Count
from datetime import date, timedelta
from .models import (
    PharmacyProduct, PharmacyStock, PharmacySale, PharmacySaleItem,
    PharmacyPurchase
)


# ─────────────────────────────────────────────────────────────
# Number Generators
# ─────────────────────────────────────────────────────────────
def generate_purchase_no(store):
    """Generate unique purchase number: PHA-{store_code}-{year}-{seq:05d}"""
    year = date.today().year
    prefix = f'PHA-{store.store_code}-{year}'
    count = PharmacyPurchase.objects.filter(
        store=store,
        purchase_no__startswith=prefix
    ).count()
    return f'{prefix}-{count + 1:05d}'


def generate_sale_no(store):
    """Generate unique sale number: PHB-{store_code}-{year}-{seq:05d}"""
    year = date.today().year
    prefix = f'PHB-{store.store_code}-{year}'
    from .models import PharmacySale
    count = PharmacySale.objects.filter(
        store=store,
        sale_no__startswith=prefix
    ).count()
    return f'{prefix}-{count + 1:05d}'


def generate_return_no(store):
    """Generate unique return number: PHR-{store_code}-{year}-{seq:05d}"""
    year = date.today().year
    prefix = f'PHR-{store.store_code}-{year}'
    from .models import PharmacySaleReturn
    count = PharmacySaleReturn.objects.filter(
        sale__store=store,
        return_no__startswith=prefix
    ).count()
    return f'{prefix}-{count + 1:05d}'


# ─────────────────────────────────────────────────────────────
# Dashboard KPI Statistics
# ─────────────────────────────────────────────────────────────
def get_dashboard_stats(store):
    today = date.today()
    thirty_days_ago = today - timedelta(days=30)

    total_products = PharmacyProduct.objects.filter(store=store, is_active=True).count()
    low_stock_count = PharmacyStock.objects.for_store(store).low_stock().count()
    expired_count = PharmacyStock.objects.for_store(store).expired().count()
    near_expiry_count = PharmacyStock.objects.for_store(store).near_expiry(days=30).count()

    today_sales = PharmacySale.objects.filter(store=store, sale_date__date=today)
    today_sales_total = today_sales.aggregate(total=Sum('total'))['total'] or 0
    today_sales_count = today_sales.count()

    month_sales = PharmacySale.objects.filter(store=store, sale_date__date__gte=thirty_days_ago)
    month_sales_total = month_sales.aggregate(total=Sum('total'))['total'] or 0

    today_purchases = PharmacyPurchase.objects.filter(store=store, purchase_date=today)
    today_purchase_total = today_purchases.aggregate(total=Sum('total'))['total'] or 0

    return {
        'total_products': total_products,
        'low_stock_count': low_stock_count,
        'expired_count': expired_count,
        'near_expiry_count': near_expiry_count,
        'today_sales_total': today_sales_total,
        'today_sales_count': today_sales_count,
        'month_sales_total': month_sales_total,
        'today_purchase_total': today_purchase_total,
    }


# ─────────────────────────────────────────────────────────────
# Chart Data (last 12 months)
# ─────────────────────────────────────────────────────────────
def get_monthly_chart_data(store):
    """Returns last 12 months sales data for ApexCharts."""
    from django.db.models.functions import TruncMonth
    from django.utils import timezone

    twelve_months_ago = timezone.now() - timedelta(days=365)
    monthly = (
        PharmacySale.objects
        .filter(store=store, sale_date__gte=twelve_months_ago)
        .annotate(month=TruncMonth('sale_date'))
        .values('month')
        .annotate(total=Sum('total'), count=Count('id'))
        .order_by('month')
    )

    labels = []
    sales_data = []
    for entry in monthly:
        labels.append(entry['month'].strftime('%b %Y'))
        sales_data.append(float(entry['total'] or 0))

    return {'labels': labels, 'sales': sales_data}
