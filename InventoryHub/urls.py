"""
Root URL configuration for InventoryHub project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),

    # Redirect root to login
    path('', RedirectView.as_view(url='/accounts/login/', permanent=False)),

    # App URLs
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('core/', include('core.urls', namespace='core')),
    path('pharmacy/', include('pharmacy.urls', namespace='pharmacy')),
    path('grocery/', include('grocery.urls', namespace='grocery')),
    path('ecommerce/', include('ecommerce.urls', namespace='ecommerce')),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
