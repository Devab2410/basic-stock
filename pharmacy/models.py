from django.db import models
from django.db.models import F, Q
from django.conf import settings
from django.utils import timezone
from datetime import date, timedelta

from core.models import Store

User = settings.AUTH_USER_MODEL


# ─────────────────────────────────────────────────────────────
# Category (hierarchical)
# ─────────────────────────────────────────────────────────────
class PharmacyCategory(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='pharmacy_categories')
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, blank=True)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='children')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    image = models.ImageField(upload_to='category_images/', blank=True, null=True)

    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        unique_together = ('store', 'name', 'parent')
        ordering = ['name']

    def __str__(self):
        if self.parent:
            return f'{self.parent.name} → {self.name}'
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────
# Brand
# ─────────────────────────────────────────────────────────────
class PharmacyBrand(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='pharmacy_brands')
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    image = models.ImageField(upload_to='brand_images/', blank=True, null=True)

    class Meta:
        unique_together = ('store', 'name')
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────
# Unit
# ─────────────────────────────────────────────────────────────
class PharmacyUnit(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='pharmacy_units')
    name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=20, blank=True)

    class Meta:
        unique_together = ('store', 'name')
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.short_name})' if self.short_name else self.name


# ─────────────────────────────────────────────────────────────
# Product
# ─────────────────────────────────────────────────────────────
class PharmacyProduct(models.Model):
    SCHEDULE_CHOICES = (
        ('OTC', 'Over the Counter (OTC)'),
        ('H', 'Schedule H'),
        ('H1', 'Schedule H1'),
        ('X', 'Schedule X'),
    )

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='pharmacy_products')
    category = models.ForeignKey(PharmacyCategory, on_delete=models.SET_NULL,
                                  null=True, blank=True, related_name='products')
    brand = models.ForeignKey(PharmacyBrand, on_delete=models.SET_NULL,
                               null=True, blank=True, related_name='products')
    unit = models.ForeignKey(PharmacyUnit, on_delete=models.SET_NULL,
                              null=True, blank=True, related_name='products')
    name = models.CharField(max_length=300)
    slug = models.SlugField(max_length=300, blank=True)
    barcode = models.CharField(max_length=100, blank=True)
    sku = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                    help_text='GST/Tax rate in percentage')
    hsn_code = models.CharField(max_length=20, blank=True, verbose_name='HSN Code')

    # ── Pharmacy-specific fields ─────────────────────────────
    requires_prescription = models.BooleanField(default=False, verbose_name='Requires Prescription')
    schedule_type = models.CharField(max_length=5, choices=SCHEDULE_CHOICES, default='OTC')

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Product'
        verbose_name_plural = 'Products'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def current_stock(self):
        total = self.stocks.filter(store=self.store).aggregate(
            total=models.Sum('quantity')
        )['total']
        return total or 0

    @property
    def profit_margin(self):
        if self.purchase_price and self.purchase_price > 0:
            return round(((self.selling_price - self.purchase_price) / self.purchase_price) * 100, 2)
        return 0

