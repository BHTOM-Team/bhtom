import os
import requests
import logging
import uuid
from .models import BHTomFits, Cpcs_user
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

try:
    from bhtom import local_settings as secret
except ImportError:
    pass

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIRequestFactory, APITestCase, APIClient
from django.http import HttpResponse, HttpResponseNotFound
from astropy.time import Time, TimezoneInfo
from tom_dataproducts.models import ReducedDatum
import json
from tom_targets.templatetags.targets_extras import target_extra_field
from requests_oauthlib import OAuth1
from astropy.coordinates import SkyCoord
from astropy import units as u
import mechanize
import numpy as np
from tom_targets.models import Target, TargetExtra
from datetime import datetime

logger = logging.getLogger(__name__)

def target_post_save(target, created):
    def get(objectId):  #gets mars data for ZTF objects
        url = 'https://mars.lco.global/'
        request = {'queries':
        [
            {'objectId': objectId}
        ]
        }

        try:
            r = requests.post(url, json=request)
            results = r.json()['results'][0]['results']
            return results
        except Exception as e:
            return [None,'Error message : \n'+str(e)]

    logger.info('Target post save hook: %s created: %s', target, created)
  ### how to pass those variables from settings?
    try:
        from bhtom import local_settings as secret
    except ImportError:
        pass
    try:
        TWITTER_APIKEY = secret.TWITTER_APIKEY
        TWITTER_SECRET = secret.TWITTER_SECRET
        TWITTER_ACCESSTOKEN = secret.TWITTER_ACCESSTOKEN
        TWITTER_ACCESSSECRET = secret.TWITTER_ACCESSSECRET
        CPCS_DATA_ACCESS_HASHTAG = secret.CPCS_DATA_ACCESS_HASHTAG
    except:
        TWITTER_APIKEY = os.environ['TWITTER_APIKEY']
        TWITTER_SECRET = os.environ['TWITTER_SECRET']
        TWITTER_ACCESSTOKEN = os.environ['TWITTER_ACCESSTOKEN']
        TWITTER_ACCESSSECRET = os.environ['TWITTER_ACCESSSECRET']
        CPCS_DATA_ACCESS_HASHTAG = os.environ['CPCS_DATA_ACCESS_HASHTAG']

    ####
    # if target_extra_field(target=target, name='tweet'):
    #     #Post to Twitter!
    #     twitter_url = 'https://api.twitter.com/1.1/statuses/update.json'

    #     api_key = TWITTER_APIKEY
    #     api_secret = TWITTER_SECRET
    #     access_token = TWITTER_ACCESSTOKEN
    #     access_secret = TWITTER_ACCESSSECRET
    #     auth = OAuth1(api_key, api_secret, access_token, access_secret)

    #     coords = SkyCoord(target.ra, target.dec, unit=u.deg)
    #     coords = coords.to_string('hmsdms', sep=':',precision=1,alwayssign=True)

        # #Explosion emoji
        # tweet = ''.join([u'\U0001F4A5 New target alert! \U0001F4A5\n',
        #     'Name: {name}\n'.format(name=target.name),
        #     'Coordinates: {coords}\n'.format(coords=coords)])
        # status = {
        #         'status': tweet
        # }

        # response = requests.post(twitter_url, params=status, auth=auth)
#     ztf_name=''  ###WORKAROUND of an error in creation of targets
#     try: 
#         ztf_name = target.targetextra_set.get(key='ztf_alert_name').value
#     except:
#         pass

#     if (ztf_name!=''):
#         alerts = get(ztf_name)

#         filters = {1: 'g_ZTF', 2: 'r_ZTF', 3: 'i_ZTF'}
#         jdarr = []
#         for alert in alerts:
#             if all([key in alert['candidate'] for key in ['jd', 'magpsf', 'fid', 'sigmapsf', 'magnr', 'sigmagnr']]):
#                 jd = Time(alert['candidate']['jd'], format='jd', scale='utc')
#                 jdarr.append(jd.jd)
#                 jd.to_datetime(timezone=TimezoneInfo())

#                 #adding reference flux to the difference psf flux
#                 zp=30.0
#                 m=alert['candidate']['magpsf']
#                 r=alert['candidate']['magnr']
#                 f=10**(-0.4*(m-zp))+10**(-0.4*(r-zp))
#                 mag = zp-2.5*np.log10(f)

#                 er=alert['candidate']['sigmagnr']
#                 em=alert['candidate']['sigmapsf']
#                 emag=np.sqrt(er**2+em**2)

