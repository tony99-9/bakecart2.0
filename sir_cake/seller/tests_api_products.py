"""
Product and seller profile API tests for BakeCart 2.0.

Coverage:
  - Public product list: pagination, search, category filter, excludes inactive.
  - Public product detail: found, not found, deactivated returns 404.
  - Category list endpoint.
  - Seller profile endpoint: requires seller role.
  - Seller create product: valid, invalid price, invalid quantity, bad image type,
    image too large, seller field cannot be injected by client.
  - Seller update product (PUT/PATCH): own product, another seller's product (403).
  - Seller delete (soft-deactivate): own product, another's product (403).
  - Admin product list: all products including inactive, seller filter.
  - Admin activate: reactivate deactivated product.
  - Cross-role access: buyer cannot create/update/delete products.
  - Anonymous access: public reads allowed; writes rejected.
  - Ownership: seller A cannot modify seller B's products.
"""
import io
import struct

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from seller.models import Item
from users.models import UserStatus

# Use a temp media root so uploaded test images don't pollute the real media dir
import tempfile
TEMP_MEDIA = tempfile.mkdtemp()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_buyer(username='buyer1', password='Pass1234!'):
    user = User.objects.create_user(username=username, password=password)
    UserStatus.objects.create(user=user, is_seller=False)
    return user


def make_seller(username='seller1', password='Pass1234!'):
    user = User.objects.create_user(username=username, password=password)
    UserStatus.objects.create(user=user, is_seller=True)
    return user


def make_admin(username='admin1', password='Pass1234!'):
    user = User.objects.create_user(username=username, password=password, is_staff=True)
    UserStatus.objects.create(user=user, is_seller=False)
    return user


def make_minimal_png():
    """Return a valid 1x1 pixel PNG as bytes (no external files needed)."""
    # 1x1 white pixel PNG binary
    png_header = b'\x89PNG\r\n\x1a\n'
    # IHDR chunk
    ihdr_data = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
    import zlib
    ihdr_crc = zlib.crc32(b'IHDR' + ihdr_data) & 0xffffffff
    ihdr_chunk = struct.pack('>I', 13) + b'IHDR' + ihdr_data + struct.pack('>I', ihdr_crc)
    # IDAT chunk
    raw_row = b'\x00\xff\xff\xff'
    compressed = zlib.compress(raw_row)
    idat_crc = zlib.crc32(b'IDAT' + compressed) & 0xffffffff
    idat_chunk = struct.pack('>I', len(compressed)) + b'IDAT' + compressed + struct.pack('>I', idat_crc)
    # IEND chunk
    iend_crc = zlib.crc32(b'IEND') & 0xffffffff
    iend_chunk = struct.pack('>I', 0) + b'IEND' + struct.pack('>I', iend_crc)
    return png_header + ihdr_chunk + idat_chunk + iend_chunk


def png_upload(name='test.png'):
    return SimpleUploadedFile(name, make_minimal_png(), content_type='image/png')


def make_item(seller, title='Test Cake', price='9.99', quantity=5, is_active=True, category='CA'):
    return Item.objects.create(
        seller=seller,
        title=title,
        price=price,
        quantity=quantity,
        category=category,
        is_active=is_active,
        image=png_upload(f'{title.replace(" ", "_")}.png'),
    )


# ---------------------------------------------------------------------------
# Public: Categories
# ---------------------------------------------------------------------------

