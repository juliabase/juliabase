from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0001_initial'),
        ('jb_common', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Clearance',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('last_modified', models.DateTimeField(auto_now=True, verbose_name='last modified', auto_now_add=True)),
            ],
            options={
                'verbose_name': 'clearance',
                'verbose_name_plural': 'clearances',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ExternalOperator',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=30, verbose_name='name')),
                ('institution', models.CharField(max_length=255, verbose_name='institution')),
                ('email', models.EmailField(max_length=75, verbose_name='email')),
                ('alternative_email', models.EmailField(max_length=75, verbose_name='alternative email', blank=True)),
                ('phone', models.CharField(max_length=30, verbose_name='phone', blank=True)),
                ('confidential', models.BooleanField(default=False, verbose_name='confidential')),
            ],
            options={
                'default_permissions': (),
                'verbose_name': 'external operator',
                'verbose_name_plural': 'external operators',
                'permissions': (('add_externaloperator', 'Can add an external operator'), ('view_every_externaloperator', 'Can view all external operators')),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='FeedEntry',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('actual_object_id', models.PositiveIntegerField(null=True, editable=False, blank=True)),
                ('timestamp', models.DateTimeField(auto_now_add=True, verbose_name='timestamp')),
                ('important', models.BooleanField(default=True, verbose_name='is important')),
                ('sha1_hash', models.CharField(verbose_name='SHA1 hex digest', max_length=40, editable=False, blank=True)),
            ],
            options={
                'ordering': ['-timestamp'],
                'verbose_name': 'feed entry',
                'verbose_name_plural': 'feed entries',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='FeedEditedTask',
            fields=[
                ('feedentry_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.FeedEntry', on_delete=models.CASCADE)),
                ('description', models.TextField(verbose_name='description')),
            ],
            options={
                'abstract': False,
                'verbose_name': 'edited task feed entry',
                'verbose_name_plural': 'edited task feed entries',
            },
            bases=('samples.feedentry',),
        ),
        migrations.CreateModel(
            name='FeedEditedSampleSeries',
            fields=[
                ('feedentry_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.FeedEntry', on_delete=models.CASCADE)),
                ('description', models.TextField(verbose_name='description')),
                ('responsible_person_changed', models.BooleanField(default=False, verbose_name='has responsible person changed')),
            ],
            options={
                'abstract': False,
                'verbose_name': 'edited sample series feed entry',
                'verbose_name_plural': 'edited sample series feed entries',
            },
            bases=('samples.feedentry',),
        ),
        migrations.CreateModel(
            name='FeedEditedSamples',
            fields=[
                ('feedentry_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.FeedEntry', on_delete=models.CASCADE)),
                ('description', models.TextField(verbose_name='description')),
                ('responsible_person_changed', models.BooleanField(default=False, verbose_name='has responsible person changed')),
            ],
            options={
                'abstract': False,
                'verbose_name': 'edited samples feed entry',
                'verbose_name_plural': 'edited samples feed entries',
            },
            bases=('samples.feedentry',),
        ),
        migrations.CreateModel(
            name='FeedEditedPhysicalProcess',
            fields=[
                ('feedentry_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.FeedEntry', on_delete=models.CASCADE)),
                ('description', models.TextField(verbose_name='description')),
            ],
            options={
                'abstract': False,
                'verbose_name': 'edited physical process feed entry',
                'verbose_name_plural': 'edited physical process feed entries',
            },
            bases=('samples.feedentry',),
        ),
        migrations.CreateModel(
            name='FeedCopiedMySamples',
            fields=[
                ('feedentry_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.FeedEntry', on_delete=models.CASCADE)),
                ('comments', models.TextField(verbose_name='comments')),
            ],
            options={
                'abstract': False,
                'verbose_name': 'copied My Samples feed entry',
                'verbose_name_plural': 'copied My Samples feed entries',
            },
            bases=('samples.feedentry',),
        ),
        migrations.CreateModel(
            name='FeedChangedTopic',
            fields=[
                ('feedentry_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.FeedEntry', on_delete=models.CASCADE)),
                ('action', models.CharField(max_length=7, verbose_name='action', choices=[('added', 'added'), ('removed', 'removed')])),
                ('topic', models.ForeignKey(verbose_name='topic', to='jb_common.Topic', on_delete=models.CASCADE)),
            ],
            options={
                'abstract': False,
                'verbose_name': 'changed topic feed entry',
                'verbose_name_plural': 'changed topic feed entries',
            },
            bases=('samples.feedentry',),
        ),
        migrations.CreateModel(
            name='FeedMovedSamples',
            fields=[
                ('feedentry_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.FeedEntry', on_delete=models.CASCADE)),
                ('description', models.TextField(verbose_name='description')),
            ],
            options={
                'abstract': False,
                'verbose_name': 'moved samples feed entry',
                'verbose_name_plural': 'moved samples feed entries',
            },
            bases=('samples.feedentry',),
        ),
        migrations.CreateModel(
            name='FeedMovedSampleSeries',
            fields=[
                ('feedentry_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.FeedEntry', on_delete=models.CASCADE)),
                ('description', models.TextField(verbose_name='description')),
                ('old_topic', models.ForeignKey(related_name='news_ex_sample_series', verbose_name='old topic', blank=True, to='jb_common.Topic', null=True, on_delete=models.CASCADE)),
            ],
            options={
                'abstract': False,
                'verbose_name': 'moved sample series feed entry',
                'verbose_name_plural': 'moved sample series feed entries',
            },
            bases=('samples.feedentry',),
        ),
        migrations.CreateModel(
            name='FeedNewPhysicalProcess',
            fields=[
                ('feedentry_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.FeedEntry', on_delete=models.CASCADE)),
            ],
            options={
                'abstract': False,
                'verbose_name': 'new physical process feed entry',
                'verbose_name_plural': 'new physical process feed entries',
            },
            bases=('samples.feedentry',),
        ),
        migrations.CreateModel(
            name='FeedNewSamples',
            fields=[
                ('feedentry_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.FeedEntry', on_delete=models.CASCADE)),
                ('purpose', models.CharField(max_length=80, verbose_name='purpose', blank=True)),
            ],
            options={
                'abstract': False,
                'verbose_name': 'new samples feed entry',
                'verbose_name_plural': 'new samples feed entries',
            },
            bases=('samples.feedentry',),
        ),
        migrations.CreateModel(
            name='FeedNewSampleSeries',
            fields=[
                ('feedentry_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.FeedEntry', on_delete=models.CASCADE)),
            ],
            options={
                'abstract': False,
                'verbose_name': 'new sample series feed entry',
                'verbose_name_plural': 'new sample series feed entries',
            },
            bases=('samples.feedentry',),
        ),
        migrations.CreateModel(
            name='FeedNewTask',
            fields=[
                ('feedentry_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.FeedEntry', on_delete=models.CASCADE)),
            ],
            options={
                'abstract': False,
                'verbose_name': 'new task feed entry',
                'verbose_name_plural': 'new task feed entries',
            },
            bases=('samples.feedentry',),
        ),
        migrations.CreateModel(
            name='FeedRemovedTask',
            fields=[
                ('feedentry_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.FeedEntry', on_delete=models.CASCADE)),
                ('old_id', models.PositiveIntegerField(unique=True, verbose_name='number')),
                ('process_class', models.ForeignKey(verbose_name='process class', to='contenttypes.ContentType', on_delete=models.CASCADE)),
            ],
            options={
                'abstract': False,
                'verbose_name': 'removed task feed entry',
                'verbose_name_plural': 'removed task feed entries',
            },
            bases=('samples.feedentry',),
        ),
        migrations.CreateModel(
            name='FeedResult',
            fields=[
                ('feedentry_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.FeedEntry', on_delete=models.CASCADE)),
                ('description', models.TextField(verbose_name='description', blank=True)),
                ('is_new', models.BooleanField(default=False, verbose_name='result is new')),
            ],
            options={
                'abstract': False,
                'verbose_name': 'result feed entry',
                'verbose_name_plural': 'result feed entries',
            },
            bases=('samples.feedentry',),
        ),
        migrations.CreateModel(
            name='FeedSampleSplit',
            fields=[
                ('feedentry_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.FeedEntry', on_delete=models.CASCADE)),
                ('sample_completely_split', models.BooleanField(default=False, verbose_name='sample was completely split')),
            ],
            options={
                'abstract': False,
                'verbose_name': 'sample split feed entry',
                'verbose_name_plural': 'sample split feed entries',
            },
            bases=('samples.feedentry',),
        ),
        migrations.CreateModel(
            name='FeedStatusMessage',
            fields=[
                ('feedentry_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.FeedEntry', on_delete=models.CASCADE)),
                ('process_class', models.ForeignKey(verbose_name='process class', to='contenttypes.ContentType', on_delete=models.CASCADE)),
            ],
            options={
                'abstract': False,
                'verbose_name': 'status message feed entry',
                'verbose_name_plural': 'status message feed entries',
            },
            bases=('samples.feedentry',),
        ),
        migrations.CreateModel(
            name='FeedWithdrawnStatusMessage',
            fields=[
                ('feedentry_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.FeedEntry', on_delete=models.CASCADE)),
                ('process_class', models.ForeignKey(verbose_name='process class', to='contenttypes.ContentType', on_delete=models.CASCADE)),
            ],
            options={
                'abstract': False,
                'verbose_name': 'withdrawn status message feed entry',
                'verbose_name_plural': 'withdrawn status message feed entries',
            },
            bases=('samples.feedentry',),
        ),
        migrations.CreateModel(
            name='Initials',
            fields=[
                ('initials', models.CharField(max_length=4, serialize=False, verbose_name='initials', primary_key=True)),
                ('external_operator', models.OneToOneField(related_name='initials', null=True, blank=True, to='samples.ExternalOperator', verbose_name='external operator', on_delete=models.CASCADE)),
            ],
            options={
                'verbose_name': 'initials',
                'verbose_name_plural': 'initialses',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Process',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('actual_object_id', models.PositiveIntegerField(null=True, editable=False, blank=True)),
                ('timestamp', models.DateTimeField(verbose_name='timestamp')),
                ('timestamp_inaccuracy', models.PositiveSmallIntegerField(default=0, verbose_name='timestamp inaccuracy', choices=[(0, 'totally accurate'), (1, 'accurate to the minute'), (2, 'accurate to the hour'), (3, 'accurate to the day'), (4, 'accurate to the month'), (5, 'accurate to the year'), (6, 'not even accurate to the year')])),
                ('comments', models.TextField(verbose_name='comments', blank=True)),
                ('last_modified', models.DateTimeField(auto_now=True, verbose_name='last modified', auto_now_add=True)),
                ('finished', models.BooleanField(default=True, verbose_name='finished')),
            ],
            options={
                'ordering': ['timestamp'],
                'get_latest_by': 'timestamp',
                'verbose_name': 'process',
                'verbose_name_plural': 'processes',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Deposition',
            fields=[
                ('process_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.Process', on_delete=models.CASCADE)),
                ('number', models.CharField(unique=True, max_length=15, verbose_name='deposition number', db_index=True)),
                ('split_done', models.BooleanField(default=False, verbose_name='split after deposition done')),
            ],
            options={
                'get_latest_by': 'timestamp',
                'ordering': ['timestamp'],
                'abstract': False,
                'verbose_name_plural': 'depositions',
                'default_permissions': (),
                'verbose_name': 'deposition',
            },
            bases=('samples.process',),
        ),
        migrations.CreateModel(
            name='Result',
            fields=[
                ('process_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.Process', on_delete=models.CASCADE)),
                ('title', models.CharField(max_length=50, verbose_name='title')),
                ('image_type', models.CharField(default='none', max_length=4, verbose_name='image file type', choices=[('none', 'none'), ('pdf', 'PDF'), ('png', 'PNG'), ('jpeg', 'JPEG')])),
                ('quantities_and_values', models.TextField(help_text='in JSON format', verbose_name='quantities and values', blank=True)),
            ],
            options={
                'abstract': False,
                'verbose_name': 'result',
                'verbose_name_plural': 'results',
            },
            bases=('samples.process',),
        ),
        migrations.CreateModel(
            name='Sample',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=30, verbose_name='name', db_index=True)),
                ('current_location', models.CharField(max_length=50, verbose_name='current location')),
                ('purpose', models.CharField(max_length=80, verbose_name='purpose', blank=True)),
                ('tags', models.CharField(help_text='separated with commas, no whitespace', max_length=255, verbose_name='tags', blank=True)),
                ('last_modified', models.DateTimeField(auto_now=True, verbose_name='last modified', auto_now_add=True)),
            ],
            options={
                'ordering': ['name'],
                'verbose_name': 'sample',
                'verbose_name_plural': 'samples',
                'permissions': (('view_every_sample', 'Can view all samples from his/her department'), ('adopt_samples', 'Can adopt samples from his/her department'), ('rename_samples', 'Can rename samples from his/her department')),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SampleAlias',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255, verbose_name='name')),
                ('sample', models.ForeignKey(related_name='aliases', verbose_name='sample', to='samples.Sample', on_delete=models.CASCADE)),
            ],
            options={
                'verbose_name': 'name alias',
                'verbose_name_plural': 'name aliases',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SampleClaim',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('closed', models.BooleanField(default=False, verbose_name='closed')),
            ],
            options={
                'verbose_name': 'sample claim',
                'verbose_name_plural': 'sample claims',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SampleDeath',
            fields=[
                ('process_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.Process', on_delete=models.CASCADE)),
                ('reason', models.CharField(max_length=50, verbose_name='cause of death', choices=[('split', 'completely split'), ('lost', 'lost and unfindable'), ('destroyed', 'completely destroyed')])),
            ],
            options={
                'abstract': False,
                'verbose_name': 'cease of existence',
                'verbose_name_plural': 'ceases of existence',
            },
            bases=('samples.process',),
        ),
        migrations.CreateModel(
            name='SampleSeries',
            fields=[
                ('name', models.CharField(help_text='must be of the form \u201coriginator-YY-name\u201d', max_length=50, serialize=False, verbose_name='name', primary_key=True)),
                ('timestamp', models.DateTimeField(verbose_name='timestamp')),
                ('description', models.TextField(verbose_name='description')),
                ('last_modified', models.DateTimeField(auto_now=True, verbose_name='last modified', auto_now_add=True)),
            ],
            options={
                'verbose_name': 'sample series',
                'verbose_name_plural': 'sample series',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SampleSplit',
            fields=[
                ('process_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='samples.Process', on_delete=models.CASCADE)),
                ('parent', models.ForeignKey(verbose_name='parent', to='samples.Sample', on_delete=models.CASCADE)),
            ],
            options={
                'abstract': False,
                'verbose_name': 'sample split',
                'verbose_name_plural': 'sample splits',
            },
            bases=('samples.process',),
        ),
        migrations.CreateModel(
            name='StatusMessage',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('timestamp', models.DateTimeField(verbose_name='timestamp')),
                ('begin', models.DateTimeField(help_text='YYYY-MM-DD HH:MM:SS', null=True, verbose_name='begin', blank=True)),
                ('end', models.DateTimeField(help_text='YYYY-MM-DD HH:MM:SS', null=True, verbose_name='end', blank=True)),
                ('begin_inaccuracy', models.PositiveSmallIntegerField(default=0, verbose_name='begin inaccuracy', choices=[(0, 'totally accurate'), (1, 'accurate to the minute'), (2, 'accurate to the hour'), (3, 'accurate to the day'), (4, 'accurate to the month'), (5, 'accurate to the year'), (6, 'not even accurate to the year')])),
                ('end_inaccuracy', models.PositiveSmallIntegerField(default=0, verbose_name='end inaccuracy', choices=[(0, 'totally accurate'), (1, 'accurate to the minute'), (2, 'accurate to the hour'), (3, 'accurate to the day'), (4, 'accurate to the month'), (5, 'accurate to the year'), (6, 'not even accurate to the year')])),
                ('message', models.TextField(verbose_name='message', blank=True)),
                ('status_level', models.CharField(default='undefined', max_length=10, verbose_name='level', choices=[('undefined', 'undefined'), ('red', 'red'), ('yellow', 'yellow'), ('green', 'green')])),
                ('withdrawn', models.BooleanField(default=False, verbose_name='withdrawn')),
            ],
            options={
                'verbose_name': 'status message',
                'verbose_name_plural': 'status messages',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('status', models.CharField(default='1 new', max_length=15, verbose_name='status', choices=[('0 finished', 'finished'), ('1 new', 'new'), ('2 accepted', 'accepted'), ('3 in progress', 'in progress')])),
                ('creating_timestamp', models.DateTimeField(help_text='YYYY-MM-DD HH:MM:SS', verbose_name='created at', auto_now_add=True)),
                ('last_modified', models.DateTimeField(auto_now=True, auto_now_add=True, help_text='YYYY-MM-DD HH:MM:SS', verbose_name='last modified')),
                ('comments', models.TextField(verbose_name='comments', blank=True)),
                ('priority', models.CharField(default='2 normal', max_length=15, verbose_name='priority', choices=[('0 critical', 'critical'), ('1 high', 'high'), ('2 normal', 'normal'), ('3 low', 'low')])),
            ],
            options={
                'verbose_name': 'task',
                'verbose_name_plural': 'tasks',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='UserDetails',
            fields=[
                ('user', models.OneToOneField(related_name='samples_user_details', primary_key=True, serialize=False, to=settings.AUTH_USER_MODEL, verbose_name='user', on_delete=models.CASCADE)),
                ('only_important_news', models.BooleanField(default=False, verbose_name='get only important news')),
                ('my_layers', models.TextField(help_text='in JSON format', verbose_name='my layers', blank=True)),
                ('display_settings_timestamp', models.DateTimeField(auto_now_add=True, verbose_name='display settings last modified')),
                ('my_samples_timestamp', models.DateTimeField(auto_now_add=True, verbose_name='My Samples last modified')),
                ('identifying_data_hash', models.CharField(max_length=40, verbose_name='identifying data hash')),
                ('folded_processes', models.TextField(default='{}', help_text='in JSON format', verbose_name='folded processes', blank=True)),
                ('folded_topics', models.TextField(default='[]', help_text='in JSON format', verbose_name='folded topics', blank=True)),
                ('folded_series', models.TextField(default='[]', help_text='in JSON format', verbose_name='folded sample series', blank=True)),
                ('auto_addition_topics', models.ManyToManyField(help_text='new samples in these topics are automatically added to \u201cMy Samples\u201d', related_name='auto_adders', verbose_name='auto-addition topics', to='jb_common.Topic', blank=True)),
                ('default_folded_process_classes', models.ManyToManyField(related_name='dont_show_to_user', verbose_name='folded processes', to='contenttypes.ContentType', blank=True)),
                ('show_users_from_departments', models.ManyToManyField(related_name='shown_users', verbose_name='show users from department', to='jb_common.Department', blank=True)),
                ('subscribed_feeds', models.ManyToManyField(related_name='subscribed_users', verbose_name='subscribed newsfeeds', to='contenttypes.ContentType', blank=True)),
                ('visible_task_lists', models.ManyToManyField(related_name='task_lists_from_user', verbose_name='visible task lists', to='contenttypes.ContentType', blank=True)),
            ],
            options={
                'verbose_name': 'user details',
                'verbose_name_plural': 'user details',
                'permissions': (('edit_permissions_for_all_physical_processes', 'Can edit permissions for all physical processes'),),
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='task',
            name='customer',
            field=models.ForeignKey(related_name='tasks', verbose_name='customer', to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='task',
            name='finished_process',
            field=models.ForeignKey(related_name='task', verbose_name='finished process', blank=True, to='samples.Process', null=True, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='task',
            name='operator',
            field=models.ForeignKey(related_name='operated tasks', verbose_name='operator', blank=True, to=settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='task',
            name='process_class',
            field=models.ForeignKey(related_name='tasks', verbose_name='process class', to='contenttypes.ContentType', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='task',
            name='samples',
            field=models.ManyToManyField(related_name='task', verbose_name='samples', to='samples.Sample'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='statusmessage',
            name='operator',
            field=models.ForeignKey(related_name='status_messages', verbose_name='reporter', to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='statusmessage',
            name='process_classes',
            field=models.ManyToManyField(related_name='status_messages', verbose_name='processes', to='contenttypes.ContentType'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='sampleseries',
            name='currently_responsible_person',
            field=models.ForeignKey(related_name='sample_series', verbose_name='currently responsible person', to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='sampleseries',
            name='results',
            field=models.ManyToManyField(related_name='sample_series', verbose_name='results', to='samples.Result', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='sampleseries',
            name='samples',
            field=models.ManyToManyField(related_name='series', verbose_name='samples', to='samples.Sample', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='sampleseries',
            name='topic',
            field=models.ForeignKey(related_name='sample_series', verbose_name='topic', to='jb_common.Topic', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='sampleclaim',
            name='requester',
            field=models.ForeignKey(related_name='claims', verbose_name='requester', to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='sampleclaim',
            name='reviewer',
            field=models.ForeignKey(related_name='claims_as_reviewer', verbose_name='reviewer', to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='sampleclaim',
            name='samples',
            field=models.ManyToManyField(related_name='claims', verbose_name='samples', to='samples.Sample'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='samplealias',
            unique_together=set([('name', 'sample')]),
        ),
        migrations.AddField(
            model_name='sample',
            name='currently_responsible_person',
            field=models.ForeignKey(related_name='samples', verbose_name='currently responsible person', to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='sample',
            name='processes',
            field=models.ManyToManyField(related_name='samples', verbose_name='processes', to='samples.Process', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='sample',
            name='split_origin',
            field=models.ForeignKey(related_name='pieces', verbose_name='split origin', blank=True, to='samples.SampleSplit', null=True, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='sample',
            name='topic',
            field=models.ForeignKey(related_name='samples', verbose_name='topic', blank=True, to='jb_common.Topic', null=True, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='sample',
            name='watchers',
            field=models.ManyToManyField(related_name='my_samples', verbose_name='watchers', to=settings.AUTH_USER_MODEL, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='process',
            name='content_type',
            field=models.ForeignKey(blank=True, editable=False, to='contenttypes.ContentType', null=True, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='process',
            name='external_operator',
            field=models.ForeignKey(related_name='processes', verbose_name='external operator', blank=True, to='samples.ExternalOperator', null=True, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='process',
            name='operator',
            field=models.ForeignKey(related_name='processes', verbose_name='operator', to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='initials',
            name='user',
            field=models.OneToOneField(related_name='initials', null=True, blank=True, to=settings.AUTH_USER_MODEL, verbose_name='user', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feedwithdrawnstatusmessage',
            name='status',
            field=models.ForeignKey(related_name='feed_entries_for_withdrawal', verbose_name='status message', to='samples.StatusMessage', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feedstatusmessage',
            name='status',
            field=models.ForeignKey(related_name='feed_entries', verbose_name='status message', to='samples.StatusMessage', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feedsamplesplit',
            name='sample_split',
            field=models.ForeignKey(verbose_name='sample split', to='samples.SampleSplit', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feedresult',
            name='result',
            field=models.ForeignKey(verbose_name='result', to='samples.Result', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feedremovedtask',
            name='samples',
            field=models.ManyToManyField(to='samples.Sample', verbose_name='samples'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feednewtask',
            name='task',
            field=models.ForeignKey(related_name='feed_entries_for_new_tasks', verbose_name='task', to='samples.Task', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feednewsampleseries',
            name='sample_series',
            field=models.ForeignKey(verbose_name='sample series', to='samples.SampleSeries', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feednewsampleseries',
            name='subscribers',
            field=models.ManyToManyField(to=settings.AUTH_USER_MODEL, verbose_name='subscribers', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feednewsampleseries',
            name='topic',
            field=models.ForeignKey(verbose_name='topic', to='jb_common.Topic', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feednewsamples',
            name='auto_adders',
            field=models.ManyToManyField(to=settings.AUTH_USER_MODEL, verbose_name='auto adders', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feednewsamples',
            name='samples',
            field=models.ManyToManyField(to='samples.Sample', verbose_name='samples'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feednewsamples',
            name='topic',
            field=models.ForeignKey(related_name='new_samples_news', verbose_name='topic', to='jb_common.Topic', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feednewphysicalprocess',
            name='process',
            field=models.OneToOneField(verbose_name='process', to='samples.Process', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feedmovedsampleseries',
            name='sample_series',
            field=models.ForeignKey(verbose_name='sample series', to='samples.SampleSeries', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feedmovedsampleseries',
            name='subscribers',
            field=models.ManyToManyField(to=settings.AUTH_USER_MODEL, verbose_name='subscribers', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feedmovedsampleseries',
            name='topic',
            field=models.ForeignKey(verbose_name='topic', to='jb_common.Topic', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feedmovedsamples',
            name='auto_adders',
            field=models.ManyToManyField(to=settings.AUTH_USER_MODEL, verbose_name='auto adders', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feedmovedsamples',
            name='old_topic',
            field=models.ForeignKey(verbose_name='old topic', blank=True, to='jb_common.Topic', null=True, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feedmovedsamples',
            name='samples',
            field=models.ManyToManyField(to='samples.Sample', verbose_name='samples'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feedmovedsamples',
            name='topic',
            field=models.ForeignKey(related_name='moved_samples_news', verbose_name='topic', to='jb_common.Topic', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feedentry',
            name='content_type',
            field=models.ForeignKey(blank=True, editable=False, to='contenttypes.ContentType', null=True, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feedentry',
            name='originator',
            field=models.ForeignKey(verbose_name='originator', to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feedentry',
            name='users',
            field=models.ManyToManyField(related_name='feed_entries', verbose_name='users', to=settings.AUTH_USER_MODEL, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feededitedtask',
            name='task',
            field=models.ForeignKey(related_name='feed_entries_for_edited_tasks', verbose_name='task', to='samples.Task', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feededitedsampleseries',
            name='sample_series',
            field=models.ForeignKey(verbose_name='sample series', to='samples.SampleSeries', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feededitedsamples',
            name='samples',
            field=models.ManyToManyField(to='samples.Sample', verbose_name='samples'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feededitedphysicalprocess',
            name='process',
            field=models.ForeignKey(verbose_name='process', to='samples.Process', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='feedcopiedmysamples',
            name='samples',
            field=models.ManyToManyField(to='samples.Sample', verbose_name='samples'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='externaloperator',
            name='contact_persons',
            field=models.ManyToManyField(related_name='external_contacts', verbose_name='contact persons in the institute', to=settings.AUTH_USER_MODEL),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='clearance',
            name='processes',
            field=models.ManyToManyField(related_name='clearances', verbose_name='processes', to='samples.Process', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='clearance',
            name='sample',
            field=models.ForeignKey(related_name='clearances', verbose_name='sample', to='samples.Sample', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='clearance',
            name='user',
            field=models.ForeignKey(related_name='clearances', verbose_name='user', to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='clearance',
            unique_together=set([('user', 'sample')]),
        ),
    ]
