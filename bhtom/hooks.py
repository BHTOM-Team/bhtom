import os
import requests
import logging
import uuid
from .models import BHTomFits, Instrument, Observatory
from .utils.coordinate_utils import fill_galactic_coordinates
from tom_targets.models import Target
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from datetime import datetime
import json

from django.core.mail import send_mail
from settings import settings

try:
    from settings import local_settings as secret
except ImportError:
    pass

logger = logging.getLogger(__name__)

def data_product_post_upload(dp, observatory, observation_filter, MJD, expTime, dry_run, matchDist, comment, user):

    url = 'data/' + format(dp)
    logger.info('Running post upload hook for DataProduct: {}'.format(url))

    if observatory != None:

        observatory = Observatory.objects.get(id=observatory.id)
        instrument = Instrument.objects.get(observatory_id=observatory.id, user_id=user)

        if matchDist != '0':
            matching_radius = matchDist
        else:
            matching_radius = observatory.matchDist

    if dp.data_product_type == 'fits_file' and observatory != None:

        with open(url, 'rb') as file:
            #fits_id = uuid.uuid4().hex
            try:
                instance = BHTomFits.objects.create(instrument_id=instrument, dataproduct_id=dp, start_time=datetime.now(),
                                                    filter=observation_filter, allow_upload=dry_run, matchDist=matching_radius,
                                                    comment=comment)

                response = requests.post(secret.CCDPHOTD_URL,  {'job_id': instance.file_id, 'instrument': observatory.obsName,
                                                                'webhook_id': secret.CCDPHOTD_WEBHOOK_ID,
                                                                'instrument_prefix': observatory.prefix}, files={'fits_file': file})
                if response.status_code == 201:
                    instance.status = 'S'
                    instance.status_message = 'Sent to photometry'
                    instance.save()
                else:
                    error_message = 'CCDPHOTD error: %s' % response.status_code
                    logger.info(error_message)
                    instance.status = 'E'
                    instance.status_message = error_message
                    instance.save()

            except Exception as e:
                logger.error('error: ' + str(e))
                instance.delete()
                raise Exception(str(e))
    elif dp.data_product_type == 'photometry_cpcs' and observatory != None and MJD != None and expTime != None:

        target = Target.objects.get(id=dp.target_id)
        try:
            instance = BHTomFits.objects.create(status='S', instrument_id=instrument, dataproduct_id=dp,
                                     status_message='Sent to Calibration', start_time=datetime.now(),
                                     cpcs_time=datetime.now(), filter=observation_filter, photometry_file=url,
                                     mjd=MJD, expTime=expTime, allow_upload=dry_run,
                                     matchDist=matching_radius)

            send_to_cpcs(url, instance, target.extra_fields['calib_server_name'])

        except Exception as e:
            logger.error('error: ' + str(e))
            instance.delete()
            raise Exception(str(e))
    elif dp.data_product_type == 'spectroscopy' or dp.data_product_type == 'photometry':
        try:
            instance = BHTomData.objects.create(user_id=user, comment=comment)
        except Exception as e:
            logger.error('error: ' + str(e))
            instance.delete()
            raise Exception(str(e))

def send_to_cpcs(result, fits, eventID):

    url_cpcs = secret.CPCS_URL + 'upload'
    logger.info('Send file to cpcs')

    try:
        if eventID == None or eventID == '':
            fits.status = 'E'
            fits.status_message = 'CPCS target name missing or not yet on CPCS'
            fits.save()
        else:
            with open(format(result), 'rb') as file:

                response = requests.post(url_cpcs, {'MJD': fits.mjd, 'EventID': eventID, 'expTime':  fits.expTime,
                                              'matchDist': fits.matchDist, 'dryRun': int(fits.allow_upload),
                                              'forceFilter': fits.filter, 'hashtag': Instrument.objects.get(id=fits.instrument_id.id).hashtag,
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
                fits.save()

                logger.info('mag: ' + str(fits.mag) + ', mag_err: ' + str(fits.mag_err) + ' ra: ' + str(fits.ra)
                            + ', dec:' + str(fits.dec) + ', zeropoint: ' + str(fits.zeropoint)
                            + ', npoints: ' + str(fits.npoints) + ', scatter: ' + str(fits.scatter))
            else:

                error_message = 'Cpcs error: %s' % response.content.decode()
                fits.status='E'
                fits.status_message = error_message
                fits.save()

    except Exception as e:
        logger.error('error: ' + str(e))
        fits.status = 'E'
        fits.status_message = 'Error: %s' % str(e)
        fits.save()

@receiver(pre_save, sender=Instrument)
def create_cpcs_user_profile(sender, instance, **kwargs):

    url_cpcs = secret.CPCS_URL + 'newuser'
    observatory = Observatory.objects.get(id=instance.observatory_id.id)

    if instance.hashtag == None or instance.hashtag == '' and observatory.cpcsOnly == False:
        try:

            response = requests.post(url_cpcs,
                                       {'obsName': observatory.obsName, 'lon': observatory.lon, 'lat': observatory.lat,
                                        'allow_upload': 1,
                                        'prefix': 'dev_bhtom_'+observatory.prefix, 'hashtag': secret.CPCS_Admin_Hashtag})

            if response.status_code == 200:
                instance.hashtag = response.content.decode('utf-8').split(': ')[1]
                logger.info('Create_cpcs_user')
                send_mail('Wygenerowano hastag', secret.EMAILTEXT_CREATE_HASTAG + str(observatory.obsName), settings.EMAIL_HOST_USER, secret.RECIPIENTEMAIL, fail_silently=False)
            else:
                logger.error('Error from hastag')
                send_mail('Error from hastag', secret.EMAILTEXT_ERROR_CREATE_HASTAG + str(observatory.obsName),
                          settings.EMAIL_HOST_USER, secret.RECIPIENTEMAIL, fail_silently=False)

                instance.isActive = False
                raise Exception(response.content.decode('utf-8')) from None

        except Exception as e:
             logger.error('Error: ' + str(e))
             return None
             #raise Exception(str(e)) from None
    else:
        logger.info('Hastag exist or cpcs Only')


@receiver(pre_save, sender=Target)
def target_pre_save(sender, instance, **kwargs):
    fill_galactic_coordinates(instance)
    logger.info('Target pre save hook: %s', str(instance))


def target_post_save(target, created):
    logger.info('Target post save hook: %s created: %s', target, created)

def delete_point_cpcs(instance):

    logger.info('Delete in cpcs: %s', instance.data)
    url_cpcs = secret.CPCS_URL + 'delpoint'
    fit = BHTomFits.objects.get(dataproduct_id=instance)

    try:
        response = requests.post(url_cpcs, {'followupid': fit.followupId,
                                            'hashtag': Instrument.objects.get(id=fit.instrument_id.id).hashtag,
                                            'outputFormat': 'json'})

        if response.status_code == 201 or response.status_code == 200:
            logger.info('Successfully deleted ')
        else:
            error_message = 'Cpcs error: %s' % response.content.decode()
            logger.info(error_message)
    except Exception as e:
        logger.error('error: ' + str(e))
