"""
API views for BakeCart B2B Wholesale Platform.
"""
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from django.contrib.auth.models import User
from seller.models import Bakery, BakeryDealerAuthorization, Item
from users.models import DealerProfile, UserStatus
from users.permissions import IsAdmin, IsSeller
from orders.models import Order
from .serializers import (
    BakeryOrderActionSerializer,
    BakerySerializer,
    DealerProfileSerializer,
    WholesaleItemSerializer,
    WholesaleOrderCreateSerializer,
    WholesaleOrderReadSerializer,
)
from .services import (
    B2BOrderError,
    advance_wholesale_order,
    confirm_wholesale_order,
    confirm_wholesale_receipt,
    create_wholesale_order,
    reject_wholesale_order,
)


def _ensure_bakery(user):
    """Ensure a Bakery record exists for a seller user."""
    bakery, created = Bakery.objects.get_or_create(
        owner=user,
        defaults={
            'name': f"{user.first_name}'s Bakery" if user.first_name else f"{user.username}'s Bakery",
            'email': user.email or '',
            'description': 'Artisan wholesale bakery supplier.',
        }
    )
    # Link any unlinked items belonging to this seller
    Item.objects.filter(seller=user, bakery__isnull=True).update(bakery=bakery)
    return bakery


# ---------------------------------------------------------------------------
# Dealer / Public: Browse Bakeries & Wholesale Catalogues
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([AllowAny])
def bakeries_list_view(request):
    """
    GET /api/b2b/bakeries/
    Lists all active bakeries with product counts and authorization status.
    """
    bakeries = Bakery.objects.filter(is_active=True).select_related('owner')
    serializer = BakerySerializer(bakeries, many=True, context={'request': request})
    return Response({'bakeries': serializer.data})