class CategoryListTests(APITestCase):
    def test_categories_returns_all_choices(self):
        response = self.client.get(reverse('api_product_categories'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        codes = [c['code'] for c in response.json()['categories']]
        self.assertIn('CO', codes)
        self.assertIn('CA', codes)
        self.assertIn('I', codes)
        self.assertIn('ALL', codes)


# ---------------------------------------------------------------------------
# Public: Product listing
# ---------------------------------------------------------------------------

@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class PublicProductListTests(APITestCase):
    def setUp(self):
        self.seller = make_seller()
        self.url = reverse('api_product_list')
        self.item1 = make_item(self.seller, title='Chocolate Cake', category='CA')
        self.item2 = make_item(self.seller, title='Almond Cookie', category='CO')
        self.inactive = make_item(self.seller, title='Hidden Cake', is_active=False)

    def test_public_list_returns_only_active_items(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [r['title'] for r in response.json()['results']]
        self.assertIn('Chocolate Cake', titles)
        self.assertIn('Almond Cookie', titles)
        self.assertNotIn('Hidden Cake', titles)

    def test_public_list_count_excludes_inactive(self):
        response = self.client.get(self.url)
        self.assertEqual(response.json()['count'], 2)

    def test_search_filters_by_title(self):
        response = self.client.get(self.url, {'search': 'Cookie'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json()['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['title'], 'Almond Cookie')

    def test_search_is_case_insensitive(self):
        response = self.client.get(self.url, {'search': 'chocolate'})
        self.assertEqual(len(response.json()['results']), 1)

    def test_category_filter(self):
        response = self.client.get(self.url, {'category': 'CO'})
        results = response.json()['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['title'], 'Almond Cookie')

    def test_all_category_returns_all_active(self):
        response = self.client.get(self.url, {'category': 'ALL'})
        self.assertEqual(response.json()['count'], 2)

    def test_invalid_page_defaults_to_first_page(self):
        response = self.client.get(self.url, {'page': 'bad'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_pagination_structure_present(self):
        response = self.client.get(self.url)
        data = response.json()
        for key in ('count', 'page', 'num_pages', 'page_size', 'results'):
            self.assertIn(key, data)

    def test_response_excludes_sensitive_fields(self):
        response = self.client.get(self.url)
        for product in response.json()['results']:
            self.assertNotIn('seller_id', product)


# ---------------------------------------------------------------------------
# Public: Product detail
# ---------------------------------------------------------------------------

@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class PublicProductDetailTests(APITestCase):
    def setUp(self):
        self.seller = make_seller()
        self.item = make_item(self.seller, title='Active Cake')
        self.inactive = make_item(self.seller, title='Gone Cake', is_active=False)

    def test_active_product_returns_200(self):
        url = reverse('api_product_detail', kwargs={'pk': self.item.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['product']['title'], 'Active Cake')

    def test_inactive_product_returns_404_to_public(self):
        url = reverse('api_product_detail', kwargs={'pk': self.inactive.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_nonexistent_product_returns_404(self):
        url = reverse('api_product_detail', kwargs={'pk': 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ---------------------------------------------------------------------------
# Seller profile
# ---------------------------------------------------------------------------

class SellerProfileTests(APITestCase):
    def setUp(self):
        self.seller = make_seller()
        self.buyer = make_buyer()
        self.url = reverse('api_seller_profile')

    def test_seller_can_access_own_profile(self):
        self.client.force_login(self.seller)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['seller']
        self.assertEqual(data['username'], 'seller1')
        self.assertTrue(data['is_seller'])
        self.assertNotIn('password', data)
        self.assertNotIn('email', data)

    def test_buyer_cannot_access_seller_profile_endpoint(self):
        self.client.force_login(self.buyer)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_cannot_access_seller_profile(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------------
# Seller: Create product
# ---------------------------------------------------------------------------

@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class SellerCreateProductTests(APITestCase):
    def setUp(self):
        self.seller = make_seller()
        self.buyer = make_buyer()
        self.admin = make_admin()
        self.url = reverse('api_seller_product_list')

    def _valid_payload(self, **overrides):
        data = {
            'title': 'Strawberry Cake',
            'price': '12.50',
            'quantity': 10,
            'category': 'CA',
            'description': 'A lovely cake',
            'image': png_upload(),
        }
        data.update(overrides)
        return data

    def test_seller_creates_product_returns_201(self):
        self.client.force_login(self.seller)
        response = self.client.post(self.url, self._valid_payload(), format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()['product']
        self.assertEqual(data['title'], 'Strawberry Cake')
        self.assertEqual(data['seller_username'], 'seller1')

    def test_seller_is_set_server_side_not_from_client(self):
        """Client supplying seller field must not affect ownership."""
        other = make_seller(username='other_seller')
        payload = self._valid_payload()
        payload['seller'] = other.pk  # attempt to inject ownership
        self.client.force_login(self.seller)
        response = self.client.post(self.url, payload, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = Item.objects.get(pk=response.json()['product']['id'])
        self.assertEqual(created.seller, self.seller)

    def test_buyer_cannot_create_product(self):
        self.client.force_login(self.buyer)
        response = self.client.post(self.url, self._valid_payload(), format='multipart')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_cannot_create_product(self):
        response = self.client.post(self.url, self._valid_payload(), format='multipart')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_negative_price_returns_400(self):
        self.client.force_login(self.seller)
        response = self.client.post(self.url, self._valid_payload(price='-1.00'), format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_negative_quantity_returns_400(self):
        self.client.force_login(self.seller)
        response = self.client.post(self.url, self._valid_payload(quantity=-5), format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_title_returns_400(self):
        self.client.force_login(self.seller)
        payload = self._valid_payload()
        payload.pop('title')
        response = self.client.post(self.url, payload, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_image_returns_400(self):
        self.client.force_login(self.seller)
        payload = self._valid_payload()
        payload.pop('image')
        response = self.client.post(self.url, payload, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_image_type_returns_400(self):
        self.client.force_login(self.seller)
        fake_file = SimpleUploadedFile('doc.pdf', b'%PDF-1.4 fake pdf', content_type='application/pdf')
        response = self.client.post(self.url, self._valid_payload(image=fake_file), format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('details', response.json())

    def test_oversized_image_returns_400(self):
        self.client.force_login(self.seller)
        # Build a fake PNG header but pad it to exceed 5 MB
        big_png = make_minimal_png() + b'\x00' * (5 * 1024 * 1024 + 1)
        big_file = SimpleUploadedFile('big.png', big_png, content_type='image/png')
        response = self.client.post(self.url, self._valid_payload(image=big_file), format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_category_returns_400(self):
        self.client.force_login(self.seller)
        response = self.client.post(self.url, self._valid_payload(category='ZZ'), format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_can_also_create_product(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url, self._valid_payload(), format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Seller: List own products
# ---------------------------------------------------------------------------

@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class SellerProductListTests(APITestCase):
    def setUp(self):
        self.seller_a = make_seller(username='sellerA')
        self.seller_b = make_seller(username='sellerB')
        self.url = reverse('api_seller_product_list')
        self.item_a1 = make_item(self.seller_a, title='A Cake 1')
        self.item_a2 = make_item(self.seller_a, title='A Cake 2', is_active=False)
        self.item_b1 = make_item(self.seller_b, title='B Cookie')

    def test_seller_sees_only_own_products(self):
        self.client.force_login(self.seller_a)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [r['title'] for r in response.json()['results']]
        self.assertIn('A Cake 1', titles)
        self.assertIn('A Cake 2', titles)  # seller sees own inactive too
        self.assertNotIn('B Cookie', titles)

    def test_seller_list_search(self):
        self.client.force_login(self.seller_a)
        response = self.client.get(self.url, {'search': 'Cake 2'})
        self.assertEqual(len(response.json()['results']), 1)


# ---------------------------------------------------------------------------
# Seller: Update product
# ---------------------------------------------------------------------------

@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class SellerUpdateProductTests(APITestCase):
    def setUp(self):
        self.seller_a = make_seller(username='sellerA')
        self.seller_b = make_seller(username='sellerB')
        self.buyer = make_buyer()
        self.item = make_item(self.seller_a, title='Original Cake')
        self.url = reverse('api_seller_product_detail', kwargs={'pk': self.item.pk})

    def test_seller_can_patch_own_product(self):
        self.client.force_login(self.seller_a)
        response = self.client.patch(self.url, {'title': 'Updated Cake'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.item.refresh_from_db()
        self.assertEqual(self.item.title, 'Updated Cake')

    def test_seller_cannot_patch_another_sellers_product(self):
        self.client.force_login(self.seller_b)
        response = self.client.patch(self.url, {'title': 'Hijacked'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.item.refresh_from_db()
        self.assertEqual(self.item.title, 'Original Cake')

    def test_buyer_cannot_patch_product(self):
        self.client.force_login(self.buyer)
        response = self.client.patch(self.url, {'title': 'Buyer Hack'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_cannot_patch_product(self):
        response = self.client.patch(self.url, {'title': 'Anon Hack'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_patch_cannot_change_seller(self):
        """A seller cannot reassign a product to another user."""
        self.client.force_login(self.seller_a)
        self.client.patch(self.url, {'seller': self.seller_b.pk}, format='json')
        self.item.refresh_from_db()
        self.assertEqual(self.item.seller, self.seller_a)

    def test_patch_invalid_price_returns_400(self):
        self.client.force_login(self.seller_a)
        response = self.client.patch(self.url, {'price': '-5.00'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_put_full_update_own_product(self):
        self.client.force_login(self.seller_a)
        response = self.client.put(
            self.url,
            {
                'title': 'Fully Updated',
                'price': '15.00',
                'quantity': 3,
                'category': 'CO',
                'image': png_upload('new.png'),
            },
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.item.refresh_from_db()
        self.assertEqual(self.item.title, 'Fully Updated')


# ---------------------------------------------------------------------------
# Seller: Soft-delete (deactivate) product
# ---------------------------------------------------------------------------

@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class SellerDeactivateProductTests(APITestCase):
    def setUp(self):
        self.seller_a = make_seller(username='sellerA')
        self.seller_b = make_seller(username='sellerB')
        self.buyer = make_buyer()
        self.item = make_item(self.seller_a, title='Deletable Cake')
        self.url = reverse('api_seller_product_detail', kwargs={'pk': self.item.pk})

    def test_seller_can_deactivate_own_product(self):
        self.client.force_login(self.seller_a)
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.item.refresh_from_db()
        self.assertFalse(self.item.is_active)

    def test_deactivated_product_still_exists_in_db(self):
        """Soft-delete: row preserved for order history."""
        self.client.force_login(self.seller_a)
        self.client.delete(self.url)
        self.assertTrue(Item.objects.filter(pk=self.item.pk).exists())

    def test_seller_cannot_deactivate_another_sellers_product(self):
        self.client.force_login(self.seller_b)
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.item.refresh_from_db()
        self.assertTrue(self.item.is_active)

    def test_buyer_cannot_deactivate_product(self):
        self.client.force_login(self.buyer)
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_cannot_deactivate_product(self):
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------------
# Admin: product list and activate
# ---------------------------------------------------------------------------

@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class AdminProductTests(APITestCase):
    def setUp(self):
        self.admin = make_admin()
        self.seller = make_seller()
        self.buyer = make_buyer()
        self.active_item = make_item(self.seller, title='Active Product')
        self.inactive_item = make_item(self.seller, title='Inactive Product', is_active=False)

    def test_admin_list_includes_inactive_items(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('api_admin_product_list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [r['title'] for r in response.json()['results']]
        self.assertIn('Active Product', titles)
        self.assertIn('Inactive Product', titles)

    def test_admin_list_active_filter(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('api_admin_product_list'), {'active': 'false'})
        titles = [r['title'] for r in response.json()['results']]
        self.assertIn('Inactive Product', titles)
        self.assertNotIn('Active Product', titles)

    def test_admin_list_seller_filter(self):
        other_seller = make_seller(username='other_s')
        make_item(other_seller, title='Other Item')
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('api_admin_product_list'),
            {'seller_id': self.seller.pk}
        )
        titles = [r['title'] for r in response.json()['results']]
        self.assertIn('Active Product', titles)
        self.assertNotIn('Other Item', titles)

    def test_admin_can_reactivate_deactivated_product(self):
        self.client.force_login(self.admin)
        url = reverse('api_admin_product_activate', kwargs={'pk': self.inactive_item.pk})
        response = self.client.patch(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.inactive_item.refresh_from_db()
        self.assertTrue(self.inactive_item.is_active)

    def test_buyer_cannot_access_admin_product_list(self):
        self.client.force_login(self.buyer)
        response = self.client.get(reverse('api_admin_product_list'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_seller_cannot_access_admin_product_list(self):
        self.client.force_login(self.seller)
        response = self.client.get(reverse('api_admin_product_list'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_cannot_access_admin_product_list(self):
        response = self.client.get(reverse('api_admin_product_list'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_activate_nonexistent_product_returns_404(self):
        self.client.force_login(self.admin)
        url = reverse('api_admin_product_activate', kwargs={'pk': 99999})
        response = self.client.patch(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
