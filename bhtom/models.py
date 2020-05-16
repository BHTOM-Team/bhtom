from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField

class obsInfo(models.Model):
    id = models.IntegerField(primary_key=True)
    obsInfo = models.TextField(default='obsInfo', null=False, blank=False, editable=False)

class Cpcs_user(models.Model):

    MATCHING_RADIUS = {
        ('1', '1 arcsec'),
        ('2', '2 arcsec'),
        ('4', '4 arcsec'),
        ('6', '6 arcsec')
    }

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    obsName = models.CharField(max_length=255, verbose_name='Observatory name', unique=True)
    cpcs_hashtag = models.CharField(max_length=255, editable=True, null=False,  blank=False)
    lon = models.FloatField(null=False, blank=False, verbose_name='Longitude')
    lat = models.FloatField(null=False, blank=False, verbose_name='Latitude')
    prefix = models.CharField(max_length=255, null=True, blank=True)
    user_activation = models.BooleanField()
    matchDist = models.CharField(max_length=10, choices=MATCHING_RADIUS, default='1 arcsec', verbose_name='Matching radius')
    allow_upload = models.BooleanField(verbose_name='Dry Run (no data will be stored in the database)')
    fits = models.FileField(upload_to='user_fits', null=False, blank=False, verbose_name='Sample fits')

    #obsInfo = models.ForeignKey(obsInfo, on_delete=models.CASCADE)

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
    user = models.ForeignKey(Cpcs_user, on_delete=models.CASCADE)
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
    cpcs_hashtag = models.CharField(max_length=255, editable=False, null=True,  blank=True)

class Catalogs(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.TextField(blank=False, editable=False)
    filters = ArrayField(models.CharField(max_length=10))



