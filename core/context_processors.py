from .models import BusinessType


def global_context(request):
    """
    Injects global template variables into every request context:
    - current_store, current_company, user_role
    - all_stores (for header store switcher dropdown)
    - business_types (for nav)
    - subscription_status (reserved for future use)
    - currency, currency_symbol
    """
    ctx = {
        'current_store': None,
        'current_company': None,
        'user_role': None,
        'all_stores': [],
        'business_types': [],
        'subscription_status': None,
        'currency': 'INR',
        'currency_symbol': '₹',
        'invoice_prefix': 'INV',
        'user_permissions': {},
    }

    if not request.user.is_authenticated:
        return ctx

    # Superuser context
    if request.user.is_superuser:
        ctx['user_role'] = 'superadmin'
        ctx['business_types'] = BusinessType.objects.filter(is_active=True)
        return ctx

    # Staff context
    if not request.user.has_staff_profile:
        return ctx

    profile = request.user.staffprofile
    company = profile.company
    store = profile.store

    ctx['current_store'] = store
    ctx['current_company'] = company
    ctx['user_role'] = profile.role
    ctx['business_types'] = BusinessType.objects.filter(is_active=True)

    # All stores the user can switch between (owner sees all, others their store only)
    if profile.is_owner:
        ctx['all_stores'] = company.stores.filter(is_active=True).select_related('business_type')
    else:
        ctx['all_stores'] = [store]

    # Phase 1: no subscription/settings dependency yet.
    ctx['subscription_status'] = None

    # User permission flags for template conditionals
    ctx['user_permissions'] = {
        'can_manage_stock': profile.can_manage_stock,
        'can_view_reports': profile.can_view_reports,
        'can_manage_users': profile.can_manage_users,
        'can_access_pos': profile.can_access_pos,
        'is_owner': profile.is_owner,
        'is_admin_or_above': profile.is_admin_or_above,
        'is_manager_or_above': profile.is_manager_or_above,
    }

    return ctx
