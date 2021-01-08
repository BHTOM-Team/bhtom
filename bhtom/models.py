from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField
from tom_targets.models import Target
from tom_dataproducts.models import DataProduct, ReducedDatum


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
    cpcsOnly = models.BooleanField(default='False', verbose_name='Only instrumental photometry file')
    obsInfo = models.FileField(upload_to='ObsInfo', null=True, blank=True, verbose_name='Obs Info')
    fits = models.FileField(upload_to='user_fits', null=True, blank=True, verbose_name='Sample fits')
    matchDist = models.CharField(max_length=10, choices=MATCHING_RADIUS, default='1',
                                 verbose_name='Matching radius')
    comment = models.TextField(null=True, blank=True)
    isVerified = models.BooleanField(default='False')

    def __str__(self):
        return self.obsName

    class Meta:
        verbose_name_plural = "Obs info"


class Instrument(models.Model):
    user_id = models.ForeignKey(User, on_delete=models.CASCADE)
    observatory_id = models.ForeignKey(Observatory, on_delete=models.CASCADE)
    hashtag = models.CharField(max_length=255, editable=True, null=False, blank=False)
    isActive = models.BooleanField(default='True')
    comment = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.user_id.username


def photometry_name(instance, filename):
    return '/'.join([Target.objects.get(id=instance.dataproduct_id.target_id).name, 'photometry', filename])


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
    dataproduct_id = models.ForeignKey(DataProduct, on_delete=models.CASCADE)
    status = models.CharField(max_length=1, choices=FITS_STATUS, default='C')
    status_message = models.TextField(default='Fits upload', blank=True, editable=False)
    mjd = models.FloatField(null=True, blank=True)
    expTime = models.FloatField(null=True, blank=True)
    photometry_file = models.FileField(upload_to=photometry_name, null=True, blank=True)
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
    followupId = models.IntegerField(null=True, blank=True)
    data_stored = models.BooleanField(default='False')
    survey = models.CharField(max_length=255, null=True, blank=True)
    cpsc_filter = models.CharField(max_length=10, null=True, blank=True)

    comment = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "BHTomFits"


class Catalogs(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.TextField(blank=False, editable=False)
    filters = ArrayField(models.CharField(max_length=10))


class BHTomUser(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    is_activate = models.BooleanField(default='False')
    latex_name = models.CharField(max_length=255, null=True, blank=True, verbose_name='LaTeX name')
    latex_affiliation = models.CharField(max_length=255, null=True, blank=True, verbose_name='LaTeX affiliation')
    address = models.CharField(max_length=255, null=True, blank=True, verbose_name='Address')
    about_me = models.TextField(null=True, blank=True, verbose_name='About me')


class BHTomData(models.Model):
    user_id = models.ForeignKey(User, on_delete=models.CASCADE)
    dataproduct_id = models.ForeignKey(DataProduct, on_delete=models.CASCADE)
    comment = models.TextField(null=True, blank=True)


class ReducedDatumExtraData(models.Model):
    reduced_datum = models.ForeignKey(ReducedDatum, on_delete=models.CASCADE, primary_key=True)
    extra_data = models.TextField(null=True, blank=True)
