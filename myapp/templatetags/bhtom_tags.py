from plotly import offline
import plotly.graph_objs as go
from django import template

from tom_targets.models import Target
from tom_targets.forms import TargetVisibilityForm
from tom_observations import utils, facility
from tom_dataproducts.models import DataProduct, ReducedDatum, ObservationRecord

from astroplan import Observer, FixedTarget, AtNightConstraint, time_grid_from_range, moon_illumination
import datetime
import json
from astropy.time import Time
from datetime import timedelta

from myapp.models import BHTomFits, Cpcs_user

from astropy import units as u
from astropy.coordinates import get_moon, get_sun, SkyCoord, AltAz
import numpy as np
import time, math

import logging
logger = logging.getLogger(__name__)

register = template.Library()

@register.inclusion_tag('bhtom/airmass_collapse.html')
def airmass_collapse(target):
    interval = 30 #min
    airmass_limit = 3.0

    obj = Target
    obj.ra = target.ra
    obj.dec = target.dec
    obj.epoch = 2000
    obj.type = 'SIDEREAL' 

    plot_data = get_24hr_airmass(obj, interval, airmass_limit)
    layout = go.Layout(
        yaxis=dict(range=[airmass_limit,1.0]),
        margin=dict(l=20,r=10,b=30,t=40),
        hovermode='closest',
        width=250,
        height=200,
        showlegend=False
    )
    visibility_graph = offline.plot(
        go.Figure(data=plot_data, layout=layout), output_type='div', show_link=False
    )
    return {
        'target': target,
        'figure': visibility_graph
    }

@register.inclusion_tag('bhtom/airmass.html', takes_context=True)
def airmass_plot(context):
    #request = context['request']
    interval = 15 #min
    airmass_limit = 3.0
    plot_data = get_24hr_airmass(context['object'], interval, airmass_limit)
    layout = go.Layout(
        yaxis=dict(range=[airmass_limit,1.0]),
        margin=dict(l=20,r=10,b=30,t=40),
        hovermode='closest',
        width=600,
        height=300
    )
    visibility_graph = offline.plot(
        go.Figure(data=plot_data, layout=layout), output_type='div', show_link=False
    )
    return {
        'target': context['object'],
        'figure': visibility_graph
    }

def get_24hr_airmass(target, interval, airmass_limit):

    plot_data = []
    
    start = Time(datetime.datetime.utcnow())
    end = Time(start.datetime + datetime.timedelta(days=1))
    time_range = time_grid_from_range(
        time_range = [start, end],
        time_resolution = interval*u.minute)
    time_plot = time_range.datetime
    
    fixed_target = FixedTarget(name = target.name, 
        coord = SkyCoord(
            target.ra,
            target.dec,
            unit = 'deg'
        )
    )

    #Hack to speed calculation up by factor of ~3
    sun_coords = get_sun(time_range[int(len(time_range)/2)])
    fixed_sun = FixedTarget(name = 'sun',
        coord = SkyCoord(
            sun_coords.ra,
            sun_coords.dec,
            unit = 'deg'
        )
    )

    for observing_facility in facility.get_service_classes():

        #        if observing_facility != 'LCO':
        #            continue

        observing_facility_class = facility.get_service_class(observing_facility)
        sites = observing_facility_class().get_observing_sites()

        for site, site_details in sites.items():

            observer = Observer(
                longitude = site_details.get('longitude')*u.deg,
                latitude = site_details.get('latitude')*u.deg,
                elevation = site_details.get('elevation')*u.m
            )
            
            sun_alt = observer.altaz(time_range, fixed_sun).alt
            obj_airmass = observer.altaz(time_range, fixed_target).secz

            bad_indices = np.argwhere(
                (obj_airmass >= airmass_limit) |
                (obj_airmass <= 1) |
                (sun_alt > -18*u.deg)  #between astro twilights
            )

            obj_airmass = [np.nan if i in bad_indices else float(x)
                for i, x in enumerate(obj_airmass)]

            label = '({facility}) {site}'.format(
                facility = observing_facility, site = site
            )

            plot_data.append(
                go.Scatter(x=time_plot, y=obj_airmass, mode='lines', name=label, )
            )

    return plot_data

