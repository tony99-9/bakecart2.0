"""
Cart serializers for BakeCart 2.0.

Price fields are read-only on all cart serializers.
The server always reads price from the Item table; client-provided prices are
silently ignored or rejected by the serializer's read-only field declarations.
"""

from rest_framework import serializers

from seller.models import Item
from cart.models import Cart, CartItem


class CartItemWriteSerializer(serializers.Serializer):
    """Validates POST/PATCH body for adding or updating a cart item."""

    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Item.objects.filter(is_active=True),
        source='product',
    )
    quantity = serializers.IntegerField(min_value=1)

    def validate(self, data):
        product = data['product']
        qty = data['quantity']
        if qty > product.quantity:
            raise serializers.ValidationError(
                {
                    'quantity': (
                        f"Only {product.quantity} unit(s) of '{product.title}' available."
                    )
                }
            )
        return data


class CartItemReadSerializer(serializers.ModelSerializer):
    """Read representation of a cart item, including denormalised product fields."""

    product_id = serializers.IntegerField(source='product.pk', read_only=True)
    product_title = serializers.CharField(source='product.title', read_only=True)
    # Price is always read from the database; the client never provides it.
    unit_price = serializers.DecimalField(
        source='product.price',
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ['id', 'product_id', 'product_title', 'unit_price', 'quantity', 'line_total']

    def get_line_total(self, obj):
        return obj.product.price * obj.quantity


class CartReadSerializer(serializers.ModelSerializer):
    """Full cart representation including computed grand_total."""

    items = CartItemReadSerializer(many=True, read_only=True)
    grand_total = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ['id', 'created_at', 'updated_at', 'items', 'grand_total']

    def get_grand_total(self, obj):
        return sum(item.product.price * item.quantity for item in obj.items.all())
