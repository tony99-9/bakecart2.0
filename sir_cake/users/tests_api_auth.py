"""
Authentication and authorization API tests for BakeCart 2.0.

Coverage:
  - Registration: valid payload, duplicate username, mismatched passwords,
    weak password, and attempts to self-assign a privileged role.
  - Login: valid credentials, wrong password, non-existent user.
  - Session: login issues session; logout invalidates it; anonymous access to
    protected endpoints returns 401.
  - Profile (GET): authenticated returns profile without password; anonymous returns 401.
  - Profile (PATCH): updates allowed fields; cannot change username or role.
  - Role assignment: admin can set seller/buyer; non-admin cannot; cannot touch
    another admin account; non-existent user returns 404.
  - Cross-role access: a buyer cannot access admin-only endpoints.
"""
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from users.models import UserStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_buyer(username='buyer_user', password='StrongPass123!'):
    user = User.objects.create_user(
        username=username,
        password=password,
        first_name='Buyer',
        last_name='One',
        email='buyer@example.com',
    )
    UserStatus.objects.create(user=user, is_seller=False)
    return user


def make_seller(username='seller_user', password='StrongPass123!'):
    user = User.objects.create_user(
        username=username,
        password=password,
        first_name='Seller',
        last_name='One',
        email='seller@example.com',
    )
    UserStatus.objects.create(user=user, is_seller=True)
    return user


def make_admin(username='admin_user', password='StrongPass123!'):
    user = User.objects.create_user(
        username=username,
        password=password,
        first_name='Admin',
        last_name='One',
        email='admin@example.com',
        is_staff=True,
    )
    UserStatus.objects.create(user=user, is_seller=False)
    return user


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class RegistrationTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('api_register')
        self.valid_payload = {
            'first_name': 'Alice',
            'last_name': 'Smith',
            'username': 'alice_smith',
            'email': 'alice@example.com',
            'password': 'StrongPass123!',
            'password_confirm': 'StrongPass123!',
        }

    def test_valid_registration_creates_buyer(self):
        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertIn('user', data)
        user_data = data['user']
        self.assertEqual(user_data['username'], 'alice_smith')
        self.assertEqual(user_data['role'], 'buyer')
        self.assertNotIn('password', user_data)
        self.assertNotIn('password_confirm', user_data)

    def test_registration_creates_user_status_record(self):
        self.client.post(self.url, self.valid_payload, format='json')
        user = User.objects.get(username='alice_smith')
        self.assertFalse(user.userstatus.is_seller)

    def test_duplicate_username_returns_400(self):
        User.objects.create_user(username='alice_smith', password='whatever99')
        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('details', response.json())

    def test_mismatched_passwords_returns_400(self):
        payload = {**self.valid_payload, 'password_confirm': 'WrongPass!'}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_weak_password_returns_400(self):
        payload = {**self.valid_payload, 'password': '123', 'password_confirm': '123'}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_can_register_as_bakery_owner(self):
        """
        Users can choose 'seller' (Bakery Owner) role on registration.
        """
        payload = {**self.valid_payload, 'role': 'seller', 'business_name': "Alice's Wholesale Bakery"}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()['user']['role'], 'seller')
        user = User.objects.get(username='alice_smith')
        self.assertTrue(user.userstatus.is_seller)
        self.assertEqual(user.bakery.name, "Alice's Wholesale Bakery")

    def test_cannot_self_assign_admin_role_on_registration(self):
        payload = {**self.valid_payload, 'role': 'admin', 'username': 'would_be_admin'}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()['user']['role'], 'buyer')
        created = User.objects.get(username='would_be_admin')
        self.assertFalse(created.is_staff)

    def test_missing_required_field_returns_400(self):
        payload = {**self.valid_payload}
        payload.pop('password')
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

class LoginTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('api_login')
        self.user = make_buyer()

    def test_valid_credentials_return_200_and_profile(self):
        response = self.client.post(
            self.url,
            {'username': 'buyer_user', 'password': 'StrongPass123!'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('user', data)
        self.assertEqual(data['user']['username'], 'buyer_user')
        self.assertNotIn('password', data['user'])

    def test_wrong_password_returns_401(self):
        response = self.client.post(
            self.url,
            {'username': 'buyer_user', 'password': 'WrongPassword!'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.json())

    def test_nonexistent_user_returns_401(self):
        response = self.client.post(
            self.url,
            {'username': 'no_such_user', 'password': 'whatever99!'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_seller_login_returns_seller_role(self):
        make_seller()
        response = self.client.post(
            self.url,
            {'username': 'seller_user', 'password': 'StrongPass123!'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['user']['role'], 'seller')

    def test_admin_login_returns_admin_role(self):
        make_admin()
        response = self.client.post(
            self.url,
            {'username': 'admin_user', 'password': 'StrongPass123!'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['user']['role'], 'admin')


# ---------------------------------------------------------------------------
# Session / Logout
# ---------------------------------------------------------------------------

class SessionTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_buyer()

    def test_logout_returns_200_for_authenticated_user(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('api_logout'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('detail', response.json())

    def test_anonymous_logout_returns_403(self):
        # DRF SessionAuthentication returns 403 for unauthenticated requests
        # (no WWW-Authenticate header / Bearer scheme is present).
        response = self.client.post(reverse('api_logout'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_profile_inaccessible_after_logout(self):
        self.client.force_login(self.user)
        self.client.post(reverse('api_logout'))
        response = self.client.get(reverse('api_profile'))
        # After logout the session is invalidated; DRF returns 403 without a Bearer scheme.
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

class ProfileTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.buyer = make_buyer()
        self.seller = make_seller()

    def test_anonymous_get_profile_returns_403(self):
        # DRF SessionAuthentication returns 403 for unauthenticated requests.
        response = self.client.get(reverse('api_profile'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_authenticated_get_profile_returns_user_data(self):
        self.client.force_login(self.buyer)
        response = self.client.get(reverse('api_profile'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['user']
        self.assertEqual(data['username'], 'buyer_user')
        self.assertEqual(data['role'], 'buyer')
        self.assertNotIn('password', data)
        self.assertNotIn('is_staff', data)

    def test_patch_profile_updates_name_and_email(self):
        self.client.force_login(self.buyer)
        response = self.client.patch(
            reverse('api_profile'),
            {'first_name': 'UpdatedName', 'email': 'new@example.com'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.first_name, 'UpdatedName')
        self.assertEqual(self.buyer.email, 'new@example.com')

    def test_patch_profile_cannot_change_username(self):
        self.client.force_login(self.buyer)
        self.client.patch(
            reverse('api_profile'),
            {'username': 'hacked_name'},
            format='json',
        )
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.username, 'buyer_user')

    def test_patch_profile_cannot_elevate_own_role(self):
        """
        A buyer supplying role='seller' in a PATCH must not change their role.
        The role field is read-only in UserProfileSerializer.
        """
        self.client.force_login(self.buyer)
        self.client.patch(
            reverse('api_profile'),
            {'role': 'seller'},
            format='json',
        )
        self.buyer.refresh_from_db()
        try:
            is_seller = self.buyer.userstatus.is_seller
        except UserStatus.DoesNotExist:
            is_seller = False
        self.assertFalse(is_seller)
        self.assertFalse(self.buyer.is_staff)

    def test_patch_profile_cannot_self_assign_admin(self):
        self.client.force_login(self.buyer)
        self.client.patch(
            reverse('api_profile'),
            {'role': 'admin', 'is_staff': True},
            format='json',
        )
        self.buyer.refresh_from_db()
        self.assertFalse(self.buyer.is_staff)


# ---------------------------------------------------------------------------
# Role Assignment (Admin-only)
# ---------------------------------------------------------------------------

class RoleAssignmentTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = make_admin()
        self.buyer = make_buyer()
        self.seller = make_seller()

    def _role_url(self, user_id):
        return reverse('api_assign_role', kwargs={'user_id': user_id})

    def test_admin_can_assign_seller_role_to_buyer(self):
        self.client.force_login(self.admin)
        response = self.client.patch(
            self._role_url(self.buyer.pk),
            {'role': 'seller'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['user']['role'], 'seller')
        self.buyer.userstatus.refresh_from_db()
        self.assertTrue(self.buyer.userstatus.is_seller)

    def test_admin_can_revoke_seller_role(self):
        self.client.force_login(self.admin)
        response = self.client.patch(
            self._role_url(self.seller.pk),
            {'role': 'buyer'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['user']['role'], 'buyer')

    def test_buyer_cannot_assign_roles(self):
        self.client.force_login(self.buyer)
        response = self.client.patch(
            self._role_url(self.seller.pk),
            {'role': 'buyer'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_seller_cannot_assign_roles(self):
        self.client.force_login(self.seller)
        response = self.client.patch(
            self._role_url(self.buyer.pk),
            {'role': 'seller'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_cannot_assign_roles(self):
        # DRF returns 403 (not 401) for session-auth-only endpoints accessed anonymously.
        response = self.client.patch(
            self._role_url(self.buyer.pk),
            {'role': 'seller'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_modify_admin_user_via_role_endpoint(self):
        """Admin accounts are protected from role-endpoint modification."""
        another_admin = make_admin(username='admin2')
        self.client.force_login(self.admin)
        response = self.client.patch(
            self._role_url(another_admin.pk),
            {'role': 'buyer'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_nonexistent_user_returns_404(self):
        self.client.force_login(self.admin)
        response = self.client.patch(
            self._role_url(99999),
            {'role': 'seller'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_invalid_role_value_returns_400(self):
        self.client.force_login(self.admin)
        response = self.client.patch(
            self._role_url(self.buyer.pk),
            {'role': 'superuser'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# Cross-role access
# ---------------------------------------------------------------------------

class CrossRoleAccessTests(APITestCase):
    """Prove that endpoints enforce their required role and deny others."""

    def setUp(self):
        self.client = APIClient()
        self.buyer = make_buyer()
        self.seller = make_seller()
        self.admin = make_admin()

    def _role_url(self, user_id):
        return reverse('api_assign_role', kwargs={'user_id': user_id})

    def test_buyer_denied_admin_endpoint(self):
        self.client.force_login(self.buyer)
        response = self.client.patch(
            self._role_url(self.seller.pk),
            {'role': 'buyer'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_seller_denied_admin_endpoint(self):
        self.client.force_login(self.seller)
        response = self.client.patch(
            self._role_url(self.buyer.pk),
            {'role': 'seller'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_profile_endpoint_is_per_user(self):
        """Each user's profile endpoint returns only their own data."""
        self.client.force_login(self.seller)
        response = self.client.get(reverse('api_profile'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['user']['username'], 'seller_user')
