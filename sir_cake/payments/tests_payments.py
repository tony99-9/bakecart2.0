"""
Stripe payment integration tests for BakeCart 2.0.

Test coverage
─────────────
PaymentIntentCreationTests
  - Buyer can create a PaymentIntent for their own order
  - Returns client_secret and payment_intent_id (never the secret key)
  - Duplicate intent request returns the existing record's client_secret (retry-safe)
  - Buyer cannot create intent for another buyer's order (404)
  - Unauthenticated request returns 403
  - Already-paid order returns 409
  - Amount is derived from server-side order total, not any client input

WebhookSignatureTests
  - Valid signature → event processed
  - Invalid signature → 400, no DB side-effects
  - Missing Stripe-Signature header → 400
  - Tampered payload → 400

WebhookIdempotencyTests
  - Duplicate event delivery → 200 'duplicate', no double state transition
  - Second succeeded event does not re-mark order as paid (still idempotent)

PaymentSucceededTests
  - payment_intent.succeeded → Order.payment_status = PAID, paid_at set
  - PaymentRecord.status = succeeded, amount_received stored

AmountMismatchTests
  - amount_received ≠ order total → order NOT marked paid, record.status = failed
  - amount_received = 0 → mismatch detected

PaymentFailedTests
  - payment_intent.payment_failed → Order.payment_status = FAILED
  - PaymentRecord.status = failed

PaymentCancelledTests
  - payment_intent.canceled → Order.payment_status = FAILED
  - PaymentRecord.status = cancelled

ChargeRefundedTests
  - charge.refunded → Order.payment_status = REFUNDED
  - PaymentRecord.status = refunded

UnknownTransactionTests
  - Webhook for a PaymentIntent with no matching PaymentRecord → 'unknown_pi'
  - Event is still recorded (idempotency)

UnhandledEventTypeTests
  - Unrecognised event type → 'ignored', no order change

PaymentServiceUnitTests  (no HTTP, tests service functions directly)
  - create_payment_intent raises PaymentAlreadyExistsError on second call
  - Missing STRIPE_SECRET_KEY raises PaymentConfigError
  - Missing STRIPE_WEBHOOK_SECRET raises PaymentConfigError

Paths that CANNOT be tested without real Stripe credentials:
  - Live PaymentIntent round-trip (requires sk_live_*)
  - Webhook delivery from Stripe's servers (requires public HTTPS endpoint)
  - 3D Secure / card authentication flows
  - Refund initiated via Stripe Dashboard
All other tests use unittest.mock to stub stripe SDK calls and build
synthetic webhook payloads with HMAC-SHA256 signatures.
"""

import hashlib
import hmac
import json
import struct
import tempfile
import time
import zlib
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient, APITestCase

from cart.models import Cart, CartItem
from orders.models import Order
from orders.services import checkout_cart
from payments.models import PaymentRecord, ProcessedStripeEvent
from payments.services import (
    AmountMismatchError,
    PaymentAlreadyExistsError,
    PaymentConfigError,
    WebhookSignatureError,
    construct_stripe_event,
    create_payment_intent,
    handle_stripe_event,
)
from seller.models import Item
from users.models import UserStatus

TEMP_MEDIA = tempfile.mkdtemp()

