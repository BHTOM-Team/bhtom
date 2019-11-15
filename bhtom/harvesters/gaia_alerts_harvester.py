from tom_catalogs.harvester import AbstractHarvester

import os
import requests
import json
from collections import OrderedDict

from tom_targets.models import Target, TargetExtra
#from tom_targets.templatetags.targets_extras import target_extra_field

from decimal import Decimal
from astropy.time import Time, TimezoneInfo
from tom_dataproducts.models import ReducedDatum

base_url = 'http://gsaweb.ast.cam.ac.uk/alerts'

##queries alerts.csv and searches for the name 
#then also loads the light curve
def get(term):
    alertindex_url = f'{base_url}/alerts.csv'

    gaiaresponse = requests.get(alertindex_url)
    gaiadata = gaiaresponse._content.decode('utf-8').split('\n')[1:-1]

    for alert in gaiadata:
        gaia_name = alert.split(',')[0]
        ra = Decimal(alert.split(',')[2])
        dec = Decimal(alert.split(',')[3])
        disc = alert.split(',')[1]
        classif = alert.split(',')[7]

        if (term.lower() in gaia_name.lower()): #case insensitive
            ##alert found, now getting the light curve

            #creating a target object
            target = Target()
            target.type = 'SIDEREAL'

            target.name = gaia_name
            target.ra = ra
            target.dec = dec
            target.epoch = 2000

            #extra fields:
#            target_extra_field(target=target, name='gaia_name')
            # TargetExtra.objects.filter(target=target, key='gaia_name')[0].value = gaia_name
            # TargetExtra.objects.filter(target=target, key='gaia_name')[0].save()
        
            target.gaia_name = gaia_name 
            target.discovery_date = disc#Time(disc, format='iso', scale='utc')
            target.classification = classif
            

            print("SUCCESSFULL created ",gaia_name)
            return target


class GaiaAlertsHarvester(AbstractHarvester):
    name = 'Gaia Alerts'

    def query(self, term):
        self.catalog_data = get(term)

    def to_target(self):
        target = self.catalog_data
        return target


#reads light curve from Gaia Alerts - NOT USED YET
def update_gaia_lc(target, gaia_name):
        lightcurve_url = f'{base_url}/alert/{gaia_name}/lightcurve.csv'
        response = requests.get(lightcurve_url)
        data = response._content.decode('utf-8').split('\n')[2:-2]
#        print("DEBUG UPDATE GAIA LC:", gaia_name, data)

        jdmax = 0
        for obs in data:
 #           print(obs.split(','))
            try: #try avoids 'nulls' and 'untrusted' in mag
                jdstr = (obs.split(',')[1])
                magstr = obs.split(',')[2]
                if (float(jdstr)>jdmax): jdmax = float(jdstr)
                # datum_mag = Decimal(magstr)
                # datum_jd = Time(Decimal(jdstr), format='jd', scale='utc')

                datum_mag = float(Decimal(magstr))
                datum_jd = Time((jdstr), scale='utc')
                value = {
                'magnitude': datum_mag,
                'filter': 'G_Gaia',
                'error': 0 # for now
                }

                rd, created = ReducedDatum.objects.get_or_create(
                timestamp=datum_jd.to_datetime(timezone=TimezoneInfo()),
                value=json.dumps(value),
                source_name=target.name,
                source_location=lightcurve_url,
                data_type='photometry',
                target=target)
                rd.save()
            except:
                pass
        print("finished updating "+gaia_name)

        #Updating/storing the last JD
        jdlast = jdmax
        
        previousjd_object = TargetExtra.objects.filter(target=target, key='jdlastobs')

        if (len(previousjd_object)>0):
            pp = previousjd_object[0]
            jj = float(pp.value)
            print("DEBUG-Gaia prev= ", jj, " this= ",jdlast)
            if (jj<jdlast) :
                print("DEBUG saving new jdlast.")
                try:
                    pp.value = jdlast
                    pp.save()
                except:
                    print("FAILED save jdlastobs (Gaia)")

