import logging
from django_cron import CronJobBase, Schedule
from tom_targets.models import Target
from django.core.management import call_command
from astropy import units as u
from astropy.coordinates import get_sun, SkyCoord
from astropy.time import Time, TimezoneInfo
from datetime import datetime
from decimal import Decimal


logger: logging.Logger = logging.getLogger(__name__)


class UpdateAllLightcurvesJob(CronJobBase):
    RUN_EVERY_MINS = 2 * 60

    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = 'update_all'

    def do(self):
        logger.info('[UPDATE ALL LIGHTCURVES JOB] Updating...')

        #SUN's position now:
        sun_pos = get_sun(Time(datetime.utcnow()))

        for target in Target.objects.all():
            # updating SUN separation
            obj_pos = SkyCoord(target.ra, target.dec, unit=u.deg)
            Sun_sep = sun_pos.separation(obj_pos).deg
            target.save(extras={'Sun_separation': Sun_sep})
            print("DEBUG: new Sun separation: ", Sun_sep, ' for target ',target.name)

            target_id = target.id
            logger.info(f'[UPDATE ALL LIGHTCURVES JOB] Updating target with id {target_id}...')
            try:
                call_command('updatereduceddata_gaia', target_id=target_id)
                call_command('updatereduceddata_aavso', target_id=target_id)
                call_command('update_reduced_data_ztf', target_id=target_id)
                call_command('update_reduced_data_cpcs', target_id=target_id)
            except Exception as e:
                logger.error(f'[UPDATE ALL LIGHTCURVES JOB] Error while updating target with id {target_id}...')
