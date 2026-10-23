"""Serializers for the payments app."""

from rest_framework import serializers

from payments.models import PaymentRecord


class PaymentIntentResponseSerializer(serializers.ModelSerializer):
    """
    Response body returned to the buyer after a PaymentIntent is created.

    Only client_secret and metadata needed by Stripe.js are exposed.
    The Stripe secret key is never included.
    """

    class Meta:
        model = PaymentRecord
        fields = [
            'stripe_payment_intent_id',
            'stripe_client_secret',
            'currency',
            'status',
        ]
        read_only_fields = fields