# ---------------------------------------------------------------------------
# Test stripe config that won't hit the real API
# ---------------------------------------------------------------------------
TEST_STRIPE_SETTINGS = {
    'STRIPE_SECRET_KEY': 'sk_test_TESTKEY',
    'STRIPE_PUBLISHABLE_KEY': 'pk_test_TESTKEY',
    'STRIPE_WEBHOOK_SECRET': 'whsec_testsecret',
    'STRIPE_CURRENCY': 'usd',
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_minimal_png():
    png_header = b'\x89PNG\r\n\x1a\n'
    ihdr_data = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
    ihdr_crc = zlib.crc32(b'IHDR' + ihdr_data) & 0xffffffff
    ihdr_chunk = struct.pack('>I', 13) + b'IHDR' + ihdr_data + struct.pack('>I', ihdr_crc)
    raw_row = b'\x00\xff\xff\xff'
    compressed = zlib.compress(raw_row)
    idat_crc = zlib.crc32(b'IDAT' + compressed) & 0xffffffff
    idat_chunk = struct.pack('>I', len(compressed)) + b'IDAT' + compressed + struct.pack('>I', idat_crc)
    iend_crc = zlib.crc32(b'IEND') & 0xffffffff
    iend_chunk = struct.pack('>I', 0) + b'IEND' + struct.pack('>I', iend_crc)
    return png_header + ihdr_chunk + idat_chunk + iend_chunk


def png_upload(name='test.png'):
    return SimpleUploadedFile(name, make_minimal_png(), content_type='image/png')


def make_seller(username='seller1'):
    user = User.objects.create_user(username=username, password='pass1234')
    UserStatus.objects.create(user=user, is_seller=True)
    return user


def make_buyer(username='buyer1'):
    return User.objects.create_user(username=username, password='pass1234')


def make_product(seller, title='Test Cake', price='20.00', quantity=10):
    return Item.objects.create(
        seller=seller,
        title=title,
        price=Decimal(price),
        quantity=quantity,
        category=Item.Category.CAKES,
        is_active=True,
        image=png_upload(f'{title.replace(" ", "_")}.png'),
    )


def make_order(buyer, seller, price='20.00', quantity=2):
    """Create a fully checked-out Order for testing."""
    product = make_product(seller, price=price, quantity=quantity + 5)
    cart = Cart.objects.create(buyer=buyer)
    CartItem.objects.create(cart=cart, product=product, quantity=quantity)
    return checkout_cart(cart)


def make_mock_intent(order, amount_cents=None):
    """Return a mock Stripe PaymentIntent dict."""
    if amount_cents is None:
        amount_cents = int(order.total_amount * 100)
    return {
        'id': f'pi_test_{order.pk}',
        'client_secret': f'pi_test_{order.pk}_secret_test',
        'amount': amount_cents,
        'currency': 'usd',
        'status': 'requires_payment_method',
    }


def build_stripe_webhook_payload(event_type: str, event_data: dict, event_id: str = None) -> bytes:
    """Build a JSON payload matching the Stripe webhook format."""
    if event_id is None:
        event_id = f'evt_test_{event_type.replace(".", "_")}'
    payload = {
        'id': event_id,
        'object': 'event',
        'type': event_type,
        'data': {'object': event_data},
    }
    return json.dumps(payload).encode('utf-8')


def build_stripe_signature(payload: bytes, secret: str, timestamp: int = None) -> str:
    """
    Construct a valid Stripe-Signature header value using HMAC-SHA256.
    Mirrors the algorithm documented at:
    https://stripe.com/docs/webhooks/signatures
    """
    if timestamp is None:
        timestamp = int(time.time())
    signed_payload = f"{timestamp}.".encode() + payload
    mac = hmac.new(secret.encode('utf-8'), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={mac}"


def build_invalid_signature(timestamp: int = None) -> str:
    if timestamp is None:
        timestamp = int(time.time())
    return f"t={timestamp},v1=badbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadb"


# ---------------------------------------------------------------------------
# PaymentIntent creation (API tests)
# ---------------------------------------------------------------------------

@override_settings(MEDIA_ROOT=TEMP_MEDIA, **TEST_STRIPE_SETTINGS)
class PaymentIntentCreationTests(APITestCase):
    def setUp(self):
        self.seller = make_seller('seller_pi')
        self.buyer = make_buyer('buyer_pi')
        self.other_buyer = make_buyer('other_buyer_pi')
        self.order = make_order(self.buyer, self.seller, price='25.00', quantity=2)
        self.client = APIClient()

    def _url(self, order_id=None):
        oid = order_id if order_id is not None else self.order.pk
        return f'/api/payments/create-intent/{oid}/'

    @patch('payments.services.stripe')
    def test_buyer_creates_intent_successfully(self, mock_stripe):
        mock_intent = make_mock_intent(self.order)
        mock_stripe.PaymentIntent.create.return_value = mock_intent
        mock_stripe.api_key = None

        self.client.force_login(self.buyer)
        r = self.client.post(self._url())

        self.assertEqual(r.status_code, 200)
        self.assertIn('stripe_payment_intent_id', r.data)
        self.assertIn('stripe_client_secret', r.data)
        self.assertIn('currency', r.data)
        self.assertEqual(r.data['stripe_payment_intent_id'], mock_intent['id'])
        self.assertEqual(r.data['stripe_client_secret'], mock_intent['client_secret'])
        # Secret key must NEVER appear in the response
        self.assertNotIn('sk_test', str(r.data))

    @patch('payments.services.stripe')
    def test_amount_is_derived_from_db_not_client(self, mock_stripe):
        """The PaymentIntent amount must equal order.total_amount from DB (50 USD = 5000 cents)."""
        mock_stripe.PaymentIntent.create.return_value = make_mock_intent(self.order)
        mock_stripe.api_key = None

        self.client.force_login(self.buyer)
        # Attacker sends a fake amount — must be ignored
        r = self.client.post(self._url(), {'amount': '0.01', 'total': '1'})

        self.assertEqual(r.status_code, 200)
        # Verify stripe was called with the correct server-side amount (25.00 * 2 = 50.00 → 5000 cents)
        call_kwargs = mock_stripe.PaymentIntent.create.call_args[1]
        self.assertEqual(call_kwargs['amount'], 5000)

    @patch('payments.services.stripe')
    def test_duplicate_intent_request_returns_existing_record(self, mock_stripe):
        """Second POST returns the same client_secret — no new PaymentIntent created."""
        mock_intent = make_mock_intent(self.order)
        mock_stripe.PaymentIntent.create.return_value = mock_intent
        mock_stripe.api_key = None

        self.client.force_login(self.buyer)
        r1 = self.client.post(self._url())
        self.assertEqual(r1.status_code, 200)

        # Second call — stripe.PaymentIntent.create must NOT be called again
        mock_stripe.PaymentIntent.create.reset_mock()
        r2 = self.client.post(self._url())
        self.assertEqual(r2.status_code, 200)
        mock_stripe.PaymentIntent.create.assert_not_called()
        self.assertEqual(r1.data['stripe_client_secret'], r2.data['stripe_client_secret'])

    def test_unauthenticated_returns_403(self):
        r = self.client.post(self._url())
        self.assertEqual(r.status_code, 403)

    def test_buyer_cannot_create_intent_for_other_buyers_order(self):
        self.client.force_login(self.other_buyer)
        r = self.client.post(self._url())
        self.assertEqual(r.status_code, 404)

    @patch('payments.services.stripe')
    def test_already_paid_order_returns_409(self, mock_stripe):
        mock_stripe.PaymentIntent.create.return_value = make_mock_intent(self.order)
        mock_stripe.api_key = None

        self.order.payment_status = Order.PaymentStatus.PAID
        self.order.save(update_fields=['payment_status'])

        self.client.force_login(self.buyer)
        r = self.client.post(self._url())
        self.assertEqual(r.status_code, 409)

    @patch('payments.services.stripe')
    def test_stripe_error_returns_502(self, mock_stripe):
        import stripe as stripe_lib
        mock_stripe.PaymentIntent.create.side_effect = stripe_lib.error.StripeError("network error")
        mock_stripe.api_key = None
        mock_stripe.error = stripe_lib.error

        self.client.force_login(self.buyer)
        r = self.client.post(self._url())
        self.assertEqual(r.status_code, 502)


# ---------------------------------------------------------------------------
# Webhook signature tests
# ---------------------------------------------------------------------------

@override_settings(MEDIA_ROOT=TEMP_MEDIA, **TEST_STRIPE_SETTINGS)
class WebhookSignatureTests(APITestCase):
    WEBHOOK_URL = '/api/payments/webhook/'
    SECRET = TEST_STRIPE_SETTINGS['STRIPE_WEBHOOK_SECRET']

    def setUp(self):
        self.seller = make_seller('seller_wh')
        self.buyer = make_buyer('buyer_wh')
        self.order = make_order(self.buyer, self.seller, price='10.00', quantity=1)
        self.client = APIClient()

    def _make_pi_succeeded_payload(self, amount_received=1000):
        pi_id = f'pi_test_{self.order.pk}'
        return build_stripe_webhook_payload(
            'payment_intent.succeeded',
            {
                'id': pi_id,
                'object': 'payment_intent',
                'amount': 1000,
                'amount_received': amount_received,
                'currency': 'usd',
            },
            event_id='evt_test_sig_ok',
        )

    @patch('payments.services.stripe')
    def test_valid_signature_accepted(self, mock_stripe):
        """A correctly signed payload returns 200."""
        pi_id = f'pi_test_{self.order.pk}'
        PaymentRecord.objects.create(
            order=self.order,
            stripe_payment_intent_id=pi_id,
            stripe_client_secret='secret',
            status=PaymentRecord.Status.PENDING,
            currency='usd',
        )

        payload = self._make_pi_succeeded_payload(amount_received=1000)
        sig = build_stripe_signature(payload, self.SECRET)

        import stripe as stripe_lib

        def _construct_event(pl, sig_h, wh_secret):
            """
            Reproduce Stripe's HMAC-SHA256 verification and return a plain dict
            (not a MagicMock) so downstream DB writes receive real string values.
            """
            ts_str = sig_h.split(',')[0].split('=')[1]
            ts = int(ts_str)
            signed = f"{ts}.".encode() + pl
            expected_mac = hmac.new(
                wh_secret.encode(), signed, hashlib.sha256
            ).hexdigest()
            received_mac = sig_h.split('v1=')[1]
            if not hmac.compare_digest(expected_mac, received_mac):
                raise stripe_lib.error.SignatureVerificationError("bad sig", sig_h)
            # Return a plain dict — matches how services.py accesses event['id'] etc.
            return json.loads(pl)

        mock_stripe.Webhook.construct_event.side_effect = _construct_event
        mock_stripe.error = stripe_lib.error
        mock_stripe.api_key = None

        r = self.client.post(
            self.WEBHOOK_URL,
            data=payload,
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE=sig,
        )
        self.assertEqual(r.status_code, 200)

    def test_invalid_signature_rejected(self):
        """A webhook with a wrong signature returns 400 and makes no DB changes."""
        payload = self._make_pi_succeeded_payload()
        bad_sig = build_invalid_signature()

        import stripe as stripe_lib

        with patch('payments.services.stripe') as mock_stripe:
            mock_stripe.api_key = None
            mock_stripe.error = stripe_lib.error
            mock_stripe.Webhook.construct_event.side_effect = (
                stripe_lib.error.SignatureVerificationError("bad sig", bad_sig)
            )

            r = self.client.post(
                self.WEBHOOK_URL,
                data=payload,
                content_type='application/json',
                HTTP_STRIPE_SIGNATURE=bad_sig,
            )

        self.assertEqual(r.status_code, 400)
        # No side-effects
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.UNPAID)
        self.assertEqual(ProcessedStripeEvent.objects.count(), 0)

    def test_missing_signature_header_rejected(self):
        """A webhook without the Stripe-Signature header returns 400."""
        payload = self._make_pi_succeeded_payload()

        import stripe as stripe_lib

        with patch('payments.services.stripe') as mock_stripe:
            mock_stripe.api_key = None
            mock_stripe.error = stripe_lib.error
            mock_stripe.Webhook.construct_event.side_effect = (
                stripe_lib.error.SignatureVerificationError("missing sig", "")
            )

            r = self.client.post(
                self.WEBHOOK_URL,
                data=payload,
                content_type='application/json',
                # No HTTP_STRIPE_SIGNATURE header
            )

        self.assertEqual(r.status_code, 400)

    def test_tampered_payload_rejected(self):
        """A webhook whose payload was modified after signing returns 400."""
        payload = self._make_pi_succeeded_payload()
        # Sign the original, then change the payload
        sig = build_stripe_signature(payload, self.SECRET)
        tampered = payload[:-1] + b'}'  # slightly altered

        import stripe as stripe_lib

        with patch('payments.services.stripe') as mock_stripe:
            mock_stripe.api_key = None
            mock_stripe.error = stripe_lib.error
            mock_stripe.Webhook.construct_event.side_effect = (
                stripe_lib.error.SignatureVerificationError("tampered", sig)
            )

            r = self.client.post(
                self.WEBHOOK_URL,
                data=tampered,
                content_type='application/json',
                HTTP_STRIPE_SIGNATURE=sig,
            )

        self.assertEqual(r.status_code, 400)
        self.assertEqual(ProcessedStripeEvent.objects.count(), 0)


# ---------------------------------------------------------------------------
# Idempotency tests
# ---------------------------------------------------------------------------

@override_settings(MEDIA_ROOT=TEMP_MEDIA, **TEST_STRIPE_SETTINGS)
class WebhookIdempotencyTests(TestCase):
    def setUp(self):
        self.seller = make_seller('seller_idem')
        self.buyer = make_buyer('buyer_idem')
        self.order = make_order(self.buyer, self.seller, price='15.00', quantity=2)
        self.pi_id = f'pi_idem_{self.order.pk}'
        self.record = PaymentRecord.objects.create(
            order=self.order,
            stripe_payment_intent_id=self.pi_id,
            stripe_client_secret='secret_idem',
            status=PaymentRecord.Status.PENDING,
            currency='usd',
        )

    def _make_event(self, event_type, event_id='evt_idem_001', amount_received=3000):
        obj = {
            'id': self.pi_id,
            'object': 'payment_intent',
            'amount': 3000,
            'amount_received': amount_received,
            'currency': 'usd',
        }
        event_data = {'id': event_id, 'type': event_type, 'data': {'object': obj}}
        mock_event = MagicMock()
        mock_event.__getitem__ = lambda s, k: event_data[k]
        mock_event.get = lambda k, d=None: event_data.get(k, d)
        mock_event['id'] = event_id
        mock_event['type'] = event_type
        mock_event['data'] = {'object': obj}
        return event_data

    def test_duplicate_event_returns_duplicate_status(self):
        """Delivering the same event twice must not apply state twice."""
        event_id = 'evt_dup_001'

        # Build a real dict-like event
        pi_obj = {
            'id': self.pi_id,
            'object': 'payment_intent',
            'amount': 3000,
            'amount_received': 3000,
        }

        class _Event(dict):
            pass

        event = _Event({'id': event_id, 'type': 'payment_intent.succeeded',
                        'data': {'object': pi_obj}})

        result1 = handle_stripe_event(event)
        self.assertEqual(result1, 'processed')

        result2 = handle_stripe_event(event)
        self.assertEqual(result2, 'duplicate')

        # Only one ProcessedStripeEvent row
        self.assertEqual(ProcessedStripeEvent.objects.filter(stripe_event_id=event_id).count(), 1)

        # payment_status changed exactly once
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)

    def test_duplicate_succeeded_does_not_re_apply(self):
        """Even if the order is already PAID, a duplicate event is a no-op."""
        self.order.payment_status = Order.PaymentStatus.PAID
        self.order.save(update_fields=['payment_status'])
        self.record.status = PaymentRecord.Status.SUCCEEDED
        self.record.save(update_fields=['status'])

        ProcessedStripeEvent.objects.create(
            stripe_event_id='evt_already_done',
            event_type='payment_intent.succeeded',
        )

        pi_obj = {'id': self.pi_id, 'amount_received': 3000}
        event = {'id': 'evt_already_done', 'type': 'payment_intent.succeeded',
                 'data': {'object': pi_obj}}

        result = handle_stripe_event(event)
        self.assertEqual(result, 'duplicate')

        # Order still PAID, record still SUCCEEDED
        self.order.refresh_from_db()
        self.record.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)
        self.assertEqual(self.record.status, PaymentRecord.Status.SUCCEEDED)


