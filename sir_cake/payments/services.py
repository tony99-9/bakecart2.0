"""
Stripe payment service layer for BakeCart 2.0.

Security invariants enforced here:
  - The PaymentIntent amount is always derived from order.total_amount stored
    in the DB at checkout time.  The client never supplies or influences the
    amount.
  - Webhook signatures are verified with stripe.Webhook.construct_event()
    using STRIPE_WEBHOOK_SECRET before any side-effects are applied.
  - Duplicate event delivery is detected via ProcessedStripeEvent.  If an
    event ID has already been recorded, the handler returns immediately.
  - After a payment_intent.succeeded event we compare amount_received against
    the order total converted to the smallest currency unit.  A mismatch is
    logged and the order is NOT marked as paid.
  - Card numbers and CVV codes are never seen, stored, or logged by this code.
    Stripe's client-side SDK (Stripe.js / React Stripe.js) handles tokenisation.

Test-mode:
  Set STRIPE_SECRET_KEY to a key starting with 'sk_test_' and
  STRIPE_WEBHOOK_SECRET to a whsec_ value from `stripe listen --forward-to`.
  All payment flows will hit Stripe's sandboxed infrastructure.

Currency:
  STRIPE_CURRENCY (default 'usd') must be a 3-letter ISO 4217 lower-case code.
  Stripe amounts are in the smallest unit (cents for USD/EUR, pence for GBP).
  order.total_amount is Decimal with 2 dp; multiply by 100 and convert to int.
"""

import logging
from decimal import Decimal

import stripe
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from orders.models import Order
from payments.models import PaymentRecord, ProcessedStripeEvent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Stripe SDK initialisation (lazy — avoids import-time errors when key absent)
# ---------------------------------------------------------------------------

def _stripe_api():
    """Return the stripe module configured with the secret key."""
    key = getattr(settings, 'STRIPE_SECRET_KEY', '')
    if not key:
        raise PaymentConfigError(
            "STRIPE_SECRET_KEY is not configured.  "
            "Add it to .env before processing payments."
        )
    stripe.api_key = key
    return stripe


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class PaymentError(Exception):
    """Base class for payment service errors."""


class PaymentConfigError(PaymentError):
    """Raised when required Stripe credentials are missing."""


class PaymentAlreadyExistsError(PaymentError):
    """Raised when a PaymentRecord already exists for this order."""


class WebhookSignatureError(PaymentError):
    """Raised when the Stripe-Signature header fails verification."""