@register.inclusion_tag('bhtom/lightcurve.html')
def lightcurve(target):
    def get_color(filter_name):
        filter_translate = {'U': 'U', 'B': 'B', 'V': 'V','I':'I', 'G':'G',
            'g': 'g', 'gp': 'g', 'r': 'r', 'rp': 'r', 'i': 'i', 'ip': 'i',
            'g_ZTF': 'g_ZTF', 'r_ZTF': 'r_ZTF', 'i_ZTF': 'i_ZTF'}
        colors = {'U': 'rgb(59,0,113)',
            'B': 'rgb(0,87,255)',
            'V': 'rgb(20,255,150)',
            'I': 'rgb(200,0,10)',
            'G': 'rgb(0,30,100)',
            'g': 'rgb(0,204,155)',
            'r': 'rgb(255,124,0)',
            'i': 'rgb(254,0,43)',
            'g_ZTF': 'rgb(0,204,155)',
            'r_ZTF': 'rgb(255,124,0)',
            'i_ZTF': 'rgb(254,0,43)',
            'other': 'rgb(0,0,0)'}
        try: color = colors[filter_translate[filter_name]]
        except: color = colors['other']
        return color
         
    photometry_data = {}
    for rd in ReducedDatum.objects.filter(target=target, data_type='photometry'):
        value = json.loads(rd.value)
        photometry_data.setdefault(value.get('filter', ''), {})
        photometry_data[value.get('filter', '')].setdefault('time', []).append(rd.timestamp)
        photometry_data[value.get('filter', '')].setdefault('magnitude', []).append(value.get('magnitude',None))
        photometry_data[value.get('filter', '')].setdefault('error', []).append(value.get('error', None))
    plot_data = [
        go.Scatter(
            x=filter_values['time'],
            y=filter_values['magnitude'], mode='markers',
            marker=dict(color=get_color(filter_name)),
            name=filter_name,
            error_y=dict(
                type='data',
                array=filter_values['error'],
                visible=True,
                color=get_color(filter_name)
            )
        ) for filter_name, filter_values in photometry_data.items()]
    layout = go.Layout(
        yaxis=dict(autorange='reversed'),
        margin=dict(l=30, r=10, b=30, t=40),
        hovermode='closest'
        #height=500,
        #width=500
    )
    if plot_data:
      return {
          'target': target,
          'plot': offline.plot(go.Figure(data=plot_data, layout=layout), output_type='div', show_link=False)
      }
    else:
        return {
            'target': target,
            'plot': 'No photometry for this target yet.'
        }

@register.inclusion_tag('bhtom/moon.html')
def moon_vis(target):

    day_range = 30
    times = Time(
        [str(datetime.datetime.utcnow() + datetime.timedelta(days=delta))
            for delta in np.arange(0, day_range, 0.2)],
        format = 'iso', scale = 'utc'
    )
    
    obj_pos = SkyCoord(target.ra, target.dec, unit=u.deg)
    moon_pos = get_moon(times)

    separations = moon_pos.separation(obj_pos).deg
    phases = moon_illumination(times)

    distance_color = 'rgb(0, 0, 255)'
    phase_color = 'rgb(255, 0, 0)'
    plot_data = [
        go.Scatter(x=times.mjd-times[0].mjd, y=separations, 
            mode='lines',name='Moon distance (degrees)',
            line=dict(color=distance_color)
        ),
        go.Scatter(x=times.mjd-times[0].mjd, y=phases, 
            mode='lines', name='Moon phase', yaxis='y2',
            line=dict(color=phase_color))
    ]
    layout = go.Layout(
        xaxis=dict(title='Days from now'),
        yaxis=dict(range=[0.,180.],tick0=0.,dtick=45.,
            tickfont=dict(color=distance_color)
        ),
        yaxis2=dict(range=[0., 1.], tick0=0., dtick=0.25, overlaying='y', side='right',
            tickfont=dict(color=phase_color)),
        margin=dict(l=20,r=10,b=30,t=40),
        #hovermode='compare',
        width=600,
        height=300,
        autosize=True
    )
    figure = offline.plot(
        go.Figure(data=plot_data, layout=layout), output_type='div', show_link=False
    )
   
    return {'plot': figure}

