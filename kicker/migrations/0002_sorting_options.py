from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kicker', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='kickernumber',
            options={'ordering': ['timestamp'], 'get_latest_by': 'timestamp', 'verbose_name': 'kicker number', 'verbose_name_plural': 'kicker numbers'},
        ),
        migrations.AlterModelOptions(
            name='match',
            options={'ordering': ['timestamp'], 'get_latest_by': 'timestamp', 'verbose_name': 'match', 'verbose_name_plural': 'matches'},
        ),
        migrations.AlterModelOptions(
            name='shares',
            options={'ordering': ['timestamp'], 'get_latest_by': 'timestamp', 'verbose_name': 'shares', 'verbose_name_plural': 'shareses'},
        ),
        migrations.AlterModelOptions(
            name='stockvalue',
            options={'ordering': ['timestamp'], 'get_latest_by': 'timestamp', 'verbose_name': 'stock value', 'verbose_name_plural': 'stock values'},
        ),
    ]
