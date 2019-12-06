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

    catalog_data = {"gaia_name":"",
                    "ra":0.,
                    "dec":0.,
                    "disc":"",
                    "classif":""
                    }

    for alert in gaiadata:
        gaia_name = alert.split(',')[0]

        if (term.lower() in gaia_name.lower()): #case insensitive
            ##alert found, now getting its params
            ra = Decimal(alert.split(',')[2])
            dec = Decimal(alert.split(',')[3])
            disc = alert.split(',')[1]
            classif = alert.split(',')[7]

            catalog_data["gaia_name"] = gaia_name
            catalog_data["ra"] = ra
            catalog_data["dec"] = dec
            catalog_data["disc"] = disc
            catalog_data["classif"] = classif
#            print("DEBUG: found: "+catalog_data["gaia_name"]+" "+catalog_data["disc"])
            break #in case of multiple entries, it will return only the first one

    return catalog_data            

class GaiaAlertsHarvester(AbstractHarvester):
    name = 'Gaia Alerts'

    def query(self, term):
        self.catalog_data = get(term)

    def to_target(self):
        #catalog_data contains now all fields needed to create a target
        target = super().to_target()

        gaia_name = self.catalog_data["gaia_name"]
        ra = self.catalog_data["ra"]
        dec = self.catalog_data["dec"]
        disc = self.catalog_data["disc"]
        classif = self.catalog_data["classif"]
        
        #checking if already in our DB
        try:
            t0 = Target.objects.get(name=gaia_name)                
            print("Target "+gaia_name+" already in the db.")
            return t0
        except:
            pass

        try:
            #creating a target object
            target.type = 'SIDEREAL'
            target.name = gaia_name
            target.ra = ra
            target.dec = dec
            target.epoch = 2000

            #extra fields:        
#            t1 = Target.objects.get(name=gaia_name)
            target.gaia_alert_name=gaia_name
#            target.save(extras={'gaia_alert_name':gaia_name})
            target.jdlastobs = 0.
            target.priority = 0.
            target.classification=classif
            target.discovery_date = disc
            target.ztf_alert_name=''
            target.calib_server_name=''
            target.cadence = 1.
            
#            target.save()
            # target.save(extras={'discovery_date':disc}) #Time(disc, format='iso', scale='utc')
            # target.save(extras={'classification':classif})            
            # #filling other extra fields with empty values
            # target.save(extras={'ztf_alert_name':''})
            # target.save(extras={'calib_server_name':''})
            # target.save(extras={'jdlastobs':0})
            # target.save(extras={'priority':0})

            print("SUCCESSFULL created ",gaia_name)
        except:
            print("ERROR while creating ",gaia_name)

        #now updating the light curve
#        update_gaia_lc(target, gaia_name)

        return target



#reads light curve from Gaia Alerts - NOT USED YET
def update_gaia_lc(target, gaia_name):
        lightcurve_url = f'{base_url}/alert/{gaia_name}/lightcurve.csv'
        response = requests.get(lightcurve_url)
        data = response._content.decode('utf-8').split('\n')[2:-2]
        print("DEBUG UPDATE GAIA LC:", gaia_name)

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
        previousjd=0

        try:        
            previousjd = float(target.targetextra_set.get(key='jdlastobs').value)
#            previousjd = target.jdlastobs
            print("DEBUG-Gaia prev= ", previousjd, " this= ",jdlast)
        except:
            pass
        if (jdlast > previousjd) : 
            target.save(extras={'jdlastobs':jdlast})
            print("DEBUG saving new jdlast ",jdlast)

        # previousjd_object = TargetExtra.objects.filter(target=target, key='jdlastobs')

        # if (len(previousjd_object)>0):
        #     pp = previousjd_object[0]
        #     jj = float(pp.value)
        #     print("DEBUG-Gaia prev= ", jj, " this= ",jdlast)
        #     if (jj<jdlast) :
        #         print("DEBUG saving new jdlast.")
        #         try:
        #             pp.value = jdlast
        #             pp.save()
        #         except:
        #             print("FAILED save jdlastobs (Gaia)")

