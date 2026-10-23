"""
Order API views for BakeCart 2.0.

Endpoints:
  POST /api/checkout/                   - Buyer: atomic checkout of their active cart
  GET  /api/orders/                     - Buyer: list own orders
  GET  /api/orders/<id>/                - Buyer: detail of own order
  GET  /api/seller/orders/              - Seller: orders containing their products
  POST /api/seller/orders/<id>/status/  - Seller/Admin: transition order_status
  GET  /api/admin/orders/               - Admin: all orders

Permission matrix:
  Buyer owns cart and orders → ownership enforced via buyer == request.user.
  Seller sees order items where item.product.seller == request.user.
  Admin sees all orders.
  Payment status is read-only at this phase (always stays 'unpaid' until payment phase).
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from users.permissions import IsAdmin, IsSeller
from cart.models import Cart
from orders.models import Order, OrderItem
from orders.serializers import (
    CheckoutSerializer,
    OrderReadSerializer,
    OrderStatusUpdateSerializer,
)
from orders.services import (
    CartEmptyError,
    CheckoutError,
    InsufficientStockError,
    ProductUnavailableError,
    checkout_cart,
    transition_order_status,
)
from users.models import ShippingAddress


def _error(message, details=None):
    payload = {'error': message}
    if details:
        payload['details'] = details
    return payload


# ---------------------------------------------------------------------------
# Checkout
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def checkout_view(request):
    """
    POST /api/checkout/

    Atomically:
      1. Validates the buyer's cart contents against live DB stock and prices.
      2. Deducts inventory.
      3. Creates an Order + OrderItems with purchase-time snapshots.
      4. Deletes the cart (prevents duplicate submissions).

    Returns 409 if the cart no longer exists (duplicate checkout attempt).
    """
    # Duplicate submission protection: if cart is gone, no-op with 409.
    try:
        cart = Cart.objects.prefetch_related('items').get(buyer=request.user)
    except Cart.DoesNotExist:
        return Response(
            _error("No active cart found. It may have already been checked out."),
            status=status.HTTP_409_CONFLICT,
        )

    serializer = CheckoutSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            _error("Invalid checkout data.", serializer.errors),
            status=status.HTTP_400_BAD_REQUEST,
        )

    shipping_address = None
    address_id = serializer.validated_data.get('shipping_address_id')
    if address_id:
        try:
            # Only the buyer's own address is accepted
            shipping_address = ShippingAddress.objects.get(pk=address_id, user=request.user)
        except ShippingAddress.DoesNotExist:
            return Response(
                _error("Shipping address not found or does not belong to you."),
                status=status.HTTP_400_BAD_REQUEST,
            )

    try:
        order = checkout_cart(cart, shipping_address=shipping_address)
    except CartEmptyError as exc:
        return Response(_error(str(exc)), status=status.HTTP_400_BAD_REQUEST)
    except ProductUnavailableError as exc:
        return Response(_error(str(exc)), status=status.HTTP_400_BAD_REQUEST)
    except InsufficientStockError as exc:
        return Response(
            _error(str(exc), {'available': exc.available}),
            status=status.HTTP_400_BAD_REQUEST,
        )
    except CheckoutError as exc:
        return Response(_error(str(exc)), status=status.HTTP_400_BAD_REQUEST)

    order_data = OrderReadSerializer(order).data
    return Response({'order': order_data}, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Buyer order endpoints
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def buyer_order_list(request):
    """GET /api/orders/ — list the authenticated buyer's own orders."""
    orders = (
        Order.objects
        .filter(buyer=request.user)
        .prefetch_related('items')
        .order_by('-created_at')
    )
    data = OrderReadSerializer(orders, many=True).data
    return Response({'orders': data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def buyer_order_detail(request, order_id):
    """GET /api/orders/<id>/ — detail of one of the buyer's orders."""
    try:
        order = (
            Order.objects
            .prefetch_related('items')
            .get(pk=order_id, buyer=request.user)
        )
    except Order.DoesNotExist:
        return Response(_error("Order not found."), status=status.HTTP_404_NOT_FOUND)

    return Response({'order': OrderReadSerializer(order).data})


# ---------------------------------------------------------------------------
# Seller order endpoints
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsSeller])
def seller_order_list(request):
    """
    GET /api/seller/orders/

    Returns orders that contain at least one item belonging to this seller.
    Only order items belonging to the seller are included in 'items'.
    """
    seller = request.user

    # Orders containing at least one item from this seller
    order_ids = (
        OrderItem.objects
        .filter(product__seller=seller)
        .values_list('order_id', flat=True)
        .distinct()
    )
    orders = (
        Order.objects
        .filter(pk__in=order_ids)
        .prefetch_related('items__product')
        .order_by('-created_at')
    )

    result = []
    for order in orders:
        seller_items = [
            item for item in order.items.all()
            if item.product and item.product.seller_id == seller.pk
        ]
        order_data = OrderReadSerializer(order).data
        # Replace full items list with only seller's items
        from orders.serializers import OrderItemSerializer
        order_data['items'] = OrderItemSerializer(seller_items, many=True).data
        result.append(order_data)

    return Response({'orders': result})


@api_view(['POST'])
@permission_classes([IsSeller])
def seller_order_status_update(request, order_id):
    """
    POST /api/seller/orders/<id>/status/

    Seller can move pending→processing and processing→shipped.
    Admin can perform all transitions.
    """
    # Sellers can only update orders containing their products
    is_admin = request.user.is_staff
    try:
        if is_admin:
            order = Order.objects.get(pk=order_id)
        else:
            order_ids = (
                OrderItem.objects
                .filter(product__seller=request.user)
                .values_list('order_id', flat=True)
                .distinct()
            )
            order = Order.objects.get(pk=order_id, pk__in=order_ids)
    except Order.DoesNotExist:
        return Response(_error("Order not found."), status=status.HTTP_404_NOT_FOUND)

    serializer = OrderStatusUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            _error("Invalid status.", serializer.errors),
            status=status.HTTP_400_BAD_REQUEST,
        )

    new_status = serializer.validated_data['order_status']
    try:
        order = transition_order_status(order, new_status, actor_is_admin=is_admin)
    except CheckoutError as exc:
        return Response(_error(str(exc)), status=status.HTTP_400_BAD_REQUEST)

    order.save(update_fields=['order_status'])
    return Response({'order': OrderReadSerializer(order).data})


# ---------------------------------------------------------------------------
# Admin order endpoint
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAdmin])
def admin_order_list(request):
    """GET /api/admin/orders/ — all orders visible to admin."""
    orders = Order.objects.prefetch_related('items').order_by('-created_at')
    data = OrderReadSerializer(orders, many=True).data
    return Response({'orders': data})