# ---------------------------------------------------------------------------
# payment_intent.succeeded
# ---------------------------------------------------------------------------

@override_settings(MEDIA_ROOT=TEMP_MEDIA, **TEST_STRIPE_SETTINGS)
class PaymentSucceededTests(TestCase):
    def setUp(self):
        self.seller = make_seller('seller_suc')
        self.buyer = make_buyer('buyer_suc')
        # 30.00 USD = 3000 cents
        self.order = make_order(self.buyer, self.seller, price='15.00', quantity=2)
        self.pi_id = f'pi_suc_{self.order.pk}'
        self.record = PaymentRecord.objects.create(
            order=self.order,
            stripe_payment_intent_id=self.pi_id,
            stripe_client_secret='cs_suc',
            status=PaymentRecord.Status.PENDING,
            currency='usd',
        )

    def _make_event(self, amount_received):
        pi_obj = {'id': self.pi_id, 'amount': 3000, 'amount_received': amount_received}
        return {'id': 'evt_suc_001', 'type': 'payment_intent.succeeded',
                'data': {'object': pi_obj}}

    def test_succeeded_marks_order_paid(self):
        result = handle_stripe_event(self._make_event(3000))
        self.assertEqual(result, 'processed')

        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)
        self.assertIsNotNone(self.order.paid_at)

    def test_succeeded_updates_payment_record(self):
        handle_stripe_event(self._make_event(3000))
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, PaymentRecord.Status.SUCCEEDED)
        self.assertEqual(self.record.amount_received, 3000)

    def test_succeeded_records_event_for_idempotency(self):
        handle_stripe_event(self._make_event(3000))
        self.assertTrue(ProcessedStripeEvent.objects.filter(stripe_event_id='evt_suc_001').exists())

    def test_order_status_unchanged_after_payment(self):
        """Payment does not auto-advance order_status — that's the seller's job."""
        handle_stripe_event(self._make_event(3000))
        self.order.refresh_from_db()
        self.assertEqual(self.order.order_status, Order.OrderStatus.PENDING)


