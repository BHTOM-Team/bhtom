import json
import logging
import os
from datetime import datetime
from decimal import Decimal
import requests
from astropy import units as u
from astropy.coordinates import get_sun, SkyCoord
from astropy.time import Time, TimezoneInfo
from tom_catalogs.harvester import AbstractHarvester
from tom_dataproducts.models import ReducedDatum
from tom_targets.models import Target

from typing import Optional, Any

### how to pass those variables from settings?
from bhtom.models import ReducedDatumExtraData, refresh_reduced_data_view
from bhtom.utils.observation_data_extra_data_utils import ObservationDatapointExtraData

try:
    from settings import local_settings as secret
except ImportError:
    secret = None
    

def read_secret(secret_key: str, default_value: Any = '') -> str:
    return getattr(secret, secret_key, default_value) if secret else default_value

    
TWITTER_APIKEY = read_secret('TWITTER_APIKEY')
TWITTER_SECRET = read_secret('TWITTER_SECRET')
TWITTER_ACCESSTOKEN = read_secret('TWITTER_ACCESSTOKEN')
TWITTER_ACCESSSECRET = read_secret('TWITTER_ACCESSSECRET')
CPCS_DATA_ACCESS_HASHTAG = read_secret('CPCS_DATA_ACCESS_HASHTAG')

base_url = 'http://gsaweb.ast.cam.ac.uk/alerts'

logger = logging.getLogger(__name__)


# queries alerts.csv and searches for the name
# then also loads the light curve
def get(term):
    alertindex_url = f'{base_url}/alerts.csv'

    gaiaresponse = requests.get(alertindex_url)
    gaiadata = gaiaresponse._content.decode('utf-8').split('\n')[1:-1]

    catalog_data = {"gaia_name": "",
                    "ra": 0.,
                    "dec": 0.,
                    "disc": "",
                    "classif": ""
                    }

    for alert in gaiadata:
        gaia_name = alert.split(',')[0]

        if term.lower() in gaia_name.lower():  # case insensitive
            # alert found, now getting its params
            ra = Decimal(alert.split(',')[2])
            dec = Decimal(alert.split(',')[3])
            disc = alert.split(',')[1]
            classif = alert.split(',')[7]

            catalog_data["gaia_name"] = gaia_name
            catalog_data["ra"] = ra
            catalog_data["dec"] = dec
            catalog_data["disc"] = disc
            catalog_data["classif"] = classif

            logger.debug(f'Found a Gaia Alert for name {gaia_name.lower()}')
            break  # in case of multiple entries, it will return only the first one

    return catalog_data


class GaiaAlertsHarvester(AbstractHarvester):
    name = 'Gaia Alerts'

    def query(self, term):
        self.catalog_data = get(term)

    def to_target(self):
        # catalog_data contains now all fields needed to create a target
        target = super().to_target()

        gaia_name = self.catalog_data["gaia_name"]
        ra = self.catalog_data["ra"]
        dec = self.catalog_data["dec"]
        disc = self.catalog_data["disc"]
        classif = self.catalog_data["classif"]

        # checking if already in our DB
        try:
            t0 = Target.objects.get(name=gaia_name)
            print("Target " + gaia_name + " already in the db.")
            return t0
        except Exception as e:
            logger.error(f'Target {gaia_name} not found in the database.')
            pass

        try:
            # creating a target object
            target.type = 'SIDEREAL'
            target.name = gaia_name
            target.ra = ra
            target.dec = dec
            target.epoch = 2000

            # extra fields:  DOES NOT WORK
            #            t1 = Target.objects.get(name=gaia_name)
            target.gaia_alert_name = gaia_name
            #            target.save(extras={'gaia_alert_name':gaia_name})
            target.jdlastobs = 0.
            target.priority = 0.
            target.classification = classif
            target.discovery_date = disc
            target.ztf_alert_name = ''
            target.calib_server_name = ''
            target.cadence = 1.

            logger.info(f'Successfully created target {gaia_name}')
        except:
            print("ERROR while creating ", gaia_name)

        return target


# reads light curve from Gaia Alerts - used in updatereduceddata_gaia
# this also updates the SUN separation
# if update_me == false, only the SUN position gets updated, not the LC

def update_gaia_lc(target, requesting_user_id):
    from .utils.last_jd import update_last_jd
    # updating SUN separation
    sun_pos = get_sun(Time(datetime.utcnow()))
    obj_pos = SkyCoord(target.ra, target.dec, unit=u.deg)
    Sun_sep = sun_pos.separation(obj_pos).deg
    target.save(extras={'Sun_separation': Sun_sep})
    print("DEBUG: new Sun separation: ", Sun_sep)

    # deciding whether to update the light curves or not
    try:
        dont_update_me: Optional[bool] = target.extra_fields.get('dont_update_me')
    except Exception as e:
        dont_update_me: Optional[bool] = None
        logger.error(f'Exception occured when accessing dont_update_me field for {target}: {e}')

    if dont_update_me:
        logger.debug("Target ", target, ' not updated because of dont_update_me = true')
        return

    try:
        gaia_name_name: Optional[str] = target.extra_fields.get('gaia_alert_name')
    except Exception as e:
        gaia_name_name: Optional[str] = None
        logger.error(f'Exception occured when accessing gaia_alert_name field for {target}: {e}')

    if gaia_name_name:

        lightcurve_url = f'{base_url}/alert/{gaia_name_name}/lightcurve.csv'
        response = requests.get(lightcurve_url)
        data = response._content.decode('utf-8').split('\n')[2:-2]

        logger.debug("Gaia harvester: UPDATE GAIA LC:", gaia_name_name)

        jdmax: float = 0.0
        maglast: float = 0.0

        for obs in data:

            try:  # try avoids 'nulls' and 'untrusted' in mag
                jdstr = obs.split(',')[1]
                magstr = obs.split(',')[2]
                if (magstr == "null" or magstr == "untrusted"): continue
                if (float(jdstr) > jdmax):
                    jdmax = float(jdstr)
                    maglast = float(magstr)

                datum_mag = float(Decimal(magstr))
                datum_jd = Time(float(jdstr), format='jd', scale='utc')
                value = {
                    'magnitude': datum_mag,
                    'filter': 'G_Gaia',
                    'error': 0,  # for now
                    'jd': datum_jd.jd
                }

                rd, created = ReducedDatum.objects.get_or_create(
                    timestamp=datum_jd.to_datetime(timezone=TimezoneInfo()),
                    value=json.dumps(value),
                    source_name='GaiaAlerts',
                    source_location=lightcurve_url,
                    data_type='photometry',
                    target=target)
                rd.save()
                rd_extra_data, _ = ReducedDatumExtraData.objects.update_or_create(
                    reduced_datum=rd,
                    defaults={'extra_data': ObservationDatapointExtraData(facility_name="Gaia",
                                                                          owner="Gaia").to_json_str()
                             }
                )
            except Exception as e:
                logger.error(f'Error while updating LC for target {target}: {e}')

        refresh_reduced_data_view()

        # Updating/storing the last JD
        update_last_jd(target=target,
                       maglast=maglast,
                       jdmax=jdmax)

        logger.info("Finished updating Gaia LC for " + gaia_name_name)