class AmountMismatchError(PaymentError):
    """
    Raised when the amount Stripe confirmed differs from the order total.

    Attributes:
        expected_cents: Amount we expected (int, smallest currency unit).
        received_cents: Amount Stripe confirmed (int, smallest currency unit).
    """
    def __init__(self, expected_cents: int, received_cents: int):
        self.expected_cents = expected_cents
        self.received_cents = received_cents
        super().__init__(
            f"Amount mismatch: expected {expected_cents} cents, "
            f"got {received_cents} cents from Stripe."
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _order_total_in_cents(order: Order) -> int:
    """Convert order.total_amount (Decimal, 2 dp) to integer cents."""
    return int((order.total_amount * 100).quantize(Decimal('1')))


def _get_currency() -> str:
    return getattr(settings, 'STRIPE_CURRENCY', 'usd').lower()


# ---------------------------------------------------------------------------
# PaymentIntent creation  (called from the API view after checkout)
# ---------------------------------------------------------------------------

def create_payment_intent(order: Order) -> PaymentRecord:
    """
    Create a Stripe PaymentIntent for *order* and persist a PaymentRecord.

    The amount is derived exclusively from order.total_amount (server-side DB
    value set at checkout).  The client never supplies or influences it.

    Args:
        order: A fully created Order instance (payment_status must be UNPAID).

    Returns:
        A newly created PaymentRecord with status=PENDING.

    Raises:
        PaymentAlreadyExistsError: A PaymentRecord already exists for this order.
        PaymentConfigError: STRIPE_SECRET_KEY is not set.
        stripe.error.StripeError: Any Stripe API error.
    """
    if PaymentRecord.objects.filter(order=order).exists():
        raise PaymentAlreadyExistsError(
            f"A payment record already exists for order {order.pk}."
        )

    s = _stripe_api()
    currency = _get_currency()
    amount_cents = _order_total_in_cents(order)

    # Idempotency key: ties this PaymentIntent to exactly one order.
    # If the same request is retried (network timeout etc.) Stripe returns the
    # same PaymentIntent rather than creating a duplicate.
    idempotency_key = f"bakecart-order-{order.pk}"

    intent = s.PaymentIntent.create(
        amount=amount_cents,
        currency=currency,
        metadata={
            'bakecart_order_id': str(order.pk),
            'bakecart_buyer_id': str(order.buyer_id) if order.buyer_id else 'anon',
        },
        # Automatic payment methods covers cards, wallets, etc., without
        # listing each explicitly.
        automatic_payment_methods={'enabled': True},
        idempotency_key=idempotency_key,
    )

    record = PaymentRecord.objects.create(
        order=order,
        stripe_payment_intent_id=intent['id'],
        stripe_client_secret=intent['client_secret'],
        status=PaymentRecord.Status.PENDING,
        currency=currency,
    )

    logger.info(
        "PaymentIntent created: pi=%s order=%s amount_cents=%s currency=%s",
        intent['id'], order.pk, amount_cents, currency,
    )
    return record


# ---------------------------------------------------------------------------
# Webhook handling
# ---------------------------------------------------------------------------

def construct_stripe_event(payload: bytes, sig_header: str):
    """
    Verify the Stripe-Signature header and deserialise the event payload.

    Args:
        payload: Raw request body bytes (must NOT be decoded before passing).
        sig_header: Value of the 'Stripe-Signature' HTTP header.

    Returns:
        A stripe.Event object.

    Raises:
        PaymentConfigError: STRIPE_WEBHOOK_SECRET is not set.
        WebhookSignatureError: Signature verification failed.
    """
    secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')
    if not secret:
        raise PaymentConfigError(
            "STRIPE_WEBHOOK_SECRET is not configured.  "
            "Add it to .env to enable webhook verification."
        )

    s = _stripe_api()
    try:
        event = s.Webhook.construct_event(payload, sig_header, secret)
    except ValueError as exc:
        # Payload could not be parsed
        raise WebhookSignatureError(f"Invalid webhook payload: {exc}") from exc
    except stripe.error.SignatureVerificationError as exc:
        raise WebhookSignatureError(f"Stripe signature verification failed: {exc}") from exc

    return event


def handle_stripe_event(event) -> str:
    """
    Apply side-effects for a verified Stripe event, idempotently.

    Returns a short human-readable status string:
      'duplicate'   — event already processed; no action taken.
      'ignored'     — event type not handled by this integration.
      'processed'   — event handled and side-effects applied.
      'unknown_pi'  — PaymentRecord not found; event recorded and skipped.
      'amount_mismatch' — confirmed amount differs from order total; not paid.

    This function must NOT raise — it is called from the webhook view which
    always returns 200 to Stripe.  Failures are logged for human review.
    """
    event_id = event['id']
    event_type = event['type']

    # --- Idempotency gate ---
    if ProcessedStripeEvent.objects.filter(stripe_event_id=event_id).exists():
        logger.info("Duplicate Stripe event ignored: %s (%s)", event_id, event_type)
        return 'duplicate'

    handled_types = {
        'payment_intent.succeeded',
        'payment_intent.payment_failed',
        'payment_intent.canceled',
        'charge.refunded',
    }
    if event_type not in handled_types:
        # Record so we don't process it again, but take no order action.
        _record_event(event_id, event_type)
        logger.debug("Unhandled Stripe event type: %s", event_type)
        return 'ignored'

    # Extract the PaymentIntent ID from the event object
    obj = event['data']['object']
    if event_type == 'charge.refunded':
        pi_id = obj.get('payment_intent')
    else:
        pi_id = obj.get('id')

    if not pi_id:
        _record_event(event_id, event_type)
        logger.warning("Stripe event %s has no payment_intent id; skipped.", event_id)
        return 'unknown_pi'

    try:
        record = PaymentRecord.objects.select_related('order').get(
            stripe_payment_intent_id=pi_id
        )
    except PaymentRecord.DoesNotExist:
        _record_event(event_id, event_type)
        logger.warning(
            "No PaymentRecord for pi=%s event=%s; event recorded and skipped.",
            pi_id, event_id,
        )
        return 'unknown_pi'

    with transaction.atomic():
        result = _apply_event(event_type, obj, record)
        _record_event(event_id, event_type)

    return result


def _apply_event(event_type: str, obj, record: PaymentRecord) -> str:
    """Apply the state transition for a single verified, non-duplicate event."""
    order = record.order

    if event_type == 'payment_intent.succeeded':
        amount_received = obj.get('amount_received', 0)
        expected = _order_total_in_cents(order)

        if amount_received != expected:
            logger.error(
                "Amount mismatch for order %s: expected %s cents, "
                "Stripe confirmed %s cents.  Payment NOT applied. pi=%s",
                order.pk, expected, amount_received, record.stripe_payment_intent_id,
            )
            record.amount_received = amount_received
            record.status = PaymentRecord.Status.FAILED
            record.save(update_fields=['amount_received', 'status', 'updated_at'])
            # Do not mark order as paid
            return 'amount_mismatch'

        record.amount_received = amount_received
        record.status = PaymentRecord.Status.SUCCEEDED
        record.save(update_fields=['amount_received', 'status', 'updated_at'])

        order.payment_status = Order.PaymentStatus.PAID
        order.paid_at = timezone.now()
        order.save(update_fields=['payment_status', 'paid_at'])

        logger.info(
            "Order %s marked PAID via pi=%s amount=%s cents.",
            order.pk, record.stripe_payment_intent_id, amount_received,
        )
        return 'processed'

    elif event_type == 'payment_intent.payment_failed':
        record.status = PaymentRecord.Status.FAILED
        record.save(update_fields=['status', 'updated_at'])

        order.payment_status = Order.PaymentStatus.FAILED
        order.save(update_fields=['payment_status'])

        logger.info(
            "Payment FAILED for order %s pi=%s.",
            order.pk, record.stripe_payment_intent_id,
        )
        return 'processed'

    elif event_type == 'payment_intent.canceled':
        record.status = PaymentRecord.Status.CANCELLED
        record.save(update_fields=['status', 'updated_at'])

        order.payment_status = Order.PaymentStatus.FAILED
        order.save(update_fields=['payment_status'])

        logger.info(
            "PaymentIntent CANCELLED for order %s pi=%s.",
            order.pk, record.stripe_payment_intent_id,
        )
        return 'processed'

    elif event_type == 'charge.refunded':
        record.status = PaymentRecord.Status.REFUNDED
        record.save(update_fields=['status', 'updated_at'])

        order.payment_status = Order.PaymentStatus.REFUNDED
        order.save(update_fields=['payment_status'])

        logger.info(
            "Charge REFUNDED for order %s pi=%s.",
            order.pk, record.stripe_payment_intent_id,
        )
        return 'processed'

    return 'ignored'


def _record_event(event_id: str, event_type: str) -> None:
    """Persist a ProcessedStripeEvent row (idempotency log)."""
    ProcessedStripeEvent.objects.get_or_create(
        stripe_event_id=event_id,
        defaults={'event_type': event_type},
    )