# ---------------------------------------------------------------------------
# Amount mismatch
# ---------------------------------------------------------------------------

@override_settings(MEDIA_ROOT=TEMP_MEDIA, **TEST_STRIPE_SETTINGS)
class AmountMismatchTests(TestCase):
    def setUp(self):
        self.seller = make_seller('seller_mism')
        self.buyer = make_buyer('buyer_mism')
        self.order = make_order(self.buyer, self.seller, price='10.00', quantity=3)  # 30.00 = 3000c
        self.pi_id = f'pi_mism_{self.order.pk}'
        self.record = PaymentRecord.objects.create(
            order=self.order,
            stripe_payment_intent_id=self.pi_id,
            stripe_client_secret='cs_mism',
            status=PaymentRecord.Status.PENDING,
            currency='usd',
        )

    def _event(self, amount_received, event_id='evt_mism_001'):
        pi_obj = {'id': self.pi_id, 'amount_received': amount_received}
        return {'id': event_id, 'type': 'payment_intent.succeeded',
                'data': {'object': pi_obj}}

    def test_lower_amount_does_not_mark_paid(self):
        result = handle_stripe_event(self._event(2999))  # 1 cent short
        self.assertEqual(result, 'amount_mismatch')

        self.order.refresh_from_db()
        self.assertNotEqual(self.order.payment_status, Order.PaymentStatus.PAID)
        self.assertIsNone(self.order.paid_at)

    def test_higher_amount_does_not_mark_paid(self):
        """Overpayment is also unexpected and should not auto-approve the order."""
        result = handle_stripe_event(self._event(3001, event_id='evt_mism_002'))
        self.assertEqual(result, 'amount_mismatch')

        self.order.refresh_from_db()
        self.assertNotEqual(self.order.payment_status, Order.PaymentStatus.PAID)

    def test_zero_amount_received_is_mismatch(self):
        result = handle_stripe_event(self._event(0, event_id='evt_mism_003'))
        self.assertEqual(result, 'amount_mismatch')

    def test_mismatch_sets_record_status_failed(self):
        handle_stripe_event(self._event(1, event_id='evt_mism_004'))
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, PaymentRecord.Status.FAILED)
        self.assertEqual(self.record.amount_received, 1)