@register.inclusion_tag('bhtom/spectra.html')
def spectra_plot(target, dataproduct=None):
    spectra = []
    spectral_dataproducts = ReducedDatum.objects.filter(target=target, data_type='spectroscopy')
    if dataproduct:
        spectral_dataproducts = DataProduct.objects.get(dataproduct=dataproduct)
    for spectrum in spectral_dataproducts:
        datum = json.loads(spectrum.value)
        wavelength = []
        flux = []
        name = str(spectrum.timestamp).split(' ')[0]
        #modification by LW: not flux but photon_flux!!
        wav=np.array(datum['wavelength'])
        flu=np.array(datum['photon_flux'])
        for i in range(len(wav)):
            wavelength.append(float(wav[i]))
            flux.append(float(flu[i]))
        # for key, value in datum.items():
        #     print("SPEC: ",float(value['wavelength']))
        #     wavelength.append(float(value['wavelength']))
        #     flux.append(float(value['flux']))
        spectra.append((wavelength, flux, name))
    plot_data = [
        go.Scatter(
            x=spectrum[0],
            y=spectrum[1],
            name=spectrum[2]
        ) for spectrum in spectra]
    layout = go.Layout(
        height=600,
        width=700,
        hovermode='closest',
        xaxis=dict(
            tickformat="d",
            title='Wavelength (angstroms)'
        ),
        yaxis=dict(
            tickformat=".1eg",
            title='Flux'
        )
    )
    if plot_data:
      return {
          'target': target,
          'plot': offline.plot(go.Figure(data=plot_data, layout=layout), output_type='div', show_link=False)
      }
    else:
        return {
            'target': target,
            'plot': 'No spectra for this target yet.'
        }

@register.inclusion_tag('bhtom/aladin_collapse.html')
def aladin_collapse(target):
    return {'target': target}

#edited by LW
@register.inclusion_tag('tom_targets/partials/target_distribution.html')
def bh_target_distribution(targets):
    """
    Displays a plot showing on a map the locations of all sidereal targets in the TOM.
    """
    from astropy.time import Time
    jd_now = Time(datetime.datetime.utcnow()).jd

    alpha_sun, delta_sun = get_sun_ra_dec()
    moon_pos = get_moon(Time(datetime.datetime.utcnow()))
    alpha_moon = moon_pos.ra.deg
    delta_moon = moon_pos.dec.deg

    ###
    locations = targets.filter(type=Target.SIDEREAL).values_list('ra', 'dec', 'name')
    # for ra,dec,name in locations:
    #     print(name,get_angular_dist_from_the_sun(ra,dec,alpha_sun, delta_sun),' deg from Sun')
    #TODO: add field per target to allow sorting by the Sun distance
    data = [
        #targets
        dict(
            lon=[l[0] for l in locations],
            lat=[l[1] for l in locations],
            text=[l[2] for l in locations],
            hoverinfo='text',
            mode='markers',
            marker=dict(size=10,
                                    color='red'),
            type='scattergeo'
        ),
        #grid
        dict(
            lon=list(range(0, 360, 60))+[180]*4,
            lat=[0]*6+[-60, -30, 30, 60],
            text=list(range(0, 360, 60))+[-60, -30, 30, 60],
            hoverinfo='none',
            mode='text',
            type='scattergeo'
        ),
        #sun
        dict(
            lon=[alpha_sun], lat=[delta_sun], text=['SUN'], hoverinfo='text', mode='markers',
            marker=dict(size=50, color='yellow', opacity=0.5),
            type='scattergeo'
        ),
        #moon
        dict(
            lon=[alpha_moon], lat=[delta_moon], text=['Moon'], hoverinfo='text', mode='markers',
            marker=dict(size=50, color='grey', opacity=0.5),
            type='scattergeo'
        )

    ]
    layout = {
        'title': 'Target Map (equatorial)',
        'hovermode': 'closest',
        'showlegend': False,
        'paper_bgcolor': 'black',
        'plot_bgcolor' : 'black',
        'margin' : {
            "l":0,
            "r":0,
            "t":30,
            "b":0
        },
        'geo': {
            'projection': {
                'type': 'mollweide',
            },
            'showlakes' : False,
            'showcoastlines': False,
            'showland': False,
            'bgcolor' : 'black',
            'lonaxis': {
                'showgrid': True,
                'range': [0, 360],
                'gridcolor' : 'white',
            },
            'lataxis': {
                'showgrid': True,
                'range': [-90, 90],
                'gridcolor' : 'white',
            },
        }
    }
    figure = offline.plot(go.Figure(data=data, layout=layout), output_type='div', show_link=False)
    return {'figure': figure}


