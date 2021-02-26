import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from tom_dataproducts.models import DataProduct
from tom_targets.models import Target, TargetExtra

from .models import BHTomFits, Instrument, Observatory, BHTomData, BHTomUser, ViewReducedDatum
from .utils.coordinate_utils import fill_galactic_coordinates
from .utils.observation_data_extra_data_utils import ObservationDatapointExtraData, \
    get_comments_extra_info_for_spectroscopy_file, get_comments_extra_info_for_photometry_file
from tom_targets.models import Target
from tom_dataproducts.models import DataProduct, ReducedDatum
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from datetime import datetime, timedelta
from django.utils import timezone
import json

from django.core.mail import send_mail
from typing import Optional

try:
    from settings import local_settings as secret
except ImportError:
    pass

logger = logging.getLogger(__name__)


def data_product_post_upload(dp, observatory, observation_filter, MJD, expTime, dry_run, matchDist, comment, user, priority):
    url = 'data/' + format(dp)
    logger.info('Running post upload hook for DataProduct: {}'.format(url))

    if observatory is not None:

        observatory = Observatory.objects.get(id=observatory.id)
        instrument = Instrument.objects.get(observatory_id=observatory.id, user_id=user)

        if matchDist != '0':
            matching_radius = matchDist
        else:
            matching_radius = observatory.matchDist

    if dp.data_product_type == 'fits_file' and observatory != None:

        with open(url, 'rb') as file:
            # fits_id = uuid.uuid4().hex
            try:
                instance = BHTomFits.objects.create(instrument_id=instrument, dataproduct_id=dp,
                                                    start_time=datetime.now(),
                                                    filter=observation_filter, allow_upload=dry_run,
                                                    matchDist=matching_radius, priority=priority,
                                                    comment=comment, data_stored=True)

                response = requests.post(secret.CCDPHOTD_URL,
                                         {'job_id': instance.file_id, 'instrument': observatory.obsName,
                                          'webhook_id': secret.CCDPHOTD_WEBHOOK_ID, 'priority': priority,
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
                logger.error('data_product_post_upload_fits_file error: ' + str(e))
                instance.delete()
                raise Exception(str(e))
    elif dp.data_product_type == 'photometry_cpcs' and observatory != None and MJD != None and expTime != None:

        target = Target.objects.get(id=dp.target_id)
        try:
            instance = BHTomFits.objects.create(status='S', instrument_id=instrument, dataproduct_id=dp,
                                                status_message='Sent to Calibration', start_time=datetime.now(),
                                                cpcs_time=datetime.now(), filter=observation_filter,
                                                photometry_file=format(dp),
                                                mjd=MJD, expTime=expTime, allow_upload=dry_run,
                                                matchDist=matching_radius, data_stored=True)

            send_to_cpcs(url, instance, target.extra_fields['calib_server_name'])

        except Exception as e:
            logger.error('data_product_post_upload-photometry_cpcs error: ' + str(e))
            instance.delete()
            raise Exception(str(e))
    elif dp.data_product_type == 'spectroscopy' or dp.data_product_type == 'photometry':
        try:
            if dp.data_product_type == 'spectroscopy':
                # Check if spectroscopy ASCII file contains facility and observation date in the comments
                extra_data: Optional[ObservationDatapointExtraData] = \
                    get_comments_extra_info_for_spectroscopy_file(dp)
                if extra_data:
                    # If there are information in the comments, then update the DataProduct
                    dp.extra_data = extra_data.to_json_str()
                    dp.save(update_fields=["extra_data"])
            elif dp.data_product_type == 'photometry':
                # Check if spectroscopy ASCII file contains facility and observation date in the comments
                extra_data: Optional[ObservationDatapointExtraData] = \
                    get_comments_extra_info_for_photometry_file(dp)
                if extra_data:
                    # If there are information in the comments, then update the DataProduct
                    dp.extra_data = extra_data.to_json_str()
                    dp.save(update_fields=["extra_data"])

            instance = BHTomData.objects.create(user_id=user, dataproduct_id=dp, comment=comment, data_stored=True)
        except Exception as e:
            logger.error('data_product_post_upload error: ' + str(e))
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

                response = requests.post(url_cpcs, {'MJD': fits.mjd, 'EventID': eventID, 'expTime': fits.expTime,
                                                    'matchDist': fits.matchDist, 'dryRun': int(fits.allow_upload),
                                                    'forceFilter': fits.filter,
                                                    'hashtag': Instrument.objects.get(id=fits.instrument_id.id).hashtag,
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

                logger.info('mag: ' + str(fits.mag) + ', mag_err: ' + str(fits.mag_err) + ' ra: ' + str(fits.ra)
                            + ', dec:' + str(fits.dec) + ', zeropoint: ' + str(fits.zeropoint)
                            + ', npoints: ' + str(fits.npoints) + ', scatter: ' + str(fits.scatter))
            else:

                error_message = 'Cpcs error: %s' % response.content.decode()
                fits.status = 'E'
                fits.status_message = error_message
                fits.save()

    except Exception as e:
        logger.error('send_to_cpcs error: ' + str(e))
        fits.status = 'E'
        fits.status_message = 'Error: %s' % str(e)
        fits.save()


@receiver(pre_save, sender=Instrument)
def create_cpcs_user_profile(sender, instance, **kwargs):
    url_cpcs = secret.CPCS_URL + 'newuser'
    observatory = Observatory.objects.get(id=instance.observatory_id.id)

    if instance.hashtag == None or instance.hashtag == '' and observatory.cpcsOnly == False:
        try:
            obsName = observatory.obsName + ', ' + instance.user_id.first_name + ' ' + instance.user_id.last_name

            response = requests.post(url_cpcs,
                                     {'obsName': obsName, 'lon': observatory.lon, 'lat': observatory.lat,
                                      'allow_upload': 1,
                                      'prefix': secret.CPCS_PREFIX_HASTAG + observatory.prefix + '_' + str(instance.user_id) + '_',
                                      'hashtag': secret.CPCS_Admin_Hashtag})

            if response.status_code == 200:
                instance.hashtag = response.content.decode('utf-8').split(': ')[1]
                logger.info('Create_cpcs_user')
                send_mail('Wygenerowano hastag', secret.EMAILTEXT_CREATE_HASTAG + str(observatory.obsName) + ', ' + str(instance.user_id),
                          settings.EMAIL_HOST_USER, secret.RECIPIENTEMAIL, fail_silently=False)
            else:
                logger.error('Error from hastag')
                send_mail('Blad przy generowaniu hastagu', secret.EMAILTEXT_ERROR_CREATE_HASTAG + str(observatory.obsName)+ ', ' + str(instance.user_id),
                          settings.EMAIL_HOST_USER, secret.RECIPIENTEMAIL, fail_silently=False)

                instance.isActive = False
                raise Exception(response.content.decode('utf-8')) from None

        except Exception as e:
            logger.error('create_cpcs_user_profile error: ' + str(e))
            return None
            # raise Exception(str(e)) from None
    else:
        logger.info('Hastag exist or cpcs Only')


@receiver(pre_save, sender=Target)
def target_pre_save(sender, instance, **kwargs):
    fill_galactic_coordinates(instance)
    logger.info('Target pre save hook: %s', str(instance))


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
        logger.error('delete_point_cpcs error: ' + str(e))


@receiver(post_save, sender=BHTomFits)
def BHTomFits_pre_save(sender, instance, **kwargs):
    time_threshold = timezone.now() - timedelta(days=secret.DAYS_DELETE_FILES)
    fits = BHTomFits.objects.filter(start_time__lte=time_threshold).exclude(data_stored=False)

    BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    url_base = BASE + '/data/'

    for fit in fits:
        data = DataProduct.objects.get(id=fit.dataproduct_id.id)
        if data:
            url_result = os.path.join(url_base, str(data.data))
            if os.path.exists(url_result) and data.data is not None:
                fit.data_stored = False
                fit.save()
                os.remove(url_result)


@receiver(pre_save, sender=BHTomUser)
def BHTomUser_pre_save(sender, instance, **kwargs):
    try:
        bHTomUser_old = BHTomUser.objects.get(id=instance.pk)
    except BHTomUser.DoesNotExist:
        bHTomUser_old = None

    user_email = None
    if bHTomUser_old is not None:
        if bHTomUser_old.is_activate == False and instance.is_activate == True:
            try:
                user_email = User.objects.get(id=instance.user.id)
            except BHTomFits.DoesNotExist:
                user_email = None

            if user_email is not None:
                send_mail(secret.EMAILTET_ACTIVATEUSER_TITLE, secret.EMAILTET_ACTIVATEUSER,
                          settings.EMAIL_HOST_USER, [user_email.email], fail_silently=False)

@receiver(pre_save, sender=Observatory)
def Observatory_pre_save(sender, instance, **kwargs):
    try:
        observatory_old = Observatory.objects.get(id=instance.pk)
    except Observatory.DoesNotExist:
        observatory_old = None

    user_email = None
    if observatory_old is not None:
        if observatory_old.isVerified == False and instance.isVerified == True and instance.user is not None:
            try:
                user_email = User.objects.get(id=instance.user.id)
            except BHTomFits.DoesNotExist:
                user_email = None
            logger.info(user_email.email)
            if user_email is not None:
                send_mail(secret.EMAILTEXT_ACTIVATEOBSERVATORY_TITLE, secret.EMAILTEXT_ACTIVATEOBSERVATORY,
                          settings.EMAIL_HOST_USER, [user_email.email], fail_silently=False)

def create_target_in_cpcs(user, instance):
    logger.info('Create target in cpcs: %s', instance.extra_fields['calib_server_name'])
    url_cpcs = secret.CPCS_URL + 'newevent'
    hastag = None

    try:
        hastag = Instrument.objects.filter(user_id=user.id).exclude(hashtag__isnull=True).first().hashtag
        url = secret.url + 'bhlist/' + str(instance.id) + '/'

        if hastag is not None and hastag != '' and instance.extra_fields['calib_server_name'] != '':

           response = requests.post(url_cpcs, {'EventID': instance.extra_fields['calib_server_name'],
                                                'ra': instance.ra, 'dec': instance.ra,
                                                'hashtag': hastag, 'url': url,
                                                'outputFormat': 'json'})

           if response.status_code == 201 or response.status_code == 200:
               logger.info('Successfully created target, user: %s' %user)
           else:
               error_message = 'Cpcs error: %s' % response.content.decode()
               logger.info(error_message)

    except Exception as e:
        logger.error('Create_target_in_cpcs error: ' + str(e))
