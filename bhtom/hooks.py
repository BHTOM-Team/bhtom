import os
import requests
import logging
import uuid
from .models import BHTomFits, Cpcs_user
from tom_targets.models import Target
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from datetime import datetime
import json

# from django.core.mail import send_mail
# from settings import settings

try:
    from settings import local_settings as secret
except ImportError:
    pass

logger = logging.getLogger(__name__)

def data_product_post_upload(dp, observation_instrument, observation_filter, MJD, expTime, allow_upload, matchDist):

    url = 'data/' + format(dp)
    logger.info('Running post upload hook for DataProduct: {}'.format(url))

    if observation_instrument != None:
        instrumet = Cpcs_user.objects.get(id=observation_instrument.id)

        if matchDist != '0':
            matching_radius = matchDist
        else:
            matching_radius = instrumet.matchDist

        if instrumet.allow_upload == '0':
            dry_run = '0'
        else:
            dry_run = allow_upload

    if dp.data_product_type == 'fits_file' and observation_instrument != None:
        with open(url, 'rb') as file:
            #fits_id = uuid.uuid4().hex

            try:
                instance = BHTomFits.objects.create(user=observation_instrument, dataproduct_id=dp.id, start_time=datetime.now(),
                                                    filter=observation_filter, allow_upload=dry_run, matchDist=matching_radius,
                                                    )


                response = requests.post(secret.CCDPHOTD_URL,  {'job_id': instance.file_id, 'instrument': instrumet.obsName, 'instrument_prefix': instrumet.prefix}, files={'fits_file': file})
                if response.status_code == 201:
                    instance.status = 'S'
                    instance.status_message = 'Sent to photometry'
                    instance.save()
                else:
                    error_message = 'Error  code: %s' % response.status_code
                    logger.info(error_message)
                    instance.status = 'E'
                    instance.status_message = 'error_message'
                    instance.save()

            except Exception as e:
                logger.error('error: ' + str(e))
                instance.delete()
                raise Exception(str(e))
    if dp.data_product_type == 'photometry_cpcs' and observation_instrument != None and MJD != None and expTime != None:

        target = Target.objects.get(id=dp.target_id)

        instance = BHTomFits.objects.create(status='S', user=observation_instrument, dataproduct_id=dp.id,
                                 status_message='Sent to Calibration', start_time=datetime.now(),
                                 cpcs_time=datetime.now(), filter=observation_filter, photometry_file=url,
                                 mjd=MJD, expTime=expTime, allow_upload=dry_run,
                                 matchDist=matching_radius)

        send_to_cpcs(url, instance, target.extra_fields['calib_server_name'])

def send_to_cpcs(result, fits, eventID):

    url_cpcs = secret.CPCS_URL + 'upload'
    logger.info('Send file to cpcs')

    try:
        with open(format(result), 'rb') as file:

            response = requests.post(url_cpcs, {'MJD': fits.mjd, 'EventID': eventID, 'expTime':  fits.expTime,
                                          'matchDist': fits.user.matchDist, 'dryRun': int(fits.user.allow_upload),
                                          'forceFilter': fits.filter, 'hashtag': fits.user.cpcs_hashtag,
                                            'outputFormat': 'json'}, files={'sexCat': file})

        logger.info(response.content)

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
            fits.save()
        else:
            error_message = 'Error: %s' % response.content

            fits.status='E'
            fits.status_message = error_message
            fits.save()

    except Exception as e:
        logger.error('error: ' + str(e))
        fits.status = 'E'
        fits.status_message = 'Error: %s' % str(e)
        fits.save()

@receiver(pre_save, sender=Cpcs_user)
def create_cpcs_user_profile(sender, instance, **kwargs):

    logger.info('Create_cpcs_user')
    url_cpcs = secret.CPCS_URL + 'newuser'

    #send_mail('TEST', 'TEST', settings.EMAIL_HOST_USER, ['arturkrawczyk19@gmail.com'], fail_silently=False)

    if instance.cpcs_hashtag == None or instance.cpcs_hashtag == '':
        try:

            response = requests.post(url_cpcs,
                                       {'obsName': instance.obsName, 'lon': instance.lon, 'lat': instance.lat,
                                        'allow_upload': int(instance.allow_upload),
                                        'prefix': instance.prefix, 'hashtag': secret.CPCD_Admin_Hashtag})

            if response.status_code == 200:
                instance.cpcs_hashtag = response.content.decode('utf-8').split(': ')[1]
            else:
                raise Exception(response.content.decode('utf-8')) from None

        except Exception as e:
             logger.error('error: ' + str(e))
             return None
             #raise Exception(str(e)) from None

