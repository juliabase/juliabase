from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('samples', '0003_django_1_8_changes'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userdetails',
            name='my_layers',
            field=models.TextField(help_text='in JSON format', verbose_name='My Layers', blank=True),
        ),
    ]