@api_view(['GET'])
@permission_classes([AllowAny])
def bakery_catalogue_view(request, bakery_id):
    """
    GET /api/b2b/bakeries/<bakery_id>/catalogue/
    Returns bakery metadata and its active wholesale products.
    """
    bakery = get_object_or_404(Bakery, pk=bakery_id, is_active=True)
    products = Item.objects.filter(
        Q(bakery=bakery) | Q(seller=bakery.owner),
        is_active=True
    ).order_by('-date_posted')

    bakery_data = BakerySerializer(bakery, context={'request': request}).data
    products_data = WholesaleItemSerializer(products, many=True).data

    return Response({
        'bakery': bakery_data,
        'products': products_data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bakery_request_auth_view(request, bakery_id):
    """
    POST /api/b2b/bakeries/<bakery_id>/authorize/
    Dealer connects with a bakery to access authorized wholesale ordering.
    """
    bakery = get_object_or_404(Bakery, pk=bakery_id, is_active=True)
    auth, created = BakeryDealerAuthorization.objects.get_or_create(
        bakery=bakery,
        dealer=request.user,
        defaults={'status': BakeryDealerAuthorization.STATUS_AUTHORIZED}
    )
    if not created and auth.status != BakeryDealerAuthorization.STATUS_AUTHORIZED:
        auth.status = BakeryDealerAuthorization.STATUS_AUTHORIZED
        auth.save(update_fields=['status'])

    return Response({
        'message': f"Successfully connected to {bakery.name} wholesale catalogue.",
        'status': auth.status,
    })


# ---------------------------------------------------------------------------
# Dealer: Wholesale Order Placement, Tracking & Repeat Orders
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def dealer_order_create_view(request):
    """
    POST /api/b2b/orders/
    Dealer submits a formal wholesale purchase order to a bakery.
    """
    serializer = WholesaleOrderCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'error': 'Invalid order data.', 'details': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    try:
        order = create_wholesale_order(
            dealer_user=request.user,
            bakery_id=data['bakery_id'],
            items_data=data['items'],
            notes=data.get('notes', ''),
            delivery_address=data.get('delivery_address', ''),
        )
    except B2BOrderError as exc:
        return Response({'error': str(exc.detail if hasattr(exc, 'detail') else exc)}, status=status.HTTP_400_BAD_REQUEST)

    out = WholesaleOrderReadSerializer(order).data
    return Response({'order': out, 'message': 'Wholesale purchase order submitted successfully.'}, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dealer_orders_list_view(request):
    """
    GET /api/b2b/orders/
    Dealer lists their wholesale orders with optional ?status= filter.
    """
    qs = Order.objects.filter(buyer=request.user).select_related('buyer', 'bakery').prefetch_related('items')
    st = request.GET.get('status', '').strip()
    if st:
        qs = qs.filter(order_status=st)

    serializer = WholesaleOrderReadSerializer(qs, many=True)
    return Response({'orders': serializer.data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dealer_order_detail_view(request, order_id):
    """
    GET /api/b2b/orders/<order_id>/
    Full details of a dealer's wholesale order.
    """
    if request.user.is_staff:
        order = get_object_or_404(Order.objects.select_related('buyer', 'bakery').prefetch_related('items'), pk=order_id)
    else:
        order = get_object_or_404(Order.objects.select_related('buyer', 'bakery').prefetch_related('items'), pk=order_id, buyer=request.user)

    serializer = WholesaleOrderReadSerializer(order)
    return Response({'order': serializer.data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def dealer_repeat_order_view(request, order_id):
    """
    POST /api/b2b/orders/<order_id>/repeat/
    Pre-populates a repeat order draft from a past order, checking current
    live product availability, MOQ, and prices.
    """
    source_order = get_object_or_404(Order.objects.prefetch_related('items'), pk=order_id, buyer=request.user)
    bakery_user = source_order.bakery
    bakery = Bakery.objects.filter(owner=bakery_user).first() if bakery_user else None
    bakery_id = bakery.id if bakery else None

    draft_items = []
    warnings = []

    for item in source_order.items.all():
        product = item.product
        if not product or not product.is_active:
            warnings.append(f"'{item.title_at_purchase}' is no longer available.")
            continue

        requested_qty = max(item.quantity, product.min_order_quantity)
        if product.quantity < requested_qty:
            warnings.append(f"'{product.title}' has only {product.quantity} in stock (requested {requested_qty}).")

        draft_items.append({
            'product_id': product.id,
            'title': product.title,
            'current_price': str(product.price),
            'unit': product.unit,
            'min_order_quantity': product.min_order_quantity,
            'available_quantity': product.quantity,
            'quantity': min(requested_qty, max(product.quantity, 1)),
        })

    return Response({
        'bakery_id': bakery_id,
        'bakery_name': bakery.name if bakery else '',
        'items': draft_items,
        'warnings': warnings,
        'notes': source_order.notes or '',
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def dealer_confirm_receipt_view(request, order_id):
    """
    POST /api/b2b/orders/<order_id>/receipt/
    Dealer acknowledges and confirms receipt of the delivered wholesale order.
    """
    order = get_object_or_404(Order, pk=order_id, buyer=request.user)
    try:
        updated = confirm_wholesale_receipt(order, request.user)
    except B2BOrderError as exc:
        return Response({'error': str(exc.detail if hasattr(exc, 'detail') else exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({
        'message': 'Order delivery confirmed. Thank you!',
        'order': WholesaleOrderReadSerializer(updated).data,
    })


# ---------------------------------------------------------------------------
# Bakery Owner: Incoming Orders Desk & Order Lifecycle
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsSeller])
def bakery_orders_list_view(request):
    """
    GET /api/b2b/bakery/orders/
    Bakery owner reviews incoming dealer wholesale orders.
    """
    _ensure_bakery(request.user)
    qs = Order.objects.filter(
        Q(bakery=request.user) | Q(items__product__seller=request.user)
    ).distinct().select_related('buyer', 'bakery').prefetch_related('items')

    st = request.GET.get('status', '').strip()
    if st:
        qs = qs.filter(order_status=st)

    serializer = WholesaleOrderReadSerializer(qs, many=True)
    return Response({'orders': serializer.data})


@api_view(['POST'])
@permission_classes([IsSeller])
def bakery_order_action_view(request, order_id):
    """
    POST /api/b2b/bakery/orders/<order_id>/action/
    Bakery owner action:
      - confirm: accept order
      - reject: reject order with reason (restores stock)
      - prepare: move to in_preparation
      - dispatch: dispatch order with dispatch_notes
    """
    _ensure_bakery(request.user)
    order = get_object_or_404(
        Order.objects.filter(Q(bakery=request.user) | Q(items__product__seller=request.user)).distinct(),
        pk=order_id
    )

    serializer = BakeryOrderActionSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'error': 'Invalid action data.', 'details': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    act = serializer.validated_data['action']
    reason = serializer.validated_data.get('rejection_reason', '')
    dispatch_notes = serializer.validated_data.get('dispatch_notes', '')

    try:
        if act == 'confirm':
            updated = confirm_wholesale_order(order, request.user)
            msg = 'Order confirmed successfully.'
        elif act == 'reject':
            updated = reject_wholesale_order(order, request.user, reason)
            msg = 'Order rejected and inventory restored.'
        elif act == 'prepare':
            updated = advance_wholesale_order(order, request.user, Order.OrderStatus.IN_PREPARATION)
            msg = 'Order marked as In Preparation.'
        elif act == 'dispatch':
            updated = advance_wholesale_order(order, request.user, Order.OrderStatus.DISPATCHED, dispatch_notes)
            msg = 'Order dispatched.'
        else:
            return Response({'error': f"Unknown action '{act}'."}, status=status.HTTP_400_BAD_REQUEST)
    except B2BOrderError as exc:
        return Response({'error': str(exc.detail if hasattr(exc, 'detail') else exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({
        'message': msg,
        'order': WholesaleOrderReadSerializer(updated).data,
    })


@api_view(['GET'])
@permission_classes([IsSeller])
def bakery_dealers_list_view(request):
    """
    GET /api/b2b/bakery/dealers/
    Lists dealers connected with this bakery.
    """
    bakery = _ensure_bakery(request.user)
    auths = BakeryDealerAuthorization.objects.filter(bakery=bakery).select_related('dealer')
    data = []
    for a in auths:
        p = getattr(a.dealer, 'dealer_profile', None)
        data.append({
            'dealer_id': a.dealer.id,
            'username': a.dealer.username,
            'business_name': p.business_name if p else '',
            'contact_name': p.contact_name if p else f"{a.dealer.first_name} {a.dealer.last_name}".strip(),
            'phone': p.phone if p else '',
            'status': a.status,
            'created_at': a.created_at,
        })
    return Response({'dealers': data})


# ---------------------------------------------------------------------------
# Profile Management: Bakery & Dealer
# ---------------------------------------------------------------------------

@api_view(['GET', 'PUT'])
@permission_classes([IsSeller])
def bakery_profile_view(request):
    """
    GET/PUT /api/b2b/bakery/profile/
    Manage bakery business details.
    """
    bakery = _ensure_bakery(request.user)
    if request.method == 'GET':
        return Response({'bakery': BakerySerializer(bakery, context={'request': request}).data})

    serializer = BakerySerializer(bakery, data=request.data, partial=True, context={'request': request})
    if not serializer.is_valid():
        return Response({'error': 'Invalid bakery data.', 'details': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    serializer.save()
    return Response({'bakery': serializer.data, 'message': 'Bakery profile updated successfully.'})


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def dealer_profile_view(request):
    """
    GET/PUT /api/b2b/dealer/profile/
    Manage dealer business details.
    """
    profile, _ = DealerProfile.objects.get_or_create(user=request.user)
    if request.method == 'GET':
        return Response({'dealer': DealerProfileSerializer(profile).data})

    serializer = DealerProfileSerializer(profile, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response({'error': 'Invalid dealer profile data.', 'details': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    serializer.save()
    return Response({'dealer': serializer.data, 'message': 'Dealer profile updated successfully.'})


# ---------------------------------------------------------------------------
# Admin B2B Oversight
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAdmin])
def admin_b2b_summary_view(request):
    """
    GET /api/b2b/admin/summary/
    High-level platform metrics for wholesale orders, bakeries, and dealers.
    """
    total_bakeries = Bakery.objects.count()
    total_dealers = User.objects.filter(is_staff=False, userstatus__is_seller=False).count()
    total_orders = Order.objects.count()
    revenue_agg = Order.objects.exclude(
        order_status__in=[Order.OrderStatus.CANCELLED, Order.OrderStatus.REJECTED]
    ).aggregate(total=Sum('total_amount'))
    total_revenue = str(revenue_agg['total'] or '0.00')

    status_counts = dict(
        Order.objects.values('order_status').annotate(count=Count('id')).values_list('order_status', 'count')
    )

    return Response({
        'total_bakeries': total_bakeries,
        'total_dealers': total_dealers,
        'total_orders': total_orders,
        'total_wholesale_volume': total_revenue,
        'status_counts': status_counts,
    })
