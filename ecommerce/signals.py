from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import EcommerceOrderItem

@receiver(post_save, sender=EcommerceOrderItem)
def order_item_update_stock(sender, instance, created, **kwargs):
    if not created:
        return
    
    # If a variant is selected, deduct from variant stock
    if instance.variant:
        instance.variant.stock = max(0, instance.variant.stock - instance.quantity)
        instance.variant.save(update_fields=['stock'])
    # If no variant, deduct from a base product stock if applicable.
    # Note: EcommerceProduct does not have a direct stock field in current design,
    # it relies on variants for stock management.
