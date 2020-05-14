from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('samples', '0004_user_details'),
    ]

    operations = [
        migrations.RenameField(
            model_name='userdetails',
            old_name='my_layers',
            new_name='my_steps',
        ),
        migrations.AlterField(
            model_name='userdetails',
            name='my_steps',
            field=models.TextField(help_text='in JSON format', verbose_name='My Steps', blank=True),
        ),
    ]
