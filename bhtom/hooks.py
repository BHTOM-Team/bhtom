import logging
import json
import logging
import os
import traceback
import unicodedata
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
from tom_targets.models import Target

from .models import BHTomFits, Instrument, Observatory, BHTomData, BHTomUser, refresh_reduced_data_view, \
    BHTomCpcsTaskAsynch
from .utils.asynch.taskCPCS import add_task_to_cpcs_queue
from .utils.coordinate_utils import fill_galactic_coordinates
from .utils.observation_data_extra_data_utils import ObservationDatapointExtraData, \
    get_comments_extra_info_for_spectroscopy_file, get_comments_extra_info_for_photometry_file, FACILITY_NAME_KEY, \
    OWNER_KEY

try:
    from settings import local_settings as secret
except ImportError:
    secret = None

logger = logging.getLogger(__name__)


def read_secret(secret_key: str, default_value: str = '') -> str:
    return getattr(secret, secret_key, default_value) if secret else default_value


def data_product_post_upload(dp, target, observatory, observation_filter, MJD, expTime, dry_run,
                             matchDist, comment, user, priority, facility_name=None, observer_name=None,
                             hashtag=None):
    url = 'data/' + format(dp)
    logger.info('Running post upload hook for DataProduct: {}'.format(url))
    instance = None

    if observatory is not None:
        try:
            observatory = Observatory.objects.get(id=observatory.id)
            instrument = Instrument.objects.get(observatory_id=observatory.id, user_id=user)

            if matchDist != '0':
                matching_radius = matchDist
            else:
                matching_radius = observatory.matchDist
        except Exception as e:
            logger.error('data_product_post_upload_fits_file error: ' + str(e))


    if dp.data_product_type == 'fits_file' and observatory != None:

        with open(url, 'rb') as file:
            # fits_id = uuid.uuid4().hex
            try:
                instance = BHTomFits.objects.create(instrument_id=instrument, dataproduct_id=dp,
                                                    filter=observation_filter, allow_upload=dry_run,
                                                    start_time=datetime.now(),
                                                    cpcs_time=datetime.now(),
                                                    matchDist=matching_radius, priority=priority,
                                                    comment=comment, data_stored=True)

                response = requests.post(read_secret('CCDPHOTD_URL'),
                                         {'job_id': instance.file_id,
                                          'instrument': observatory.obsName,
                                          'webhook_id': read_secret('CCDPHOTD_WEBHOOK_ID'),
                                          'priority': priority,
                                          'instrument_prefix': observatory.prefix,
                                          'target_name': target.name,
                                          'target_ra': target.ra,
                                          'target_dec': target.dec,
                                          'username': user.username,
                                          'hashtag': hashtag,
                                          'dry_run': dry_run,
                                          'fits_id': instance.file_id},
                                         files={'fits_file': file})
                if response.status_code == 201:
                    logger.info('successfull send to CCDPHOTD, fits id: ' + str(instance.file_id))
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
                traceback.print_exc()
                if instance:
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
    elif dp.data_product_type == 'spectroscopy' \
            or dp.data_product_type == 'photometry' \
            or dp.data_product_type == 'photometry_asassn':
        try:
            if dp.data_product_type == 'spectroscopy':
                if facility_name or observer_name:
                    # If there are information in the comments, then update the DataProduct
                    dp.extra_data = {
                        FACILITY_NAME_KEY: facility_name,
                        OWNER_KEY: observer_name
                    }
                    dp.save(update_fields=["extra_data"])
                    refresh_reduced_data_view()
            elif dp.data_product_type == 'photometry':
                if facility_name or observer_name:
                    dp.extra_data = {
                        FACILITY_NAME_KEY: facility_name,
                        OWNER_KEY: observer_name
                    }
                    dp.save(update_fields=["extra_data"])
                    refresh_reduced_data_view()
            elif dp.data_product_type == 'photometry_asassn':
                # ASAS-SN photometry should have ASAS-SN added as the facility
                dp.extra_data = ObservationDatapointExtraData(facility_name="ASAS-SN", owner="ASAS-SN").to_json_str()
                dp.save(update_fields=["extra_data"])
                refresh_reduced_data_view()
            instance = BHTomData.objects.create(user_id=user, dataproduct_id=dp, comment=comment, data_stored=True)
            logger.info('successful create: ' + str(dp.data_product_type))
        except Exception as e:
            logger.error('data_product_post_upload error: ' + str(e))
            instance.delete()
            raise Exception(str(e))


def send_to_cpcs(result, fits, eventID):
    logger.info('Save file in CPCS asych : ' + str(fits.file_id))

    if eventID == None or eventID == '':
        fits.status = 'E'
        fits.status_message = 'CPCS target name missing or not yet on CPCS'
        fits.save()
        logger.info('CPCS target name missing or not yet on CPCS')
    else:
        try:
            instance = BHTomCpcsTaskAsynch.objects.create(bhtomFits=fits, url=result, target=eventID,
                                                      data_send=datetime.now(), data_created=datetime.now(),
                                                      number_tries=1)
            add_task_to_cpcs_queue(instance.id)
        except Exception as e:
            logger.error('Save file %s error:  %s', str(fits.file_id), str(e))




