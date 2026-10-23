"""Cart URL routes, mounted under /api/ in the root urls.py."""

from django.urls import path
from cart import api_views

urlpatterns = [
    path('cart/', api_views.cart_detail, name='cart_detail'),
    path('cart/items/', api_views.cart_items_list, name='cart_items_list'),
    path('cart/items/<int:item_id>/', api_views.cart_item_detail, name='cart_item_detail'),
]
