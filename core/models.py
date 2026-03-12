from django.db import models
from django.conf import settings
from django.utils import timezone


User = settings.AUTH_USER_MODEL


# ─────────────────────────────────────────────────────────────
# Business Type  (pharmacy, grocery, ecommerce …)
# ─────────────────────────────────────────────────────────────
class BusinessType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=50, unique=True)  # 'pharmacy','grocery','ecommerce'
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=100, blank=True, help_text='Tabler icon class e.g. ti ti-pill')
    color = models.CharField(max_length=20, blank=True, help_text='CSS hex or variable e.g. #7638FF')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Business Type'
        verbose_name_plural = 'Business Types'
        ordering = ['name']

    def __str__(self):
        return self.name


# ─────────────────────────────────────────────────────────────
# Subscription Plan  (Free, Pro, Enterprise)
# ─────────────────────────────────────────────────────────────
class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100, unique=True)
    max_stores = models.PositiveIntegerField(default=1)
    max_users = models.PositiveIntegerField(default=5)
    max_products = models.PositiveIntegerField(default=100)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    duration_days = models.PositiveIntegerField(default=30)
    features = models.JSONField(default=dict, blank=True,
                                help_text='Dict of feature flags e.g. {"pos": true, "reports": true}')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Subscription Plan'
        verbose_name_plural = 'Subscription Plans'
        ordering = ['price']

    def __str__(self):
        return self.name

    @property
    def is_free(self):
        return self.price == 0


# ─────────────────────────────────────────────────────────────
# Company  (client/tenant)
# ─────────────────────────────────────────────────────────────
class Company(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    registration_no = models.CharField(max_length=100, blank=True)
    gstin = models.CharField(max_length=20, blank=True, verbose_name='GSTIN')
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                               related_name='owned_companies')
    business_types = models.ManyToManyField(BusinessType, related_name='companies', blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    address = models.TextField()
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='India')
    logo = models.ImageField(upload_to='company_logos/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Company'
        verbose_name_plural = 'Companies'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            base = slugify(self.name)
            slug = base
            n = 1
            while Company.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{n}'
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def active_subscription(self):
        try:
            sub = self.subscription
            return sub if sub.is_active and not sub.is_expired() else None
        except CompanySubscription.DoesNotExist:
            return None

    @property
    def store_count(self):
        return self.stores.filter(is_active=True).count()


# ─────────────────────────────────────────────────────────────
# Company Subscription
# ─────────────────────────────────────────────────────────────
class CompanySubscription(models.Model):
    company = models.OneToOneField(Company, on_delete=models.CASCADE,
                                    related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)
    auto_renew = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Company Subscription'
        verbose_name_plural = 'Company Subscriptions'

    def __str__(self):
        return f'{self.company.name} — {self.plan.name}'

    def is_expired(self):
        return timezone.now().date() > self.end_date

    @property
    def days_remaining(self):
        delta = self.end_date - timezone.now().date()
        return max(delta.days, 0)


# ─────────────────────────────────────────────────────────────
# Store / Branch
# ─────────────────────────────────────────────────────────────
class Store(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='stores')
    business_type = models.ForeignKey(BusinessType, on_delete=models.PROTECT,
                                       related_name='stores')
    name = models.CharField(max_length=200)
    store_code = models.CharField(max_length=50)
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='managed_stores')
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='India')
    is_main_branch = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Store'
        verbose_name_plural = 'Stores'
        unique_together = ('company', 'store_code')
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.company.name})'


# ─────────────────────────────────────────────────────────────
# Staff Profile  (links User → Company → Store → Role)
# ─────────────────────────────────────────────────────────────
class StaffProfile(models.Model):
    ROLE_CHOICES = (
        ('owner', 'Owner'),
        ('admin', 'Admin'),
        ('manager', 'Manager'),
        ('staff', 'Staff'),
        ('viewer', 'Viewer'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staffprofile')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='staff')
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='staff')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff')
    designation = models.CharField(max_length=100, blank=True)
    joined_date = models.DateField()
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Staff Profile'
        verbose_name_plural = 'Staff Profiles'

    def __str__(self):
        return f'{self.user.username} — {self.get_role_display()} @ {self.store.name}'

    # ── Permission helpers ──────────────────────────────────────
    @property
    def is_owner(self):
        return self.role == 'owner'

    @property
    def is_admin_or_above(self):
        return self.role in ('owner', 'admin')

    @property
    def is_manager_or_above(self):
        return self.role in ('owner', 'admin', 'manager')

    @property
    def can_manage_stock(self):
        return self.role in ('owner', 'admin', 'manager', 'staff')

    @property
    def can_view_reports(self):
        return self.role in ('owner', 'admin', 'manager')

    @property
    def can_manage_users(self):
        return self.role in ('owner', 'admin')

    @property
    def can_access_pos(self):
        return self.role in ('owner', 'admin', 'manager', 'staff')


# ─────────────────────────────────────────────────────────────
# Company Settings  (per company configuration)
# ─────────────────────────────────────────────────────────────
class CompanySetting(models.Model):
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='settings')
    currency = models.CharField(max_length=10, default='INR')
    currency_symbol = models.CharField(max_length=5, default='₹')
    tax_enabled = models.BooleanField(default=True)
    default_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=18.00)
    invoice_prefix = models.CharField(max_length=20, default='INV')
    timezone = models.CharField(max_length=50, default='Asia/Kolkata')
    date_format = models.CharField(max_length=20, default='%d/%m/%Y')
    low_stock_alert_days = models.PositiveIntegerField(default=30,
                           help_text='Alert days before expiry')
    extra_settings = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'Company Setting'
        verbose_name_plural = 'Company Settings'

    def __str__(self):
        return f'Settings — {self.company.name}'