#                 value = {
#                     'magnitude': mag,
#                     'filter': filters[alert['candidate']['fid']],
#                     'error': emag
#                 }
#                 rd, created = ReducedDatum.objects.get_or_create(
#                     timestamp=jd.to_datetime(timezone=TimezoneInfo()),
#                     value=json.dumps(value),
#                     source_name=target.name,
#                     source_location=alert['lco_id'],
#                     data_type='photometry',
#                     target=target)
#                 rd.save()

#         jdlast = np.array(jdarr).max()

#         #modifying jd of last obs 

#         previousjd=0

#         try:        
#             previousjd = float(target.targetextra_set.get(key='jdlastobs').value)
#             print("DEBUG-ZTF prev= ", previousjd, " this= ",jdlast)
#         except:
#             pass
#         if (jdlast > previousjd) : 
#             target.save(extras={'jdlastobs':jdlast})
#             print("DEBUG saving new jdlast from ZTF: ",jdlast)


#     gaia_name=''  ###WORKAROUND of an error in creation of targets  
#     try: 
#         gaia_name = target.targetextra_set.get(key='gaia_alert_name').value
#     except:
#         pass
#     if (gaia_name!=''):
#         base_url = 'http://gsaweb.ast.cam.ac.uk/alerts/alert'
#         lightcurve_url = f'{base_url}/{gaia_name}/lightcurve.csv'

#         response = requests.get(lightcurve_url)
#         data = response._content.decode('utf-8').split('\n')[2:-2]

        # jd = [x.split(',')[1] for x in data]
        # mag = [x.split(',')[2] for x in data]

        # for i in reversed(range(len(mag))):
        #     try:
        #         datum_mag = float(mag[i])
        #         datum_jd = Time(float(jd[i]), format='jd', scale='utc')
        #         value = {
        #             'magnitude': datum_mag,
        #             'filter': 'G_Gaia',
        #             'error': 0 # for now
        #         }
        #         rd, created = ReducedDatum.objects.get_or_create(
        #             timestamp=datum_jd.to_datetime(timezone=TimezoneInfo()),
        #             value=json.dumps(value),
        #             source_name=target.name,
        #             source_location=lightcurve_url,
        #             data_type='photometry',
        #             target=target)
        #         rd.save()
        #     except:
        #         pass

#         #Updating/storing the last JD
#         jdlast = np.max(np.array(jd).astype(np.float))

#         #Updating/storing the last JD
#         previousjd=0

#         try:        
#             previousjd = float(target.targetextra_set.get(key='jdlastobs').value)
# #            previousjd = target.jdlastobs
#             print("DEBUG-Gaia prev= ", previousjd, " this= ",jdlast)
#         except:
#             pass
#         if (jdlast > previousjd) : 
#             target.save(extras={'jdlastobs':jdlast})
#             print("DEBUG saving new jdlast from Gaia: ",jdlast)

#     ############## CPCS follow-up server
#     cpcs_name=''  ###WORKAROUND of an error in creation of targets  
#     try: 
#         cpcs_name = target.targetextra_set.get(key='calib_server_name').value
#     except:
#         pass
#     if (cpcs_name!=''):
#         nam = cpcs_name[6:] #removing ivo://
#         br = mechanize.Browser()
#         followuppage=br.open('http://gsaweb.ast.cam.ac.uk/followup/')
#         req=br.click_link(text='Login')
#         br.open(req)
#         br.select_form(nr=0)
#         br.form['hashtag']=CPCS_DATA_ACCESS_HASHTAG
#         br.submit()

#         try:
#             page=br.open('http://gsaweb.ast.cam.ac.uk/followup/get_alert_lc_data?alert_name=ivo:%%2F%%2F%s'%nam)
#             pagetext=page.read()
#             data1=json.loads(pagetext)
#             if len(set(data1["filter"]) & set(['u','B','g','V','B2pg','r','R','R1pg','i','I','Ipg','z']))>0:
#                 fup=[data1["mjd"],data1["mag"],data1["magerr"],data1["filter"],data1["observatory"]] 
#                 logger.info('%s: follow-up data on CPCS found', target)
#             else:
#                 logger.info('DEBUG: no CPCS follow-up for %s', target)


#             ## ascii for single filter:
#             datajson = data1

#             mjd0=np.array(datajson['mjd'])
#             mag0=np.array(datajson['mag'])
#             magerr0=np.array(datajson['magerr'])
#             filter0=np.array(datajson['filter'])
#             caliberr0=np.array(datajson['caliberr'])
#             obs0 = np.array(datajson['observatory'])
#             w=np.where((magerr0 != -1))

