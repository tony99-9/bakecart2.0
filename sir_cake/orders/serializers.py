"""
Order serializers for BakeCart 2.0.

OrderItemSerializer exposes snapshots (title_at_purchase, unit_price_at_purchase)
so historical reads are never affected by later product changes.
"""

from rest_framework import serializers

from orders.models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = [
            'id',
            'product_id',
            'title_at_purchase',
            'unit_price_at_purchase',
            'quantity',
            'subtotal',
        ]
        read_only_fields = fields


class OrderReadSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    buyer_username = serializers.CharField(source='buyer.username', read_only=True, default=None)

    class Meta:
        model = Order
        fields = [
            'id',
            'buyer_username',
            'order_status',
            'payment_status',
            'total_amount',
            'created_at',
            'paid_at',
            'shipped_at',
            'items',
        ]
        read_only_fields = fields


class OrderStatusUpdateSerializer(serializers.Serializer):
    """Used by seller/admin to transition order_status."""

    order_status = serializers.ChoiceField(choices=Order.OrderStatus.CHOICES)


class CheckoutSerializer(serializers.Serializer):
    """
    Checkout request body.

    Deliberately minimal: the server derives all prices from the DB.
    shipping_address_id is optional in this phase (stored if supplied).
    Any client-supplied 'price' field is not present and would be silently
    absent from the validated data.
    """
    shipping_address_id = serializers.IntegerField(required=False, allow_null=True)
