# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('samples', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AbstractMeasurementOne',
            fields=[
                ('process_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.Process')),
                ('number', models.PositiveIntegerField(unique=True, verbose_name='number', db_index=True)),
            ],
            options={
                'ordering': ['timestamp'],
                'abstract': False,
                'verbose_name': 'Apparatus 1 measurement',
                'verbose_name_plural': 'Apparatus 1 measurements',
                'permissions': (('add_abstract_measurement_one', 'Can add Apparatus 1 measurements'), ('edit_permissions_for_abstract_measurement_one', 'Can edit perms for Apparatus 1 measurements'), ('view_every_abstract_measurement_one', 'Can view all Apparatus 1 measurements')),
            },
            bases=('samples.process',),
        ),
        migrations.CreateModel(
            name='AbstractMeasurementTwo',
            fields=[
                ('process_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.Process')),
                ('number', models.PositiveIntegerField(unique=True, verbose_name='number', db_index=True)),
            ],
            options={
                'ordering': ['timestamp'],
                'abstract': False,
                'verbose_name': 'Apparatus 2 measurement',
                'verbose_name_plural': 'Apparatus 2 measurements',
                'permissions': (('add_abstract_measurement_two', 'Can add Apparatus 2 measurements'), ('edit_permissions_for_abstract_measurement_two', 'Can edit perms for Apparatus 2 measurements'), ('view_every_abstract_measurement_two', 'Can view all Apparatus 2 measurements')),
            },
            bases=('samples.process',),
        ),
        migrations.CreateModel(
            name='TestPhysicalProcess',
            fields=[
                ('process_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.Process')),
                ('number', models.PositiveIntegerField(unique=True, verbose_name='measurement number', db_index=True)),
                ('raw_datafile', models.CharField(help_text='only the relative path below "data/"', max_length=200, verbose_name='raw data file')),
                ('evaluated_datafile', models.CharField(help_text='only the relative path below "data/"', max_length=200, verbose_name='evaluated data file', blank=True)),
                ('apparatus', models.CharField(default='setup1', max_length=15, verbose_name='apparatus', choices=[('setup1', 'Setup #1'), ('setup2', 'Setup #2')])),
            ],
            options={
                'ordering': ['number'],
                'abstract': False,
                'verbose_name': 'test measurement',
                'verbose_name_plural': 'test measurements',
                'permissions': (('add_measurement', 'Can add test measurements'), ('edit_permissions_for_measurement', 'Can edit perms for test measurements'), ('view_every_measurement', 'Can view all test measurements')),
            },
            bases=('samples.process',),
        ),
    ]
