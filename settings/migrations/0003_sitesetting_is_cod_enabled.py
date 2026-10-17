from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('settings', '0002_sitesetting_base_delivery_charge_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesetting',
            name='is_cod_enabled',
            field=models.BooleanField(default=False, help_text='Allow customers to place Cash on Delivery (COD) orders.'),
        ),
    ]
