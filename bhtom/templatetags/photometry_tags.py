import json
import logging

import numpy as np
import plotly.graph_objs as go
from django import template
from django.conf import settings
from guardian.shortcuts import get_objects_for_user
from plotly import offline

from bhtom.models import ViewReducedDatum

logger = logging.getLogger(__name__)
register = template.Library()


OWNER_KEY = "owner"
FACILITY_KEY = "facility"


def load_datum_json(json_values):
    if json_values:
        if type(json_values) is dict:
            return json_values
        else:
            return json.loads(json_values.replace("\'", "\""))
    else:
        return {}


@register.inclusion_tag('tom_dataproducts/partials/photometry_for_target.html', takes_context=True)
def photometry_for_target(context, target):
    """
    Renders a photometric plot for a target.

    This templatetag requires all ``ReducedDatum`` objects with a data_type of ``photometry`` to be structured with the
    following keys in the JSON representation: magnitude, error, filter
    """

    photometry_data = {}

    # Marked in ASAS-SN with error 99 mag
    non_detection_data = {}
    if settings.TARGET_PERMISSIONS_ONLY:
        datums = ViewReducedDatum.objects.filter(target=target,
                                                 data_type__in=[
                                                     settings.DATA_PRODUCT_TYPES['photometry'][0],
                                                     settings.DATA_PRODUCT_TYPES['photometry_asassn'][0]])

    else:
        datums = get_objects_for_user(context['request'].user,
                                      'bhtom_viewreduceddatum',
                                      klass=ViewReducedDatum.objects.filter(
                                          target=target,
                                          data_type__in=[settings.DATA_PRODUCT_TYPES['photometry'][0],
                                                         settings.DATA_PRODUCT_TYPES['photometry_asassn'][0]]))

    for datum in datums:

        values = load_datum_json(datum.value)
        rd_extra_data = load_datum_json(datum.rd_extra_data)
        dp_extra_data = load_datum_json(datum.dp_extra_data)

        if values.get('error', 0.0) < 99.0 and values.get('magnitude') < 99.0:
            photometry_data.setdefault(values['filter'], {})
            photometry_data[values['filter']].setdefault('time', []).append(datum.timestamp)
            photometry_data[values['filter']].setdefault('magnitude', []).append(values.get('magnitude'))
            photometry_data[values['filter']].setdefault('error', []).append(values.get('error', 0.0))
            photometry_data[values['filter']].setdefault('owner', []).append(rd_extra_data.get(OWNER_KEY, dp_extra_data.get(OWNER_KEY, '')))
            photometry_data[values['filter']].setdefault('facility', []).append(rd_extra_data.get(FACILITY_KEY, dp_extra_data.get(FACILITY_KEY, '')))
        # Non-detection
        elif values.get('magnitude') < 99.0:
            non_detection_data.setdefault(values['filter'], {})
            non_detection_data[values['filter']].setdefault('time', []).append(datum.timestamp)
            non_detection_data[values['filter']].setdefault('magnitude', []).append(values.get('magnitude'))
            non_detection_data[values['filter']].setdefault('error', []).append(values.get('error', 0.0))
            non_detection_data[values['filter']].setdefault('owner', []).append(rd_extra_data.get(OWNER_KEY, dp_extra_data.get(OWNER_KEY, '')))
            non_detection_data[values['filter']].setdefault('facility', []).append(rd_extra_data.get(FACILITY_KEY, dp_extra_data.get(FACILITY_KEY, '')))

        # TODO: hovering arror down in case of 99.99 mag?

    plot_data = [
        go.Scatter(
            x=filter_values['time'],
            y=filter_values['magnitude'],
            mode='markers',
            name=filter_name,
            error_y=dict(type='data',
                         array=filter_values['error'],
                         visible=True),
            customdata=np.stack((filter_values['owner'], filter_values['facility']), axis=-1),
            hovertemplate='Owner: %{customdata[0]} <br>Facility: %{customdata[1]}',
        ) for filter_name, filter_values in photometry_data.items()] + [
        go.Scatter(
            x=filter_values['time'],
            y=filter_values['magnitude'],
            mode='markers',
            marker_symbol=6,
            name=f'{filter_name}',
            customdata=np.stack((filter_values['owner'], filter_values['facility']), axis=-1),
            hovertemplate='Owner: %{customdata[0]} <br>Facility: %{customdata[1]}',
        ) for filter_name, filter_values in non_detection_data.items()]

    layout = go.Layout(
        yaxis=dict(autorange='reversed'),
        xaxis=dict(title='UTC time'),
        height=600,
        width=700
    )
    return {
        'target': target,
        'plot': offline.plot(go.Figure(data=plot_data, layout=layout), output_type='div', show_link=False)
    }
