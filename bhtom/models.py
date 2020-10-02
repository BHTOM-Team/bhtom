from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField

class Observatory(models.Model):

    MATCHING_RADIUS = {
        ('1', '1 arcsec'),
        ('2', '2 arcsec'),
        ('4', '4 arcsec'),
        ('6', '6 arcsec')
    }

    obsName = models.CharField(max_length=255, verbose_name='Observatory name', unique=True)
    lon = models.FloatField(null=False, blank=False, verbose_name='Longitude')
    lat = models.FloatField(null=False, blank=False, verbose_name='Latitude')
    prefix = models.CharField(max_length=255, null=True, blank=True)
    userActivation = models.BooleanField()
    matchDist = models.CharField(max_length=10, choices=MATCHING_RADIUS, default='1 arcsec', verbose_name='Matching radius')
    fits = models.FileField(upload_to='user_fits', null=True, blank=True, verbose_name='Sample fits')
    obsInfo = models.FileField(upload_to='ObsInfo', null=True, blank=True, verbose_name='Obs Info')

class Instrument(models.Model):
    user_id = models.ForeignKey(User, on_delete=models.CASCADE)
    observatory_id = models.ForeignKey(Observatory, on_delete=models.CASCADE)
    insName = models.CharField(max_length=255, verbose_name='Instrument name', null=True, blank=True)
    dry_run = models.BooleanField(verbose_name='Dry Run (no data will be stored in the database)')
    hashtag = models.CharField(max_length=255, editable=True, null=False, blank=False)

class BHTomFits(models.Model):
    FITS_STATUS = [
        ('C', 'Created'),
        ('S', 'Sent to photometry'),
        ('I', 'Photometry in progress'),
        ('R', 'Photometry result'),
        ('F', 'Finished'),
        ('E', 'Error'),
        ('U', 'User not active'),
    ]
    MATCHING_RADIUS = {
        ('1', '1 arcsec'),
        ('2', '2 arcsec'),
        ('4', '4 arcsec'),
        ('6', '6 arcsec')
    }

    file_id = models.AutoField(db_index=True, primary_key=True)
    instrument_id = models.ForeignKey(Instrument, on_delete=models.CASCADE)
    dataproduct_id = models.IntegerField(null=False, blank=False)
    status = models.CharField(max_length=1, choices=FITS_STATUS, default='C')
    status_message = models.TextField(default='Fits upload', blank=True, editable=False)
    mjd = models.FloatField(null=True, blank=True)
    expTime = models.FloatField(null=True, blank=True)
    photometry_file = models.FileField(upload_to='photometry', null=True, blank=True, editable=False)
    cpcs_plot = models.TextField(null=True, blank=True)
    mag = models.FloatField(null=True, blank=True)
    mag_err = models.FloatField(null=True, blank=True)
    ra = models.FloatField(null=True, blank=True)
    dec = models.FloatField(null=True, blank=True)
    zeropoint = models.FloatField(null=True, blank=True)
    outlier_fraction = models.FloatField(null=True, blank=True)
    scatter = models.FloatField(null=True, blank=True)
    npoints = models.IntegerField(null=True, blank=True)
    ccdphot_filter = models.CharField(max_length=255, null=True, blank=True)
    cpcs_time = models.DateTimeField(null=True, blank=True, editable=False)
    start_time = models.DateTimeField(null=True, blank=True, editable=False)
    filter = models.CharField(max_length=255, null=True, blank=True)
    matchDist = models.CharField(max_length=10, choices=MATCHING_RADIUS, default='2 arcsec',
                                 verbose_name='Matching radius')
    allow_upload = models.BooleanField(verbose_name='Dry Run (no data will be stored in the database)')

class Catalogs(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.TextField(blank=False, editable=False)
    filters = ArrayField(models.CharField(max_length=10))

class Comments(models.Model):
    comments_id = models.AutoField(db_index=True, primary_key=True)
    dataproduct_id = models.IntegerField(null=False, blank=False)
    comments = models.TextField()
