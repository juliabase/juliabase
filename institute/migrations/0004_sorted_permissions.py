from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('institute', '0003_django_1_8_changes'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='clustertooldeposition',
            options={'default_permissions': (), 'permissions': (('add_clustertooldeposition', "Can add 'cluster tool deposition'"), ('change_clustertooldeposition', "Can edit every 'cluster tool deposition'"), ('edit_permissions_for_clustertooldeposition', "Can edit permissions for 'cluster tool deposition'"), ('view_every_clustertooldeposition', "Can view every 'cluster tool deposition'")), 'get_latest_by': 'timestamp', 'verbose_name_plural': 'cluster tool depositions', 'verbose_name': 'cluster tool deposition', 'ordering': ['timestamp']},
        ),
        migrations.AlterModelOptions(
            name='fivechamberdeposition',
            options={'default_permissions': (), 'permissions': (('add_fivechamberdeposition', "Can add 'five chamber deposition'"), ('change_fivechamberdeposition', "Can edit every 'five chamber deposition'"), ('edit_permissions_for_fivechamberdeposition', "Can edit permissions for 'five chamber deposition'"), ('view_every_fivechamberdeposition', "Can view every 'five chamber deposition'")), 'get_latest_by': 'timestamp', 'verbose_name_plural': '5-chamber depositions', 'verbose_name': '5-chamber deposition', 'ordering': ['timestamp']},
        ),
        migrations.AlterModelOptions(
            name='pdsmeasurement',
            options={'default_permissions': (), 'permissions': (('add_pdsmeasurement', "Can add 'PDS measurement'"), ('edit_permissions_for_pdsmeasurement', "Can edit permissions for 'PDS measurement'"), ('view_every_pdsmeasurement', "Can view every 'PDS measurement'")), 'get_latest_by': 'timestamp', 'verbose_name_plural': 'PDS measurements', 'verbose_name': 'PDS measurement', 'ordering': ['number']},
        ),
        migrations.AlterModelOptions(
            name='solarsimulatormeasurement',
            options={'default_permissions': (), 'permissions': (('add_solarsimulatormeasurement', "Can add 'solarsimulator measurement'"), ('edit_permissions_for_solarsimulatormeasurement', "Can edit permissions for 'solarsimulator measurement'"), ('view_every_solarsimulatormeasurement', "Can view every 'solarsimulator measurement'")), 'get_latest_by': 'timestamp', 'verbose_name_plural': 'solarsimulator measurements', 'verbose_name': 'solarsimulator measurement', 'ordering': ['timestamp']},
        ),
    ]
