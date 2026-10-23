"""Payments URL routes, mounted under /api/ in the root urls.py."""

from django.urls import path
from payments import api_views

urlpatterns = [
    path(
        'payments/create-intent/<int:order_id>/',
        api_views.create_payment_intent_view,
        name='payment_create_intent',
    ),
    path(
        'payments/webhook/',
        api_views.stripe_webhook_view,
        name='stripe_webhook',
    ),
]
