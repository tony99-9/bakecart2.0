"""
DRF serializers for authentication and user profile.

Security notes:
- password fields are write_only=True; they are never returned in any response.
- role is a derived, read-only field computed server-side from User.is_staff and
  UserStatus.is_seller. It cannot be set by the client on registration or profile update.
- username uniqueness and Django password validators are enforced on registration.
"""
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from users.models import UserStatus, ShippingAddress


class ShippingAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingAddress
        fields = ['id', 'street_name', 'house_number', 'city', 'country']
        read_only_fields = ['id']


def _derive_role(user):
    """
    Derive role string from Django User flags and UserStatus.
    Admin (is_staff) takes precedence. Only 'buyer' can self-register.
    """
    if user.is_staff:
        return 'admin'
    try:
        if user.userstatus.is_seller:
            return 'seller'
    except UserStatus.DoesNotExist:
        pass
    return 'buyer'


class UserRegistrationSerializer(serializers.Serializer):
    """
    Accepts: first_name, last_name, username, email, password, password_confirm, role, business_name.
    Role can be 'dealer' (or 'buyer') or 'seller' (bakery owner).
    Privileged roles like 'admin' cannot be self-assigned.
    """
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    password_confirm = serializers.CharField(write_only=True, style={'input_type': 'password'})
    role = serializers.CharField(required=False, default='dealer')
    business_name = serializers.CharField(max_length=150, required=False, allow_blank=True)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("A user with that username already exists.")
        return value

    def validate_role(self, value):
        val = (value or '').strip().lower()
        if val in ['seller', 'bakery_owner', 'bakery']:
            return 'seller'
        return 'dealer'

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        # Run Django's built-in password validators
        try:
            validate_password(attrs['password'])
        except DjangoValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        role = validated_data.pop('role', 'dealer')
        business_name = validated_data.pop('business_name', '').strip()

        user = User(
            username=validated_data['username'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            email=validated_data.get('email', ''),
        )
        user.set_password(password)  # hashes with PBKDF2
        user.save()

        is_seller = (role == 'seller')
        UserStatus.objects.create(
            user=user,
            is_seller=is_seller,
            is_dealer=not is_seller,
        )

        display_name = business_name or (f"{user.first_name or user.username}'s Bakery" if is_seller else f"{user.first_name or user.username}'s Dealership")
        if is_seller:
            from seller.models import Bakery
            Bakery.objects.create(
                owner=user,
                name=display_name,
                email=user.email or '',
            )
        else:
            from users.models import DealerProfile
            DealerProfile.objects.create(
                user=user,
                business_name=display_name,
            )

        return user


class LoginSerializer(serializers.Serializer):
    """
    Validates username + password credentials.
    The authenticated User object is stored in validated_data['user'].
    """
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get('request'),
            username=attrs['username'],
            password=attrs['password'],
        )
        if user is None:
            raise serializers.ValidationError(
                {"non_field_errors": "Invalid credentials. Please try again."}
            )
        if not user.is_active:
            raise serializers.ValidationError(
                {"non_field_errors": "This account has been deactivated."}
            )
        attrs['user'] = user
        return attrs


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Read-only profile response. Never returns password or is_staff directly.
    role is derived server-side; it cannot be set via this serializer.
    """
    role = serializers.SerializerMethodField(read_only=True)
    b2b_role = serializers.SerializerMethodField(read_only=True)
    bakery_id = serializers.SerializerMethodField(read_only=True)
    bakery_name = serializers.SerializerMethodField(read_only=True)
    dealer_profile = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'first_name', 'last_name', 'email',
            'role', 'b2b_role', 'bakery_id', 'bakery_name', 'dealer_profile',
            'date_joined'
        ]
        read_only_fields = ['id', 'username', 'role', 'b2b_role', 'bakery_id', 'bakery_name', 'dealer_profile', 'date_joined']

    def get_role(self, obj):
        return _derive_role(obj)

    def get_b2b_role(self, obj):
        if obj.is_staff:
            return 'admin'
        try:
            if obj.userstatus.is_seller:
                return 'bakery_owner'
        except Exception:
            pass
        return 'dealer'

    def get_bakery_id(self, obj):
        bakery = getattr(obj, 'bakery', None)
        return bakery.id if bakery else None

    def get_bakery_name(self, obj):
        bakery = getattr(obj, 'bakery', None)
        return bakery.name if bakery else ''

    def get_dealer_profile(self, obj):
        profile = getattr(obj, 'dealer_profile', None)
        if not profile:
            return None
        return {
            'business_name': profile.business_name,
            'contact_name': profile.contact_name,
            'phone': profile.phone,
            'delivery_address': profile.delivery_address,
        }

    def update(self, instance, validated_data):
        # Prevent any client-supplied role, is_staff, or password changes here
        instance.first_name = validated_data.get('first_name', instance.first_name)
        instance.last_name = validated_data.get('last_name', instance.last_name)
        instance.email = validated_data.get('email', instance.email)
        instance.save()
        return instance


class RoleAssignmentSerializer(serializers.Serializer):
    """
    Admin-only: assigns or revokes seller status on a given user.
    Accepted role values: 'buyer', 'seller'.
    Admin role assignment (is_staff) is done via Django admin only.
    """
    ASSIGNABLE_ROLES = ('buyer', 'seller')
    role = serializers.ChoiceField(choices=ASSIGNABLE_ROLES)

    def update(self, instance, validated_data):
        """instance is a User object."""
        role = validated_data['role']
        status_obj, _ = UserStatus.objects.get_or_create(user=instance)
        status_obj.is_seller = (role == 'seller')
        status_obj.save()
        return instance
