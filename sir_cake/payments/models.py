"""
PaymentRecord model for BakeCart 2.0.

Design decisions:
- payment_status on Order is the source of truth for fulfillment logic.
  PaymentRecord is the audit trail for the Stripe side.
- stripe_payment_intent_id is stored here, NOT on Order, to keep the Order
  model provider-agnostic.
- idempotency_key is stored per processed stripe_event_id so duplicate
  webhook deliveries are silently ignored.
- card numbers and security codes are never stored. Stripe handles tokenisation.
- amount_received is stored in the smallest currency unit (cents / paise) as
  returned by Stripe so we can verify it against the order total without
  floating-point arithmetic.
"""

from django.db import models
from django.utils import timezone

from orders.models import Order


class PaymentRecord(models.Model):
    """
    Associates a Stripe PaymentIntent with a local Order.

    One Order has at most one active PaymentRecord.  If a buyer retries after
    a failure we reuse the same PaymentIntent (idempotent creation via
    stripe_payment_intent_id) rather than creating a new record.
    """

    class Status:
        PENDING = 'pending'        # PaymentIntent created, awaiting confirmation
        SUCCEEDED = 'succeeded'    # payment_intent.succeeded received
        FAILED = 'failed'          # payment_intent.payment_failed received
        CANCELLED = 'cancelled'    # payment_intent.canceled received
        REFUNDED = 'refunded'      # charge.refunded received

        CHOICES = [
            (PENDING, 'Pending'),
            (SUCCEEDED, 'Succeeded'),
            (FAILED, 'Failed'),
            (CANCELLED, 'Cancelled'),
            (REFUNDED, 'Refunded'),
        ]

    order = models.OneToOneField(
        Order,
        on_delete=models.PROTECT,
        related_name='payment_record',
        help_text='The order this payment belongs to.',
    )
    stripe_payment_intent_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text='Stripe PaymentIntent ID (pi_xxx). Stored server-side only.',
    )
    stripe_client_secret = models.CharField(
        max_length=500,
        help_text=(
            'Stripe client secret sent to the frontend to complete payment. '
            'Not a secret from Stripe\'s perspective but treated as sensitive '
            '— do not log or return outside the create-intent endpoint.'
        ),
    )
    status = models.CharField(
        max_length=20,
        choices=Status.CHOICES,
        default=Status.PENDING,
        db_index=True,
    )
    # Amount in smallest currency unit (e.g. cents), as confirmed by Stripe.
    # NULL until the webhook fires; used to detect mismatched amounts.
    amount_received = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Confirmed amount in smallest currency unit, populated by webhook.',
    )
    currency = models.CharField(
        max_length=3,
        default='usd',
        help_text='ISO 4217 lower-case currency code used for this PaymentIntent.',
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return (
            f"PaymentRecord(order={self.order_id}, "
            f"pi={self.stripe_payment_intent_id}, status={self.status})"
        )


class ProcessedStripeEvent(models.Model):
    """
    Records every Stripe webhook event that has been fully processed.

    Purpose: idempotent webhook handling.  Before processing any event we
    check whether its ID is already here.  If it is, we return 200 immediately
    without re-applying side-effects.

    Stripe guarantees at-least-once delivery; this table provides
    exactly-once processing.
    """

    stripe_event_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text='Stripe event ID (evt_xxx).',
    )
    event_type = models.CharField(
        max_length=100,
        help_text='Stripe event type string, e.g. payment_intent.succeeded.',
    )
    processed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-processed_at']

    def __str__(self):
        return f"ProcessedStripeEvent({self.stripe_event_id}, {self.event_type})"
