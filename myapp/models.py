from django.db import models

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
