from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    """
    Extended User model with phone and avatar support.
    Supports login via email OR username.
    """
    phone = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    is_verified = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    @property
    def has_staff_profile(self):
        return hasattr(self, 'staffprofile')

    @property
    def active_store(self):
        if self.has_staff_profile:
            return self.staffprofile.store
        return None

    @property
    def active_company(self):
        if self.has_staff_profile:
            return self.staffprofile.company
        return None

    @property
    def role(self):
        if self.has_staff_profile:
            return self.staffprofile.role
        if self.is_superuser:
            return 'superadmin'
        return None
