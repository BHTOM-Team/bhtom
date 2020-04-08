# Generated by Django 2.2.8 on 2020-04-07 16:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0013_auto_20200407_1607'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bhtomfits',
            name='status',
            field=models.CharField(choices=[('C', 'Created'), ('S', 'Sent to photometry'), ('I', 'Photometry in progress'), ('R', 'Photometry result'), ('F', 'Finished'), ('E', 'Error'), ('U', 'User not active')], default='C', max_length=1),
        ),
        migrations.AlterField(
            model_name='cpcs_user',
            name='matchDist',
            field=models.CharField(choices=[('6', '6 arcsec'), ('2', '2 arcsec'), ('4', '4 arcsec'), ('1', '1 arcsec')], default='1 arcsec', max_length=10, verbose_name='Matching radius'),
        ),
    ]