#             jd=mjd0[w]+2400000.5
#             mag=mag0[w]
#             magerr=np.sqrt(magerr0[w]*magerr0[w] + caliberr0[w]*caliberr0[w]) #adding calibration err in quad
#             filter=filter0[w]
#             obs=obs0[w]

#             for i in reversed(range(len(mag))):
#                 try:
#                     datum_mag = float(mag[i])
#                     datum_jd = Time(float(jd[i]), format='jd', scale='utc')
#                     datum_f = filter[i]
#                     datum_err = float(magerr[i])
#                     datum_source = obs[i]
#                     value = {
#                         'magnitude': datum_mag,
#                         'filter': datum_f,
#                         'error': datum_err
#                     }
#                     rd, created = ReducedDatum.objects.get_or_create(
#                         timestamp=datum_jd.to_datetime(timezone=TimezoneInfo()),
#                         value=json.dumps(value),
#                         source_name=datum_source,
#                         source_location=page,
#                         data_type='photometry',
#                         target=target)
#                     rd.save()
#                 except:
#                     print("FAILED storing (CPCS)")

#             #Updating the last observation JD
#             jdlast = np.max(np.array(jd).astype(np.float))

#             #Updating/storing the last JD
#             previousjd=0

#             try:        
#                 previousjd = float(target.targetextra_set.get(key='jdlastobs').value)
#     #            previousjd = target.jdlastobs
#                 print("DEBUG-CPCS prev= ", previousjd, " this= ",jdlast)
#             except:
#                 pass
#             if (jdlast > previousjd) : 
#                 target.save(extras={'jdlastobs':jdlast})
#                 print("DEBUG saving new jdlast from CPCS: ",jdlast)
#         except:
#             print("target ",cpcs_name, " not on CPCS")
def data_product_post_upload(dp, observation_instrument, observation_filter):

    url = 'data/' + format(dp)
    logger.info('Running post upload hook for DataProduct: {}'.format(url))

    if dp.data_product_type == 'fits_file' and observation_instrument != None:
        with open(url, 'rb') as file:
            fits_id = uuid.uuid4().hex
            try:
                response = requests.post(secret.CCDPHOTD_URL,  {'job_id': fits_id}, files={'fits_file': file})
                if response.status_code == 201:
                    logger.info('Fits send to ccdphotd')
                    BHTomFits.objects.create(fits_id=fits_id, status='S', user_id=observation_instrument, dataproduct_id=dp.id,
                                                 status_message='Fits send to ccdphotd', filter=observation_filter)

                else:
                    error_message = 'Error  code: %s' % response.status_code
                    logger.info(error_message)
                    BHTomFits.objects.create(fits_id=fits_id, status='E', user_id=observation_instrument, dataproduct_id=dp.id, fits_file=url, status_message=error_message, filter=observation_filter)
            except Exception as e:
                logger.error('error: ' + str(e))
                raise Exception(response.content.decode('utf-8')) from None

def send_to_cpcs(result, fits, eventID):

    logger.info('Send file to cpcs')
    url_cpcs = secret.CPCS_URL + 'upload'

    try:

        response = requests.post(url_cpcs, {'MJD': fits.mjd, 'EventID': eventID, 'expTime':  fits.expTime,
                                            'matchDist': fits.user_id.matchDist, 'dryRun': int(fits.user_id.allow_upload),
                                            'forceFilter': fits.filter, 'hashtag': fits.user_id.cpcs_hashtag}, files={'sexCat': result})

        logger.info(response.content)

        if response.status_code == 201:

            fits.status='F'
            fits.status_message='Finished'
            fits.save()
        else:
            error_message = 'Error: %s' % response.content

            fits.status='E'
            fits.status_message = error_message
            fits.save()

    except Exception as e:
        logger.error('error: ' + str(e))



@receiver(pre_save, sender=Cpcs_user)
def create_cpcs_user_profile(sender, instance, **kwargs):

    #from django.core.mail import send_mail
    #from bhtom import settings

    #send_mail('TEST',
     #         'TEST', settings.EMAIL_HOST_USER, ['arturkrawczyk19@gmail.com'], fail_silently=False)
    logger.info('Create_cpcs_user')
    url_cpcs = secret.CPCS_URL + 'newuser'

    if instance.cpcs_hashtag == None:
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
             #logger.error('error: ' + str(e))
             raise Exception(str(e)) from None
