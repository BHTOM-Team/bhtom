from datetime import datetime

from astroplan import Observer
from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField
from tom_targets.models import Target
from tom_dataproducts.models import DataProduct, ReducedDatum
from django_pgviews import view as pg


class Observatory(models.Model):
    MATCHING_RADIUS = [
        ('1', '1 arcsec'),
        ('2', '2 arcsec'),
        ('4', '4 arcsec'),
        ('6', '6 arcsec')
    ]

    obsName = models.CharField(max_length=255, verbose_name='Observatory name', unique=True)
    lon = models.FloatField(null=False, blank=False, verbose_name='Longitude (West is positive) [deg]')
    lat = models.FloatField(null=False, blank=False, verbose_name='Latitude (North is positive) [deg]')
    altitude = models.FloatField(null=False, blank=False, default=0.0, verbose_name="Altitude [m]")
    prefix = models.CharField(max_length=255, null=True, blank=True)
    cpcsOnly = models.BooleanField(default='False', verbose_name='Only instrumental photometry file')
    obsInfo = models.FileField(upload_to='ObsInfo', null=True, blank=False, verbose_name='Obs Info')
    fits = models.FileField(upload_to='user_fits', null=False, blank=False, verbose_name='Sample fits')
    matchDist = models.CharField(max_length=10, choices=MATCHING_RADIUS, default='2',
                                 verbose_name='Matching radius')
    comment = models.TextField(null=True, blank=True,
                               verbose_name="Comments (e.g. hyperlink to the observatory website, camera specifications, telescope info)")
    isVerified = models.BooleanField(default='False')
    user = models.ForeignKey(User, models.SET_NULL, blank=True, null=True)

    gain: models.FloatField = models.FloatField(null=False, blank=False,
                                                verbose_name='Gain [e/ADU]', default=2)
    readout_noise: models.FloatField = models.FloatField(null=False, blank=False,
                                                         verbose_name='Readout Noise [e]', default=2)
    binning: models.IntegerField = models.IntegerField(null=False, blank=False, default=1)
    saturation_level: models.FloatField = models.FloatField(null=False, blank=False,
                                                            verbose_name='Saturation Level [ADU]', default=63000)
    pixel_scale: models.FloatField = models.FloatField(null=False, blank=False,
                                                       verbose_name='Pixel Scale [arcseconds/pixel]', default=0.8)
    readout_speed: models.FloatField = models.FloatField(verbose_name='Readout Speed [microseconds/pixel]', default=9999.0)
    pixel_size: models.FloatField = models.FloatField(verbose_name='Pixel size [micrometers]', default=13.5)
    approx_lim_mag: models.FloatField = models.FloatField(verbose_name="Approximate limit magnitude [mag]", default=18.0)
    filters: models.CharField = models.CharField(max_length=100, blank=True,
                                                 verbose_name="Filters (comma-separated list, as they are visible in FITS)",
                                                 default="V,R,I")

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
    MATCHING_RADIUS = [
        ('1', '1 arcsec'),
        ('2', '2 arcsec'),
        ('4', '4 arcsec'),
        ('6', '6 arcsec')
    ]

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
    priority = models.IntegerField(null=True, blank=True, editable=False)

    comment = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = 'BHTomFile'
        verbose_name_plural = "BHTomFiles"


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
    data_stored = models.BooleanField(default='False')
    comment = models.TextField(null=True, blank=True)


class ReducedDatumExtraData(models.Model):
    reduced_datum = models.ForeignKey(ReducedDatum, on_delete=models.CASCADE, primary_key=True)
    extra_data = models.TextField(null=True, blank=True)


class ViewReducedDatum(pg.MaterializedView):
    concurrent_index = 'id'
    sql = """
        SELECT rd.id AS id,
        rd.target_id, rd.data_product_id, rd.data_type, rd.source_name, rd.timestamp, rd.value,
        rdd.extra_data AS rd_extra_data,
        dpobr.extra_data AS dp_extra_data,
        dpobr.obr_facility AS observation_record_facility
        FROM tom_dataproducts_reduceddatum AS rd
            LEFT JOIN bhtom_reduceddatumextradata AS rdd ON rd.id=rdd.reduced_datum_id
            LEFT JOIN (SELECT dp.id AS dp_id, dp.extra_data AS extra_data, obr.facility AS obr_facility
                FROM tom_dataproducts_dataproduct AS dp
                LEFT JOIN tom_observations_observationrecord AS obr ON dp.observation_record_id=obr.id) dpobr
                ON rd.data_product_id=dpobr.dp_id;
        
    """
    id = models.IntegerField(primary_key=True)
    target = models.ForeignKey(Target, null=False, on_delete=models.DO_NOTHING)
    data_product = models.ForeignKey(DataProduct, null=True, on_delete=models.DO_NOTHING)
    data_type = models.CharField(
        max_length=100,
        default=''
    )
    source_name = models.CharField(max_length=100, default='')
    timestamp = models.DateTimeField(null=False, blank=False, default=datetime.now, db_index=True)
    value = models.TextField(null=False, blank=False)
    rd_extra_data = models.TextField(null=True, blank=True)
    dp_extra_data = models.TextField(null=True, blank=True)
    observation_record_facility = models.TextField(null=True, blank=True)


class BHTomCpcsTaskAsynch(models.Model):

    STATUS = [
        ('1', 'TODO'),
        ('2', 'IN_PROGRESS'),
        ('4', 'SUCCESS'),
        ('6', 'FAILED')
    ]
    bhtomFits = models.ForeignKey(BHTomFits, on_delete=models.CASCADE)
    url = models.CharField(max_length=255, null=False)
    status = models.CharField(max_length=20, choices=STATUS, default='TODO')
    target = models.CharField(max_length=64, null=False)
    data_send = models.DateField()
    data_created = models.DateField(null=False, editable=False)
    number_tries = models.IntegerField(null=False)

def refresh_reduced_data_view():
    ViewReducedDatum.refresh(concurrently=True)