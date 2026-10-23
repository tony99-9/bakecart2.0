"""Orders URL routes, mounted under /api/ in the root urls.py."""

from django.urls import path
from orders import api_views

urlpatterns = [
    path('checkout/', api_views.checkout_view, name='checkout'),
    path('orders/', api_views.buyer_order_list, name='buyer_order_list'),
    path('orders/<int:order_id>/', api_views.buyer_order_detail, name='buyer_order_detail'),
    path('seller/orders/', api_views.seller_order_list, name='seller_order_list'),
    path('seller/orders/<int:order_id>/status/', api_views.seller_order_status_update, name='seller_order_status_update'),
    path('admin/orders/', api_views.admin_order_list, name='admin_order_list'),
]
