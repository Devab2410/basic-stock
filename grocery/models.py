from django.db import models
from django.db.models import F, Q, Sum
from django.conf import settings
from django.utils import timezone
from datetime import date, timedelta

from core.models import Store

User = settings.AUTH_USER_MODEL


# ─────────────────────────────────────────────────────────────
# Category
# ─────────────────────────────────────────────────────────────
class GroceryCategory(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='grocery_categories')
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, blank=True)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='children')
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        unique_together = ('store', 'name', 'parent')

    def __str__(self):
        return f'{self.parent.name} → {self.name}' if self.parent else self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────
# Brand
# ─────────────────────────────────────────────────────────────
class GroceryBrand(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='grocery_brands')
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('store', 'name')

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
class GroceryUnit(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='grocery_units')
    name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=20, blank=True)

    class Meta:
        unique_together = ('store', 'name')

    def __str__(self):
        return f'{self.name} ({self.short_name})' if self.short_name else self.name


# ─────────────────────────────────────────────────────────────
# Product
# ─────────────────────────────────────────────────────────────
class GroceryProduct(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='grocery_products')
    category = models.ForeignKey(GroceryCategory, on_delete=models.SET_NULL, null=True, blank=True)
    brand = models.ForeignKey(GroceryBrand, on_delete=models.SET_NULL, null=True, blank=True)
    unit = models.ForeignKey(GroceryUnit, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=300)
    slug = models.SlugField(max_length=300, blank=True)
    barcode = models.CharField(max_length=100, blank=True)
    sku = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='grocery/products/', blank=True, null=True)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    hsn_code = models.CharField(max_length=20, blank=True)

    # ── Grocery-specific fields ─────────────────────────────
    weight = models.DecimalField(max_digits=10, decimal_places=3, default=0, help_text='Weight per unit')
    is_perishable = models.BooleanField(default=False)
    shelf_life_days = models.PositiveIntegerField(null=True, blank=True, help_text='Estimated shelf life')

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
        return self.stocks.filter(store=self.store).aggregate(total=Sum('quantity'))['total'] or 0


# ─────────────────────────────────────────────────────────────
# Stock
# ─────────────────────────────────────────────────────────────
class StockQuerySet(models.QuerySet):
    def for_store(self, store): return self.filter(store=store)
    def low_stock(self): return self.filter(quantity__lte=F('min_quantity'))
    def expired(self): return self.filter(expiry_date__lt=date.today())
    def near_expiry(self, days=5):
        # Groceries expire much faster, default 5 days warning
        threshold = date.today() + timedelta(days=days)
        return self.filter(expiry_date__gte=date.today(), expiry_date__lte=threshold)


class GroceryStock(models.Model):
    product = models.ForeignKey(GroceryProduct, on_delete=models.CASCADE, related_name='stocks')
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='grocery_stocks')
    batch_no = models.CharField(max_length=100, blank=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    min_quantity = models.DecimalField(max_digits=10, decimal_places=3, default=10)
    warehouse = models.CharField(max_length=100, blank=True)
    rack_location = models.CharField(max_length=100, blank=True)
    manufacturing_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = StockQuerySet.as_manager()

    class Meta:
        verbose_name = 'Stock'
        ordering = ['product__name', 'expiry_date']

    def __str__(self): return f'{self.product.name} (Qty: {self.quantity})'

    @property
    def is_low_stock(self): return self.quantity <= self.min_quantity

    @property
    def is_expired(self): return bool(self.expiry_date and self.expiry_date < date.today())

    @property
    def days_to_expiry(self):
        if not self.expiry_date:
            return None
        return (self.expiry_date - date.today()).days


# ─────────────────────────────────────────────────────────────
# Adjustments & Transfers
# ─────────────────────────────────────────────────────────────
TYPE_CHOICES = [
    ('add', 'Add'), ('remove', 'Remove'), ('damage', 'Damage/Loss'),
    ('expired', 'Expired'), ('return', 'Return'),
]


class GroceryStockAdjustment(models.Model):
    stock = models.ForeignKey(GroceryStock, on_delete=models.CASCADE, related_name='adjustments')
    adjustment_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    quantity = models.DecimalField(max_digits=10, decimal_places=3)
    reason = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    adjusted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    date = models.DateTimeField(auto_now_add=True)


class GroceryStockTransfer(models.Model):
    product = models.ForeignKey(GroceryProduct, on_delete=models.CASCADE)
    from_store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='grocery_outbound')
    to_store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='grocery_inbound')
    quantity = models.DecimalField(max_digits=10, decimal_places=3)
    batch_no = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=15, default='pending', choices=[
        ('pending', 'Pending'), ('completed', 'Completed'), ('cancelled', 'Cancelled'),
    ])
    transferred_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    date = models.DateTimeField(auto_now_add=True)


