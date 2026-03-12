from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    path('superadmin-dashboard/', views.superadmin_dashboard, name='superadmin_dashboard'),

    # Business Types
    path('business-types/', views.business_types, name='business_types'),

    # Subscription Plans
    path('plans/', views.plans, name='plans'),

    # Companies
    path('companies/', views.companies, name='companies'),
    path('companies/<int:pk>/', views.company_detail, name='company_detail'),
    path('companies/<int:pk>/toggle/', views.company_toggle, name='company_toggle'),

    # Stores
    path('stores/', views.stores, name='stores'),

    # Staff
    path('staff/', views.staff, name='staff_list'),
]
