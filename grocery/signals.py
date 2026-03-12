from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import (
    GroceryPurchaseItem, GrocerySaleItem, GroceryStock,
    GroceryStockAdjustment, GroceryStockTransfer
)

@receiver(post_save, sender=GroceryPurchaseItem)
def purchase_item_update_stock(sender, instance, created, **kwargs):
    if not created or instance.purchase.status != 'received':
        return
    stock, _ = GroceryStock.objects.get_or_create(
        product=instance.product,
        store=instance.purchase.store,
        defaults={'quantity': 0, 'expiry_date': instance.expiry_date}
    )
    stock.quantity += instance.quantity
    if instance.expiry_date:
        stock.expiry_date = instance.expiry_date
    stock.save(update_fields=['quantity', 'expiry_date'])

@receiver(post_save, sender=GrocerySaleItem)
def sale_item_update_stock(sender, instance, created, **kwargs):
    if not created:
        return
    remaining_qty = instance.quantity
    stocks = GroceryStock.objects.filter(
        product=instance.product, store=instance.sale.store, quantity__gt=0
    ).order_by('expiry_date', 'id')

    for stock in stocks:
        if remaining_qty <= 0: break
        deduct = min(stock.quantity, remaining_qty)
        stock.quantity -= deduct
        stock.save(update_fields=['quantity'])
        remaining_qty -= deduct

@receiver(post_save, sender=GroceryStockAdjustment)
def apply_adjustment(sender, instance, created, **kwargs):
    if not created: return
    stock = instance.stock
    if instance.adjustment_type == 'add':
        stock.quantity += instance.quantity
    else:
        stock.quantity = max(0, stock.quantity - instance.quantity)
    stock.save(update_fields=['quantity'])

@receiver(post_save, sender=GroceryStockTransfer)
def apply_transfer(sender, instance, created, **kwargs):
    if created or instance.status != 'completed': return
    
    # Deduct from source
    from_stocks = GroceryStock.objects.filter(
        product=instance.product, store=instance.from_store, quantity__gt=0
    ).order_by('expiry_date')
    remaining = instance.quantity
    for stock in from_stocks:
        if remaining <= 0: break
        deduct = min(stock.quantity, remaining)
        stock.quantity -= deduct
        stock.save(update_fields=['quantity'])
        remaining -= deduct

    # Add to destination
    dest_stock, _ = GroceryStock.objects.get_or_create(
        product=instance.product, store=instance.to_store,
        defaults={'quantity': 0}
    )
    dest_stock.quantity += instance.quantity
    dest_stock.save(update_fields=['quantity'])