# ─────────────────────────────────────────────────────────────
# Product Images (Multiple images per product)
# ─────────────────────────────────────────────────────────────
class PharmacyProductImage(models.Model):
    product = models.ForeignKey(
        PharmacyProduct,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(upload_to='pharmacy/products/')
    alt_text = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Product Image"
        verbose_name_plural = "Product Images"
        ordering = ['-is_primary', 'id']

    def __str__(self):
        return f"{self.product.name} Image"


# ─────────────────────────────────────────────────────────────
# Stock (per batch, per store)
# ─────────────────────────────────────────────────────────────
class StockQuerySet(models.QuerySet):
    def for_store(self, store):
        return self.filter(store=store)

    def low_stock(self):
        return self.filter(quantity__lte=F('min_quantity'))

    def expired(self):
        return self.filter(expiry_date__lt=date.today())

    def near_expiry(self, days=30):
        threshold = date.today() + timedelta(days=days)
        return self.filter(
            expiry_date__isnull=False,
            expiry_date__gte=date.today(),
            expiry_date__lte=threshold
        )

    def in_stock(self):
        return self.filter(quantity__gt=0)


class PharmacyStock(models.Model):
    product = models.ForeignKey(PharmacyProduct, on_delete=models.CASCADE, related_name='stocks')
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='pharmacy_stocks')
    warehouse = models.CharField(max_length=100, blank=True, help_text='Warehouse or storage location')
    rack_location = models.CharField(max_length=100, blank=True)
    batch_no = models.CharField(max_length=100, blank=True)
    quantity = models.PositiveIntegerField(default=0)
    min_quantity = models.PositiveIntegerField(default=10, help_text='Low stock alert threshold')
    manufacturing_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = StockQuerySet.as_manager()

    class Meta:
        verbose_name = 'Stock'
        verbose_name_plural = 'Stocks'
        ordering = ['product__name', 'expiry_date']

    def __str__(self):
        return f'{self.product.name} — Batch: {self.batch_no or "N/A"} — Qty: {self.quantity}'

    @property
    def is_low_stock(self):
        return self.quantity <= self.min_quantity

    @property
    def is_expired(self):
        return bool(self.expiry_date and self.expiry_date < date.today())

    @property
    def days_to_expiry(self):
        if self.expiry_date:
            return (self.expiry_date - date.today()).days
        return None

    @property
    def is_near_expiry(self, threshold_days=30):
        d = self.days_to_expiry
        return d is not None and 0 <= d <= threshold_days


# ─────────────────────────────────────────────────────────────
# Stock Adjustment
# ─────────────────────────────────────────────────────────────
class PharmacyStockAdjustment(models.Model):
    TYPE_CHOICES = (
        ('add', 'Add'),
        ('remove', 'Remove'),
        ('damage', 'Damage/Loss'),
        ('expired', 'Expired'),
        ('return', 'Customer Return'),
    )

    stock = models.ForeignKey(PharmacyStock, on_delete=models.CASCADE, related_name='adjustments')
    adjustment_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    quantity = models.PositiveIntegerField()
    reason = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    adjusted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Stock Adjustment'
        ordering = ['-date']

    def __str__(self):
        return f'{self.get_adjustment_type_display()} — {self.stock.product.name} — {self.quantity}'


# ─────────────────────────────────────────────────────────────
# Stock Transfer (store to store)
# ─────────────────────────────────────────────────────────────
class PharmacyStockTransfer(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('in_transit', 'In Transit'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )

    product = models.ForeignKey(PharmacyProduct, on_delete=models.CASCADE, related_name='transfers')
    from_store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='outbound_transfers')
    to_store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='inbound_transfers')
    quantity = models.PositiveIntegerField()
    transferred_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                        related_name='initiated_transfers')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    date = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Stock Transfer'
        ordering = ['-date']

    def __str__(self):
        return f'{self.product.name}: {self.from_store.name} → {self.to_store.name} ({self.quantity})'


# ─────────────────────────────────────────────────────────────
# Supplier
# ─────────────────────────────────────────────────────────────
class PharmacySupplier(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='pharmacy_suppliers')
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    gstin = models.CharField(max_length=20, blank=True, verbose_name='GSTIN')
    drug_license_no = models.CharField(max_length=100, blank=True,
                                        verbose_name='Drug License No.',
                                        help_text='Pharmacy-specific license')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('store', 'name')
        ordering = ['name']

    def __str__(self):
        return self.name


# ─────────────────────────────────────────────────────────────
# Customer
# ─────────────────────────────────────────────────────────────
class PharmacyCustomer(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='pharmacy_customers')
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    dob = models.DateField(null=True, blank=True, verbose_name='Date of Birth')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('store', 'phone')
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.phone})'


