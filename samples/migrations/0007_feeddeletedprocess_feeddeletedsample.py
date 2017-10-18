# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-05-09 19:20
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('samples', '0006_verbose_name_in_userdetails_field'),
    ]

    operations = [
        migrations.CreateModel(
            name='FeedDeletedProcess',
            fields=[
                ('feedentry_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='samples.FeedEntry')),
                ('process_name', models.TextField(verbose_name='process name')),
            ],
            options={
                'verbose_name': 'deleted process feed entry',
                'abstract': False,
                'verbose_name_plural': 'deleted process feed entries',
            },
            bases=('samples.feedentry',),
        ),
        migrations.CreateModel(
            name='FeedDeletedSample',
            fields=[
                ('feedentry_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='samples.FeedEntry')),
                ('sample_name', models.CharField(max_length=30, verbose_name='sample name')),
            ],
            options={
                'verbose_name': 'deleted sample feed entry',
                'abstract': False,
                'verbose_name_plural': 'deleted sample feed entries',
            },
            bases=('samples.feedentry',),
        ),
    ]
