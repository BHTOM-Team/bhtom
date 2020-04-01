from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField


class BHEvent(models.Model):

    name = models.CharField(
        max_length=100, default='', verbose_name='Name', help_text='The name of the target, e.g. Gaia17bts or ASASSN-16oe'
    )

    gaia_alert_name = models.CharField(
        max_length=100, default='', verbose_name='Gaia Alert', help_text='Name in Gaia Alerts, if available'
    )

    ztf_alert_name = models.CharField(
        max_length=100, default='', verbose_name='ZTF Alert', help_text='Name in ZTF Alerts, if available'
    )

    calib_server_name = models.CharField(
        max_length=100, default='', verbose_name='Calib.Server name', help_text='Name in the Calibration Server, if available'
    )

    ra = models.FloatField(
        verbose_name='Right Ascension', help_text='Right Ascension, in degrees.'
    )
    dec = models.FloatField(
        verbose_name='Declination', help_text='Declination, in degrees.'
    )

    classification = models.CharField(
        max_length=100, default='', verbose_name='Target classification', help_text='The classification of this target, e.g. Ulens, Be, FUORI',
        blank=True, null=True
    )

    all_phot = models.TextField(
        verbose_name='All photometry', help_text='All photometry',
        null=True, blank=True
    )


    class Meta:
        ordering = ('-id',)
        get_latest_by = ('-name',)

class Cpcs_user(models.Model):

    MATCHING_RADIUS = {
        ('1', '1 arcsec'),
        ('2', '2 arcsec'),
        ('4', '4 arcsec'),
        ('6', '6 arcsec')
    }

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    obsName = models.CharField(max_length=255, verbose_name='Observatory name')
    cpcs_hashtag = models.CharField(max_length=255, editable=True, null=False,  blank=False)
    lon = models.FloatField(null=False, blank=False, verbose_name='Longitude')
    lat = models.FloatField(null=False, blank=False, verbose_name='Latitude')
    prefix = models.CharField(max_length=255, null=True,  blank=True)
    user_activation = models.BooleanField()
    matchDist = models.CharField(max_length=10, choices=MATCHING_RADIUS, default='1 arcsec', verbose_name='Matching radius')
    allow_upload = models.BooleanField(verbose_name='Dry Run (no data will be stored in the database)')
    fits = models.FileField(upload_to='user_fits', null=True, blank=True, verbose_name='Sample fits')


class BHTomFits(models.Model):
    FITS_STATUS = [
        ('C', 'Created'),
        ('S', 'Send_to_ccdphotd'),
        ('I', 'In_progress'),
        ('R', 'Result_from_ccdphotd'),
        ('F', 'Finished'),
        ('E', 'Error'),
        ('U', 'User not active'),
    ]
    fits_id = models.CharField(db_index=True, max_length=50, primary_key=True)
    user_id = models.ForeignKey(Cpcs_user, on_delete=models.CASCADE)
    dataproduct_id = models.IntegerField(null=False, blank=False)
    status = models.CharField(max_length=1, choices=FITS_STATUS, default='C')
    status_message = models.TextField(default='Fits upload', blank=True, editable=False)
    mjd = models.FloatField(null=True, blank=True)
    expTime = models.FloatField(null=True, blank=True)
    ccdphot_result = models.FileField(upload_to='photometry', null=True, blank=True, editable=False)
    cpcs_time = models.DateTimeField(null=True, blank=True, editable=False)
    filter = models.CharField(max_length=255, null=True, blank=True)

class Catalogs(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.TextField(blank=False, editable=False)
    filters = ArrayField(models.CharField(max_length=10))