# ─────────────────────────────────────────────────────────────
# Purchase (Goods Receipt from Supplier)
# ─────────────────────────────────────────────────────────────
class PharmacyPurchase(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('received', 'Fully Received'),
        ('partial', 'Partially Received'),
        ('cancelled', 'Cancelled'),
    )

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='pharmacy_purchases')
    supplier = models.ForeignKey(PharmacySupplier, on_delete=models.PROTECT,
                                  related_name='purchases')
    purchase_no = models.CharField(max_length=50, unique=True)
    supplier_invoice_no = models.CharField(max_length=100, blank=True)
    purchase_date = models.DateField()
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='draft')
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Purchase'
        ordering = ['-purchase_date', '-created_at']

    def __str__(self):
        return f'{self.purchase_no} — {self.supplier.name}'

    def recalculate_totals(self):
        """Recalculate purchase totals from items."""
        items = self.items.all()
        self.subtotal = sum(item.subtotal for item in items)
        self.tax_amount = sum(item.tax_amount for item in items)
        self.total = self.subtotal + self.tax_amount - self.discount
        self.save(update_fields=['subtotal', 'tax_amount', 'total'])


class PharmacyPurchaseItem(models.Model):
    purchase = models.ForeignKey(PharmacyPurchase, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(PharmacyProduct, on_delete=models.PROTECT, related_name='purchase_items')
    quantity = models.PositiveIntegerField()
    received_qty = models.PositiveIntegerField(default=0)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    batch_no = models.CharField(max_length=100, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Purchase Item'

    def __str__(self):
        return f'{self.product.name} x {self.quantity}'

    def save(self, *args, **kwargs):
        self.subtotal = self.unit_price * self.quantity
        self.tax_amount = (self.subtotal * self.tax_rate) / 100
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────
# Sale
# ─────────────────────────────────────────────────────────────
class PharmacySale(models.Model):
    PAYMENT_METHOD_CHOICES = (
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('upi', 'UPI'),
        ('credit', 'Credit'),
        ('cheque', 'Cheque'),
    )
    STATUS_CHOICES = (
        ('paid', 'Paid'),
        ('partial', 'Partially Paid'),
        ('pending', 'Pending'),
        ('refunded', 'Refunded'),
    )

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='pharmacy_sales')
    customer = models.ForeignKey(PharmacyCustomer, on_delete=models.SET_NULL,
                                  null=True, blank=True, related_name='sales')
    biller = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                related_name='pharmacy_sales_billed')
    sale_no = models.CharField(max_length=50, unique=True)
    sale_date = models.DateTimeField(default=timezone.now)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES, default='cash')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='paid')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Sale'
        ordering = ['-sale_date']

    def __str__(self):
        return f'{self.sale_no} — {self.total}'

    @property
    def balance_due(self):
        return self.total - self.amount_paid

    def recalculate_totals(self):
        items = self.items.all()
        self.subtotal = sum(item.subtotal for item in items)
        self.tax_amount = sum(item.tax_amount for item in items)
        self.total = self.subtotal + self.tax_amount - self.discount
        self.save(update_fields=['subtotal', 'tax_amount', 'total'])


class PharmacySaleItem(models.Model):
    sale = models.ForeignKey(PharmacySale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(PharmacyProduct, on_delete=models.PROTECT, related_name='sale_items')
    stock = models.ForeignKey(PharmacyStock, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        self.subtotal = self.unit_price * self.quantity
        self.tax_amount = (self.subtotal * self.tax_rate) / 100
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────
# Sale Return
# ─────────────────────────────────────────────────────────────
class PharmacySaleReturn(models.Model):
    REFUND_METHOD_CHOICES = (
        ('cash', 'Cash'),
        ('credit', 'Store Credit'),
        ('upi', 'UPI'),
    )

    sale = models.ForeignKey(PharmacySale, on_delete=models.CASCADE, related_name='returns')
    return_no = models.CharField(max_length=50, unique=True)
    return_date = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(max_length=300)
    total_refund = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    refund_method = models.CharField(max_length=10, choices=REFUND_METHOD_CHOICES, default='cash')
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ['-return_date']

    def __str__(self):
        return f'{self.return_no} — Return for {self.sale.sale_no}'


class PharmacySaleReturnItem(models.Model):
    sale_return = models.ForeignKey(PharmacySaleReturn, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(PharmacyProduct, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        self.subtotal = self.unit_price * self.quantity
        super().save(*args, **kwargs)
