from tom_catalogs.harvester import AbstractHarvester

import os
import requests
import json
import logging

from collections import OrderedDict

from tom_targets.models import Target, TargetExtra
#from tom_targets.templatetags.targets_extras import target_extra_field

from decimal import Decimal
from astropy.time import Time, TimezoneInfo
from astropy.coordinates import get_moon, get_sun, SkyCoord, AltAz
from astropy import units as u
from datetime import datetime

from tom_dataproducts.models import ReducedDatum

import mechanize
import numpy as np

### how to pass those variables from settings?
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

base_url = 'http://gsaweb.ast.cam.ac.uk/alerts'

logger = logging.getLogger(__name__)

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

            #extra fields:  DOES NOT WORK      
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



#reads light curve from Gaia Alerts - used in updatereduceddata_gaia
#also reads CPCS and ZTF data here - FIXME: move some day to separate method?
#this also updates the SUN separation
#if update_me == false, only the SUN position gets updated, not the LC

def update_gaia_lc(target, gaia_name):
        ## updating SUN separation
        sun_pos = get_sun(Time(datetime.utcnow()))
        obj_pos = SkyCoord(target.ra, target.dec, unit=u.deg)
        Sun_sep = sun_pos.separation(obj_pos).deg
        target.save(extras={'Sun_separation':Sun_sep})
        print("DEBUG: new Sun separation: ",Sun_sep)
        
        ##deciding whether to update the light curves or not
        dontupdateme="None"
        try:
            dontupdateme = (target.targetextra_set.get(key='dont_update_me').value)
        except:
            pass
        if (dontupdateme=='True'): 
            print("DEBUG: target ",target,' not updated because of dont_update_me = true')
            return 

        ##GAIA LC update
        gaia_name_name=''  ###WORKAROUND of an error in creation of targets  
        try: 
            gaia_name_name = target.targetextra_set.get(key='gaia_alert_name').value
        except:
            pass

        if (gaia_name_name!=''):

            lightcurve_url = f'{base_url}/alert/{gaia_name_name}/lightcurve.csv'
            response = requests.get(lightcurve_url)
            data = response._content.decode('utf-8').split('\n')[2:-2]
            print("DEBUG gaia harvester - UPDATE GAIA LC:", gaia_name_name)

            jdmax = 0
            maglast = 0

            for obs in data:
                #print(obs.split(','))
                try: #try avoids 'nulls' and 'untrusted' in mag
                    jdstr = (obs.split(',')[1])
                    magstr = obs.split(',')[2]
                    if (magstr=="null" or magstr=="untrusted"): continue
                    if (float(jdstr)>jdmax): 
                        jdmax = float(jdstr)
                        maglast = float(magstr)
                    # datum_mag = Decimal(magstr)
                    # datum_jd = Time(Decimal(jdstr), format='jd', scale='utc')

                    datum_mag = float(Decimal(magstr))
                    datum_jd = Time(float(jdstr), format='jd', scale='utc')
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
            print("finished updating "+gaia_name_name)

            #Updating/storing the last JD
            jdlast = jdmax
            previousjd=0

            try:        
                previousjd = float(target.targetextra_set.get(key='jdlastobs').value)
    #            previousjd = target.jdlastobs
#                print("DEBUG-Gaia prev= ", previousjd, " this= ",jdlast)
                target.save(extras={'maglast':maglast})
