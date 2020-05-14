from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('institute', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='solarsimulatorcellmeasurement',
            options={'ordering': ('measurement', 'position'), 'verbose_name': 'solarsimulator cell measurement', 'verbose_name_plural': 'solarsimulator cell measurements'},
        ),
    ]
