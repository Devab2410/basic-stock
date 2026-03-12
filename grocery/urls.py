from django.urls import path
from . import views

app_name = 'grocery'

urlpatterns = [
    # ── Dashboard ────────────────────────────────────────────────
    path('', views.dashboard, name='dashboard'),

    # ── Products ─────────────────────────────────────────────────
    path('products/', views.product_list, name='product_list'),
    path('products/create/', views.product_create, name='product_create'),
    path('products/<int:pk>/', views.product_detail, name='product_detail'),
    path('products/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('products/<int:pk>/delete/', views.product_delete, name='product_delete'),

    # ── Categories (single-page) ─────────────────────────────────
    path('categories/', views.categories, name='categories'),
    path('categories/', views.categories, name='category_list'),  # legacy alias

    # ── Brands (single-page) ─────────────────────────────────────
    path('brands/', views.brands, name='brands'),
    path('brands/', views.brands, name='brand_list'),  # legacy alias

    # ── Units (single-page) ──────────────────────────────────────
    path('units/', views.units, name='units'),
    path('units/', views.units, name='unit_list'),  # legacy alias

    # ── Stock ────────────────────────────────────────────────────
    path('stock/', views.manage_stock, name='manage_stock'),
    path('stock/low/', views.low_stocks, name='low_stocks'),
    path('stock/expired/', views.expired_products, name='expired_products'),
    path('stock/near-expiry/', views.near_expiry, name='near_expiry'),
    path('stock/adjustments/', views.stock_adjustment_list, name='stock_adjustment_list'),
    path('stock/adjustments/create/', views.stock_adjustment_create, name='stock_adjustment_create'),
    path('stock/transfers/', views.stock_transfer_list, name='stock_transfer_list'),
    path('stock/transfers/create/', views.stock_transfer_create, name='stock_transfer_create'),
    path('stock/transfers/<int:pk>/complete/', views.stock_transfer_complete, name='stock_transfer_complete'),

    # ── Suppliers (single-page) ──────────────────────────────────
    path('suppliers/', views.suppliers, name='suppliers'),
    path('suppliers/', views.suppliers, name='supplier_list'),  # legacy alias

    # ── Customers (single-page) ──────────────────────────────────
    path('customers/', views.customers, name='customers'),
    path('customers/', views.customers, name='customer_list'),  # legacy alias

    # ── Offers / Promotions ──────────────────────────────────────
    path('offers/', views.offer_list, name='offer_list'),
    path('offers/create/', views.offer_create, name='offer_create'),
    path('offers/<int:pk>/edit/', views.offer_edit, name='offer_edit'),
    path('offers/<int:pk>/delete/', views.offer_delete, name='offer_delete'),

    # ── Purchases ────────────────────────────────────────────────
    path('purchases/', views.purchase_list, name='purchase_list'),
    path('purchases/create/', views.purchase_create, name='purchase_create'),
    path('purchases/<int:pk>/', views.purchase_detail, name='purchase_detail'),
    path('purchases/<int:pk>/receive/', views.purchase_receive, name='purchase_receive'),
    path('purchases/<int:pk>/delete/', views.purchase_delete, name='purchase_delete'),

    # ── Sales / POS ──────────────────────────────────────────────
    path('sales/', views.sale_list, name='sale_list'),
    path('sales/<int:pk>/', views.sale_detail, name='sale_detail'),
    path('pos/', views.pos, name='pos'),

    # ── AJAX ─────────────────────────────────────────────────────
    path('api/products/search/', views.product_search_api, name='api_product_search'),

    # ── Reports ──────────────────────────────────────────────────
    path('reports/sales/', views.report_sales, name='report_sales'),
    path('reports/purchases/', views.report_purchases, name='report_purchases'),
    path('reports/inventory/', views.report_inventory, name='report_inventory'),
    path('reports/expiry/', views.report_expiry, name='report_expiry'),
]
