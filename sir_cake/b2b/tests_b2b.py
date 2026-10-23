"""
Tests for BakeCart B2B Wholesale Platform.
"""
from decimal import Decimal
import io
from PIL import Image
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from seller.models import Bakery, BakeryDealerAuthorization, Item
from users.models import DealerProfile, UserStatus
from orders.models import Order, OrderItem
from b2b.services import (
    create_wholesale_order,
    confirm_wholesale_order,
    reject_wholesale_order,
    advance_wholesale_order,
    confirm_wholesale_receipt,
    B2BOrderError,
)


def make_test_png():
    img = Image.new('RGB', (100, 100), color=(180, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return SimpleUploadedFile('test.png', buf.getvalue(), content_type='image/png')


class B2BWholesaleTests(APITestCase):

    def setUp(self):
        # 1. Bakery Owner
        self.bakery_owner = User.objects.create_user(
            username='artisan_bob', password='password123', email='bob@bakery.com',
            first_name='Bob', last_name='Baker'
        )
        UserStatus.objects.create(user=self.bakery_owner, is_seller=True)
        self.bakery = Bakery.objects.create(
            owner=self.bakery_owner,
            name='Golden Crust Artisanal Bakery',
            description='Wholesale sourdough, brioche and patisserie.',
            address='10 Grain Way, Flourtown',
            phone='+44 123 456 789',
            email='orders@goldencrust.com',
        )

        # 2. Products
        self.product1 = Item.objects.create(
            seller=self.bakery_owner,
            bakery=self.bakery,
            title='Artisan Sourdough Loaves',
            price=Decimal('4.50'),
            unit='crate of 10',
            min_order_quantity=2,
            quantity=50,
            category='CA',
            image=make_test_png(),
        )
        self.product2 = Item.objects.create(
            seller=self.bakery_owner,
            bakery=self.bakery,
            title='Butter Croissants',
            price=Decimal('1.80'),
            unit='box of 24',
            min_order_quantity=3,
            quantity=100,
            category='CO',
            image=make_test_png(),
        )

        # 3. Dealer
        self.dealer_user = User.objects.create_user(
            username='corner_cafe', password='password123', email='orders@cornercafe.com',
            first_name='Claire', last_name='Cafe'
        )
        UserStatus.objects.create(user=self.dealer_user, is_seller=False)
        self.dealer_profile = DealerProfile.objects.create(
            user=self.dealer_user,
            business_name='Cornerstone Cafe & Deli',
            contact_name='Claire Cafe',
            phone='+44 987 654 321',
            delivery_address='42 High Street, Townsville',
        )

        # 4. Admin
        self.admin_user = User.objects.create_superuser(
            username='admin_boss', password='password123', email='admin@bakecart.com'
        )
        UserStatus.objects.create(user=self.admin_user, is_seller=False)

    # --- Bakery Catalogues ---

    def test_list_bakeries(self):
        url = reverse('b2b_bakeries_list')
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.json()['bakeries']), 1)
        b = res.json()['bakeries'][0]
        self.assertEqual(b['name'], 'Golden Crust Artisanal Bakery')
        self.assertEqual(b['products_count'], 2)

    def test_bakery_catalogue(self):
        url = reverse('b2b_bakery_catalogue', kwargs={'bakery_id': self.bakery.id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(data['bakery']['name'], 'Golden Crust Artisanal Bakery')
        self.assertEqual(len(data['products']), 2)
        p1 = next(p for p in data['products'] if p['id'] == self.product1.id)
        self.assertEqual(p1['unit'], 'crate of 10')
        self.assertEqual(p1['min_order_quantity'], 2)

    # --- Wholesale Ordering ---

    def test_dealer_can_create_wholesale_order_respecting_moq(self):
        self.client.force_authenticate(user=self.dealer_user)
        url = reverse('b2b_dealer_order_create')
        payload = {
            'bakery_id': self.bakery.id,
            'items': [
                {'product_id': self.product1.id, 'quantity': 2},  # exactly MOQ
                {'product_id': self.product2.id, 'quantity': 5},  # > MOQ 3
            ],
            'notes': 'Please deliver via rear kitchen entrance.',
        }
        res = self.client.post(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        order_data = res.json()['order']
        self.assertEqual(order_data['order_status'], 'submitted')
        # Total: (4.50 * 2) + (1.80 * 5) = 9.00 + 9.00 = 18.00
        self.assertEqual(order_data['total_amount'], '18.00')

        # Stock deducted
        self.product1.refresh_from_db()
        self.product2.refresh_from_db()
        self.assertEqual(self.product1.quantity, 48)
        self.assertEqual(self.product2.quantity, 95)

    def test_order_creation_rejects_below_moq(self):
        self.client.force_authenticate(user=self.dealer_user)
        url = reverse('b2b_dealer_order_create')
        payload = {
            'bakery_id': self.bakery.id,
            'items': [
                {'product_id': self.product1.id, 'quantity': 1},  # MOQ is 2!
            ],
        }
        res = self.client.post(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('minimum order quantity', str(res.json()))
        # Stock untouched
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.quantity, 50)

    def test_order_creation_rejects_exceeding_stock(self):
        self.client.force_authenticate(user=self.dealer_user)
        url = reverse('b2b_dealer_order_create')
        payload = {
            'bakery_id': self.bakery.id,
            'items': [
                {'product_id': self.product1.id, 'quantity': 999},
            ],
        }
        res = self.client.post(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Insufficient stock', str(res.json()))

    # --- Bakery Owner Order Management ---

    def test_bakery_owner_confirm_order(self):
        order = create_wholesale_order(
            dealer_user=self.dealer_user,
            bakery_id=self.bakery.id,
            items_data=[{'product_id': self.product1.id, 'quantity': 2}],
        )
        self.client.force_authenticate(user=self.bakery_owner)
        url = reverse('b2b_bakery_order_action', kwargs={'order_id': order.id})
        res = self.client.post(url, {'action': 'confirm'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.order_status, 'confirmed')
        self.assertIsNotNone(order.confirmed_at)

    def test_bakery_owner_reject_order_restores_inventory(self):
        initial_stock = self.product1.quantity
        order = create_wholesale_order(
            dealer_user=self.dealer_user,
            bakery_id=self.bakery.id,
            items_data=[{'product_id': self.product1.id, 'quantity': 5}],
        )
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.quantity, initial_stock - 5)

        self.client.force_authenticate(user=self.bakery_owner)
        url = reverse('b2b_bakery_order_action', kwargs={'order_id': order.id})
        res = self.client.post(url, {
            'action': 'reject',
            'rejection_reason': 'Oven maintenance scheduled tomorrow morning.'
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        order.refresh_from_db()
        self.assertEqual(order.order_status, 'rejected')
        self.assertEqual(order.rejection_reason, 'Oven maintenance scheduled tomorrow morning.')

        # Inventory restored!
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.quantity, initial_stock)

    def test_order_advance_and_dealer_receipt(self):
        order = create_wholesale_order(
            dealer_user=self.dealer_user,
            bakery_id=self.bakery.id,
            items_data=[{'product_id': self.product1.id, 'quantity': 2}],
        )
        confirm_wholesale_order(order, self.bakery_owner)

        # Bakery moves to in_preparation
        self.client.force_authenticate(user=self.bakery_owner)
        url = reverse('b2b_bakery_order_action', kwargs={'order_id': order.id})
        res = self.client.post(url, {'action': 'prepare'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.order_status, 'in_preparation')

        # Bakery dispatches
        res = self.client.post(url, {
            'action': 'dispatch',
            'dispatch_notes': 'Driver: Mike, Van #4, ETA 7:30 AM.'
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.order_status, 'dispatched')
        self.assertEqual(order.dispatch_notes, 'Driver: Mike, Van #4, ETA 7:30 AM.')
        self.assertIsNotNone(order.shipped_at)

        # Dealer confirms receipt
        self.client.force_authenticate(user=self.dealer_user)
        receipt_url = reverse('b2b_dealer_order_receipt', kwargs={'order_id': order.id})
        res = self.client.post(receipt_url, {}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.order_status, 'delivered')
        self.assertIsNotNone(order.delivered_at)

    def test_repeat_order_endpoint(self):
        order = create_wholesale_order(
            dealer_user=self.dealer_user,
            bakery_id=self.bakery.id,
            items_data=[{'product_id': self.product1.id, 'quantity': 4}],
            notes='Deliver to back entrance',
        )
        self.client.force_authenticate(user=self.dealer_user)
        url = reverse('b2b_dealer_order_repeat', kwargs={'order_id': order.id})
        res = self.client.post(url, {}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(data['bakery_id'], self.bakery.id)
        self.assertEqual(len(data['items']), 1)
        self.assertEqual(data['items'][0]['quantity'], 4)
        self.assertEqual(data['items'][0]['product_id'], self.product1.id)
