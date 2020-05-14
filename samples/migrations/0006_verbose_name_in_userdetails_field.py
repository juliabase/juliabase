from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('samples', '0005_rename_my_layers'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userdetails',
            name='default_folded_process_classes',
            field=models.ManyToManyField(related_name='dont_show_to_user', verbose_name='process classes folded by default', to='contenttypes.ContentType', blank=True),
        ),
    ]