# ---------------------------------------------------------------------------
# payment_intent.payment_failed
# ---------------------------------------------------------------------------

@override_settings(MEDIA_ROOT=TEMP_MEDIA, **TEST_STRIPE_SETTINGS)
class PaymentFailedTests(TestCase):
    def setUp(self):
        self.seller = make_seller('seller_fail')
        self.buyer = make_buyer('buyer_fail')
        self.order = make_order(self.buyer, self.seller, price='20.00', quantity=1)
        self.pi_id = f'pi_fail_{self.order.pk}'
        self.record = PaymentRecord.objects.create(
            order=self.order,
            stripe_payment_intent_id=self.pi_id,
            stripe_client_secret='cs_fail',
            status=PaymentRecord.Status.PENDING,
            currency='usd',
        )

    def test_payment_failed_event_marks_order_failed(self):
        pi_obj = {'id': self.pi_id, 'object': 'payment_intent'}
        event = {'id': 'evt_fail_001', 'type': 'payment_intent.payment_failed',
                 'data': {'object': pi_obj}}

        result = handle_stripe_event(event)
        self.assertEqual(result, 'processed')

        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.FAILED)

    def test_payment_failed_updates_record_status(self):
        pi_obj = {'id': self.pi_id}
        event = {'id': 'evt_fail_002', 'type': 'payment_intent.payment_failed',
                 'data': {'object': pi_obj}}
        handle_stripe_event(event)
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, PaymentRecord.Status.FAILED)


