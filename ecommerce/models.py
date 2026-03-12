from django.db import models
from django.conf import settings
from django.utils import timezone
from core.models import Store

User = settings.AUTH_USER_MODEL

# ─────────────────────────────────────────────────────────────
# Product & Taxonomy
# ─────────────────────────────────────────────────────────────
class EcommerceCategory(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, blank=True)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self): return self.name


class EcommerceBrand(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self): return self.name


class EcommerceProduct(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    category = models.ForeignKey(EcommerceCategory, on_delete=models.SET_NULL, null=True, blank=True)
    brand = models.ForeignKey(EcommerceBrand, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=300)
    slug = models.SlugField(max_length=300, blank=True)
    sku = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    
    # Base Prices (overridden by variants if any)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    compare_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Strikethrough price')
    
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_featured = models.BooleanField(default=False)
    
    # SEO
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self): return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class EcommerceProductVariant(models.Model):
    product = models.ForeignKey(EcommerceProduct, on_delete=models.CASCADE, related_name='variants')
    sku = models.CharField(max_length=100, unique=True)
    attribute_name = models.CharField(max_length=50, help_text='e.g. Size, Color, Storage')
    attribute_value = models.CharField(max_length=50, help_text='e.g. XL, Red, 128GB')
    price_modifier = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='+/- to base price')
    stock = models.PositiveIntegerField(default=0)
    
    def __str__(self): return f'{self.product.name} - {self.attribute_value}'
    
    @property
    def final_price(self):
        return self.product.selling_price + self.price_modifier


class EcommerceProductImage(models.Model):
    product = models.ForeignKey(EcommerceProduct, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='ecommerce/products/')
    alt_text = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['sort_order', '-is_primary']


# ─────────────────────────────────────────────────────────────
# Customers, Orders & Cart
# ─────────────────────────────────────────────────────────────
class EcommerceCustomer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    phone = models.CharField(max_length=20, blank=True)
    billing_address = models.TextField(blank=True)
    shipping_address = models.TextField(blank=True)

    def __str__(self): return self.user.get_full_name() or self.user.username


class EcommerceOrder(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'), ('processing', 'Processing'),
        ('shipped', 'Shipped'), ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'), ('refunded', 'Refunded')
    )
    
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    customer = models.ForeignKey(EcommerceCustomer, on_delete=models.SET_NULL, null=True, blank=True)
    order_no = models.CharField(max_length=50, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('paid', 'Paid'), ('failed', 'Failed')], default='pending')
    payment_method = models.CharField(max_length=50, default='credit_card')
    tracking_no = models.CharField(max_length=100, blank=True)
    shipping_address = models.TextField()
    billing_address = models.TextField()
    
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return self.order_no


class EcommerceOrderItem(models.Model):
    order = models.ForeignKey(EcommerceOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(EcommerceProduct, on_delete=models.SET_NULL, null=True)
    variant = models.ForeignKey(EcommerceProductVariant, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        self.subtotal = self.unit_price * self.quantity
        super().save(*args, **kwargs)


class EcommerceCart(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    customer = models.ForeignKey(EcommerceCustomer, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=40, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def total(self):
        return sum(item.subtotal for item in self.items.all())

    @property
    def item_count(self):
        return sum(item.quantity for item in self.items.all())


class EcommerceCartItem(models.Model):
    cart = models.ForeignKey(EcommerceCart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(EcommerceProduct, on_delete=models.CASCADE)
    variant = models.ForeignKey(EcommerceProductVariant, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    
    @property
    def subtotal(self):
        price = self.variant.final_price if self.variant else self.product.selling_price
        return price * self.quantity


class EcommerceReview(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    product = models.ForeignKey(EcommerceProduct, on_delete=models.CASCADE, related_name='reviews')
    customer = models.ForeignKey(EcommerceCustomer, on_delete=models.CASCADE)
    rating = models.PositiveIntegerField(choices=[(i, str(i)) for i in range(1, 6)])
    title = models.CharField(max_length=200, blank=True)
    comment = models.TextField(blank=True)
    is_approved = models.BooleanField(default=False)
    is_verified_purchase = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
