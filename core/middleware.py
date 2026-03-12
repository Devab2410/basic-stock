from django.shortcuts import redirect
from django.contrib import messages


# Business type → URL prefix mapping
BUSINESS_TYPE_URL_MAP = {
    'pharmacy': '/pharmacy/',
    'grocery': '/grocery/',
    'ecommerce': '/ecommerce/',
}

# Protected URL prefixes and their required business_type codes
PROTECTED_PREFIXES = {
    '/pharmacy/': 'pharmacy',
    '/grocery/': 'grocery',
    '/ecommerce/': 'ecommerce',
}


class BusinessTypeAccessMiddleware:
    """
    Guards /pharmacy/, /grocery/, /ecommerce/ URL prefixes so that
    only users whose store's business_type code matches can access them.

    Superusers bypass this check entirely.
    Unauthenticated requests are NOT blocked here — handled by LoginRequiredMixin.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        if request.user.is_authenticated and not request.user.is_superuser:
            for prefix, required_code in PROTECTED_PREFIXES.items():
                if path.startswith(prefix):
                    # Check staff profile exists
                    if not request.user.has_staff_profile:
                        messages.error(request,
                            'Your account is not linked to any store. Contact your administrator.')
                        return redirect('/accounts/login/')

                    store = request.user.active_store
                    if not store or not store.business_type:
                        messages.error(request,
                            'Your store has no business type configured.')
                        return redirect('/core/dashboard/')

                    actual_code = store.business_type.code.lower()
                    if actual_code != required_code:
                        messages.warning(request,
                            f'You do not have access to the {required_code.title()} module.')
                        # Redirect to correct module
                        correct_url = BUSINESS_TYPE_URL_MAP.get(actual_code, '/core/dashboard/')
                        return redirect(correct_url)
                    break  # Only check the matched prefix

        return self.get_response(request)