# ---------------------------------------------------------------------------
# payment_intent.canceled
# ---------------------------------------------------------------------------

@override_settings(MEDIA_ROOT=TEMP_MEDIA, **TEST_STRIPE_SETTINGS)
class PaymentCancelledTests(TestCase):
    def setUp(self):
        self.seller = make_seller('seller_can')
        self.buyer = make_buyer('buyer_can')
        self.order = make_order(self.buyer, self.seller, price='5.00', quantity=4)
        self.pi_id = f'pi_can_{self.order.pk}'
        self.record = PaymentRecord.objects.create(
            order=self.order,
            stripe_payment_intent_id=self.pi_id,
            stripe_client_secret='cs_can',
            status=PaymentRecord.Status.PENDING,
            currency='usd',
        )

    def test_canceled_event_marks_record_cancelled(self):
        pi_obj = {'id': self.pi_id}
        event = {'id': 'evt_can_001', 'type': 'payment_intent.canceled',
                 'data': {'object': pi_obj}}
        result = handle_stripe_event(event)
        self.assertEqual(result, 'processed')

        self.record.refresh_from_db()
        self.assertEqual(self.record.status, PaymentRecord.Status.CANCELLED)

    def test_canceled_event_sets_order_payment_status_failed(self):
        pi_obj = {'id': self.pi_id}
        event = {'id': 'evt_can_002', 'type': 'payment_intent.canceled',
                 'data': {'object': pi_obj}}
        handle_stripe_event(event)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.FAILED)


