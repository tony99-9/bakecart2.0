# Generated for BakeCart 2.0 Phase 4:
# - Add seller FK to Item (nullable, to protect existing rows)
# - Add is_active boolean with default True
# - Convert price from FloatField to DecimalField(10,2)

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seller', '0005_alter_item_description'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Add seller FK (nullable so existing Item rows without a seller remain valid)
        migrations.AddField(
            model_name='item',
            name='seller',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='items',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Seller',
            ),
        ),
        # 2. Add is_active for soft-deletion / lifecycle management
        migrations.AddField(
            model_name='item',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Active'),
        ),
        # 3. Migrate price from FloatField → DecimalField
        #    PostgreSQL casts FLOAT to NUMERIC natively, no data loss on typical prices.
        migrations.AlterField(
            model_name='item',
            name='price',
            field=models.DecimalField(
                decimal_places=2,
                default='0.00',
                max_digits=10,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name='Price in €',
            ),
        ),
    ]
