import time

from background_task import background, tasks
import requests

from bhtom.models import BHTomFits, Instrument, BHTomCpcsTaskAsynch
from settings import settings
import json
import logging

logger = logging.getLogger(__name__)


@background(queue='cpcs_file_queue')
def add_task_to_cpcs_queue(instanceID):
    url_cpcs = settings.CPCS_BASE_URL + 'upload'

    try:
        instance = BHTomCpcsTaskAsynch.objects.get(id=instanceID)
        fits = BHTomFits.objects.get(file_id=instance.bhtomFits_id)
        instrument = Instrument.objects.get(id=fits.instrument_id.id)
    except Exception as e:
        logger.error('instanceID: ' + str(instanceID) + ', ' + str(e))
        raise Exception(str(e))

    if instance.status == 'TODO':
        instance.status = 'IN_PROGRESS'
        instance.save()

    if instance.status == 'IN_PROGRESS':

        try:
            logger.info('Start processing file: ' + str(instanceID))
            with open(format(instance.url), 'rb') as file:

                response = requests.post(url_cpcs,
                                         {'MJD': fits.mjd, 'EventID': instance.target, 'expTime': fits.expTime,
                                          'matchDist': fits.matchDist, 'dryRun': int(fits.allow_upload),
                                          'forceFilter': fits.filter,
                                          'fits_id': fits.file_id,
                                          'hashtag': instrument.hashtag,
                                          'outputFormat': 'json'}, files={'sexCat': file})

                if response.status_code == 201 or response.status_code == 200:

                    json_data = json.loads(response.text)
                    fits.status = 'F'
                    fits.status_message = 'Finished'
                    fits.cpcs_plot = json_data['image_link']
                    fits.mag = json_data['mag']
                    fits.mag_err = json_data['mag_err']
                    fits.ra = json_data['ra']
                    fits.dec = json_data['dec']
                    fits.zeropoint = json_data['zeropoint']
                    fits.outlier_fraction = json_data['outlier_fraction']
                    fits.scatter = json_data['scatter']
                    fits.npoints = json_data['npoints']
                    fits.followupId = json_data['followup_id']
                    fits.cpsc_filter = json_data['filter']
                    fits.survey = json_data['survey']
                    fits.save()

                    instance.status = 'SUCCESS'
                    instance.save()

                    logger.info('Response status from cpcs: success, mag: ' + str(fits.mag) + ', mag_err: ' + str(
                        fits.mag_err) + 'ra: ' + str(fits.ra)
                                + ', dec:' + str(fits.dec) + ', zeropoint: ' + str(fits.zeropoint)
                                + ', npoints: ' + str(fits.npoints) + ', scatter: ' + str(fits.scatter))
                else:

                    logger.info('Response status from cpcs: error, number of tries: ' + str(instance.number_tries))

                    if len(response.content.decode()) > 100:
                        if instance.number_tries > 1:
                            instance.status = 'FAILED'
                            instance.save()
                            fits.status_message = 'Cpcs error'
                            fits.status = 'E'
                            fits.save()
                        else:
                            instance.number_tries += 1
                            instance.save()

                            # czekamy 10 sekund na ponowne wyslanie
                            time.sleep(10)
                            add_task_to_cpcs_queue(instance.id)
                    else:
                        fits.status_message = 'Cpcs error: %s' % response.content.decode()
                        fits.status = 'E'
                        fits.save()
                        instance.status = 'FAILED'
                        instance.save()

        except Exception as e:
            logger.error('send_to_cpcs error: ' + str(e))
            fits.status = 'E'
            fits.status_message = 'Error: %s' % str(e)
            fits.save()
            instance.status = 'FAILED'
            instance.save()
