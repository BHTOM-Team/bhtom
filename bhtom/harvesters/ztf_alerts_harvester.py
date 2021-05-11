import json
import logging
import os
from typing import Dict, List, Optional

import numpy as np
import requests
from astropy.time import Time, TimezoneInfo
from tom_dataproducts.models import ReducedDatum

### how to pass those variables from settings?
from bhtom.models import ReducedDatumExtraData, refresh_reduced_data_view
from bhtom.utils.observation_data_extra_data_utils import ObservationDatapointExtraData

# from tom_targets.templatetags.targets_extras import target_extra_field

try:
    from settings import local_settings as secret
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


MARS_URL: str = 'https://mars.lco.global/'
ZTF_OBSERVATORY_NAME: str = 'Palomar'
logger: logging.Logger = logging.getLogger(__name__)
filters: Dict[int, str] = {1: 'g_ZTF', 2: 'r_ZTF', 3: 'i_ZTF'}

# reads light curve from Gaia Alerts - used in updatereduceddata_gaia
# also reads CPCS and ZTF data here - FIXME: move some day to separate method?
# this also updates the SUN separation
# if update_me == false, only the SUN position gets updated, not the LC

def update_ztf_lc(target, requesting_user_id):
    ##deciding whether to update the light curves or not
    dontupdateme = "None"
    try:
        dontupdateme = (target.targetextra_set.get(key='dont_update_me').value)
    except Exception as e:
        print(f'Exception occured when accessing dont_update_me field: {e}')
    if dontupdateme == 'True':
        print("DEBUG: target ", target, ' not updated because of dont_update_me = true')
        return

    try:
        ztf_name: Optional[str] = target.extra_fields.get('ztf_alert_name')
    except Exception as e:
        ztf_name: Optional[str] = None
        logger.error(f'Error while accessing ztf_alert_name for {target}: {e}')

    if ztf_name:
        alerts = getmars(ztf_name)

        jdarr: List[float] = []

        for alert in alerts:
            if all([key in alert['candidate'] for key in ['jd', 'magpsf', 'fid', 'sigmapsf', 'magnr', 'sigmagnr']]):
                jd = Time(alert['candidate']['jd'], format='jd', scale='utc')
                jdarr.append(jd.jd)
                jd.to_datetime(timezone=TimezoneInfo())

                # adding reference flux to the difference psf flux
                zp = 30.0
                m = alert['candidate']['magpsf']
                r = alert['candidate']['magnr']
                f = 10 ** (-0.4 * (m - zp)) + 10 ** (-0.4 * (r - zp))
                mag = zp - 2.5 * np.log10(f)

                er = alert['candidate']['sigmagnr']
                em = alert['candidate']['sigmapsf']
                emag = np.sqrt(er ** 2 + em ** 2)

                value = {
                    'magnitude': mag,
                    'filter': filters[alert['candidate']['fid']],
                    'error': emag,
                    'jd': jd.jd
                }
                rd, created = ReducedDatum.objects.get_or_create(
                    timestamp=jd.to_datetime(timezone=TimezoneInfo()),
                    value=json.dumps(value),
                    source_name='ZTF',
                    source_location=alert['lco_id'],
                    data_type='photometry',
                    target=target)
                rd.save()
                rd_extra_data, _ = ReducedDatumExtraData.objects.update_or_create(
                    reduced_datum=rd,
                    defaults={'extra_data': ObservationDatapointExtraData(facility_name=ZTF_OBSERVATORY_NAME,
                                                                          owner='ZTF').to_json_str()
                             }
                )

        refresh_reduced_data_view()

        if jdarr:
            jdlast = np.array(jdarr).max()

            # modifying jd of last obs

            previousjd = 0

            try:
                previousjd = float(target.targetextra_set.get(key='jdlastobs').value)
                logger.debug("DEBUG-ZTF prev= ", previousjd, " this= ", jdlast)
            except Exception as e:
                logger.error(f'Error while updating last JD for {target}: {e}')
            if (jdlast > previousjd):
                target.save(extras={'jdlastobs': jdlast})
                logger.debug("DEBUG saving new jdlast from ZTF: ", jdlast)


def getmars(objectId: int):  # gets mars data for ZTF objects
    request = {'queries':
        [
            {'objectId': objectId}
        ]
    }

    try:
        r = requests.post(MARS_URL, json=request)
        results = r.json()['results'][0]['results']
        return results
    except Exception as e:
        logger.error(f'Error while getting MARS for target with ID {objectId}: {e}')
        return [None, 'Error message : \n' + str(e)]
