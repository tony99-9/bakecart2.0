"""
Cart models for BakeCart 2.0.

Design decisions:
- Cart is 1-to-1 with a registered buyer (no guest cart in this phase).
- CartItem enforces unique (cart, product) so quantity updates go through
  PATCH, not duplicate POSTs.
- Quantity validation (positive, <= stock) is enforced in the serializer/service,
  not at the DB level, so we can return readable error messages.
"""

from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from seller.models import Item


class Cart(models.Model):
    """A buyer's active shopping cart. Created on first add-to-cart, deleted on checkout."""

    buyer = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='cart',
        verbose_name='Buyer',
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart({self.buyer_id})"


class CartItem(models.Model):
    """A single product line in a buyer's cart."""

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name='cart_items',
    )
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
    )

    class Meta:
        unique_together = [('cart', 'product')]

    def __str__(self):
        return f"CartItem(cart={self.cart_id}, product={self.product_id}, qty={self.quantity})"
