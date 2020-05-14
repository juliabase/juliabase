from django.db import models, migrations
import jb_common.model_fields


class Migration(migrations.Migration):

    dependencies = [
        ('samples', '0001_initial'),
        ('contenttypes', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClusterToolDeposition',
            fields=[
                ('deposition_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.Deposition', on_delete=models.CASCADE)),
                ('carrier', models.CharField(max_length=10, verbose_name='carrier', blank=True)),
            ],
            options={
                'get_latest_by': 'timestamp',
                'ordering': ['timestamp'],
                'abstract': False,
                'verbose_name_plural': 'cluster tool depositions',
                'default_permissions': (),
                'verbose_name': 'cluster tool deposition',
                'permissions': (('view_every_clustertooldeposition', "Can view every 'cluster tool deposition'"), ('add_clustertooldeposition', "Can add 'cluster tool deposition'"), ('edit_permissions_for_clustertooldeposition', "Can edit permissions for 'cluster tool deposition'"), ('change_clustertooldeposition', "Can edit every 'cluster tool deposition'")),
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
                ('clustertoollayer_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='institute.ClusterToolLayer', on_delete=models.CASCADE)),
                ('h2', jb_common.model_fields.DecimalQuantityField(null=True, verbose_name='H\u2082', max_digits=5, decimal_places=2, blank=True)),
                ('sih4', jb_common.model_fields.DecimalQuantityField(null=True, verbose_name='SiH\u2084', max_digits=5, decimal_places=2, blank=True)),
                ('time', models.CharField(help_text='format HH:MM:SS', max_length=9, verbose_name='deposition time', blank=True)),
                ('comments', models.TextField(verbose_name='comments', blank=True)),
                ('wire_material', models.CharField(max_length=20, verbose_name='wire material', choices=[('unknown', 'unknown'), ('rhenium', 'rhenium'), ('tantalum', 'tantalum'), ('tungsten', 'tungsten')])),
                ('base_pressure', jb_common.model_fields.FloatQuantityField(null=True, verbose_name='base pressure', blank=True)),
            ],
            options={
                'ordering': ['number'],
                'abstract': False,
                'verbose_name': 'cluster tool hot-wire layer',
                'verbose_name_plural': 'cluster tool hot-wire layers',
            },
            bases=('institute.clustertoollayer', models.Model),
        ),
        migrations.CreateModel(
            name='ClusterToolPECVDLayer',
            fields=[
                ('clustertoollayer_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='institute.ClusterToolLayer', on_delete=models.CASCADE)),
                ('h2', jb_common.model_fields.DecimalQuantityField(null=True, verbose_name='H\u2082', max_digits=5, decimal_places=2, blank=True)),
                ('sih4', jb_common.model_fields.DecimalQuantityField(null=True, verbose_name='SiH\u2084', max_digits=5, decimal_places=2, blank=True)),
                ('chamber', models.CharField(max_length=5, verbose_name='chamber', choices=[('#1', '#1'), ('#2', '#2'), ('#3', '#3')])),
                ('time', models.CharField(help_text='format HH:MM:SS', max_length=9, verbose_name='deposition time', blank=True)),
                ('comments', models.TextField(verbose_name='comments', blank=True)),
                ('plasma_start_with_shutter', models.BooleanField(default=False, verbose_name='plasma start with shutter')),
                ('deposition_power', jb_common.model_fields.DecimalQuantityField(null=True, verbose_name='deposition power', max_digits=6, decimal_places=2, blank=True)),
            ],
            options={
                'ordering': ['number'],
                'abstract': False,
                'verbose_name': 'cluster tool PECVD layer',
                'verbose_name_plural': 'cluster tool PECVD layers',
            },
            bases=('institute.clustertoollayer', models.Model),
        ),
        migrations.CreateModel(
            name='FiveChamberDeposition',
            fields=[
                ('deposition_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.Deposition', on_delete=models.CASCADE)),
            ],
            options={
                'get_latest_by': 'timestamp',
                'ordering': ['timestamp'],
                'abstract': False,
                'verbose_name_plural': '5-chamber depositions',
                'default_permissions': (),
                'verbose_name': '5-chamber deposition',
                'permissions': (('view_every_fivechamberdeposition', "Can view every 'five chamber deposition'"), ('add_fivechamberdeposition', "Can add 'five chamber deposition'"), ('edit_permissions_for_fivechamberdeposition', "Can edit permissions for 'five chamber deposition'"), ('change_fivechamberdeposition', "Can edit every 'five chamber deposition'")),
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
                ('sih4', jb_common.model_fields.DecimalQuantityField(null=True, verbose_name='SiH\u2084', max_digits=7, decimal_places=3, blank=True)),
                ('h2', jb_common.model_fields.DecimalQuantityField(null=True, verbose_name='H\u2082', max_digits=7, decimal_places=3, blank=True)),
                ('temperature_1', jb_common.model_fields.DecimalQuantityField(null=True, verbose_name='temperature 1', max_digits=7, decimal_places=3, blank=True)),
                ('temperature_2', jb_common.model_fields.DecimalQuantityField(null=True, verbose_name='temperature 2', max_digits=7, decimal_places=3, blank=True)),
                ('deposition', models.ForeignKey(related_name='layers', verbose_name='deposition', to='institute.FiveChamberDeposition', on_delete=models.CASCADE)),
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
                ('thickness', jb_common.model_fields.DecimalQuantityField(verbose_name='thickness', max_digits=8, decimal_places=1)),
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
            name='LayerThicknessMeasurement',
            fields=[
                ('process_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.Process', on_delete=models.CASCADE)),
                ('thickness', jb_common.model_fields.FloatQuantityField(verbose_name='layer thickness')),
                ('method', models.CharField(default='profilers&edge', max_length=30, verbose_name='measurement method', choices=[('profilers&edge', 'profilometer + edge'), ('ellipsometer', 'ellipsometer'), ('calculated', 'calculated from deposition parameters'), ('estimate', 'estimate'), ('other', 'other')])),
            ],
            options={
                'get_latest_by': 'timestamp',
                'ordering': ['timestamp'],
                'abstract': False,
                'verbose_name_plural': 'layer thickness measurements',
                'default_permissions': (),
                'verbose_name': 'layer thickness measurement',
            },
            bases=('samples.process',),
        ),
        migrations.CreateModel(
            name='PDSMeasurement',
            fields=[
                ('process_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.Process', on_delete=models.CASCADE)),
                ('number', models.PositiveIntegerField(unique=True, verbose_name='PDS number', db_index=True)),
                ('raw_datafile', models.CharField(help_text='only the relative path below "pds_raw_data/"', max_length=200, verbose_name='raw data file')),
                ('apparatus', models.CharField(default='pds1', max_length=15, verbose_name='apparatus', choices=[('pds1', 'PDS #1'), ('pds2', 'PDS #2')])),
            ],
            options={
                'get_latest_by': 'timestamp',
                'ordering': ['number'],
                'abstract': False,
                'verbose_name_plural': 'PDS measurements',
                'default_permissions': (),
                'verbose_name': 'PDS measurement',
                'permissions': (('view_every_pdsmeasurement', "Can view every 'PDS measurement'"), ('add_pdsmeasurement', "Can add 'PDS measurement'"), ('edit_permissions_for_pdsmeasurement', "Can edit permissions for 'PDS measurement'")),
            },
            bases=('samples.process',),
        ),
        migrations.CreateModel(
            name='SampleDetails',
            fields=[
                ('sample', models.OneToOneField(related_name='sample_details', primary_key=True, serialize=False, to='samples.Sample', verbose_name='sample', on_delete=models.CASCADE)),
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
                ('area', jb_common.model_fields.FloatQuantityField(null=True, verbose_name='area', blank=True)),
                ('eta', jb_common.model_fields.FloatQuantityField(null=True, verbose_name='efficiency \u03b7', blank=True)),
                ('isc', jb_common.model_fields.FloatQuantityField(null=True, verbose_name='short-circuit current density', blank=True)),
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
                ('process_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.Process', on_delete=models.CASCADE)),
                ('irradiation', models.CharField(max_length=10, verbose_name='irradiation', choices=[('AM1.5', 'AM1.5'), ('OG590', 'OG590'), ('BG7', 'BG7')])),
                ('temperature', jb_common.model_fields.DecimalQuantityField(default=25.0, verbose_name='temperature', max_digits=3, decimal_places=1)),
            ],
            options={
                'get_latest_by': 'timestamp',
                'ordering': ['timestamp'],
                'abstract': False,
                'verbose_name_plural': 'solarsimulator measurements',
                'default_permissions': (),
                'verbose_name': 'solarsimulator measurement',
                'permissions': (('view_every_solarsimulatormeasurement', "Can view every 'solarsimulator measure\u2026'"), ('add_solarsimulatormeasurement', "Can add 'solarsimulator measure\u2026'"), ('edit_permissions_for_solarsimulatormeasurement', "Can edit permissions for 'solarsimulator measure\u2026'")),
            },
            bases=('samples.process',),
        ),
        migrations.CreateModel(
            name='Structuring',
            fields=[
                ('process_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.Process', on_delete=models.CASCADE)),
                ('layout', models.CharField(max_length=30, verbose_name='layout', choices=[('inm standard', 'INM Standard'), ('acme1', 'ACME 1'), ('custom', 'custom')])),
                ('length', jb_common.model_fields.FloatQuantityField(null=True, verbose_name='length', blank=True)),
                ('width', jb_common.model_fields.FloatQuantityField(null=True, verbose_name='width', blank=True)),
                ('parameters', models.TextField(verbose_name='parameters', blank=True)),
            ],
            options={
                'get_latest_by': 'timestamp',
                'ordering': ['timestamp'],
                'abstract': False,
                'verbose_name_plural': 'structurings',
                'default_permissions': (),
                'verbose_name': 'structuring',
            },
            bases=('samples.process',),
        ),
        migrations.CreateModel(
            name='Substrate',
            fields=[
                ('process_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.Process', on_delete=models.CASCADE)),
                ('material', models.CharField(max_length=30, verbose_name='substrate material', choices=[('custom', 'custom'), ('asahi-u', 'ASAHI-U'), ('asahi-vu', 'ASAHI-VU'), ('corning', 'Corning glass'), ('glass', 'glass'), ('si-wafer', 'silicon wafer'), ('quartz', 'quartz'), ('sapphire', 'sapphire'), ('aluminium foil', 'aluminium foil')])),
            ],
            options={
                'get_latest_by': 'timestamp',
                'ordering': ['timestamp'],
                'abstract': False,
                'verbose_name_plural': 'substrates',
                'default_permissions': (),
                'verbose_name': 'substrate',
            },
            bases=('samples.process',),
        ),
        migrations.AddField(
            model_name='solarsimulatorcellmeasurement',
            name='measurement',
            field=models.ForeignKey(related_name='cells', verbose_name='solarsimulator measurement', to='institute.SolarsimulatorMeasurement', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='solarsimulatorcellmeasurement',
            unique_together=set([('position', 'data_file'), ('measurement', 'position')]),
        ),
        migrations.AddField(
            model_name='informallayer',
            name='process',
            field=models.ForeignKey(related_name='informal_layers', verbose_name='process', blank=True, to='samples.Process', null=True, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='informallayer',
            name='sample_details',
            field=models.ForeignKey(related_name='informal_layers', verbose_name='sample details', to='institute.SampleDetails', on_delete=models.CASCADE),
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
            field=models.ForeignKey(blank=True, editable=False, to='contenttypes.ContentType', null=True, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='clustertoollayer',
            name='deposition',
            field=models.ForeignKey(related_name='layers', verbose_name='deposition', to='institute.ClusterToolDeposition', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='clustertoollayer',
            unique_together=set([('deposition', 'number')]),
        ),
    ]
