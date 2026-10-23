"""
DRF permissions for BakeCart 2.0 role-based authorization.

Roles:
  admin  → User.is_staff = True
  seller → UserStatus.is_seller = True (and not is_staff)
  buyer  → authenticated user with neither of the above

These permissions are composable and should be used at the view level.
Never disable IsAuthenticated globally to simplify development.
"""
from rest_framework.permissions import BasePermission

from users.models import UserStatus


class IsAdmin(BasePermission):
    """Grants access only to staff (admin) users."""
    message = "Admin access required."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class IsSeller(BasePermission):
    """
    Grants access to sellers (UserStatus.is_seller=True) or admins.
    Admins can perform all seller operations.
    """
    message = "Seller or admin access required."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.is_staff:
            return True
        try:
            return request.user.userstatus.is_seller
        except UserStatus.DoesNotExist:
            return False


class IsOwnerOrAdmin(BasePermission):
    """
    Object-level permission: allow access if the requesting user owns the object
    (object.user == request.user) or is an admin.
    Views must call get_object() so check_object_permissions is invoked.
    """
    message = "You do not have permission to access this resource."

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        return getattr(obj, 'user', None) == request.user
