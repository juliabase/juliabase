from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Department',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=30, verbose_name='name')),
                ('app_label', models.CharField(max_length=30, verbose_name='app label')),
            ],
            options={
                'ordering': ['name'],
                'verbose_name': 'department',
                'verbose_name_plural': 'departments',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ErrorPage',
            fields=[
                ('hash_value', models.CharField(max_length=40, serialize=False, verbose_name='hash value', primary_key=True)),
                ('requested_url', models.TextField(verbose_name='requested URL', blank=True)),
                ('html', models.TextField(verbose_name='HTML')),
                ('timestamp', models.DateTimeField(auto_now_add=True, verbose_name='timestamp')),
            ],
            options={
                'verbose_name': 'error page',
                'verbose_name_plural': 'error pages',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Topic',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=80, verbose_name='name')),
                ('confidential', models.BooleanField(default=False, verbose_name='confidential')),
                ('department', models.ForeignKey(related_name='topic', verbose_name='department', to='jb_common.Department', on_delete=models.CASCADE)),
            ],
            options={
                'ordering': ['name'],
                'verbose_name_plural': 'topics',
                'default_permissions': (),
                'verbose_name': 'topic',
                'permissions': (('add_topic', 'Can add new topics'), ('change_topic', 'Can edit all topics'), ('edit_their_topics', 'Can edit topics that he/she is a manager of')),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='UserDetails',
            fields=[
                ('user', models.OneToOneField(related_name='jb_user_details', primary_key=True, serialize=False, to=settings.AUTH_USER_MODEL, verbose_name='user', on_delete=models.CASCADE)),
                ('language', models.CharField(default='de', max_length=10, verbose_name='language', choices=[('en', 'English'), ('de', 'Deutsch')])),
                ('browser_system', models.CharField(default='windows', max_length=10, verbose_name='operating system')),
                ('layout_last_modified', models.DateTimeField(auto_now_add=True, verbose_name='layout last modified')),
                ('department', models.ForeignKey(related_name='user_details', verbose_name='department', blank=True, to='jb_common.Department', null=True, on_delete=models.CASCADE)),
            ],
            options={
                'verbose_name': 'user details',
                'verbose_name_plural': 'user details',
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='topic',
            name='manager',
            field=models.ForeignKey(related_name='managed_topics', verbose_name='topic manager', to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='topic',
            name='members',
            field=models.ManyToManyField(related_name='topics', verbose_name='members', to=settings.AUTH_USER_MODEL, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='topic',
            name='parent_topic',
            field=models.ForeignKey(related_name='child_topics', verbose_name='parent topic', blank=True, to='jb_common.Topic', null=True, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='topic',
            unique_together=set([('name', 'department')]),
        ),
        migrations.AddField(
            model_name='errorpage',
            name='user',
            field=models.ForeignKey(related_name='error_pages', verbose_name='user', blank=True, to=settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE),
            preserve_default=True,
        ),
    ]
