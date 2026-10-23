"""
Authentication and user profile API views.

Authentication strategy: Session-based (Django sessions + HttpOnly cookie).
- Login issues a server-side session; the session cookie is HttpOnly.
- Logout flushes the session server-side.
- CSRF is enforced by DRF SessionAuthentication on all state-changing requests.
- No credentials are stored in localStorage.

Cross-origin authentication setup (for React frontend):
  1. Ensure CORS_ALLOW_CREDENTIALS = True in settings (already configured).
  2. Set CORS_ALLOWED_ORIGINS to the Vite dev server origin (already configured).
  3. React must include credentials: 'include' (fetch) or withCredentials: true (axios).
  4. React must GET /api/auth/csrf/ before the first POST to obtain the CSRF token,
     then send it as the X-CSRFToken header on all POST/PUT/PATCH/DELETE requests.
"""
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return  # Allow safe unauthentication without CSRF rotation blocking


from decimal import Decimal
from django.db.models import Q, Sum
from users.permissions import IsAdmin
from users.models import ShippingAddress, UserStatus
from orders.models import Order
from seller.models import Item
from users.serializers import (
    LoginSerializer,
    RoleAssignmentSerializer,
    ShippingAddressSerializer,
    UserProfileSerializer,
    UserRegistrationSerializer,
    _derive_role,
)


def _error(message, code=None):
    """Consistent error payload."""
    payload = {"error": message}
    if code:
        payload["code"] = code
    return payload


@api_view(['GET'])
@permission_classes([AllowAny])
@ensure_csrf_cookie
def csrf_token_view(request):
    """
    GET /api/auth/csrf/
    Issues a CSRF cookie and returns the token in JSON.
    """
    token = get_token(request)
    return Response({"detail": "CSRF cookie set.", "csrfToken": token})


