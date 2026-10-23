"""
Product and seller profile API views for BakeCart 2.0.

Endpoint summary:
  GET    /api/products/                    Public — list active products
  GET    /api/products/<id>/               Public — product detail
  GET    /api/products/categories/         Public — list valid categories
  GET    /api/seller/profile/              Seller — own profile
  GET    /api/seller/products/             Seller — own products (all statuses)
  POST   /api/seller/products/             Seller — create product
  GET    /api/seller/products/<id>/        Seller — own product detail
  PUT    /api/seller/products/<id>/        Seller — full update
  PATCH  /api/seller/products/<id>/        Seller — partial update
  DELETE /api/seller/products/<id>/        Seller — soft-deactivate
  PATCH  /api/admin/products/<id>/activate/ Admin  — reactivate a deactivated product

Authorization:
  - Seller ownership is verified server-side on every mutating operation.
  - seller field on Item is always set from request.user; never from request body.
  - Buyers have no write access to any product endpoint.
"""
from django.contrib.auth.models import User
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from seller.models import Item
from seller.serializers import (
    ProductDetailSerializer,
    ProductListSerializer,
    SellerProfileSerializer,
)
from users.permissions import IsAdmin, IsSeller

PAGE_SIZE = 20


def _error(message, code=None):
    payload = {"error": message}
    if code:
        payload["code"] = code
    return payload


