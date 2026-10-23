"""
B2B Wholesale Ordering Services.

Enforces server-authoritative pricing, row-locking (select_for_update),
MOQ validation, stock reservations, order acceptance/rejection,
inventory restoral on rejection, and dispatch/receipt tracking.
"""
from decimal import Decimal
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.contrib.auth.models import User
from rest_framework.exceptions import ValidationError, PermissionDenied

from seller.models import Bakery, Item
from users.models import DealerProfile
from orders.models import Order, OrderItem


class B2BOrderError(ValidationError):
    pass


def create_wholesale_order(dealer_user: User, bakery_id: int, items_data: list, notes: str = '', delivery_address: str = '') -> Order:
    """
    Atomically validate items, check bakery ownership, enforce MOQ, reserve stock,
    and create a wholesale Order and OrderItems.
    """
    if not items_data:
        raise B2BOrderError({"items": "Order must contain at least one item."})

    try:
        bakery = Bakery.objects.select_related('owner').get(pk=bakery_id, is_active=True)
    except Bakery.DoesNotExist:
        raise B2BOrderError({"bakery_id": "Bakery not found or currently inactive."})

    product_ids = [item['product_id'] for item in items_data]
    qty_by_id = {item['product_id']: item['quantity'] for item in items_data}

    with transaction.atomic():
        # Lock products in pk order to prevent deadlocks
        locked_products = {
            p.pk: p
            for p in Item.objects.select_for_update().filter(pk__in=product_ids).order_by('pk')
        }

        # 1. Validation
        line_items = []
        total_amount = Decimal('0.00')

        for pid, requested_qty in qty_by_id.items():
            product = locked_products.get(pid)
            if not product or not product.is_active:
                raise B2BOrderError({"items": f"Product (ID {pid}) is inactive or no longer available."})

            # Check that product belongs to this bakery / bakery owner
            if product.bakery_id and product.bakery_id != bakery.id:
                raise B2BOrderError({"items": f"'{product.title}' does not belong to {bakery.name}."})
            elif not product.bakery_id and product.seller_id != bakery.owner_id:
                raise B2BOrderError({"items": f"'{product.title}' does not belong to {bakery.name}."})

            # Minimum Order Quantity (MOQ) validation
            if requested_qty < product.min_order_quantity:
                raise B2BOrderError({
                    "items": (
                        f"Requested quantity ({requested_qty}) for '{product.title}' "
                        f"is below the minimum order quantity of {product.min_order_quantity} {product.unit}."
                    )
                })

            # Inventory validation
            if product.quantity < requested_qty:
                raise B2BOrderError({
                    "items": (
                        f"Insufficient stock for '{product.title}'. "
                        f"Requested {requested_qty} {product.unit}, but only {product.quantity} available."
                    )
                })

            subtotal = product.price * requested_qty
            total_amount += subtotal
            line_items.append((product, requested_qty, subtotal))

        # Update dealer profile delivery address if provided
        if delivery_address:
            profile, _ = DealerProfile.objects.get_or_create(user=dealer_user)
            profile.delivery_address = delivery_address
            profile.save(update_fields=['delivery_address'])

        # 2. Create Order
        order = Order.objects.create(
            buyer=dealer_user,
            bakery=bakery.owner,
            order_status=Order.OrderStatus.SUBMITTED,
            payment_status=Order.PaymentStatus.UNPAID,
            total_amount=total_amount,
            notes=notes.strip() if notes else None,
        )

        # 3. Create OrderItems & Decrement stock
        for product, qty, subtotal in line_items:
            OrderItem.objects.create(
                order=order,
                product=product,
                title_at_purchase=product.title,
                unit_price_at_purchase=product.price,
                unit_at_purchase=product.unit,
                quantity=qty,
                subtotal=subtotal,
            )
            Item.objects.filter(pk=product.pk).update(quantity=F('quantity') - qty)

        return order


def confirm_wholesale_order(order: Order, actor_user: User) -> Order:
    """Bakery owner confirms a submitted wholesale order."""
    if not (actor_user.is_staff or order.bakery_id == actor_user.id):
        raise PermissionDenied("You do not have permission to confirm this order.")

    if order.order_status not in [Order.OrderStatus.SUBMITTED, Order.OrderStatus.PENDING]:
        raise B2BOrderError(f"Cannot confirm order in status '{order.order_status}'.")

    order.order_status = Order.OrderStatus.CONFIRMED
    order.confirmed_at = timezone.now()
    order.save(update_fields=['order_status', 'confirmed_at'])
    return order


def reject_wholesale_order(order: Order, actor_user: User, rejection_reason: str) -> Order:
    """
    Bakery owner rejects a wholesale order. Restores inventory back to products.
    """
    if not (actor_user.is_staff or order.bakery_id == actor_user.id):
        raise PermissionDenied("You do not have permission to reject this order.")

    if order.order_status not in [Order.OrderStatus.SUBMITTED, Order.OrderStatus.PENDING]:
        raise B2BOrderError(f"Cannot reject order in status '{order.order_status}'.")

    if not rejection_reason or not rejection_reason.strip():
        raise B2BOrderError({"rejection_reason": "A reason must be given when rejecting an order."})

    with transaction.atomic():
        # Restore inventory
        for item in order.items.select_related('product').all():
            if item.product_id:
                Item.objects.filter(pk=item.product_id).update(quantity=F('quantity') + item.quantity)

        order.order_status = Order.OrderStatus.REJECTED
        order.rejection_reason = rejection_reason.strip()
        order.save(update_fields=['order_status', 'rejection_reason'])

    return order


def advance_wholesale_order(order: Order, actor_user: User, target_status: str, dispatch_notes: str = None) -> Order:
    """Advances order to in_preparation or dispatched."""
    if not (actor_user.is_staff or order.bakery_id == actor_user.id):
        raise PermissionDenied("You do not have permission to update this order.")

    if target_status == Order.OrderStatus.IN_PREPARATION:
        if order.order_status not in [Order.OrderStatus.CONFIRMED, Order.OrderStatus.PROCESSING]:
            raise B2BOrderError(f"Cannot move order from '{order.order_status}' to in_preparation.")
        order.order_status = Order.OrderStatus.IN_PREPARATION
        order.save(update_fields=['order_status'])

    elif target_status == Order.OrderStatus.DISPATCHED:
        if order.order_status not in [
            Order.OrderStatus.CONFIRMED,
            Order.OrderStatus.PROCESSING,
            Order.OrderStatus.IN_PREPARATION,
        ]:
            raise B2BOrderError(f"Cannot move order from '{order.order_status}' to dispatched.")
        order.order_status = Order.OrderStatus.DISPATCHED
        order.shipped_at = timezone.now()
        if dispatch_notes:
            order.dispatch_notes = dispatch_notes.strip()
        order.save(update_fields=['order_status', 'shipped_at', 'dispatch_notes'])

    else:
        raise B2BOrderError(f"Unsupported status transition: '{target_status}'.")

    return order


def confirm_wholesale_receipt(order: Order, dealer_user: User) -> Order:
    """Dealer confirms delivery/receipt of the dispatched wholesale order."""
    if order.buyer_id != dealer_user.id:
        raise PermissionDenied("Only the ordering dealer can confirm receipt of this order.")

    if order.order_status not in [Order.OrderStatus.DISPATCHED, Order.OrderStatus.SHIPPED]:
        raise B2BOrderError(f"Cannot confirm receipt for order in status '{order.order_status}'.")

    order.order_status = Order.OrderStatus.DELIVERED
    order.delivered_at = timezone.now()
    order.save(update_fields=['order_status', 'delivered_at'])
    return order
