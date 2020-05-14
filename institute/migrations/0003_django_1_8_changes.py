from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('institute', '0002_solarsimulator_cell_ordering'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='solarsimulatormeasurement',
            options={'get_latest_by': 'timestamp', 'ordering': ['timestamp'], 'verbose_name_plural': 'solarsimulator measurements', 'default_permissions': (), 'verbose_name': 'solarsimulator measurement', 'permissions': (('view_every_solarsimulatormeasurement', "Can view every 'solarsimulator measurement'"), ('add_solarsimulatormeasurement', "Can add 'solarsimulator measurement'"), ('edit_permissions_for_solarsimulatormeasurement', "Can edit permissions for 'solarsimulator measurement'"))},
        ),
    ]
