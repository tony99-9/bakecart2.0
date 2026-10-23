"""
Phase 5 tests for BakeCart 2.0: Cart, Checkout, Orders, Inventory.

Test coverage:
  CartTests:
    - Buyer can create/view their cart
    - Add item to cart (success, stock validation, quantity=0 rejected)
    - Update cart item quantity
    - Remove cart item
    - Clear cart
    - Cross-user cart isolation (buyer A cannot see buyer B's cart items)
    - Client-supplied price in cart add request is ignored (no such field)
    - Unauthenticated access returns 403

  CheckoutTests:
    - Successful checkout: order created, stock decremented, cart deleted
    - Cart preserved on checkout failure (stock error)
    - Insufficient stock → 400, no order, no stock change
    - Inactive product → 400, no order, no stock change
    - Empty cart → 400
    - Duplicate checkout (second request after cart deleted) → 409
    - Client-supplied price in checkout request body is ignored
    - Transaction rollback: all-or-nothing (one bad item blocks entire order)

  OrderAccessTests:
    - Buyer can list and view own orders
    - Buyer cannot access another buyer's order (404)
    - Seller can view orders containing their products
    - Seller cannot view orders that do not contain their products
    - Admin can view all orders
    - Unauthenticated access → 403

  OrderStatusTransitionTests:
    - Seller: pending → processing (allowed)
    - Seller: processing → shipped (allowed)
    - Seller: pending → shipped (not allowed, skip processing)
    - Seller: delivered → cancelled (not allowed)
    - Admin: can perform extended transitions
    - Seller cannot update orders that do not contain their products

  ConcurrentCheckoutTest (TransactionTestCase):
    - Two concurrent checkout requests for the same product with quantity=1.
    - Exactly one should succeed; the other should fail with InsufficientStockError.
    - Post-condition: stock = 0, exactly one Order exists.
    - LIMITATION: This test uses threading against a real PostgreSQL connection.
      It is non-deterministic under load but demonstrates the mechanism.
      True isolation guarantees require a load-test harness; unit tests alone
      cannot fully verify concurrency safety.
"""

import struct
import tempfile
import threading
import zlib
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient, APITestCase

from cart.models import Cart, CartItem
from orders.models import Order, OrderItem
from orders.services import (
    CartEmptyError,
    InsufficientStockError,
    ProductUnavailableError,
    checkout_cart,
)
from seller.models import Item
from users.models import UserStatus

# Use a temp media root so uploaded test images don't pollute the real media dir
TEMP_MEDIA = tempfile.mkdtemp()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_minimal_png():
    """Return a valid 1x1 pixel PNG as bytes (no external files needed)."""
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


def make_product(seller, title='Choco Cake', price='10.00', quantity=10, active=True):
    product = Item.objects.create(
        seller=seller,
        title=title,
        price=Decimal(price),
        quantity=quantity,
        category=Item.Category.CAKES,
        is_active=active,
        image=png_upload(f'{title.replace(" ", "_")}.png'),
    )
    return product


# ---------------------------------------------------------------------------
# Cart tests
# ---------------------------------------------------------------------------