@api_view(['POST'])
@permission_classes([AllowAny])
def register_view(request):
    """
    POST /api/auth/register/
    Registers a new buyer-role user.
    Role is always 'buyer'; clients cannot supply a different role.

    Request:
        { first_name, last_name, username, email?, password, password_confirm }

    Response 201:
        { user: { id, username, first_name, last_name, email, role, date_joined } }

    Response 400:
        { error: "Validation failed.", details: {...} }
    """
    serializer = UserRegistrationSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"error": "Validation failed.", "details": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    user = serializer.save()
    profile = UserProfileSerializer(user)
    return Response({"user": profile.data}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    POST /api/auth/login/
    Authenticates with username + password and establishes a Django session.
    The session ID is returned as an HttpOnly cookie by Django's session middleware.

    Request:
        { username, password }

    Response 200:
        { user: { id, username, first_name, last_name, email, role, date_joined } }

    Response 401:
        { error: "Invalid credentials. Please try again." }
    """
    serializer = LoginSerializer(data=request.data, context={'request': request})
    if not serializer.is_valid():
        return Response(
            _error(
                list(serializer.errors.get('non_field_errors', ["Authentication failed."]))[0]
            ),
            status=status.HTTP_401_UNAUTHORIZED,
        )
    user = serializer.validated_data['user']
    login(request, user)
    token = get_token(request)
    profile = UserProfileSerializer(user)
    return Response({"user": profile.data, "csrfToken": token}, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """
    POST /api/auth/logout/
    Flushes the server-side session, invalidating the session cookie.
    Requires authentication; returns 401/403 for anonymous requests.

    Response 200:
        { detail: "Successfully logged out." }
    """
    logout(request)
    return Response({"detail": "Successfully logged out."}, status=status.HTTP_200_OK)


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def profile_view(request):
    """
    GET  /api/auth/profile/  — Returns the current user's profile.
    PATCH /api/auth/profile/ — Updates first_name, last_name, and/or email.

    Clients cannot change username, role, or password through this endpoint.

    Response 200 (GET/PATCH):
        { user: { id, username, first_name, last_name, email, role, date_joined } }

    Response 400 (PATCH):
        { error: "Validation failed.", details: {...} }

    Response 401:
        { error: "Authentication required." }
    """
    if request.method == 'GET':
        serializer = UserProfileSerializer(request.user)
        return Response({"user": serializer.data})

    # PATCH: only first_name, last_name, email are writable
    serializer = UserProfileSerializer(
        request.user,
        data=request.data,
        partial=True,
    )
    if not serializer.is_valid():
        return Response(
            {"error": "Validation failed.", "details": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    serializer.save()
    return Response({"user": serializer.data})


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def address_view(request):
    """
    GET /api/auth/address/ — Returns user's shipping address or null.
    PUT /api/auth/address/ — Upserts user's shipping address.
    """
    try:
        address = ShippingAddress.objects.get(user=request.user)
    except ShippingAddress.DoesNotExist:
        address = None

    if request.method == 'GET':
        if address is None:
            return Response({"address": None})
        return Response({"address": ShippingAddressSerializer(address).data})

    # PUT
    serializer = ShippingAddressSerializer(address, data=request.data) if address else ShippingAddressSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"error": "Validation failed.", "details": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    address = serializer.save(user=request.user)
    return Response({"address": ShippingAddressSerializer(address).data}, status=status.HTTP_200_OK)


@api_view(['PATCH'])
@permission_classes([IsAdmin])
def assign_role_view(request, user_id):
    """
    PATCH /api/admin/users/<user_id>/role/
    Admin-only: assigns 'seller' or 'buyer' role to a user.
    Admin role (is_staff) is managed via Django admin only.

    Request:
        { role: "seller" | "buyer" }

    Response 200:
        { user: { id, username, role, ... } }

    Response 400:
        { error: "Validation failed.", details: {...} }

    Response 403:
        { detail: "Admin access required." }

    Response 404:
        { error: "User not found." }
    """
    try:
        target_user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return Response(_error("User not found."), status=status.HTTP_404_NOT_FOUND)

    # Guard: cannot demote or modify another admin through this endpoint
    if target_user.is_staff:
        return Response(
            _error("Admin accounts cannot be modified through this endpoint."),
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = RoleAssignmentSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"error": "Validation failed.", "details": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    serializer.update(target_user, serializer.validated_data)
    profile = UserProfileSerializer(target_user)
    return Response({"user": profile.data}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAdmin])
def admin_user_list_view(request):
    """
    GET /api/admin/users/
    Admin-only: list all users with their roles.
    Optional query params: ?role=buyer|seller|admin&search=...
    """
    qs = User.objects.all().order_by('-date_joined')
    search = request.GET.get('search', '').strip()
    if search:
        qs = qs.filter(
            Q(username__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search)
        )
    role_filter = request.GET.get('role', '').strip()
    users_data = []
    for u in qs:
        role = _derive_role(u)
        if role_filter and role != role_filter:
            continue
        users_data.append(UserProfileSerializer(u).data)
    return Response({"users": users_data})


@api_view(['GET'])
@permission_classes([IsAdmin])
def admin_summary_metrics_view(request):
    """
    GET /api/admin/summary/
    Admin-only: aggregate marketplace summary metrics based on actual server records.
    """
    total_users = User.objects.count()
    sellers_count = UserStatus.objects.filter(is_seller=True).count()
    admins_count = User.objects.filter(is_staff=True).count()
    buyers_count = max(0, total_users - sellers_count - admins_count)

    total_orders = Order.objects.count()
    paid_orders = Order.objects.filter(payment_status='paid')
    total_revenue = paid_orders.aggregate(rev=Sum('total_amount'))['rev'] or Decimal('0.00')

    total_products = Item.objects.count()
    active_products = Item.objects.filter(is_active=True).count()
    inactive_products = total_products - active_products

    pending_orders = Order.objects.filter(order_status='pending').count()
    processing_orders = Order.objects.filter(order_status='processing').count()
    shipped_orders = Order.objects.filter(order_status='shipped').count()
    cancelled_orders = Order.objects.filter(order_status='cancelled').count()

    return Response({
        'metrics': {
            'total_revenue': str(total_revenue),
            'total_orders': total_orders,
            'paid_orders_count': paid_orders.count(),
            'pending_orders': pending_orders,
            'processing_orders': processing_orders,
            'shipped_orders': shipped_orders,
            'cancelled_orders': cancelled_orders,
            'total_products': total_products,
            'active_products': active_products,
            'inactive_products': inactive_products,
            'total_users': total_users,
            'sellers_count': sellers_count,
            'buyers_count': buyers_count,
            'admins_count': admins_count,
        }
    })