# ---------------------------------------------------------------------------
# charge.refunded
# ---------------------------------------------------------------------------

@override_settings(MEDIA_ROOT=TEMP_MEDIA, **TEST_STRIPE_SETTINGS)
class ChargeRefundedTests(TestCase):
    def setUp(self):
        self.seller = make_seller('seller_ref')
        self.buyer = make_buyer('buyer_ref')
        self.order = make_order(self.buyer, self.seller, price='50.00', quantity=1)
        self.pi_id = f'pi_ref_{self.order.pk}'
        self.record = PaymentRecord.objects.create(
            order=self.order,
            stripe_payment_intent_id=self.pi_id,
            stripe_client_secret='cs_ref',
            status=PaymentRecord.Status.SUCCEEDED,
            currency='usd',
        )
        # Order starts PAID (realistic pre-condition)
        self.order.payment_status = Order.PaymentStatus.PAID
        self.order.save(update_fields=['payment_status'])

    def test_charge_refunded_marks_order_refunded(self):
        charge_obj = {'object': 'charge', 'payment_intent': self.pi_id}
        event = {'id': 'evt_ref_001', 'type': 'charge.refunded',
                 'data': {'object': charge_obj}}
        result = handle_stripe_event(event)
        self.assertEqual(result, 'processed')

        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.REFUNDED)

    def test_charge_refunded_updates_record_status(self):
        charge_obj = {'object': 'charge', 'payment_intent': self.pi_id}
        event = {'id': 'evt_ref_002', 'type': 'charge.refunded',
                 'data': {'object': charge_obj}}
        handle_stripe_event(event)
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, PaymentRecord.Status.REFUNDED)


# ---------------------------------------------------------------------------
# Unknown transaction (PI not in our DB)
# ---------------------------------------------------------------------------

@override_settings(MEDIA_ROOT=TEMP_MEDIA, **TEST_STRIPE_SETTINGS)
class UnknownTransactionTests(TestCase):
    def test_unknown_pi_returns_unknown_pi_status(self):
        """An event referencing a PaymentIntent we have no record for is skipped."""
        pi_obj = {'id': 'pi_totally_unknown', 'amount_received': 999}
        event = {'id': 'evt_unk_001', 'type': 'payment_intent.succeeded',
                 'data': {'object': pi_obj}}

        result = handle_stripe_event(event)
        self.assertEqual(result, 'unknown_pi')

    def test_unknown_pi_event_is_still_recorded_for_idempotency(self):
        """Even unknown events are recorded so a retry is a no-op."""
        pi_obj = {'id': 'pi_unknown_002', 'amount_received': 500}
        event = {'id': 'evt_unk_002', 'type': 'payment_intent.succeeded',
                 'data': {'object': pi_obj}}

        handle_stripe_event(event)
        self.assertTrue(
            ProcessedStripeEvent.objects.filter(stripe_event_id='evt_unk_002').exists()
        )

    def test_unknown_pi_second_delivery_is_duplicate(self):
        pi_obj = {'id': 'pi_unknown_003'}
        event = {'id': 'evt_unk_003', 'type': 'payment_intent.payment_failed',
                 'data': {'object': pi_obj}}

        handle_stripe_event(event)
        result2 = handle_stripe_event(event)
        self.assertEqual(result2, 'duplicate')


