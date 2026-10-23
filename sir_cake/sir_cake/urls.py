"""sir_cake URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.0/topics/http/urls/
"""
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from django.contrib import admin
from django.http import JsonResponse

from sir_cake.health import health_check_view


def api_root(request):
    return JsonResponse({
        "name": "BakeCart B2B Platform API",
        "version": "2.0",
        "status": "operational",
        "endpoints": {
            "health": "/api/health/",
            "auth": "/api/auth/",
            "products": "/api/products/",
            "seller": "/api/seller/",
            "b2b": "/api/b2b/",
            "cart": "/api/cart/",
            "orders": "/api/orders/",
            "payments": "/api/payments/",
            "admin": "/admin/",
        }
    })


urlpatterns = [
    # Health check endpoint
    path('api/health/', health_check_view, name="health_check"),

    # Auth & user management API
    path('api/', include('users.urls')),

    # Product & seller management API
    path('api/', include('seller.urls')),

    # Cart API
    path('api/', include('cart.urls')),

    # Orders & checkout API
    path('api/', include('orders.urls')),

    # Stripe payment API
    path('api/', include('payments.urls')),

    # B2B Wholesale Ordering API
    path('api/b2b/', include('b2b.urls')),

    # Django Admin
    path('admin/', admin.site.urls),

    # Root API information
    path('', api_root, name="api_root"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
