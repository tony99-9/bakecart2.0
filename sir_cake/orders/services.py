"""
Checkout service for BakeCart 2.0.

Concurrency strategy:
  select_for_update() acquires a row-level exclusive lock on each product row
  involved in the checkout. Concurrent transactions that also attempt
  select_for_update() on the same rows will block until the first transaction
  commits or rolls back. This prevents overselling under PostgreSQL's default
  READ COMMITTED isolation level.

Ordering guarantee:
  Products are locked in primary-key order (order_by('pk')) to prevent
  deadlocks when two concurrent checkouts share a subset of the same products.

Atomicity guarantee:
  The entire checkout (validation, Order creation, OrderItem creation,
  inventory decrement) runs inside a single transaction.atomic() block.
  Any exception (ValidationError, InsufficientStockError, DB error) causes
  a full rollback: no Order, no OrderItem, no stock change persists.

Duplicate submission protection:
  The cart is deleted as the final step inside the same transaction.
  If the cart is already gone (second request), the service raises CartEmptyError.

What is NOT verified by unit tests alone:
  True concurrent isolation can only be validated with multi-process or
  multi-connection tests. Django TestCase wraps each test in a transaction and
  rolls it back, which means in-process threading tests share the same DB
  connection and cannot observe the lock. The TransactionTestCase-based
  concurrent test in tests_orders.py spawns real threads against separate
  connections to approximate real concurrency, but remains non-deterministic.
  See tests_orders.py for the documented test and its limitations.
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import F

from seller.models import Item
from cart.models import Cart, CartItem
from orders.models import Order, OrderItem


class CheckoutError(Exception):
    """Base class for checkout service errors."""


class CartEmptyError(CheckoutError):
    """Cart has no items or does not exist."""


class ProductUnavailableError(CheckoutError):
    """A product is inactive or has been deleted."""
    def __init__(self, product_title):
        self.product_title = product_title
        super().__init__(f"'{product_title}' is no longer available.")


class InsufficientStockError(CheckoutError):
    """Requested quantity exceeds available stock."""
    def __init__(self, product_title, available):
        self.product_title = product_title
        self.available = available
        super().__init__(
            f"Insufficient stock for '{product_title}'. "
            f"Only {available} unit(s) available."
        )


def checkout_cart(cart: Cart, shipping_address=None) -> Order:
    """
    Atomically validate, reserve inventory, create an Order, and clear the cart.

    Args:
        cart: The buyer's Cart instance (already verified to belong to the buyer).
        shipping_address: Optional ShippingAddress instance.

    Returns:
        The newly created Order instance (order_status='pending', payment_status='unpaid').

    Raises:
        CartEmptyError: Cart has no items.
        ProductUnavailableError: A product in the cart is inactive or deleted.
        InsufficientStockError: A product's stock is less than the requested quantity.
    """
    with transaction.atomic():
        # Re-fetch cart items with their products inside the transaction
        cart_items = list(
            CartItem.objects
            .filter(cart=cart)
            .select_related('product')
        )

        if not cart_items:
            raise CartEmptyError("Your cart is empty.")

        product_ids = [ci.product_id for ci in cart_items]

        # Lock product rows in pk order to prevent deadlocks between concurrent checkouts.
        # select_for_update() blocks any other transaction attempting the same lock
        # until this transaction completes.
        locked_products = {
            p.pk: p
            for p in Item.objects.select_for_update().filter(pk__in=product_ids).order_by('pk')
        }

        # --- Validation (all checks before any mutation) ---
        for ci in cart_items:
            product = locked_products.get(ci.product_id)
            if product is None or not product.is_active:
                name = product.title if product else f"(id={ci.product_id})"
                raise ProductUnavailableError(name)
            if product.quantity < ci.quantity:
                raise InsufficientStockError(product.title, product.quantity)

        # --- Calculate total from DB prices only (client prices are never trusted) ---
        total = sum(
            locked_products[ci.product_id].price * ci.quantity
            for ci in cart_items
        )

        # --- Create Order ---
        order = Order.objects.create(
            buyer=cart.buyer,
            shipping_address=shipping_address,
            order_status=Order.OrderStatus.PENDING,
            payment_status=Order.PaymentStatus.UNPAID,
            total_amount=total,
        )

        # --- Create OrderItems with purchase-time snapshots and decrement stock ---
        for ci in cart_items:
            p = locked_products[ci.product_id]
            subtotal = p.price * ci.quantity
            OrderItem.objects.create(
                order=order,
                product=p,
                title_at_purchase=p.title,
                unit_price_at_purchase=p.price,
                unit_at_purchase=getattr(p, 'unit', 'box'),
                quantity=ci.quantity,
                subtotal=subtotal,
            )
            # Use F() expression to decrement atomically at DB level.
            # No Python-side read-modify-write race is possible here because
            # the row is already locked by select_for_update().
            Item.objects.filter(pk=p.pk).update(quantity=F('quantity') - ci.quantity)

        # --- Delete cart (idempotent — second request will find no cart) ---
        cart.delete()

        return order


# ---------------------------------------------------------------------------
# Status transition service
# ---------------------------------------------------------------------------

SELLER_ALLOWED_TRANSITIONS = {
    # Sellers / Bakery owners can move pending/submitted -> confirmed/rejected,
    # confirmed -> in_preparation/dispatched, etc.
    Order.OrderStatus.PENDING: [
        Order.OrderStatus.PROCESSING,
        Order.OrderStatus.CONFIRMED,
        Order.OrderStatus.REJECTED,
    ],
    Order.OrderStatus.SUBMITTED: [
        Order.OrderStatus.CONFIRMED,
        Order.OrderStatus.PROCESSING,
        Order.OrderStatus.REJECTED,
    ],
    Order.OrderStatus.CONFIRMED: [
        Order.OrderStatus.IN_PREPARATION,
        Order.OrderStatus.PROCESSING,
        Order.OrderStatus.SHIPPED,
        Order.OrderStatus.DISPATCHED,
    ],
    Order.OrderStatus.PROCESSING: [
        Order.OrderStatus.SHIPPED,
        Order.OrderStatus.IN_PREPARATION,
        Order.OrderStatus.DISPATCHED,
    ],
    Order.OrderStatus.IN_PREPARATION: [
        Order.OrderStatus.DISPATCHED,
        Order.OrderStatus.SHIPPED,
    ],
}

ADMIN_ALLOWED_TRANSITIONS = Order.OrderStatus.TRANSITIONS


def transition_order_status(order: Order, new_status: str, actor_is_admin: bool) -> Order:
    """
    Apply an order_status transition with role-based permission checks.

    Args:
        order: The Order to transition.
        new_status: The target status string.
        actor_is_admin: True if the requesting user is an admin.

    Returns:
        The updated Order instance (not yet saved — caller must save).

    Raises:
        CheckoutError: If the transition is not permitted.
    """
    allowed_map = ADMIN_ALLOWED_TRANSITIONS if actor_is_admin else SELLER_ALLOWED_TRANSITIONS
    allowed = allowed_map.get(order.order_status, [])
    if new_status not in allowed:
        raise CheckoutError(
            f"Cannot transition order from '{order.order_status}' to '{new_status}'."
        )
    order.order_status = new_status
    return order
