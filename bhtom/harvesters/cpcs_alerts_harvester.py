import json
import logging
import os
from typing import Optional

import mechanize
import numpy as np
from astropy.time import Time, TimezoneInfo
from tom_dataproducts.models import ReducedDatum
from django.conf import settings

from .utils.last_jd import update_last_jd
from ..models import ReducedDatumExtraData, refresh_reduced_data_view
from ..utils.observation_data_extra_data_utils import ObservationDatapointExtraData

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

cpcs_base_url = settings.CPCS_BASE_URL

logger = logging.getLogger(__name__)

def update_cpcs_lc(target):
    try:
        cpcs_name: Optional[str] = target.targetextra_set.get(key='calib_server_name').value
    except:
        cpcs_name: Optional[str] = None
        logger.error(f'Error while accessing calib_server_name for {target}: {e}')
    if cpcs_name:
        logger.debug("Starting CPCS update for ", cpcs_name)
        nam = cpcs_name[6:]  # removing ivo://
        br = mechanize.Browser()
        br.open(cpcs_base_url)
        req = br.click_link(text='Login')
        br.open(req)
        br.select_form(nr=0)
        br.form['hashtag'] = CPCS_DATA_ACCESS_HASHTAG
        br.submit()

        try:
            page = br.open(f'{cpcs_base_url}/get_alert_lc_data?alert_name=ivo://%s' % nam)
            pagetext = page.read()
            data1 = json.loads(pagetext)
            if len(set(data1["filter"]) & set(
                    ['u', 'B', 'g', 'V', 'B2pg', 'r', 'R', 'R1pg', 'i', 'I', 'Ipg', 'z'])) > 0:
                # fup=[data1["mjd"],data1["mag"],data1["magerr"],data1["filter"],data1["observatory"]]
                logger.info('%s: follow-up data on CPCS found', target)
            else:
                logger.info('DEBUG: no CPCS follow-up for %s', target)

            ## ascii for single filter:
            datajson = data1

            mjd0 = np.array(datajson['mjd'])
            mag0 = np.array(datajson['mag'])
            magerr0 = np.array(datajson['magerr'])
            filter0 = np.array(datajson['filter'])
            catalog0 = np.array(datajson['catalog'])  # filter+catalog is the full info
            caliberr0 = np.array(datajson['caliberr'])
            obs0 = np.array(datajson['observatory'])
            id0 = np.array(datajson['id'])
            # filtering out observations which are limits (flagged with error=-1 in CPCS)
            w = np.where((magerr0 != -1))

            jd = mjd0[w] + 2400000.5
            mag = mag0[w]
            magerr = np.sqrt(magerr0[w] * magerr0[w] + caliberr0[w] * caliberr0[w])  # adding calibration err in quad
            filter = filter0[w]
            obs = obs0[w]
            catalog = catalog0[w]
            ids = id0[w]

            for i in reversed(range(len(mag))):
                try:
                    datum_mag = float(mag[i])
                    datum_jd = Time(float(jd[i]), format='jd', scale='utc')
                    datum_f = filter[i] + "(" + catalog[i] + ")"
                    datum_err = float(magerr[i])
                    datum_source = obs[i]
                    sourcelink = (f'{cpcs_base_url}/get_alert_lc_data?alert_name=ivo://%s' % nam) + "&" + str(
                        ids[i])
                    observer = obs[i]

                    value = {
                        'magnitude': datum_mag,
                        'filter': datum_f,
                        'error': datum_err,
                        'jd': datum_jd.jd
                    }
                    rd, created = ReducedDatum.objects.get_or_create(
                        timestamp=datum_jd.to_datetime(timezone=TimezoneInfo()),
                        value=json.dumps(value),
                        source_name="CPCS",
                        source_location=sourcelink,
                        data_type='photometry',
                        target=target)
                    rd.save()
                    rd_extra_data, _ = ReducedDatumExtraData.objects.update_or_create(
                        reduced_datum=rd,
                        defaults={'extra_data': ObservationDatapointExtraData(facility_name=observer,
                                                                              owner=observer).to_json_str()
                                  }
                    )
                except:
                    print("FAILED storing (CPCS)")

            refresh_reduced_data_view()

            # Updating the last observation JD
            jdlast = np.max(np.array(jd).astype(np.float))

            update_last_jd(target,
                           jdmax=jdlast)
        except Exception as e:
            logger.error("Error reading CPCS, target ", cpcs_name, " probably not on CPCS", e)
