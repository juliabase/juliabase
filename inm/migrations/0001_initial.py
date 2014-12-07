#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, the samples database.
#
# Copyright © 2008–2014 Forschungszentrum Jülich, Germany,
#                       Marvin Goblet <m.goblet@fz-juelich.de>,
#                       Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.

from __future__ import absolute_import, unicode_literals, division

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('samples', '0001_initial'),
        ('contenttypes', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClusterToolDeposition',
            fields=[
                ('deposition_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.Deposition')),
                ('carrier', models.CharField(max_length=10, verbose_name='carrier', blank=True)),
            ],
            options={
                'get_latest_by': 'timestamp',
                'ordering': ['timestamp'],
                'abstract': False,
                'verbose_name_plural': 'cluster tool depositions',
                'verbose_name': 'cluster tool deposition',
                'permissions': (('add_cluster_tool_deposition', 'Can add cluster tool depositions'), ('edit_permissions_for_cluster_tool_deposition', 'Can edit perms for cluster tool I depositions'), ('view_every_cluster_tool_deposition', 'Can view all cluster tool depositions'), ('edit_every_cluster_tool_deposition', 'Can edit all cluster tool depositions')),
            },
            bases=('samples.deposition',),
        ),
        migrations.CreateModel(
            name='ClusterToolLayer',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('actual_object_id', models.PositiveIntegerField(null=True, editable=False, blank=True)),
                ('number', models.PositiveIntegerField(verbose_name='layer number')),
            ],
            options={
                'ordering': ['number'],
                'abstract': False,
                'verbose_name': 'cluster tool layer',
                'verbose_name_plural': 'cluster tool layers',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ClusterToolHotWireLayer',
            fields=[
                ('clustertoollayer_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='inm.ClusterToolLayer')),
                ('h2', models.DecimalField(decimal_places=2, max_digits=5, blank=True, help_text='in\xa0sccm', null=True, verbose_name='H\u2082')),
                ('sih4', models.DecimalField(decimal_places=2, max_digits=5, blank=True, help_text='in\xa0sccm', null=True, verbose_name='SiH\u2084')),
                ('time', models.CharField(help_text='format HH:MM:SS', max_length=9, verbose_name='deposition time', blank=True)),
                ('comments', models.TextField(verbose_name='comments', blank=True)),
                ('wire_material', models.CharField(max_length=20, verbose_name='wire material', choices=[('unknown', 'unknown'), ('rhenium', 'rhenium'), ('tantalum', 'tantalum'), ('tungsten', 'tungsten')])),
                ('base_pressure', models.FloatField(help_text='in\xa0mbar', null=True, verbose_name='base pressure', blank=True)),
            ],
            options={
                'ordering': ['number'],
                'abstract': False,
                'verbose_name': 'cluster tool hot-wire layer',
                'verbose_name_plural': 'cluster tool hot-wire layers',
            },
            bases=('inm.clustertoollayer', models.Model),
        ),
        migrations.CreateModel(
            name='ClusterToolPECVDLayer',
            fields=[
                ('clustertoollayer_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='inm.ClusterToolLayer')),
                ('h2', models.DecimalField(decimal_places=2, max_digits=5, blank=True, help_text='in\xa0sccm', null=True, verbose_name='H\u2082')),
                ('sih4', models.DecimalField(decimal_places=2, max_digits=5, blank=True, help_text='in\xa0sccm', null=True, verbose_name='SiH\u2084')),
                ('chamber', models.CharField(max_length=5, verbose_name='chamber', choices=[('#1', '#1'), ('#2', '#2'), ('#3', '#3')])),
                ('time', models.CharField(help_text='format HH:MM:SS', max_length=9, verbose_name='deposition time', blank=True)),
                ('comments', models.TextField(verbose_name='comments', blank=True)),
                ('plasma_start_with_shutter', models.BooleanField(default=False, verbose_name='plasma start with shutter')),
                ('deposition_power', models.DecimalField(decimal_places=2, max_digits=6, blank=True, help_text='in\xa0W', null=True, verbose_name='deposition power')),
            ],
            options={
                'ordering': ['number'],
                'abstract': False,
                'verbose_name': 'cluster tool PECVD layer',
                'verbose_name_plural': 'cluster tool PECVD layers',
            },
            bases=('inm.clustertoollayer', models.Model),
        ),
        migrations.CreateModel(
            name='FiveChamberDeposition',
            fields=[
                ('deposition_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.Deposition')),
            ],
            options={
                'get_latest_by': 'timestamp',
                'ordering': ['timestamp'],
                'abstract': False,
                'verbose_name_plural': '5-chamber depositions',
                'verbose_name': '5-chamber deposition',
                'permissions': (('add_five_chamber_deposition', 'Can add 5-chamber depositions'), ('edit_permissions_for_five_chamber_deposition', 'Can edit perms for 5-chamber depositions'), ('view_every_five_chamber_deposition', 'Can view all 5-chamber depositions'), ('edit_every_five_chamber_deposition', 'Can edit all 5-chamber depositions')),
            },
            bases=('samples.deposition',),
        ),
        migrations.CreateModel(
            name='FiveChamberLayer',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('number', models.PositiveIntegerField(verbose_name='layer number')),
                ('layer_type', models.CharField(blank=True, max_length=2, verbose_name='layer type', choices=[('p', 'p'), ('i', 'i'), ('n', 'n')])),
                ('chamber', models.CharField(max_length=2, verbose_name='chamber', choices=[('i1', 'i1'), ('i2', 'i2'), ('i3', 'i3'), ('p', 'p'), ('n', 'n')])),
                ('sih4', models.DecimalField(decimal_places=3, max_digits=7, blank=True, help_text='in\xa0sccm', null=True, verbose_name='SiH\u2084')),
                ('h2', models.DecimalField(decimal_places=3, max_digits=7, blank=True, help_text='in\xa0sccm', null=True, verbose_name='H\u2082')),
                ('temperature_1', models.DecimalField(decimal_places=3, max_digits=7, blank=True, help_text='in\xa0\u2103', null=True, verbose_name='temperature 1')),
                ('temperature_2', models.DecimalField(decimal_places=3, max_digits=7, blank=True, help_text='in\xa0\u2103', null=True, verbose_name='temperature 2')),
                ('deposition', models.ForeignKey(related_name='layers', verbose_name='deposition', to='inm.FiveChamberDeposition')),
            ],
            options={
                'ordering': ['number'],
                'abstract': False,
                'verbose_name': '5-chamber layer',
                'verbose_name_plural': '5-chamber layers',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='InformalLayer',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('index', models.PositiveIntegerField(verbose_name='index')),
                ('doping', models.CharField(blank=True, max_length=10, null=True, verbose_name='doping', choices=[('p', 'p'), ('i', 'i'), ('n', 'n')])),
                ('classification', models.CharField(blank=True, max_length=30, null=True, verbose_name='classification', choices=[('a-Si:H', 'a-Si:H'), ('muc-Si:H', '\xb5c-Si:H'), ('si-wafer', 'silicon wafer'), ('SiC', 'SiC'), ('glass', 'glass'), ('silver', 'silver'), ('ZnO', 'ZnO'), ('HF dip', 'HF dip'), ('SiO2', 'SiO\u2082')])),
                ('comments', models.CharField(max_length=100, null=True, verbose_name='comments', blank=True)),
                ('color', models.CharField(max_length=30, verbose_name='color', choices=[('black', 'black'), ('blue', 'blue'), ('brown', 'brown'), ('darkgray', 'darkgray'), ('green', 'green'), ('lightblue', 'lightblue'), ('lightgreen', 'lightgreen'), ('magenta', 'magenta'), ('orange', 'orange'), ('red', 'red'), ('silver', 'silver'), ('white', 'white'), ('yellow', 'yellow')])),
                ('thickness', models.DecimalField(help_text='in\xa0nm', verbose_name='thickness', max_digits=8, decimal_places=1)),
                ('thickness_reliable', models.BooleanField(default=False, verbose_name='thickness reliable')),
                ('structured', models.BooleanField(default=False, verbose_name='structured')),
                ('textured', models.BooleanField(default=False, verbose_name='textured')),
                ('always_collapsed', models.BooleanField(default=False, verbose_name='always collapsed')),
                ('additional_process_data', models.TextField(verbose_name='additional process data', blank=True)),
                ('verified', models.BooleanField(default=False, verbose_name='verified')),
            ],
            options={
                'ordering': ['sample_details', 'index'],
                'verbose_name': 'informal layer',
                'verbose_name_plural': 'informal layers',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='PDSMeasurement',
            fields=[
                ('process_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.Process')),
                ('number', models.PositiveIntegerField(unique=True, verbose_name='PDS number', db_index=True)),
                ('raw_datafile', models.CharField(help_text='only the relative path below "pds_raw_data/"', max_length=200, verbose_name='raw data file')),
                ('apparatus', models.CharField(default='pds1', max_length=15, verbose_name='apparatus', choices=[('pds1', 'PDS #1'), ('pds2', 'PDS #2')])),
            ],
            options={
                'get_latest_by': 'timestamp',
                'ordering': ['number'],
                'abstract': False,
                'verbose_name_plural': 'PDS measurements',
                'verbose_name': 'PDS measurement',
                'permissions': (('add_pds_measurement', 'Can add PDS measurements'), ('edit_permissions_for_pds_measurement', 'Can edit perms for PDS measurements'), ('view_every_pds_measurement', 'Can view all PDS measurements')),
            },
            bases=('samples.process',),
        ),
        migrations.CreateModel(
            name='SampleDetails',
            fields=[
                ('sample', models.OneToOneField(related_name='sample_details', primary_key=True, serialize=False, to='samples.Sample', verbose_name='sample')),
            ],
            options={
                'verbose_name': 'sample details',
                'verbose_name_plural': 'sample details',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SolarsimulatorCellMeasurement',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('position', models.CharField(max_length=5, verbose_name='cell position')),
                ('data_file', models.CharField(help_text='only the relative path below "solarsimulator_raw_data/"', max_length=200, verbose_name='data file', db_index=True)),
                ('area', models.FloatField(help_text='in cm\xb2', null=True, verbose_name='area', blank=True)),
                ('eta', models.FloatField(help_text='in %', null=True, verbose_name='efficiency \u03b7', blank=True)),
                ('isc', models.FloatField(help_text='in mA/cm\xb2', null=True, verbose_name='short-circuit current density', blank=True)),
            ],
            options={
                'verbose_name': 'solarsimulator cell measurement',
                'verbose_name_plural': 'solarsimulator cell measurements',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SolarsimulatorMeasurement',
            fields=[
                ('process_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.Process')),
                ('irradiation', models.CharField(max_length=10, verbose_name='irradiation', choices=[('AM1.5', 'AM1.5'), ('OG590', 'OG590'), ('BG7', 'BG7')])),
                ('temperature', models.DecimalField(default=25.0, help_text='in \u2103', verbose_name='temperature', max_digits=3, decimal_places=1)),
            ],
            options={
                'get_latest_by': 'timestamp',
                'ordering': ['timestamp'],
                'abstract': False,
                'verbose_name_plural': 'solarsimulator measurements',
                'verbose_name': 'solarsimulator measurement',
                'permissions': (('add_solarsimulator_measurement', 'Can add solarsimulator measurements'), ('edit_permissions_for_solarsimulator_measurement', 'Can edit perms for solarsimulator measurements'), ('view_every_solarsimulator_measurement', 'Can view all solarsimulator measurements')),
            },
            bases=('samples.process',),
        ),
        migrations.CreateModel(
            name='Structuring',
            fields=[
                ('process_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.Process')),
                ('layout', models.CharField(max_length=30, verbose_name='layout', choices=[('inm standard', 'INM Standard'), ('acme1', 'ACME 1'), ('custom', 'custom')])),
                ('length', models.FloatField(help_text='in\xa0mm', null=True, verbose_name='length', blank=True)),
                ('width', models.FloatField(help_text='in\xa0mm', null=True, verbose_name='width', blank=True)),
                ('parameters', models.TextField(verbose_name='parameters', blank=True)),
            ],
            options={
                'ordering': ['timestamp'],
                'abstract': False,
                'get_latest_by': 'timestamp',
                'verbose_name': 'structuring',
                'verbose_name_plural': 'structurings',
            },
            bases=('samples.process',),
        ),
        migrations.CreateModel(
            name='Substrate',
            fields=[
                ('process_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.Process')),
                ('material', models.CharField(max_length=30, verbose_name='substrate material', choices=[('custom', 'custom'), ('asahi-u', 'ASAHI-U'), ('asahi-vu', 'ASAHI-VU'), ('corning', 'Corning glass'), ('glass', 'glass'), ('si-wafer', 'silicon wafer'), ('quartz', 'quartz'), ('sapphire', 'sapphire'), ('aluminium foil', 'aluminium foil')])),
            ],
            options={
                'ordering': ['timestamp'],
                'abstract': False,
                'get_latest_by': 'timestamp',
                'verbose_name': 'substrate',
                'verbose_name_plural': 'substrates',
            },
            bases=('samples.process',),
        ),
        migrations.AddField(
            model_name='solarsimulatorcellmeasurement',
            name='measurement',
            field=models.ForeignKey(related_name='cells', verbose_name='solarsimulator measurement', to='inm.SolarsimulatorMeasurement'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='solarsimulatorcellmeasurement',
            unique_together=set([('position', 'data_file'), ('measurement', 'position')]),
        ),
        migrations.AddField(
            model_name='informallayer',
            name='process',
            field=models.ForeignKey(related_name='informal_layers', verbose_name='process', blank=True, to='samples.Process', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='informallayer',
            name='sample_details',
            field=models.ForeignKey(related_name='informal_layers', verbose_name='sample details', to='inm.SampleDetails'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='informallayer',
            unique_together=set([('index', 'sample_details')]),
        ),
        migrations.AlterUniqueTogether(
            name='fivechamberlayer',
            unique_together=set([('deposition', 'number')]),
        ),
        migrations.AddField(
            model_name='clustertoollayer',
            name='content_type',
            field=models.ForeignKey(blank=True, editable=False, to='contenttypes.ContentType', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='clustertoollayer',
            name='deposition',
            field=models.ForeignKey(related_name='layers', verbose_name='deposition', to='inm.ClusterToolDeposition'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='clustertoollayer',
            unique_together=set([('deposition', 'number')]),
        ),
    ]
