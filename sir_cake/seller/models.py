from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from PIL import Image

from .image_utils import crop_max_square
from users.models import AnonymousUser


class Bakery(models.Model):
    owner = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='bakery',
        verbose_name='Bakery Owner',
    )
    name = models.CharField(max_length=150, verbose_name='Bakery Name')
    description = models.TextField(blank=True, verbose_name='Description')
    address = models.CharField(max_length=255, blank=True, verbose_name='Address')
    phone = models.CharField(max_length=50, blank=True, verbose_name='Phone')
    email = models.EmailField(blank=True, verbose_name='Contact Email')
    is_active = models.BooleanField(default=True, verbose_name='Active')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name_plural = 'Bakeries'

    def __str__(self):
        return self.name


class BakeryDealerAuthorization(models.Model):
    STATUS_AUTHORIZED = 'authorized'
    STATUS_PENDING = 'pending'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_AUTHORIZED, 'Authorized'),
        (STATUS_PENDING, 'Pending'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    bakery = models.ForeignKey(Bakery, on_delete=models.CASCADE, related_name='dealer_authorizations')
    dealer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bakery_authorizations')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_AUTHORIZED)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('bakery', 'dealer')

    def __str__(self):
        return f"{self.bakery.name} <-> {self.dealer.username} ({self.status})"


class Item(models.Model):

    class Category:
        COOKIES = 'CO'
        CAKES = 'CA'
        ICE_CREAMS = 'I'
        ALL = 'ALL'

    CATEGORIES_CHOICES = [
        (Category.COOKIES, 'Cookies'),
        (Category.CAKES, 'Cakes'),
        (Category.ICE_CREAMS, 'Ice creams'),
        (Category.ALL, 'All Sweets'),
    ]

    SHORT_CATEGORY_TO_NAME = dict(CATEGORIES_CHOICES)

    # BakeCart 2.0: seller ownership FK (nullable to preserve legacy rows)
    seller = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='items',
        verbose_name='Seller',
    )
    bakery = models.ForeignKey(
        Bakery,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='products',
        verbose_name='Bakery',
    )

    title = models.CharField(max_length=50)
    # Decimal field prevents floating-point rounding errors in order totals
    price = models.DecimalField(
        "Wholesale Price in €",
        max_digits=10,
        decimal_places=2,
        default='0.00',
        validators=[MinValueValidator(0)],
    )
    unit = models.CharField(
        max_length=30,
        default='box',
        verbose_name='Wholesale Unit',
        help_text='e.g., box, crate, tray, dozen, kg, batch',
    )
    min_order_quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name='Minimum Order Quantity',
    )
    description = models.TextField(max_length=255, null=True, blank=True)
    category = models.CharField(
        max_length=3,
        choices=CATEGORIES_CHOICES,
        default=Category.ALL,
    )
    image = models.ImageField(upload_to='product_pics')
    date_posted = models.DateTimeField(default=timezone.now)
    quantity = models.IntegerField(default=0, validators=[MinValueValidator(0)])

    # BakeCart 2.0: soft-deletion flag (deleted items stay in DB for order history)
    is_active = models.BooleanField(default=True, verbose_name='Active')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.assign_shorter_title()
        self.assign_category_full_name()

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Crop and resize image after saving so the path exists on disk
        try:
            img = Image.open(self.image.path)
            img_cropped = crop_max_square(img)
            if img_cropped.height > 400:
                img_cropped.thumbnail((400, 400))
            img_cropped.save(self.image.path)
        except (FileNotFoundError, OSError):
            # Skip image processing if the file cannot be accessed
            # (e.g. in-memory test fixtures that aren't written to disk)
            pass

    def assign_shorter_title(self):
        if len(self.title) > 20:
            self.short_title = self.title[:17] + "..."
        else:
            self.short_title = self.title

    def assign_category_full_name(self):
        self.long_category = self.SHORT_CATEGORY_TO_NAME[self.category]


class Order(models.Model):

    class Status:
        PREORDER = 'preorder'
        PAID = 'paid'
        SHIPPED = 'shipped'
        UNSENT = 'unsent'
        ALL = 'all'

    buyer = models.ForeignKey(
        User, on_delete=models.CASCADE, blank=True, null=True)
    buyer_anon = models.ForeignKey(
        AnonymousUser, on_delete=models.CASCADE, blank=True, null=True)
    order_date = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=10)
