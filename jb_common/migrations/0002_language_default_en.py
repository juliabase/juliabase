from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('jb_common', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userdetails',
            name='language',
            field=models.CharField(default='en', max_length=10, verbose_name='language', choices=[('en', 'English'), ('de', 'Deutsch')]),
        ),
    ]