@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class CartTests(APITestCase):
    def setUp(self):
        self.seller = make_seller('seller_cart')
        self.buyer = make_buyer('buyer_cart')
        self.other_buyer = make_buyer('other_buyer_cart')
        self.product = make_product(self.seller, quantity=5)
        self.client = APIClient()

    # Helper
    def _add_to_cart(self, buyer, product, quantity):
        self.client.force_login(buyer)
        return self.client.post('/api/cart/items/', {
            'product_id': product.pk,
            'quantity': quantity,
        })

    def test_unauthenticated_cart_returns_403(self):
        r = self.client.get('/api/cart/')
        self.assertEqual(r.status_code, 403)

    def test_get_cart_creates_empty_cart(self):
        self.client.force_login(self.buyer)
        r = self.client.get('/api/cart/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['cart']['items'], [])

    def test_add_item_to_cart_success(self):
        r = self._add_to_cart(self.buyer, self.product, 2)
        self.assertEqual(r.status_code, 201)
        cart_data = r.data['cart']
        self.assertEqual(len(cart_data['items']), 1)
        self.assertEqual(cart_data['items'][0]['quantity'], 2)

    def test_add_item_quantity_zero_rejected(self):
        self.client.force_login(self.buyer)
        r = self.client.post('/api/cart/items/', {
            'product_id': self.product.pk,
            'quantity': 0,
        })
        self.assertEqual(r.status_code, 400)

    def test_add_item_negative_quantity_rejected(self):
        self.client.force_login(self.buyer)
        r = self.client.post('/api/cart/items/', {
            'product_id': self.product.pk,
            'quantity': -1,
        })
        self.assertEqual(r.status_code, 400)

    def test_add_item_exceeds_stock_rejected(self):
        r = self._add_to_cart(self.buyer, self.product, 999)
        self.assertEqual(r.status_code, 400)
        self.assertIn('quantity', r.data.get('details', {}))

    def test_add_item_idempotent_upsert(self):
        """Adding the same product twice replaces the quantity, not duplicates the row."""
        self._add_to_cart(self.buyer, self.product, 2)
        r = self._add_to_cart(self.buyer, self.product, 3)
        self.assertEqual(r.status_code, 200)
        cart_data = r.data['cart']
        self.assertEqual(len(cart_data['items']), 1, "Should still be 1 item, not 2")
        self.assertEqual(cart_data['items'][0]['quantity'], 3)

    def test_client_price_field_ignored(self):
        """
        Any 'price' or 'unit_price' field sent by the client must not affect
        the cart or order totals. The serializer has no such writable field.
        """
        self.client.force_login(self.buyer)
        r = self.client.post('/api/cart/items/', {
            'product_id': self.product.pk,
            'quantity': 1,
            'price': '0.01',           # attacker sends fake price
            'unit_price': '0.01',
        })
        # Request should succeed (extra fields ignored)
        self.assertIn(r.status_code, [200, 201])
        # Price in response must come from DB
        item = r.data['cart']['items'][0]
        self.assertEqual(Decimal(item['unit_price']), self.product.price)

    def test_update_cart_item_quantity(self):
        self._add_to_cart(self.buyer, self.product, 2)
        self.client.force_login(self.buyer)
        cart = Cart.objects.get(buyer=self.buyer)
        item = cart.items.first()

        r = self.client.patch(f'/api/cart/items/{item.pk}/', {'quantity': 4})
        self.assertEqual(r.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.quantity, 4)

    def test_remove_cart_item(self):
        self._add_to_cart(self.buyer, self.product, 2)
        self.client.force_login(self.buyer)
        cart = Cart.objects.get(buyer=self.buyer)
        item = cart.items.first()

        r = self.client.delete(f'/api/cart/items/{item.pk}/')
        self.assertEqual(r.status_code, 204)
        self.assertFalse(CartItem.objects.filter(pk=item.pk).exists())

    def test_clear_cart(self):
        self._add_to_cart(self.buyer, self.product, 2)
        self.client.force_login(self.buyer)
        r = self.client.delete('/api/cart/')
        self.assertEqual(r.status_code, 200)
        cart = Cart.objects.get(buyer=self.buyer)
        self.assertEqual(cart.items.count(), 0)

    def test_cross_user_cart_item_isolation(self):
        """buyer A cannot patch or delete buyer B's cart item."""
        self._add_to_cart(self.buyer, self.product, 2)
        cart_b = Cart.objects.get(buyer=self.buyer)
        item_b = cart_b.items.first()

        # other_buyer tries to manipulate buyer's cart item
        self.client.force_login(self.other_buyer)
        r = self.client.patch(f'/api/cart/items/{item_b.pk}/', {'quantity': 99})
        self.assertEqual(r.status_code, 404, "Should not see other buyer's cart item")

        r2 = self.client.delete(f'/api/cart/items/{item_b.pk}/')
        self.assertEqual(r2.status_code, 404)

    def test_inactive_product_not_addable(self):
        self.product.is_active = False
        self.product.save(update_fields=['is_active'])
        r = self._add_to_cart(self.buyer, self.product, 1)
        self.assertEqual(r.status_code, 400)


# ---------------------------------------------------------------------------
# Checkout tests
# ---------------------------------------------------------------------------

@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class CheckoutTests(APITestCase):
    def setUp(self):
        self.seller = make_seller('seller_co')
        self.buyer = make_buyer('buyer_co')
        self.client = APIClient()

    def _make_cart_with_product(self, quantity_in_cart=2, stock=10, price='15.00', active=True):
        product = make_product(self.seller, price=price, quantity=stock, active=active)
        cart, _ = Cart.objects.get_or_create(buyer=self.buyer)
        CartItem.objects.create(cart=cart, product=product, quantity=quantity_in_cart)
        return cart, product

    def test_successful_checkout(self):
        cart, product = self._make_cart_with_product(quantity_in_cart=2, stock=10)
        self.client.force_login(self.buyer)

        r = self.client.post('/api/checkout/')
        self.assertEqual(r.status_code, 201)

        order = r.data['order']
        self.assertEqual(order['order_status'], 'pending')
        self.assertEqual(order['payment_status'], 'unpaid')
        self.assertEqual(Decimal(order['total_amount']), Decimal('30.00'))

        # Verify stock decremented
        product.refresh_from_db()
        self.assertEqual(product.quantity, 8)

        # Verify cart is deleted
        self.assertFalse(Cart.objects.filter(buyer=self.buyer).exists())

        # Verify order items have purchase-time snapshots
        db_order = Order.objects.get(pk=order['id'])
        item = db_order.items.first()
        self.assertEqual(item.title_at_purchase, product.title)
        self.assertEqual(item.unit_price_at_purchase, product.price)
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.subtotal, Decimal('30.00'))

    def test_insufficient_stock_returns_400_no_order_no_stock_change(self):
        # Stock=1, requesting 5
        cart, product = self._make_cart_with_product(quantity_in_cart=5, stock=1)
        self.client.force_login(self.buyer)

        r = self.client.post('/api/checkout/')
        self.assertEqual(r.status_code, 400)
        self.assertIn('error', r.data)

        # No order created
        self.assertEqual(Order.objects.count(), 0)
        # Stock unchanged
        product.refresh_from_db()
        self.assertEqual(product.quantity, 1)
        # Cart preserved
        self.assertTrue(Cart.objects.filter(buyer=self.buyer).exists())

    def test_inactive_product_checkout_returns_400(self):
        cart, product = self._make_cart_with_product(active=False)
        self.client.force_login(self.buyer)

        r = self.client.post('/api/checkout/')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_empty_cart_checkout_returns_400(self):
        Cart.objects.get_or_create(buyer=self.buyer)  # empty cart
        self.client.force_login(self.buyer)

        r = self.client.post('/api/checkout/')
        self.assertEqual(r.status_code, 400)

    def test_duplicate_checkout_returns_409(self):
        """After a successful checkout the cart is deleted. A second POST returns 409."""
        cart, _ = self._make_cart_with_product()
        self.client.force_login(self.buyer)

        r1 = self.client.post('/api/checkout/')
        self.assertEqual(r1.status_code, 201)

        # Cart should be gone
        self.assertFalse(Cart.objects.filter(buyer=self.buyer).exists())

        r2 = self.client.post('/api/checkout/')
        self.assertEqual(r2.status_code, 409, "Duplicate checkout must return 409")

    def test_client_supplied_price_in_checkout_body_is_ignored(self):
        """
        Even if the attacker sends a price field in the checkout POST body,
        the server must use DB prices. The CheckoutSerializer has no 'price' field.
        Snapshot unit_price_at_purchase must equal the real DB price.
        """
        cart, product = self._make_cart_with_product(price='20.00')
        self.client.force_login(self.buyer)

        r = self.client.post('/api/checkout/', {
            'price': '0.01',
            'total': '0.02',
            'unit_price': '0.01',
        })
        self.assertEqual(r.status_code, 201)

        order = Order.objects.get(pk=r.data['order']['id'])
        item = order.items.first()
        self.assertEqual(item.unit_price_at_purchase, Decimal('20.00'),
                         "Snapshot must equal DB price, not client value")
        self.assertEqual(order.total_amount, Decimal('40.00'),
                         "Total must be qty(2) * DB_price(20) = 40")

    def test_transaction_rollback_on_partial_failure(self):
        """
        If the cart contains two products and the second one has insufficient stock,
        the entire checkout must roll back: no Order, no OrderItem, no stock decremented.
        """
        cart, _ = Cart.objects.get_or_create(buyer=self.buyer)

        product_a = make_product(self.seller, title='Cake A', quantity=10)
        product_b = make_product(self.seller, title='Cake B', quantity=1)

        CartItem.objects.create(cart=cart, product=product_a, quantity=2)
        CartItem.objects.create(cart=cart, product=product_b, quantity=5)  # exceeds stock=1

        self.client.force_login(self.buyer)
        r = self.client.post('/api/checkout/')
        self.assertEqual(r.status_code, 400)

        # Both products' stock must be unchanged (rollback)
        product_a.refresh_from_db()
        product_b.refresh_from_db()
        self.assertEqual(product_a.quantity, 10)
        self.assertEqual(product_b.quantity, 1)

        # No order created
        self.assertEqual(Order.objects.count(), 0)

    def test_checkout_service_raises_cart_empty(self):
        """Direct service layer test for CartEmptyError."""
        cart = Cart.objects.create(buyer=self.buyer)
        with self.assertRaises(CartEmptyError):
            checkout_cart(cart)

    def test_checkout_service_raises_insufficient_stock(self):
        """Direct service layer test for InsufficientStockError."""
        product = make_product(self.seller, quantity=2)
        cart = Cart.objects.create(buyer=self.buyer)
        CartItem.objects.create(cart=cart, product=product, quantity=5)
        with self.assertRaises(InsufficientStockError):
            checkout_cart(cart)

    def test_checkout_service_raises_product_unavailable(self):
        """Direct service layer test for ProductUnavailableError."""
        product = make_product(self.seller, quantity=5, active=False)
        cart = Cart.objects.create(buyer=self.buyer)
        CartItem.objects.create(cart=cart, product=product, quantity=1)
        with self.assertRaises(ProductUnavailableError):
            checkout_cart(cart)