# ─────────────────────────────────────────────────────────────
# Supplier & Customer
# ─────────────────────────────────────────────────────────────
class GrocerySupplier(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    gstin = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self): return self.name


class GroceryCustomer(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    loyalty_points = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self): return self.name or self.phone


# ─────────────────────────────────────────────────────────────
# Purchase
# ─────────────────────────────────────────────────────────────
STATUS_PURCHASE = [
    ('draft', 'Draft'),
    ('partial', 'Partial Received'),
    ('received', 'Received'),
    ('cancelled', 'Cancelled'),
]


class GroceryPurchase(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    supplier = models.ForeignKey(GrocerySupplier, on_delete=models.PROTECT)
    purchase_no = models.CharField(max_length=50, unique=True)
    supplier_invoice_no = models.CharField(max_length=100, blank=True)
    purchase_date = models.DateField()
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=15, default='draft', choices=STATUS_PURCHASE)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return self.purchase_no


class GroceryPurchaseItem(models.Model):
    purchase = models.ForeignKey(GroceryPurchase, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(GroceryProduct, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=3)
    received_qty = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    batch_no = models.CharField(max_length=100, blank=True)
    expiry_date = models.DateField(null=True, blank=True)

    def save(self, *args, **kwargs):
        line_total = self.unit_price * self.quantity
        self.tax_amount = (line_total * self.tax_rate) / 100
        self.subtotal = line_total + self.tax_amount
        if not self.received_qty:
            self.received_qty = self.quantity
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────
# Sale
# ─────────────────────────────────────────────────────────────
PAYMENT_METHODS = [
    ('cash', 'Cash'), ('card', 'Card'), ('upi', 'UPI'),
    ('wallet', 'Wallet'), ('credit', 'Credit'),
]


class GrocerySale(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    customer = models.ForeignKey(GroceryCustomer, on_delete=models.SET_NULL, null=True, blank=True)
    biller = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    sale_no = models.CharField(max_length=50, unique=True)
    sale_date = models.DateTimeField(default=timezone.now)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=15, default='cash', choices=PAYMENT_METHODS)
    status = models.CharField(max_length=10, default='paid', choices=[
        ('paid', 'Paid'), ('partial', 'Partial'), ('unpaid', 'Unpaid'), ('returned', 'Returned'),
    ])
    notes = models.TextField(blank=True)

    def __str__(self): return self.sale_no


class GrocerySaleItem(models.Model):
    sale = models.ForeignKey(GrocerySale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(GroceryProduct, on_delete=models.PROTECT)
    stock = models.ForeignKey(GroceryStock, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=3)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        line_total = self.unit_price * self.quantity
        self.tax_amount = (line_total * self.tax_rate) / 100
        self.subtotal = line_total + self.tax_amount - self.discount
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────
# Sale Return
# ─────────────────────────────────────────────────────────────
class GrocerySaleReturn(models.Model):
    sale = models.ForeignKey(GrocerySale, on_delete=models.CASCADE, related_name='returns')
    return_no = models.CharField(max_length=50, unique=True)
    return_date = models.DateTimeField(default=timezone.now)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reason = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self): return self.return_no


class GrocerySaleReturnItem(models.Model):
    sale_return = models.ForeignKey(GrocerySaleReturn, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(GroceryProduct, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=3)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        self.subtotal = self.unit_price * self.quantity
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────
# Grocery-specific Promotions
# ─────────────────────────────────────────────────────────────
class GroceryOffer(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    product = models.ForeignKey(GroceryProduct, on_delete=models.CASCADE, related_name='offers')
    offer_type = models.CharField(max_length=20, choices=[
        ('flat', 'Flat Discount'), ('percent', 'Percentage (%)'), ('buy_x_get_y', 'Buy X Get Y')
    ])
    value = models.DecimalField(max_digits=10, decimal_places=2)
    x_quantity = models.PositiveIntegerField(default=1, blank=True)
    y_quantity = models.PositiveIntegerField(default=1, blank=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