#                print("DEBUG saving maglast ",maglast)
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

        ############## CPCS follow-up server
        cpcs_name=''  ###WORKAROUND of an error in creation of targets  
        try: 
            cpcs_name = target.targetextra_set.get(key='calib_server_name').value
        except:
            pass
        if (cpcs_name!=''):
            print("DEBUG: starting CPCS data update for ", cpcs_name)
            nam = cpcs_name[6:] #removing ivo://
            br = mechanize.Browser()
            followuppage=br.open('http://gsaweb.ast.cam.ac.uk/followup/')
            req=br.click_link(text='Login')
            br.open(req)
            br.select_form(nr=0)
            br.form['hashtag']=CPCS_DATA_ACCESS_HASHTAG
            br.submit()

            try:
                page=br.open('http://gsaweb.ast.cam.ac.uk/followup/get_alert_lc_data?alert_name=ivo:%%2F%%2F%s'%nam)
                pagetext=page.read()
                data1=json.loads(pagetext)
                if len(set(data1["filter"]) & set(['u','B','g','V','B2pg','r','R','R1pg','i','I','Ipg','z']))>0:
                    #fup=[data1["mjd"],data1["mag"],data1["magerr"],data1["filter"],data1["observatory"]] 
                    logger.info('%s: follow-up data on CPCS found', target)
                else:
                    logger.info('DEBUG: no CPCS follow-up for %s', target)


                ## ascii for single filter:
                datajson = data1

                mjd0=np.array(datajson['mjd'])
                mag0=np.array(datajson['mag'])
                magerr0=np.array(datajson['magerr'])
                filter0=np.array(datajson['filter']) 
                catalog0=np.array(datajson['catalog']) #filter+catalog is the full info
                caliberr0=np.array(datajson['caliberr'])
                obs0 = np.array(datajson['observatory'])
                id0 = np.array(datajson['id'])
                # filtering out observations which are limits (flagged with error=-1 in CPCS)
                w=np.where((magerr0 != -1))

                jd=mjd0[w]+2400000.5
                mag=mag0[w]
                magerr=np.sqrt(magerr0[w]*magerr0[w] + caliberr0[w]*caliberr0[w]) #adding calibration err in quad
                filter=filter0[w]
                obs=obs0[w]
                catalog = catalog0[w]
                ids=id0[w]

                for i in reversed(range(len(mag))):
                    try:
                        datum_mag = float(mag[i])
                        datum_jd = Time(float(jd[i]), format='jd', scale='utc')
                        datum_f = filter[i]+"("+catalog[i]+")"
                        datum_err = float(magerr[i])
                        datum_source = obs[i]
                        sourcelink = ('http://gsaweb.ast.cam.ac.uk/followup/get_alert_lc_data?alert_name=ivo:%%2F%%2F%s'%nam)+"&"+str(ids[i])

                        value = {
                            'magnitude': datum_mag,
                            'filter': datum_f,
                            'error': datum_err
                        }
                        rd, created = ReducedDatum.objects.get_or_create(
                            timestamp=datum_jd.to_datetime(timezone=TimezoneInfo()),
                            value=json.dumps(value),
                            source_name=datum_source,
                            source_location=sourcelink,
                            data_type='photometry',
                            target=target)
                        rd.save()
                    except:
                        print("FAILED storing (CPCS)")
                
                #Updating the last observation JD
                jdlast = np.max(np.array(jd).astype(np.float))

                #Updating/storing the last JD
                previousjd=0

                try:        
                    previousjd = float(target.targetextra_set.get(key='jdlastobs').value)
        #            previousjd = target.jdlastobs
                    print("DEBUG-CPCS prev= ", previousjd, " this= ",jdlast)
                except:
                    pass
                if (jdlast > previousjd) : 
                    target.save(extras={'jdlastobs':jdlast})
                    print("DEBUG saving new jdlast from CPCS: ",jdlast)
            except:
                print("Error reading CPCS, target ",cpcs_name, " probably not on CPCS")

                #############ZTF
        ztf_name=''  ###WORKAROUND of an error in creation of targets  
        try: 
            ztf_name = target.targetextra_set.get(key='ztf_alert_name').value
        except:
            pass

        if (ztf_name!=''):
            alerts = getmars(ztf_name)

            filters = {1: 'g_ZTF', 2: 'r_ZTF', 3: 'i_ZTF'}
            jdarr = []
            for alert in alerts:
                if all([key in alert['candidate'] for key in ['jd', 'magpsf', 'fid', 'sigmapsf', 'magnr', 'sigmagnr']]):
                    jd = Time(alert['candidate']['jd'], format='jd', scale='utc')
                    jdarr.append(jd.jd)
                    jd.to_datetime(timezone=TimezoneInfo())


                    #adding reference flux to the difference psf flux
                    zp=30.0
                    m=alert['candidate']['magpsf']
                    r=alert['candidate']['magnr']
                    f=10**(-0.4*(m-zp))+10**(-0.4*(r-zp))
                    mag = zp-2.5*np.log10(f)

                    er=alert['candidate']['sigmagnr']
                    em=alert['candidate']['sigmapsf']
                    emag=np.sqrt(er**2+em**2)

                    value = {
                        'magnitude': mag,
                        'filter': filters[alert['candidate']['fid']],
                        'error': emag
                    }
                    rd, created = ReducedDatum.objects.get_or_create(
                        timestamp=jd.to_datetime(timezone=TimezoneInfo()),
                        value=json.dumps(value),
                        source_name=target.name,
                        source_location=alert['lco_id'],
                        data_type='photometry',
                        target=target)
                    rd.save()

            jdlast = np.array(jdarr).max()

            #modifying jd of last obs 

            previousjd=0

            try:        
                previousjd = float(target.targetextra_set.get(key='jdlastobs').value)
                print("DEBUG-ZTF prev= ", previousjd, " this= ",jdlast)
            except:
                pass
            if (jdlast > previousjd) : 
                target.save(extras={'jdlastobs':jdlast})
                print("DEBUG saving new jdlast from ZTF: ",jdlast)
        ####


def getmars(objectId):  #gets mars data for ZTF objects
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
