"""
URL configuration for auth and user management API endpoints.

Prefix: mounted under /api/auth/ and /api/admin/ in the root urls.py.
"""
from django.urls import path

from users import api_views

urlpatterns = [
    # CSRF cookie — must be called by React before first POST
    path('auth/csrf/', api_views.csrf_token_view, name='api_csrf'),

    # Authentication
    path('auth/register/', api_views.register_view, name='api_register'),
    path('auth/login/',    api_views.login_view,    name='api_login'),
    path('auth/logout/',   api_views.logout_view,   name='api_logout'),

    # Current-user profile & address
    path('auth/profile/',  api_views.profile_view,  name='api_profile'),
    path('auth/address/',  api_views.address_view,  name='api_address'),

    # Admin endpoints
    path('admin/users/',                   api_views.admin_user_list_view,       name='api_admin_users'),
    path('admin/users/<int:user_id>/role/', api_views.assign_role_view,           name='api_assign_role'),
    path('admin/summary/',                 api_views.admin_summary_metrics_view, name='api_admin_summary'),
]
