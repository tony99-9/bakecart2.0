"""
Stripe payment API views for BakeCart 2.0.

Endpoints:
  POST /api/payments/create-intent/<order_id>/
      Buyer creates a Stripe PaymentIntent for their order.
      Returns {client_secret, payment_intent_id} — never the secret key.

  POST /api/payments/webhook/
      Stripe webhook receiver.  Signature is verified with
      STRIPE_WEBHOOK_SECRET before any DB writes occur.
      Always returns HTTP 200 to Stripe (idempotent; errors are logged).

Security notes:
  - The frontend receives only the client_secret needed for Stripe.js.
  - A client-redirect or frontend 'success' message is never trusted.
    Order.payment_status transitions happen exclusively in the webhook handler
    after Stripe's server-to-server confirmation.
  - The raw request body is read before DRF can decode it so that the
    Stripe signature covers the exact bytes Stripe sent.
"""

import logging

import stripe
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from orders.models import Order
from payments.services import (
    PaymentAlreadyExistsError,
    PaymentConfigError,
    WebhookSignatureError,
    construct_stripe_event,
    create_payment_intent,
    handle_stripe_event,
)
from payments.serializers import PaymentIntentResponseSerializer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Create PaymentIntent
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_payment_intent_view(request, order_id):
    """
    POST /api/payments/create-intent/<order_id>/

    Creates a Stripe PaymentIntent for the given order and returns the
    client_secret to the authenticated buyer so Stripe.js can complete payment
    client-side.

    The buyer must own the order.  The amount is taken from the DB — never
    from the request body.
    """
    try:
        order = Order.objects.get(pk=order_id, buyer=request.user)
    except Order.DoesNotExist:
        return Response(
            {'error': 'Order not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if order.payment_status == Order.PaymentStatus.PAID:
        return Response(
            {'error': 'This order has already been paid.'},
            status=status.HTTP_409_CONFLICT,
        )

    try:
        record = create_payment_intent(order)
    except PaymentAlreadyExistsError:
        # Return the existing record's client_secret so the buyer can retry
        # using the same PaymentIntent (Stripe best practice for retries).
        record = order.payment_record
        logger.info(
            "Returning existing PaymentIntent for order %s pi=%s",
            order.pk, record.stripe_payment_intent_id,
        )
    except PaymentConfigError as exc:
        logger.error("Payment config error: %s", exc)
        return Response(
            {'error': 'Payment service is not configured.  Contact support.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except stripe.error.StripeError as exc:
        logger.error("Stripe API error creating intent for order %s: %s", order.pk, exc)
        return Response(
            {'error': 'Payment provider error.  Please try again.'},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    serializer = PaymentIntentResponseSerializer(record)
    return Response(serializer.data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Webhook receiver
# ---------------------------------------------------------------------------

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def stripe_webhook_view(request):
    """
    POST /api/payments/webhook/

    Receives Stripe webhook events.  Signature verification happens before
    any state is mutated.

    We always return 200 after successful verification so Stripe does not
    retry unnecessarily.  Actual processing errors are logged — not propagated
    as 4xx/5xx so Stripe keeps the event as 'delivered'.
    """
    payload = request.body  # raw bytes — must NOT use request.data
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

    try:
        event = construct_stripe_event(payload, sig_header)
    except WebhookSignatureError as exc:
        logger.warning("Webhook signature failure: %s", exc)
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except PaymentConfigError as exc:
        logger.error("Webhook config error: %s", exc)
        return Response(
            {'error': 'Webhook secret not configured.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    result = handle_stripe_event(event)
    logger.debug("Stripe event %s (%s) → %s", event['id'], event['type'], result)

    return Response({'status': result}, status=status.HTTP_200_OK)
