from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='KickerNumber',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('number', models.FloatField(verbose_name='kicker number')),
                ('timestamp', models.DateTimeField(verbose_name='timestamp')),
            ],
            options={
                'ordering': ['timestamp'],
                'verbose_name': 'kicker number',
                'verbose_name_plural': 'kicker numbers',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Match',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('goals_a', models.PositiveSmallIntegerField(verbose_name='goals of team A')),
                ('goals_b', models.PositiveSmallIntegerField(verbose_name='goals of team B')),
                ('seconds', models.FloatField(help_text='duration of the match', verbose_name='seconds')),
                ('timestamp', models.DateTimeField(verbose_name='timestamp')),
                ('finished', models.BooleanField(default=False, verbose_name='finished')),
            ],
            options={
                'ordering': ['timestamp'],
                'verbose_name': 'match',
                'verbose_name_plural': 'matches',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Shares',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('number', models.PositiveSmallIntegerField(verbose_name='number of shares')),
                ('timestamp', models.DateTimeField(auto_now_add=True, verbose_name='timestamp')),
            ],
            options={
                'verbose_name': 'shares',
                'verbose_name_plural': 'shareses',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='StockValue',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('value', models.FloatField(verbose_name='stock value')),
                ('timestamp', models.DateTimeField(verbose_name='timestamp')),
            ],
            options={
                'ordering': ['timestamp'],
                'verbose_name': 'stock value',
                'verbose_name_plural': 'stock values',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='UserDetails',
            fields=[
                ('user', models.OneToOneField(related_name='kicker_user_details', primary_key=True, serialize=False, to=settings.AUTH_USER_MODEL, verbose_name='user', on_delete=models.CASCADE)),
                ('nickname', models.CharField(max_length=30, verbose_name='nickname', blank=True)),
                ('shortkey', models.CharField(max_length=1, verbose_name='shortkey', blank=True)),
            ],
            options={
                'verbose_name': 'user details',
                'verbose_name_plural': 'user details',
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='stockvalue',
            name='gambler',
            field=models.ForeignKey(related_name='stock_values', verbose_name='gambler', to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='shares',
            name='bought_person',
            field=models.ForeignKey(related_name='sold_shares', verbose_name='bought person', to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='shares',
            name='owner',
            field=models.ForeignKey(related_name='bought_shares', verbose_name='owner', to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='match',
            name='player_a_1',
            field=models.ForeignKey(related_name='match_player_a_1', verbose_name='player 1 of team A', to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='match',
            name='player_a_2',
            field=models.ForeignKey(related_name='match_player_a_2', verbose_name='player 2 of team A', to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='match',
            name='player_b_1',
            field=models.ForeignKey(related_name='match_player_b_1', verbose_name='player 1 of team B', to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='match',
            name='player_b_2',
            field=models.ForeignKey(related_name='match_player_b_2', verbose_name='player 2 of team B', to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='match',
            name='reporter',
            field=models.ForeignKey(related_name='+', verbose_name='reporter', to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='kickernumber',
            name='player',
            field=models.ForeignKey(related_name='kicker_numbers', verbose_name='player', to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE),
            preserve_default=True,
        ),
    ]
