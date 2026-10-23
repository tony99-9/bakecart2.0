"""
URL configuration for BakeCart B2B Wholesale Platform.
"""
from django.urls import path
from . import api_views

urlpatterns = [
    # Bakeries & Catalogues
    path('bakeries/', api_views.bakeries_list_view, name='b2b_bakeries_list'),
    path('bakeries/<int:bakery_id>/catalogue/', api_views.bakery_catalogue_view, name='b2b_bakery_catalogue'),
    path('bakeries/<int:bakery_id>/authorize/', api_views.bakery_request_auth_view, name='b2b_bakery_authorize'),

    # Dealer Orders & Operations
    path('orders/', api_views.dealer_orders_list_view, name='b2b_dealer_orders_list'),
    path('orders/create/', api_views.dealer_order_create_view, name='b2b_dealer_order_create'),
    path('orders/<int:order_id>/', api_views.dealer_order_detail_view, name='b2b_dealer_order_detail'),
    path('orders/<int:order_id>/repeat/', api_views.dealer_repeat_order_view, name='b2b_dealer_order_repeat'),
    path('orders/<int:order_id>/receipt/', api_views.dealer_confirm_receipt_view, name='b2b_dealer_order_receipt'),

    # Bakery Owner Desk & Management
    path('bakery/orders/', api_views.bakery_orders_list_view, name='b2b_bakery_orders_list'),
    path('bakery/orders/<int:order_id>/action/', api_views.bakery_order_action_view, name='b2b_bakery_order_action'),
    path('bakery/dealers/', api_views.bakery_dealers_list_view, name='b2b_bakery_dealers_list'),
    path('bakery/profile/', api_views.bakery_profile_view, name='b2b_bakery_profile'),

    # Dealer Profile
    path('dealer/profile/', api_views.dealer_profile_view, name='b2b_dealer_profile'),

    # Admin Oversight
    path('admin/summary/', api_views.admin_b2b_summary_view, name='b2b_admin_summary'),
]
