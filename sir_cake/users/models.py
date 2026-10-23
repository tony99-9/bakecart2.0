from django.contrib.auth.models import User
from django.db import models
from django.contrib.sessions.models import Session


class AnonymousUser(models.Model):
    session = models.OneToOneField(Session, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=40, default=None, null=True)
    last_name = models.CharField(max_length=40, default=None, null=True)


class ShippingAddress(models.Model):
    street_name = models.CharField(max_length=200)
    house_number = models.CharField(max_length=5)
    city = models.CharField(max_length=50)
    country = models.CharField(max_length=50)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, default=None, blank=True, null=True,
        related_name='address')
    user_anon = models.OneToOneField(
        AnonymousUser, on_delete=models.CASCADE,
        default=None, blank=True, null=True, related_name='address_anon')


class UserStatus(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_seller = models.BooleanField(default=False)
    is_dealer = models.BooleanField(default=True)


class DealerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='dealer_profile')
    business_name = models.CharField(max_length=150, blank=True)
    contact_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    delivery_address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"DealerProfile({self.business_name or self.user.username})"
