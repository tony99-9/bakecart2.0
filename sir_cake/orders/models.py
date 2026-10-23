"""
Order and OrderItem models for BakeCart 2.0.

Design decisions:
- order_status and payment_status are separate state machines.
- OrderItem snapshots title_at_purchase and unit_price_at_purchase so that
  historical orders are never corrupted by later price or catalogue changes.
- product FK uses SET_NULL so the order item is preserved even if the seller
  later hard-deletes the product row (admin operation only).
- total_amount is stored once at checkout and never recalculated from live prices.
- Allowed order_status transitions are enforced in the service layer, not only at DB.
"""

from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from seller.models import Item
from users.models import ShippingAddress


class Order(models.Model):
    """A completed or in-progress purchase created at checkout."""

    class OrderStatus:
        PENDING = 'pending'
        SUBMITTED = 'submitted'
        PROCESSING = 'processing'
        CONFIRMED = 'confirmed'
        IN_PREPARATION = 'in_preparation'
        SHIPPED = 'shipped'
        DISPATCHED = 'dispatched'
        DELIVERED = 'delivered'
        CANCELLED = 'cancelled'
        REJECTED = 'rejected'

        CHOICES = [
            (PENDING, 'Pending'),
            (SUBMITTED, 'Submitted'),
            (PROCESSING, 'Processing'),
            (CONFIRMED, 'Confirmed'),
            (IN_PREPARATION, 'In Preparation'),
            (SHIPPED, 'Shipped'),
            (DISPATCHED, 'Dispatched'),
            (DELIVERED, 'Delivered'),
            (CANCELLED, 'Cancelled'),
            (REJECTED, 'Rejected'),
        ]

        # Valid transitions: {from_status: [allowed_to_statuses]}
        TRANSITIONS = {
            PENDING: [PROCESSING, CONFIRMED, REJECTED, CANCELLED],
            SUBMITTED: [CONFIRMED, PROCESSING, REJECTED, CANCELLED],
            PROCESSING: [SHIPPED, IN_PREPARATION, DISPATCHED, CANCELLED],
            CONFIRMED: [IN_PREPARATION, PROCESSING, SHIPPED, DISPATCHED, CANCELLED],
            IN_PREPARATION: [DISPATCHED, SHIPPED, CANCELLED],
            SHIPPED: [DELIVERED],
            DISPATCHED: [DELIVERED],
            DELIVERED: [],
            CANCELLED: [],
            REJECTED: [],
        }

    class PaymentStatus:
        UNPAID = 'unpaid'
        PAID = 'paid'
        REFUNDED = 'refunded'
        FAILED = 'failed'

        CHOICES = [
            (UNPAID, 'Unpaid'),
            (PAID, 'Paid'),
            (REFUNDED, 'Refunded'),
            (FAILED, 'Failed'),
        ]

    buyer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
        verbose_name='Buyer',
    )
    bakery = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bakery_received_orders',
        verbose_name='Bakery',
    )
    shipping_address = models.ForeignKey(
        ShippingAddress,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
    )
    order_status = models.CharField(
        max_length=20,
        choices=OrderStatus.CHOICES,
        default=OrderStatus.PENDING,
        db_index=True,
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.CHOICES,
        default=PaymentStatus.UNPAID,
        db_index=True,
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator('0.00')],
    )
    notes = models.TextField(blank=True, null=True, verbose_name='Dealer Notes')
    rejection_reason = models.TextField(blank=True, null=True, verbose_name='Rejection Reason')
    dispatch_notes = models.TextField(blank=True, null=True, verbose_name='Dispatch Notes')
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order({self.pk}, buyer={self.buyer_id}, status={self.order_status})"

    def can_transition_to(self, new_status):
        allowed = self.OrderStatus.TRANSITIONS.get(self.order_status, [])
        return new_status in allowed


class OrderItem(models.Model):
    """
    A single product line within an order.

    Snapshots title_at_purchase and unit_price_at_purchase from the live
    Item at the moment of checkout. These values NEVER change after creation.
    """

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(
        Item,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_items',
    )
    # Purchase-time snapshots (immutable after creation)
    title_at_purchase = models.CharField(max_length=200)
    unit_price_at_purchase = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator('0.00')],
    )
    unit_at_purchase = models.CharField(max_length=30, default='box')
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator('0.00')],
    )

    def __str__(self):
        return (
            f"OrderItem(order={self.order_id}, '{self.title_at_purchase}', "
            f"qty={self.quantity}, unit={self.unit_price_at_purchase})"
        )