def get_sun_ra_dec():
        #computing Sun's position, https://en.wikipedia.org/wiki/Position_of_the_Sun
    jd_now = Time(datetime.datetime.utcnow()).jd
    n = jd_now - 2451545.0
    L = 280.460 + 0.9856474*n #mean longitude of the Sun, in deg
    g = 357.528 + 0.9856003*n #mean anomaly
    while (L>360 and L>0): L-=360.
    while (L<0 and L<360): L+=360. 
    lam = L + 1.915*np.sin(np.deg2rad(g)) + 0.020*np.sin(np.deg2rad(2*g))
    bet = 0.0
    eps = 23.439-0.0000004*n
    alpha_sun_rad = np.arctan2(np.cos(np.deg2rad(eps))*np.sin(np.deg2rad(lam)), np.cos(np.deg2rad(lam)))
    delta_sun_rad = np.arcsin(np.sin(np.deg2rad(eps))*np.sin(np.deg2rad(lam)))
    alpha_sun = np.rad2deg(alpha_sun_rad)
    delta_sun = np.rad2deg(delta_sun_rad)
    return alpha_sun, delta_sun

#computes the angular separation in degrees from the SUN
#returns truncated string
#after https://www.skythisweek.info/angsep.pdf
def get_angular_dist_from_the_sun(ra, dec, alpha_sun, delta_sun):
    a1=np.deg2rad(ra)
    d1=np.deg2rad(dec)
    a2=np.deg2rad(alpha_sun)
    d2=np.deg2rad(delta_sun)

    licz=np.sqrt(np.cos(d2)*np.cos(d2)*np.sin(a2-a1)*np.sin(a2-a1) +
    (np.cos(d1)*np.sin(d2) - np.sin(d1)*np.cos(d2)*np.cos(a2-a1))**2)
    mian = np.sin(d1)*np.sin(d2) + np.cos(d1)*np.cos(d2)*np.cos(a2-a1)

    sep_rad = math.atan(licz/mian)
    sep = np.rad2deg(sep_rad)
    sep_str = "{:.0f}".format(sep)

    return sep_str


@register.inclusion_tag('tom_targets/partials/detail_fits_upload.html')
def detail_fits_upload(target, user):
    """
    Given a ``Target``, returns a list of ``Upload Fits``
    """
    user = Cpcs_user.objects.filter(user=user).values_list('id')
    fits = BHTomFits.objects.filter(user_id__in=user)
    tabFits=[]
    for fit in fits:
        tabFits.append([fit.status, fit.status_message, DataProduct.objects.get(id=fit.dataproduct_id).data])

    return {
        'fits': tabFits,
        'target': target

    }