@receiver(pre_save, sender=Instrument)
def create_cpcs_user_profile(sender, instance, **kwargs):
    url_cpcs = settings.CPCS_BASE_URL + 'newuser'
    observatory = Observatory.objects.get(id=instance.observatory_id.id)

    if instance.hashtag == None or instance.hashtag == '' and observatory.cpcsOnly == False:
        try:
            obsName = observatory.obsName + ', ' + instance.user_id.first_name + ' ' + instance.user_id.last_name
            obsName = unicodedata.normalize('NFD', obsName).encode('ascii', 'ignore')

            response = requests.post(url_cpcs,
                                     {'obsName': obsName, 'lon': observatory.lon, 'lat': observatory.lat,
                                      'allow_upload': 1,
                                      'prefix': read_secret('CPCS_PREFIX_HASTAG') + observatory.prefix + '_' + str(
                                          instance.user_id) + '_',
                                      'hashtag': 'ac643e2c196e144ef7758d5d225735f2'})
            #
            if response.status_code == 200:
                instance.hashtag = response.content.decode('utf-8').split(': ')[1]
                logger.info('Create_cpcs_user' + str(obsName))

                try:
                    send_mail('Wygenerowano hastag',
                          read_secret('EMAILTEXT_CREATE_HASTAG') + str(observatory.obsName) + ', ' + str(
                              instance.user_id),
                          settings.EMAIL_HOST_USER, read_secret('RECIPIENTEMAIL'), fail_silently=False)
                except Exception as e:
                    logger.error(str(e))
            else:
                logger.error('Error from hastag' + str(obsName))

                try:
                    send_mail('Blad przy generowaniu hastagu',
                          read_secret('EMAILTEXT_ERROR_CREATE_HASTAG') + str(observatory.obsName) + ', ' + str(
                              instance.user_id),
                          settings.EMAIL_HOST_USER, read_secret('RECIPIENTEMAIL'), fail_silently=False)
                except Exception as e:
                    logger.error(str(e))

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
    logger.info('Delete in cpcs: %s', str(instance.data))
    url_cpcs = settings.CPCS_BASE_URL + 'delpoint'
    fit = BHTomFits.objects.get(dataproduct_id=instance)

    try:
        response = requests.post(url_cpcs, {'followupid': fit.followupId,
                                            'hashtag': Instrument.objects.get(id=fit.instrument_id.id).hashtag,
                                            'outputFormat': 'json'})

        if response.status_code == 201 or response.status_code == 200:
            logger.info('Successfully deleted ')
        else:
            error_message = 'Cpcs error: %s' % str(response.content.decode())
            logger.info(error_message)
    except Exception as e:
        logger.error('delete_point_cpcs error: ' + str(e))


@receiver(post_save, sender=BHTomFits)
def BHTomFits_pre_save(sender, instance, **kwargs):
    time_threshold = timezone.now() - timedelta(days=float(read_secret('DAYS_DELETE_FILES', '1')))
    fits = BHTomFits.objects.filter(start_time__lte=time_threshold).exclude(data_stored=False)[:10]

    BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    url_base = BASE + '/data/'

    try:
        for fit in fits:
            data = DataProduct.objects.get(id=fit.dataproduct_id.id)
            if data:
                url_result = os.path.join(url_base, str(data.data))
                if os.path.exists(url_result) and data.data is not None:
                    os.remove(url_result)
                    fit.data_stored = False
                    fit.save()
                    logger.info('remove fits: ' + str(data.data))
                elif data.data is not None and fit.data_stored:
                    fit.data_stored = False
                    fit.save()
                    logger.info('file not exist, change data_stored=false, fits: ' + str(data.data))
    except Exception as e:
        logger.info("Error with remove fits, dataproduct_id: " + format(fits.dataproduct_id))
        logger.info(e)

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
                try:
                    send_mail(read_secret('EMAILTET_ACTIVATEUSER_TITLE'), read_secret('EMAILTET_ACTIVATEUSER'),
                          settings.EMAIL_HOST_USER, [user_email.email], fail_silently=False)
                    logger.info('Ativate user, Send mail: ' + str(user_email.email))
                except Exception as e:
                    logging.error(str(e))


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

            if user_email is not None:
                try:
                    send_mail(read_secret('EMAILTEXT_ACTIVATEOBSERVATORY_TITLE'),
                          read_secret('EMAILTEXT_ACTIVATEOBSERVATORY'),
                          settings.EMAIL_HOST_USER, [user_email.email], fail_silently=False)
                    logger.info('Ativate observatory' + instance.obsName + ', Send mail: ' + user_email.email)
                except Exception as e:
                    logger.error(str(e))


def create_target_in_cpcs(user, instance):
    logger.info('Create target in cpcs: %s', str(instance.extra_fields['calib_server_name']))
    url_cpcs = settings.CPCS_BASE_URL + 'newevent'
    try:
        hastag = Instrument.objects.filter(user_id=user.id).exclude(hashtag__isnull=True).first().hashtag
        url = read_secret('url') + 'bhlist/' + str(instance.id) + '/'

        if hastag is not None and hastag != '' and instance.extra_fields['calib_server_name'] != '':

            response = requests.post(url_cpcs, {'EventID': instance.extra_fields['calib_server_name'],
                                                'ra': instance.ra, 'dec': instance.dec,
                                                'hashtag': hastag, 'url': url,
                                                'outputFormat': 'json'})

            if response.status_code == 201 or response.status_code == 200:
                logger.info('Successfully created target, user: %s' % str(user))
            else:
                error_message = 'Cpcs error: %s' % str(response.content.decode())
                logger.info(error_message)
        else:
            logger.info('Hastag or calib_server_name is none')
    except Exception as e:
        logger.error('Create_target_in_cpcs error: ' + str(e))
