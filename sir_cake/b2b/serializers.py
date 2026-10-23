"""
Serializers for BakeCart B2B Wholesale Platform.
"""
from decimal import Decimal
from rest_framework import serializers
from django.contrib.auth.models import User
from seller.models import Bakery, BakeryDealerAuthorization, Item
from users.models import DealerProfile, UserStatus
from orders.models import Order, OrderItem


class BakerySerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source='owner.username', read_only=True)
    products_count = serializers.SerializerMethodField()
    is_authorized = serializers.SerializerMethodField()

    class Meta:
        model = Bakery
        fields = [
            'id', 'name', 'description', 'address', 'phone', 'email',
            'is_active', 'created_at', 'owner_username', 'products_count',
            'is_authorized'
        ]
        read_only_fields = ['id', 'created_at', 'owner_username', 'products_count', 'is_authorized']

    def get_products_count(self, obj):
        return obj.products.filter(is_active=True).count()

    def get_is_authorized(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        # If user is staff or the bakery owner themselves, they are authorized
        if request.user.is_staff or obj.owner_id == request.user.id:
            return True
        # Check authorization record
        auth = BakeryDealerAuthorization.objects.filter(
            bakery=obj, dealer=request.user, status=BakeryDealerAuthorization.STATUS_AUTHORIZED
        ).exists()
        # If no explicit restriction exists yet, default to authorized for active dealers
        return auth or not BakeryDealerAuthorization.objects.filter(bakery=obj).exists()


class WholesaleItemSerializer(serializers.ModelSerializer):
    category_label = serializers.CharField(source='get_category_display', read_only=True)
    bakery_name = serializers.CharField(source='bakery.name', default='', read_only=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, coerce_to_string=True)

    class Meta:
        model = Item
        fields = [
            'id', 'title', 'price', 'unit', 'min_order_quantity', 'quantity',
            'category', 'category_label', 'description', 'image', 'is_active',
            'bakery_id', 'bakery_name'
        ]
        read_only_fields = ['id', 'category_label', 'bakery_name']


class DealerProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = DealerProfile
        fields = [
            'id', 'username', 'email', 'business_name', 'contact_name',
            'phone', 'delivery_address', 'created_at'
        ]
        read_only_fields = ['id', 'username', 'email', 'created_at']


class WholesaleOrderItemCreateSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1)


class WholesaleOrderCreateSerializer(serializers.Serializer):
    bakery_id = serializers.IntegerField(min_value=1)
    items = WholesaleOrderItemCreateSerializer(many=True)
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    delivery_address = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one product item is required.")
        return value


class WholesaleOrderItemReadSerializer(serializers.ModelSerializer):
    unit_price_at_purchase = serializers.DecimalField(max_digits=10, decimal_places=2, coerce_to_string=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, coerce_to_string=True)

    class Meta:
        model = OrderItem
        fields = [
            'id', 'product_id', 'title_at_purchase', 'unit_price_at_purchase',
            'unit_at_purchase', 'quantity', 'subtotal'
        ]


class WholesaleOrderReadSerializer(serializers.ModelSerializer):
    items = WholesaleOrderItemReadSerializer(many=True, read_only=True)
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, coerce_to_string=True)
    dealer = serializers.SerializerMethodField()
    bakery = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'order_status', 'total_amount', 'notes', 'rejection_reason',
            'dispatch_notes', 'created_at', 'confirmed_at', 'shipped_at',
            'delivered_at', 'dealer', 'bakery', 'items'
        ]

    def get_dealer(self, obj):
        if not obj.buyer:
            return None
        profile = getattr(obj.buyer, 'dealer_profile', None)
        return {
            'id': obj.buyer.id,
            'username': obj.buyer.username,
            'business_name': profile.business_name if profile else '',
            'contact_name': (profile.contact_name if profile and profile.contact_name
                            else f"{obj.buyer.first_name} {obj.buyer.last_name}".strip()),
            'phone': profile.phone if profile else '',
            'delivery_address': profile.delivery_address if profile else '',
        }

    def get_bakery(self, obj):
        if not obj.bakery:
            return None
        bakery = getattr(obj.bakery, 'bakery', None)
        return {
            'id': bakery.id if bakery else None,
            'owner_id': obj.bakery.id,
            'name': bakery.name if bakery else obj.bakery.username,
            'phone': bakery.phone if bakery else '',
            'email': bakery.email if bakery else obj.bakery.email,
            'address': bakery.address if bakery else '',
        }


class BakeryOrderActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['confirm', 'reject', 'prepare', 'dispatch'])
    rejection_reason = serializers.CharField(required=False, allow_blank=True, default='')
    dispatch_notes = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, attrs):
        if attrs['action'] == 'reject' and not attrs.get('rejection_reason', '').strip():
            raise serializers.ValidationError({"rejection_reason": "A reason is required when rejecting an order."})
        return attrs
