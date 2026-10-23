"""
DRF serializers for seller profile and product (Item) management.

Security notes:
- seller is always set server-side from request.user; clients cannot supply it.
- price and quantity are validated server-side; no client value is trusted.
- Image content-type and file-size are validated before saving.
- is_active is a server-side lifecycle flag; deactivation is done via a
  dedicated endpoint, not by accepting the field on a general update.
"""
import imghdr

from django.contrib.auth.models import User
from rest_framework import serializers

from users.models import UserStatus
from seller.models import Item

# 5 MB maximum upload size
MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {'jpeg', 'png', 'gif', 'webp'}


class SellerProfileSerializer(serializers.ModelSerializer):
    """
    Read-only seller public profile.
    Returns id, username, and first/last name only — no email or auth details.
    """
    is_seller = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'is_seller']
        read_only_fields = fields

    def get_is_seller(self, obj):
        try:
            return obj.userstatus.is_seller
        except UserStatus.DoesNotExist:
            return False


class ProductListSerializer(serializers.ModelSerializer):
    """
    Compact representation used in list endpoints.
    Includes computed category_label and seller username.
    """
    category_label = serializers.SerializerMethodField()
    seller_username = serializers.SerializerMethodField()
    bakery_name = serializers.SerializerMethodField()

    class Meta:
        model = Item
        fields = [
            'id', 'title', 'price', 'category', 'category_label',
            'quantity', 'image', 'date_posted', 'seller_username',
            'bakery_name', 'unit',
        ]

    def get_category_label(self, obj):
        return Item.SHORT_CATEGORY_TO_NAME.get(obj.category, obj.category)

    def get_seller_username(self, obj):
        return obj.seller.username if obj.seller else None

    def get_bakery_name(self, obj):
        if obj.bakery and obj.bakery.name:
            return obj.bakery.name
        return "Sweet Bites Bakery"


class ProductDetailSerializer(serializers.ModelSerializer):
    """
    Full product representation for detail / create / update endpoints.
    seller is read-only and always set server-side.
    is_active is read-only here; deactivation uses a separate endpoint.
    """
    category_label = serializers.SerializerMethodField(read_only=True)
    seller_username = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Item
        fields = [
            'id', 'title', 'price', 'unit', 'min_order_quantity', 'description',
            'category', 'category_label', 'quantity', 'image', 'date_posted',
            'is_active', 'seller_username',
        ]
        read_only_fields = ['id', 'date_posted', 'is_active', 'seller_username', 'category_label']

    def get_category_label(self, obj):
        return Item.SHORT_CATEGORY_TO_NAME.get(obj.category, obj.category)

    def get_seller_username(self, obj):
        return obj.seller.username if obj.seller else None

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Price must be zero or greater.")
        return value

    def validate_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError("Quantity must be zero or greater.")
        return value

    def validate_image(self, value):
        if value.size > MAX_IMAGE_BYTES:
            raise serializers.ValidationError(
                f"Image file too large. Maximum size is {MAX_IMAGE_BYTES // (1024*1024)} MB."
            )
        # Read the first bytes to detect image format
        header = value.read(512)
        value.seek(0)
        detected = imghdr.what(None, h=header)
        if detected not in ALLOWED_IMAGE_TYPES:
            raise serializers.ValidationError(
                f"Unsupported image type '{detected}'. "
                f"Allowed types: {', '.join(sorted(ALLOWED_IMAGE_TYPES))}."
            )
        return value

    def create(self, validated_data):
        # seller is injected by the view from request.user — never from request.data
        return Item.objects.create(**validated_data)

    def update(self, instance, validated_data):
        # seller cannot be changed after creation
        validated_data.pop('seller', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