# ---------------------------------------------------------------------------
# Order access control tests
# ---------------------------------------------------------------------------

@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class OrderAccessTests(APITestCase):
    def setUp(self):
        self.seller = make_seller('seller_access')
        self.buyer_a = make_buyer('buyer_a')
        self.buyer_b = make_buyer('buyer_b')
        self.admin = User.objects.create_superuser('admin_access', password='pass1234')
        self.client = APIClient()

        # Create a checkout for buyer_a
        product = make_product(self.seller, quantity=10)
        cart = Cart.objects.create(buyer=self.buyer_a)
        CartItem.objects.create(cart=cart, product=product, quantity=1)
        self.order_a = checkout_cart(cart)

    def test_buyer_can_list_own_orders(self):
        self.client.force_login(self.buyer_a)
        r = self.client.get('/api/orders/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data['orders']), 1)
        self.assertEqual(r.data['orders'][0]['id'], self.order_a.pk)

    def test_buyer_can_get_own_order_detail(self):
        self.client.force_login(self.buyer_a)
        r = self.client.get(f'/api/orders/{self.order_a.pk}/')
        self.assertEqual(r.status_code, 200)

    def test_buyer_cannot_see_other_buyers_order(self):
        self.client.force_login(self.buyer_b)
        r = self.client.get(f'/api/orders/{self.order_a.pk}/')
        self.assertEqual(r.status_code, 404, "Buyer B must not see Buyer A's order")

    def test_buyer_b_order_list_is_empty(self):
        self.client.force_login(self.buyer_b)
        r = self.client.get('/api/orders/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['orders'], [])

    def test_seller_can_see_orders_containing_their_products(self):
        self.client.force_login(self.seller)
        r = self.client.get('/api/seller/orders/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data['orders']), 1)

    def test_seller_sees_only_their_items_in_order(self):
        """
        A second seller's items should not appear in the first seller's response.
        """
        other_seller = make_seller('seller_other')
        product_other = make_product(other_seller, title='Other Cake', quantity=10)

        buyer2 = make_buyer('buyer_scope')
        cart2 = Cart.objects.create(buyer=buyer2)
        CartItem.objects.create(cart=cart2, product=product_other, quantity=1)
        checkout_cart(cart2)

        self.client.force_login(self.seller)
        r = self.client.get('/api/seller/orders/')
        self.assertEqual(r.status_code, 200)
        # seller should see only 1 order (their product)
        self.assertEqual(len(r.data['orders']), 1)
        # Items visible should belong to this seller only
        for order in r.data['orders']:
            for item in order['items']:
                item_obj = OrderItem.objects.get(pk=item['id'])
                self.assertEqual(item_obj.product.seller, self.seller)

    def test_admin_can_list_all_orders(self):
        self.client.force_login(self.admin)
        r = self.client.get('/api/admin/orders/')
        self.assertEqual(r.status_code, 200)
        ids = [o['id'] for o in r.data['orders']]
        self.assertIn(self.order_a.pk, ids)

    def test_unauthenticated_order_list_returns_403(self):
        r = self.client.get('/api/orders/')
        self.assertEqual(r.status_code, 403)

    def test_buyer_cannot_access_seller_orders_endpoint(self):
        self.client.force_login(self.buyer_a)
        r = self.client.get('/api/seller/orders/')
        self.assertEqual(r.status_code, 403)

    def test_buyer_cannot_access_admin_orders_endpoint(self):
        self.client.force_login(self.buyer_a)
        r = self.client.get('/api/admin/orders/')
        self.assertEqual(r.status_code, 403)


# ---------------------------------------------------------------------------
# Order status transition tests
# ---------------------------------------------------------------------------

@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class OrderStatusTransitionTests(APITestCase):
    def setUp(self):
        self.seller = make_seller('seller_st')
        self.buyer = make_buyer('buyer_st')
        self.admin = User.objects.create_superuser('admin_st', password='pass1234')
        self.client = APIClient()

        product = make_product(self.seller, quantity=10)
        cart = Cart.objects.create(buyer=self.buyer)
        CartItem.objects.create(cart=cart, product=product, quantity=1)
        self.order = checkout_cart(cart)

    def _update_status(self, actor, new_status):
        self.client.force_login(actor)
        return self.client.post(
            f'/api/seller/orders/{self.order.pk}/status/',
            {'order_status': new_status},
        )

    def test_seller_can_move_pending_to_processing(self):
        r = self._update_status(self.seller, 'processing')
        self.assertEqual(r.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.order_status, 'processing')

    def test_seller_can_move_processing_to_shipped(self):
        self.order.order_status = 'processing'
        self.order.save()
        r = self._update_status(self.seller, 'shipped')
        self.assertEqual(r.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.order_status, 'shipped')

    def test_seller_cannot_skip_processing(self):
        """pending → shipped directly should be rejected for sellers."""
        r = self._update_status(self.seller, 'shipped')
        self.assertEqual(r.status_code, 400)
        self.order.refresh_from_db()
        self.assertEqual(self.order.order_status, 'pending', "Status must not change")

    def test_seller_cannot_move_delivered_to_cancelled(self):
        self.order.order_status = 'delivered'
        self.order.save()
        r = self._update_status(self.seller, 'cancelled')
        self.assertEqual(r.status_code, 400)

    def test_admin_can_cancel_from_pending(self):
        r = self._update_status(self.admin, 'cancelled')
        self.assertEqual(r.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.order_status, 'cancelled')

    def test_invalid_status_string_returns_400(self):
        r = self._update_status(self.seller, 'nonexistent_status')
        self.assertEqual(r.status_code, 400)

    def test_seller_cannot_update_order_not_containing_their_products(self):
        other_seller = make_seller('seller_st_other')
        buyer2 = make_buyer('buyer_st_other')
        product2 = make_product(other_seller, quantity=5)
        cart2 = Cart.objects.create(buyer=buyer2)
        CartItem.objects.create(cart=cart2, product=product2, quantity=1)
        other_order = checkout_cart(cart2)

        # self.seller tries to update other_seller's order
        self.client.force_login(self.seller)
        r = self.client.post(
            f'/api/seller/orders/{other_order.pk}/status/',
            {'order_status': 'processing'},
        )
        self.assertEqual(r.status_code, 404, "Seller must not see or modify other seller's orders")


# ---------------------------------------------------------------------------
# Snapshot integrity test
# ---------------------------------------------------------------------------

@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class SnapshotIntegrityTest(APITestCase):
    """
    Verifies that order item snapshots are immutable even when the live product
    is later modified or deactivated.
    """

    def setUp(self):
        self.seller = make_seller('seller_snap')
        self.buyer = make_buyer('buyer_snap')
        self.client = APIClient()

    def test_snapshot_unaffected_by_product_price_change(self):
        product = make_product(self.seller, price='25.00', quantity=5)
        cart = Cart.objects.create(buyer=self.buyer)
        CartItem.objects.create(cart=cart, product=product, quantity=2)
        order = checkout_cart(cart)

        # Seller changes price after checkout
        product.price = Decimal('99.99')
        product.save(update_fields=['price'])

        order_item = order.items.first()
        self.assertEqual(order_item.unit_price_at_purchase, Decimal('25.00'))

    def test_snapshot_preserved_after_product_deactivated(self):
        product = make_product(self.seller, title='Vintage Tart', quantity=5)
        cart = Cart.objects.create(buyer=self.buyer)
        CartItem.objects.create(cart=cart, product=product, quantity=1)
        order = checkout_cart(cart)

        product.is_active = False
        product.save(update_fields=['is_active'])

        order_item = order.items.first()
        self.assertEqual(order_item.title_at_purchase, 'Vintage Tart')
        self.assertIsNotNone(order_item.pk)


# ---------------------------------------------------------------------------
# Concurrent checkout test (TransactionTestCase — real DB connections)
# ---------------------------------------------------------------------------

@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ConcurrentCheckoutTest(TransactionTestCase):
    """
    Concurrency test using real threads and real PostgreSQL transactions.

    CONCURRENCY VERIFICATION STATUS:
    - select_for_update() is used in the checkout service to lock product rows.
    - This test spawns two threads that simultaneously call checkout_cart()
      for the same product with stock=1.
    - Expected result: exactly one checkout succeeds, the other raises
      InsufficientStockError. Post-condition: stock=0, one Order in DB.

    KNOWN LIMITATION:
    - Django TestCase wraps each test in a transaction (so all threads share
      one DB connection and one transaction). TransactionTestCase does NOT wrap
      in a transaction, so each thread gets its own connection and proper
      row locking applies under PostgreSQL.
    - However, this test remains non-deterministic: if the test runner runs
      both checkouts sequentially (due to GIL, timing, or load), the locking
      mechanism is not actually exercised concurrently. The test validates the
      outcome (one success, one failure) but cannot guarantee that the locking
      prevented a race — it only shows that the result is correct.
    - True concurrency safety verification requires a dedicated load-testing
      harness (e.g., locust, k6) with multiple OS processes, not threads.
    - This test does NOT run under SQLite (select_for_update is a no-op on SQLite).
    """

    def _make_buyer_with_cart(self, username, product, quantity_in_cart):
        buyer = User.objects.create_user(username=username, password='pass1234')
        cart = Cart.objects.create(buyer=buyer)
        CartItem.objects.create(cart=cart, product=product, quantity=quantity_in_cart)
        return buyer, cart

    def test_concurrent_checkouts_prevent_overselling(self):
        seller = make_seller('seller_conc')
        product = make_product(seller, title='Last Cookie', quantity=1)

        _, cart_a = self._make_buyer_with_cart('conc_buyer_a', product, 1)
        _, cart_b = self._make_buyer_with_cart('conc_buyer_b', product, 1)

        results = []
        errors = []
        barrier = threading.Barrier(2)

        def do_checkout(cart):
            try:
                barrier.wait()  # sync start to maximise concurrency
                order = checkout_cart(cart)
                results.append(('success', order))
            except InsufficientStockError as e:
                results.append(('stock_error', str(e)))
            except Exception as e:
                errors.append(e)
            finally:
                # Close the thread-local DB connection so PostgreSQL does not
                # block the test runner from dropping the test database at teardown.
                from django.db import connections
                connections.close_all()

        t1 = threading.Thread(target=do_checkout, args=(cart_a,))
        t2 = threading.Thread(target=do_checkout, args=(cart_b,))

        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        # Surface any unexpected exceptions
        if errors:
            raise errors[0]

        successes = [r for r in results if r[0] == 'success']
        failures = [r for r in results if r[0] == 'stock_error']

        self.assertEqual(
            len(successes), 1,
            "Exactly one checkout must succeed when stock=1 and two buyers compete"
        )
        self.assertEqual(
            len(failures), 1,
            "Exactly one checkout must fail with InsufficientStockError"
        )

        # Post-condition: stock should be 0
        product.refresh_from_db()
        self.assertEqual(product.quantity, 0, "Stock must be exactly 0 after one successful checkout")

        # Post-condition: exactly one order
        self.assertEqual(Order.objects.count(), 1)
