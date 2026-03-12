from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Company


@receiver(post_save, sender=Company)
def create_company_defaults(sender, instance, created, **kwargs):
    """
    Phase 1 keeps onboarding explicit in function-based views.
    No auto-creation of settings/subscriptions here.
    """
    return None
