from django.urls import path
from . import views

app_name = 'ecommerce'

urlpatterns = [
    # ── Dashboard ────────────────────────────────────────────────
    path('', views.dashboard, name='dashboard'),

    # ── Products ─────────────────────────────────────────────────
    path('products/', views.product_list, name='product_list'),
    path('products/create/', views.product_create, name='product_create'),
    path('products/<int:pk>/', views.product_detail, name='product_detail'),
    path('products/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('products/<int:pk>/delete/', views.product_delete, name='product_delete'),

    # ── Product Variants ─────────────────────────────────────────
    path('products/<int:product_pk>/variants/create/', views.variant_create, name='variant_create'),
    path('variants/<int:pk>/edit/', views.variant_edit, name='variant_edit'),
    path('variants/<int:pk>/delete/', views.variant_delete, name='variant_delete'),

    # ── Categories (single-page) ─────────────────────────────────
    path('categories/', views.categories, name='categories'),
    path('categories/', views.categories, name='category_list'),  # legacy alias

    # ── Brands (single-page) ─────────────────────────────────────
    path('brands/', views.brands, name='brands'),
    path('brands/', views.brands, name='brand_list'),  # legacy alias

    # ── Orders ───────────────────────────────────────────────────
    path('orders/', views.order_list, name='order_list'),
    path('orders/create/', views.order_create, name='order_create'),
    path('orders/<int:pk>/', views.order_detail, name='order_detail'),
    path('orders/<int:pk>/status/', views.order_update_status, name='order_update_status'),
    path('orders/<int:pk>/payment/', views.order_update_payment, name='order_update_payment'),

    # ── Customers ────────────────────────────────────────────────
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/<int:pk>/', views.customer_detail, name='customer_detail'),

    # ── Reviews ──────────────────────────────────────────────────
    path('reviews/', views.review_list, name='review_list'),
    path('reviews/<int:pk>/approve/', views.review_approve, name='review_approve'),
    path('reviews/<int:pk>/delete/', views.review_delete, name='review_delete'),

    # ── AJAX APIs ────────────────────────────────────────────────
    path('api/products/search/', views.product_search_api, name='api_product_search'),
    path('api/products/<int:pk>/variants/', views.product_variants_api, name='api_product_variants'),

    # ── Reports ──────────────────────────────────────────────────
    path('reports/orders/', views.report_orders, name='report_orders'),
    path('reports/inventory/', views.report_inventory, name='report_inventory'),
    path('reports/reviews/', views.report_reviews, name='report_reviews'),
]
