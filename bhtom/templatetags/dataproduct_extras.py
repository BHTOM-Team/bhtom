import base64
import io
import json
import urllib
from datetime import datetime

import matplotlib.pyplot as plt
import plotly.graph_objs as go
from django import template
from django.conf import settings
from guardian.shortcuts import get_objects_for_user
from plotly import offline
from tom_dataproducts.models import DataProduct, ReducedDatum
from tom_dataproducts.processors.data_serializers import SpectrumSerializer

from bhtom.models import BHTomFits, Instrument
import logging

register = template.Library()
logger = logging.getLogger(__name__)

@register.inclusion_tag('tom_dataproducts/partials/detail_fits_upload.html')
def detail_fits_upload(target, user):
    """
    Given a ``Target``, returns a list of ``Upload Fits``
    """
    user = Instrument.objects.filter(user_id=user).values_list('id')
    data_product = DataProduct.objects.filter(target_id=target.id).values_list('id')
    fits = BHTomFits.objects.filter(user_id__in=user, dataproduct_id__in=data_product)
    tabFits=[]

    for fit in fits:
        try:
            tabFits.append([fit.status.split('/')[-1], fit.status_message,
                            format(DataProduct.objects.get(id=fit.dataproduct_id).data).split('/')[-1]])
        except Exception as e:
            logger.error('detail_fits_upload error: ' + str(e))

    return {
        'fits': tabFits,
        'target': target

    }



@register.inclusion_tag('tom_dataproducts/partials/spectroscopy_for_target.html', takes_context=True)
def spectroscopy_for_target(context, target, dataproduct=None):
    """
    Renders a spectroscopic plot for a ``Target``. If a ``DataProduct`` is specified, it will only render a plot with
    that spectrum.
    """
    spectral_dataproducts = DataProduct.objects.filter(target=target,
                                                       data_product_type=settings.DATA_PRODUCT_TYPES['spectroscopy'][0])
    if dataproduct:
        spectral_dataproducts = DataProduct.objects.get(data_product=dataproduct)

    plot_data = []
    if settings.TARGET_PERMISSIONS_ONLY:
        datums = ReducedDatum.objects.filter(data_product__in=spectral_dataproducts)
    else:
        datums = get_objects_for_user(context['request'].user,
                                      'tom_dataproducts.view_reduceddatum',
                                      klass=ReducedDatum.objects.filter(data_product__in=spectral_dataproducts))
    for datum in datums:
        deserialized = SpectrumSerializer().deserialize(datum.value)
        plot_data.append(go.Scattergl(
            x=deserialized.wavelength.value,
            y=deserialized.flux.value,
            name=datetime.strftime(datum.timestamp, '%Y%m%d-%H:%M:%s')
        ))

    layout = go.Layout(
        height=600,
        width=700,
        xaxis=dict(
            tickformat="d"
        ),
        yaxis=dict(
            tickformat=".1eg"
        )
    )
    return {
        'target': target,
        'plot': offline.plot(go.Figure(data=plot_data, layout=layout), output_type='div', show_link=False)
    }

@register.inclusion_tag('tom_dataproducts/partials/photometry_for_target_static.html', takes_context=True)
def photometry_for_target_static(context, target):
    """
    Renders a photometric plot for a target.

    This templatetag requires all ``ReducedDatum`` objects with a data_type of ``photometry`` to be structured with the
    following keys in the JSON representation: magnitude, error, filter
    """
    photometry_data = {}
    if settings.TARGET_PERMISSIONS_ONLY:
        datums = ReducedDatum.objects.filter(target=target, data_type=settings.DATA_PRODUCT_TYPES['photometry'][0])
    else:
        datums = get_objects_for_user(context['request'].user,
                                      'tom_dataproducts.view_reduceddatum',
                                      klass=ReducedDatum.objects.filter(
                                          target=target,
                                          data_type=settings.DATA_PRODUCT_TYPES['photometry'][0]))

    for datum in datums:
        values = json.loads(datum.value)
        photometry_data.setdefault(values['filter'], {})
        photometry_data[values['filter']].setdefault('time', []).append(datum.timestamp)
        photometry_data[values['filter']].setdefault('magnitude', []).append(values.get('magnitude'))
        photometry_data[values['filter']].setdefault('error', []).append(values.get('error', 0.0))


    figure: plt.Figure = plt.figure(figsize=(7, 6))
    ax = figure.add_axes((0.15, 0.15, 0.75, 0.75))
    ax.invert_yaxis()
    ax.grid(color='white', linestyle='solid')
    ax.set_facecolor('#E5ECF6')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    ax.spines['left'].set_visible(False)

    ax.tick_params(axis='x', colors='#2A3F5F')
    ax.tick_params(axis='y', colors="#2A3F5F")

    for filter_name, filter_values in photometry_data.items():
        ax.errorbar(x=filter_values['time'],
                    y=filter_values['magnitude'],
                    yerr=filter_values['error'],
                    fmt='o',
                    ms=2.5,
                    capsize=1,
                    elinewidth=1,
                    markeredgewidth=1)

    buf: io.BytesIO = io.BytesIO()
    figure.savefig(buf, format='png')
    buf.seek(0)
    imsrc = base64.b64encode(buf.read())
    imuri = 'data:image/png;base64,{}'.format(urllib.parse.quote(imsrc))

    return {
        'target': target,
        'plot_path': imuri
    }
