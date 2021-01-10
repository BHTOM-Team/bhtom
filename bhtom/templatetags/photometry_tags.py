import json
import plotly.graph_objs as go
from django import template
from django.conf import settings
from guardian.shortcuts import get_objects_for_user
from plotly import offline
from tom_dataproducts.models import ReducedDatum
import logging

from bhtom.utils.aavso_data_fetch import fetch_aavso_photometry

logger = logging.getLogger(__name__)
register = template.Library()


@register.inclusion_tag('tom_dataproducts/partials/photometry_for_target.html', takes_context=True)
def photometry_for_target(context, target):
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

    plot_data = [
        go.Scatter(
            x=filter_values['time'],
            y=filter_values['magnitude'],
            mode='markers',
            name=filter_name,
            error_y=dict(type='data',
                         array=filter_values['error'],
                         visible=True)
        ) for filter_name, filter_values in photometry_data.items()]
    layout = go.Layout(
        yaxis=dict(autorange='reversed'),
        height=600,
        width=700
    )
    return {
        'target': target,
        'plot': offline.plot(go.Figure(data=plot_data, layout=layout), output_type='div', show_link=False)
    }
