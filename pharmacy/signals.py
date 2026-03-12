from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import (
    PharmacyPurchaseItem, PharmacySaleItem, PharmacySaleReturnItem,
    PharmacyStock, PharmacyStockAdjustment, PharmacyStockTransfer
)


# ─────────────────────────────────────────────────────────────
# PURCHASE → Stock Increase
# When a purchase item is received, increase the matching stock batch.
# ─────────────────────────────────────────────────────────────
@receiver(post_save, sender=PharmacyPurchaseItem)
def purchase_item_update_stock(sender, instance, created, **kwargs):
    if not created:
        return  # Only run on new purchase items
    if instance.purchase.status not in ('received', 'partial'):
        return

    stock, stock_created = PharmacyStock.objects.get_or_create(
        product=instance.product,
        store=instance.purchase.store,
        batch_no=instance.batch_no or '',
        defaults={
            'quantity': 0,
            'expiry_date': instance.expiry_date,
            'min_quantity': 10,
        }
    )
    stock.quantity += instance.received_qty or instance.quantity
    if instance.expiry_date:
        stock.expiry_date = instance.expiry_date
    stock.save(update_fields=['quantity', 'expiry_date'])


# ─────────────────────────────────────────────────────────────
# SALE → Stock Decrease
# When a sale item is saved, decrement stock using FEFO
# (First Expiry, First Out) strategy.
# ─────────────────────────────────────────────────────────────
@receiver(post_save, sender=PharmacySaleItem)
def sale_item_update_stock(sender, instance, created, **kwargs):
    if not created:
        return

    remaining_qty = instance.quantity
    store = instance.sale.store

    # FEFO: consume earliest expiring batches first
    stocks = PharmacyStock.objects.filter(
        product=instance.product,
        store=store,
        quantity__gt=0
    ).order_by('expiry_date', 'id')

    for stock in stocks:
        if remaining_qty <= 0:
            break
        deduct = min(stock.quantity, remaining_qty)
        stock.quantity -= deduct
        stock.save(update_fields=['quantity'])
        remaining_qty -= deduct


# ─────────────────────────────────────────────────────────────
# SALE RETURN → Stock Increase
# Returned items go back into stock.
# ─────────────────────────────────────────────────────────────
@receiver(post_save, sender=PharmacySaleReturnItem)
def sale_return_update_stock(sender, instance, created, **kwargs):
    if not created:
        return

    store = instance.sale_return.sale.store
    # Add back to the first available stock batch of this product
    stock, _ = PharmacyStock.objects.get_or_create(
        product=instance.product,
        store=store,
        batch_no='RETURN',
        defaults={'quantity': 0, 'min_quantity': 0}
    )
    stock.quantity += instance.quantity
    stock.save(update_fields=['quantity'])


# ─────────────────────────────────────────────────────────────
# STOCK ADJUSTMENT → Apply manually
# ─────────────────────────────────────────────────────────────
@receiver(post_save, sender=PharmacyStockAdjustment)
def apply_stock_adjustment(sender, instance, created, **kwargs):
    if not created:
        return

    stock = instance.stock
    if instance.adjustment_type == 'add':
        stock.quantity += instance.quantity
    else:  # remove, damage, expired, return
        stock.quantity = max(0, stock.quantity - instance.quantity)
    stock.save(update_fields=['quantity'])


# ─────────────────────────────────────────────────────────────
# STOCK TRANSFER (completed) → Move stock between stores
# ─────────────────────────────────────────────────────────────
@receiver(post_save, sender=PharmacyStockTransfer)
def apply_stock_transfer(sender, instance, created, **kwargs):
    if created:
        return
    if instance.status != 'completed':
        return

    # Deduct from source store
    from_stocks = PharmacyStock.objects.filter(
        product=instance.product,
        store=instance.from_store,
        quantity__gt=0
    ).order_by('expiry_date', 'id')

    remaining = instance.quantity
    for stock in from_stocks:
        if remaining <= 0:
            break
        deduct = min(stock.quantity, remaining)
        stock.quantity -= deduct
        stock.save(update_fields=['quantity'])
        remaining -= deduct

    # Add to destination store
    dest_stock, _ = PharmacyStock.objects.get_or_create(
        product=instance.product,
        store=instance.to_store,
        batch_no='TRANSFER',
        defaults={'quantity': 0, 'min_quantity': 10}
    )
    dest_stock.quantity += instance.quantity
    dest_stock.save(update_fields=['quantity'])

    # Record completion time
    PharmacyStockTransfer.objects.filter(pk=instance.pk).update(
        completed_at=timezone.now()
    )
