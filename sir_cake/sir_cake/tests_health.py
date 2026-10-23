from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status


class HealthCheckTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('health_check')

    def test_health_check_endpoint_returns_200_and_expected_structure(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data.get("status"), "healthy")
        self.assertEqual(data.get("service"), "bakecart-api")
        self.assertIn("database", data)
        self.assertTrue(data["database"].get("connected"))