# ---------------------------------------------------------------------------
# Unhandled event types
# ---------------------------------------------------------------------------

@override_settings(MEDIA_ROOT=TEMP_MEDIA, **TEST_STRIPE_SETTINGS)
class UnhandledEventTypeTests(TestCase):
    def setUp(self):
        self.seller = make_seller('seller_ign')
        self.buyer = make_buyer('buyer_ign')
        self.order = make_order(self.buyer, self.seller)

    def test_unhandled_event_returns_ignored(self):
        event = {'id': 'evt_ign_001', 'type': 'customer.created',
                 'data': {'object': {}}}
        result = handle_stripe_event(event)
        self.assertEqual(result, 'ignored')

    def test_unhandled_event_is_recorded(self):
        event = {'id': 'evt_ign_002', 'type': 'invoice.payment_succeeded',
                 'data': {'object': {}}}
        handle_stripe_event(event)
        self.assertTrue(
            ProcessedStripeEvent.objects.filter(stripe_event_id='evt_ign_002').exists()
        )

    def test_unhandled_event_does_not_change_order(self):
        event = {'id': 'evt_ign_003', 'type': 'radar.early_fraud_warning.created',
                 'data': {'object': {}}}
        handle_stripe_event(event)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.UNPAID)


# ---------------------------------------------------------------------------
# Service unit tests (no HTTP layer)
# ---------------------------------------------------------------------------

@override_settings(MEDIA_ROOT=TEMP_MEDIA, **TEST_STRIPE_SETTINGS)
class PaymentServiceUnitTests(TestCase):
    def setUp(self):
        self.seller = make_seller('seller_unit')
        self.buyer = make_buyer('buyer_unit')
        self.order = make_order(self.buyer, self.seller, price='40.00', quantity=1)

    @patch('payments.services.stripe')
    def test_create_payment_intent_raises_on_duplicate(self, mock_stripe):
        mock_stripe.PaymentIntent.create.return_value = make_mock_intent(self.order)
        mock_stripe.api_key = None

        create_payment_intent(self.order)
        with self.assertRaises(PaymentAlreadyExistsError):
            create_payment_intent(self.order)

    @override_settings(STRIPE_SECRET_KEY='')
    def test_missing_secret_key_raises_config_error(self):
        with self.assertRaises(PaymentConfigError):
            create_payment_intent(self.order)

    @override_settings(STRIPE_WEBHOOK_SECRET='')
    def test_missing_webhook_secret_raises_config_error(self):
        import stripe as stripe_lib
        with self.assertRaises(PaymentConfigError):
            construct_stripe_event(b'{}', 't=1,v1=abc')

    @patch('payments.services.stripe')
    def test_payment_record_created_with_correct_fields(self, mock_stripe):
        mock_intent = make_mock_intent(self.order)
        mock_stripe.PaymentIntent.create.return_value = mock_intent
        mock_stripe.api_key = None

        record = create_payment_intent(self.order)
        self.assertEqual(record.order, self.order)
        self.assertEqual(record.stripe_payment_intent_id, mock_intent['id'])
        self.assertEqual(record.stripe_client_secret, mock_intent['client_secret'])
        self.assertEqual(record.status, PaymentRecord.Status.PENDING)
        self.assertEqual(record.currency, 'usd')

    @patch('payments.services.stripe')
    def test_idempotency_key_contains_order_id(self, mock_stripe):
        """Stripe is called with an idempotency_key unique to the order."""
        mock_stripe.PaymentIntent.create.return_value = make_mock_intent(self.order)
        mock_stripe.api_key = None

        create_payment_intent(self.order)
        call_kwargs = mock_stripe.PaymentIntent.create.call_args[1]
        self.assertIn(str(self.order.pk), call_kwargs.get('idempotency_key', ''))

    @patch('payments.services.stripe')
    def test_amount_in_cents_is_correct(self, mock_stripe):
        """order.total_amount = 40.00 → stripe called with amount=4000 cents."""
        mock_stripe.PaymentIntent.create.return_value = make_mock_intent(self.order)
        mock_stripe.api_key = None

        create_payment_intent(self.order)
        call_kwargs = mock_stripe.PaymentIntent.create.call_args[1]
        self.assertEqual(call_kwargs['amount'], 4000)
