"""
URL configuration for product and seller management API endpoints.
Mounted under /api/ in the root urls.py.
"""
from django.urls import path

from seller import api_views

urlpatterns = [
    # Public product endpoints
    path('products/',                             api_views.product_list_view,           name='api_product_list'),
    path('products/categories/',                  api_views.product_categories_view,     name='api_product_categories'),
    path('products/<int:pk>/',                    api_views.product_detail_view,         name='api_product_detail'),

    # Seller endpoints
    path('seller/profile/',                       api_views.seller_profile_view,         name='api_seller_profile'),
    path('seller/summary/',                       api_views.seller_summary_metrics_view, name='api_seller_summary'),
    path('seller/products/',                      api_views.seller_product_list_view,    name='api_seller_product_list'),
    path('seller/products/<int:pk>/',             api_views.seller_product_detail_view,  name='api_seller_product_detail'),

    # Admin endpoints
    path('admin/products/',                       api_views.admin_product_list_view,     name='api_admin_product_list'),
    path('admin/products/<int:pk>/activate/',     api_views.admin_product_activate_view, name='api_admin_product_activate'),
]
