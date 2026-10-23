"""
Cart API views for BakeCart 2.0.

Endpoints:
  GET  /api/cart/               - Return the buyer's cart (creates if absent)
  POST /api/cart/items/         - Add a product to the cart (or set quantity if already in cart)
  PATCH  /api/cart/items/<id>/  - Update the quantity of a cart item
  DELETE /api/cart/items/<id>/  - Remove a cart item
  DELETE /api/cart/             - Clear (empty) the entire cart

Permission rules:
  All endpoints require IsAuthenticated.
  Ownership is enforced by always filtering on cart.buyer == request.user.
  Sellers and admins can also have buyer carts; roles are not exclusive here.
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from cart.models import Cart, CartItem
from cart.serializers import CartItemWriteSerializer, CartReadSerializer


def _error(message, details=None):
    payload = {'error': message}
    if details:
        payload['details'] = details
    return payload


# ---------------------------------------------------------------------------
# Cart resource
# ---------------------------------------------------------------------------

@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def cart_detail(request):
    """
    GET  → return the buyer's cart (creates an empty cart if none exists).
    DELETE → clear all items from the cart (cart itself remains).
    """
    if request.method == 'GET':
        cart, _ = Cart.objects.get_or_create(buyer=request.user)
        serializer = CartReadSerializer(cart)
        return Response({'cart': serializer.data})

    # DELETE → clear cart
    try:
        cart = Cart.objects.get(buyer=request.user)
        cart.items.all().delete()
        cart_data = CartReadSerializer(cart).data
        return Response({'cart': cart_data})
    except Cart.DoesNotExist:
        return Response({'cart': {'id': None, 'items': [], 'grand_total': '0.00'}})


# ---------------------------------------------------------------------------
# CartItem resources
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cart_items_list(request):
    """
    POST → add a product to the cart.

    If the product is already in the cart the quantity is replaced (idempotent
    upsert). The client sends {product_id, quantity}; price is never read from
    the request.
    """
    serializer = CartItemWriteSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            _error("Invalid cart item data.", serializer.errors),
            status=status.HTTP_400_BAD_REQUEST,
        )

    product = serializer.validated_data['product']
    quantity = serializer.validated_data['quantity']

    cart, _ = Cart.objects.get_or_create(buyer=request.user)

    cart_item, created = CartItem.objects.update_or_create(
        cart=cart,
        product=product,
        defaults={'quantity': quantity},
    )

    cart_refreshed = Cart.objects.prefetch_related('items__product').get(pk=cart.pk)
    return Response(
        {'cart': CartReadSerializer(cart_refreshed).data},
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def cart_item_detail(request, item_id):
    """
    PATCH  → update the quantity of an existing cart item.
    DELETE → remove the cart item.
    """
    try:
        cart_item = CartItem.objects.select_related('cart', 'product').get(
            pk=item_id,
            cart__buyer=request.user,  # ownership check
        )
    except CartItem.DoesNotExist:
        return Response(_error("Cart item not found."), status=status.HTTP_404_NOT_FOUND)

    if request.method == 'DELETE':
        cart_item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # PATCH: validate quantity only (product is already in the cart, we just update quantity)
    from rest_framework import serializers as drf_serializers

    class _QuantitySerializer(drf_serializers.Serializer):
        quantity = drf_serializers.IntegerField(min_value=1)

        def validate_quantity(self, value):
            product = self.context['product']
            if value > product.quantity:
                raise drf_serializers.ValidationError(
                    f"Only {product.quantity} unit(s) available."
                )
            return value

    serializer = _QuantitySerializer(
        data=request.data,
        context={'product': cart_item.product},
    )
    if not serializer.is_valid():
        return Response(
            _error("Invalid quantity.", serializer.errors),
            status=status.HTTP_400_BAD_REQUEST,
        )

    cart_item.quantity = serializer.validated_data['quantity']
    cart_item.save(update_fields=['quantity'])

    cart = Cart.objects.prefetch_related('items__product').get(pk=cart_item.cart_id)
    return Response({'cart': CartReadSerializer(cart).data})