def _paginate(queryset, request):
    """Manual pagination to avoid coupling to DRF generic views."""
    try:
        page = max(1, int(request.GET.get('page', 1)))
    except (ValueError, TypeError):
        page = 1
    size = PAGE_SIZE
    total = queryset.count()
    start = (page - 1) * size
    end = start + size
    items = list(queryset[start:end])
    return {
        'count': total,
        'page': page,
        'page_size': size,
        'num_pages': max(1, (total + size - 1) // size),
        'results': items,
    }


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([AllowAny])
def product_categories_view(request):
    """
    GET /api/products/categories/
    Returns all valid category codes and their display labels.
    """
    categories = [
        {'code': code, 'label': label}
        for code, label in Item.CATEGORIES_CHOICES
    ]
    return Response({'categories': categories})


@api_view(['GET'])
@permission_classes([AllowAny])
def product_list_view(request):
    """
    GET /api/products/?search=&category=&page=
    Public listing of active products only.

    Query params:
      search   — case-insensitive title search
      category — category code (CO, CA, I, ALL)
      page     — page number (default 1)
    """
    qs = Item.objects.filter(is_active=True).order_by('-date_posted')

    search = request.GET.get('search', '').strip()
    if search:
        qs = qs.filter(title__icontains=search)

    category = request.GET.get('category', '').strip()
    if category and category in Item.SHORT_CATEGORY_TO_NAME:
        if category != Item.Category.ALL:
            qs = qs.filter(category=category)

    page_data = _paginate(qs, request)
    serializer = ProductListSerializer(page_data['results'], many=True, context={'request': request})
    return Response({
        'count': page_data['count'],
        'page': page_data['page'],
        'num_pages': page_data['num_pages'],
        'page_size': page_data['page_size'],
        'results': serializer.data,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def product_detail_view(request, pk):
    """
    GET /api/products/<id>/
    Returns a single active product. Deactivated products return 404 to the public.
    """
    try:
        item = Item.objects.get(pk=pk, is_active=True)
    except Item.DoesNotExist:
        return Response(_error("Product not found."), status=status.HTTP_404_NOT_FOUND)

    serializer = ProductDetailSerializer(item, context={'request': request})
    return Response({'product': serializer.data})


# ---------------------------------------------------------------------------
# Seller profile
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsSeller])
def seller_profile_view(request):
    """
    GET /api/seller/profile/
    Returns the authenticated seller's own profile.
    """
    serializer = SellerProfileSerializer(request.user)
    return Response({'seller': serializer.data})


@api_view(['GET'])
@permission_classes([IsSeller])
def seller_summary_metrics_view(request):
    """
    GET /api/seller/summary/
    Returns real sales summary metrics for the authenticated seller.
    """
    from decimal import Decimal
    from orders.models import Order, OrderItem

    seller = request.user
    seller_items = Item.objects.filter(seller=seller)
    total_products = seller_items.count()
    active_products = seller_items.filter(is_active=True).count()
    out_of_stock = seller_items.filter(quantity=0).count()

    order_ids = (
        OrderItem.objects
        .filter(product__seller=seller)
        .values_list('order_id', flat=True)
        .distinct()
    )
    orders = Order.objects.filter(pk__in=order_ids)
    total_orders = orders.count()
    pending_orders = orders.filter(order_status='pending').count()
    processing_orders = orders.filter(order_status='processing').count()
    shipped_orders = orders.filter(order_status='shipped').count()

    paid_order_ids = orders.filter(payment_status='paid').values_list('id', flat=True)
    sold_items = OrderItem.objects.filter(product__seller=seller, order_id__in=paid_order_ids)
    total_sales = sum((item.subtotal for item in sold_items), Decimal('0.00'))
    total_units_sold = sum((item.quantity for item in sold_items), 0)

    return Response({
        'summary': {
            'total_sales': str(total_sales),
            'total_units_sold': total_units_sold,
            'total_orders': total_orders,
            'pending_orders': pending_orders,
            'processing_orders': processing_orders,
            'shipped_orders': shipped_orders,
            'total_products': total_products,
            'active_products': active_products,
            'out_of_stock_products': out_of_stock,
        }
    })


# ---------------------------------------------------------------------------
# Seller product management
# ---------------------------------------------------------------------------

@api_view(['GET', 'POST'])
@permission_classes([IsSeller])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def seller_product_list_view(request):
    """
    GET  /api/seller/products/  — list caller's own products (all statuses)
    POST /api/seller/products/  — create a new product

    seller is always set to request.user — never accepted from request body.
    """
    if request.method == 'GET':
        qs = Item.objects.filter(seller=request.user).order_by('-date_posted')

        search = request.GET.get('search', '').strip()
        if search:
            qs = qs.filter(title__icontains=search)

        page_data = _paginate(qs, request)
        serializer = ProductDetailSerializer(
            page_data['results'], many=True, context={'request': request}
        )
        return Response({
            'count': page_data['count'],
            'page': page_data['page'],
            'num_pages': page_data['num_pages'],
            'results': serializer.data,
        })

    # POST
    serializer = ProductDetailSerializer(data=request.data, context={'request': request})
    if not serializer.is_valid():
        return Response(
            {"error": "Validation failed.", "details": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    # Inject seller from request.user — never from client data
    item = serializer.save(seller=request.user)
    out = ProductDetailSerializer(item, context={'request': request})
    return Response({'product': out.data}, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsSeller])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def seller_product_detail_view(request, pk):
    """
    GET    /api/seller/products/<id>/   — retrieve own product (any status)
    PUT    /api/seller/products/<id>/   — full update
    PATCH  /api/seller/products/<id>/  — partial update
    DELETE /api/seller/products/<id>/  — soft-deactivate (sets is_active=False)

    Ownership: a seller can only access and modify their own products.
    Admin can access any product through the admin endpoint.
    """
    try:
        item = Item.objects.get(pk=pk)
    except Item.DoesNotExist:
        return Response(_error("Product not found."), status=status.HTTP_404_NOT_FOUND)

    # Enforce ownership: seller can only touch their own items
    if not request.user.is_staff and item.seller != request.user:
        return Response(
            _error("You do not have permission to access this product."),
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == 'GET':
        serializer = ProductDetailSerializer(item, context={'request': request})
        return Response({'product': serializer.data})

    if request.method == 'DELETE':
        # Soft-deactivate — preserves the row for existing order references
        item.is_active = False
        item.save(update_fields=['is_active'])
        return Response(
            {"detail": "Product deactivated.", "id": item.pk},
            status=status.HTTP_200_OK,
        )

    # PUT / PATCH
    partial = (request.method == 'PATCH')
    serializer = ProductDetailSerializer(
        item, data=request.data, partial=partial, context={'request': request}
    )
    if not serializer.is_valid():
        return Response(
            {"error": "Validation failed.", "details": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    # seller cannot be changed via update
    updated = serializer.save()
    out = ProductDetailSerializer(updated, context={'request': request})
    return Response({'product': out.data})


# ---------------------------------------------------------------------------
# Admin product management
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAdmin])
def admin_product_list_view(request):
    """
    GET /api/admin/products/
    Admin view: all products including inactive, with optional filters.

    Query params:
      search    — title search
      category  — category code
      seller_id — filter by seller user ID
      active    — 'true' | 'false' | omit for all
      page      — page number
    """
    qs = Item.objects.all().order_by('-date_posted')

    search = request.GET.get('search', '').strip()
    if search:
        qs = qs.filter(title__icontains=search)

    category = request.GET.get('category', '').strip()
    if category and category in Item.SHORT_CATEGORY_TO_NAME and category != Item.Category.ALL:
        qs = qs.filter(category=category)

    seller_id = request.GET.get('seller_id', '').strip()
    if seller_id:
        try:
            qs = qs.filter(seller_id=int(seller_id))
        except (ValueError, TypeError):
            return Response(_error("Invalid seller_id."), status=status.HTTP_400_BAD_REQUEST)

    active_filter = request.GET.get('active', '').strip().lower()
    if active_filter == 'true':
        qs = qs.filter(is_active=True)
    elif active_filter == 'false':
        qs = qs.filter(is_active=False)

    page_data = _paginate(qs, request)
    serializer = ProductDetailSerializer(
        page_data['results'], many=True, context={'request': request}
    )
    return Response({
        'count': page_data['count'],
        'page': page_data['page'],
        'num_pages': page_data['num_pages'],
        'results': serializer.data,
    })


@api_view(['PATCH'])
@permission_classes([IsAdmin])
def admin_product_activate_view(request, pk):
    """
    PATCH /api/admin/products/<id>/activate/
    Admin-only: reactivate a soft-deactivated product.
    """
    try:
        item = Item.objects.get(pk=pk)
    except Item.DoesNotExist:
        return Response(_error("Product not found."), status=status.HTTP_404_NOT_FOUND)

    item.is_active = True
    item.save(update_fields=['is_active'])
    serializer = ProductDetailSerializer(item, context={'request': request})
    return Response({'product': serializer.data})
