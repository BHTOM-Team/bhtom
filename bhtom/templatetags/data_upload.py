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
from bhtom.models import BHTomFits, Observatory, Instrument, BHTomUser, BHTomData

import logging

register = template.Library()
logger = logging.getLogger(__name__)

@register.inclusion_tag('tom_dataproducts/partials/dataproduct_upload_list.html', takes_context=True)
def dataproduct_list(context, target):
    user = context['request'].user
    data_product = DataProduct.objects.filter(target=target).order_by('-created')
    tabData = []

    for data in data_product:
        filter, fit_id, status_message, mjd, expTime, observatory, data_user = None, None, None, None, None, None, None
        fit, data_user, ccdphot_url, ccdphot_name = None, None, None, None

        if data.data_product_type == 'photometry_cpcs' or data.data_product_type == 'fits_file':
            try:
                fit = BHTomFits.objects.get(dataproduct_id=data)
            except BHTomFits.DoesNotExist:
                fit = None

        try:

            if fit is not None:
                instrument = Instrument.objects.get(id=fit.instrument_id.id)
                observatory = Observatory.objects.get(id=instrument.observatory_id.id).obsName

                if fit.filter == 'no':
                    filter = 'Auto'
                else:
                    filter = fit.filter

                fit_id = fit.file_id
                status_message = fit.status_message
                mjd = fit.mjd
                expTime = fit.expTime
                data_user = instrument.user_id.id
            else:
                try:
                    data = BHTomData.objects.get(dataproduct_id=data)
                    data_user = data.user_id
                except BHTomData.DoesNotExist:
                    data_user = -1

            if data.data_product_type == 'photometry_cpcs':
                ccdphot_url = format(data.data)
                ccdphot_name = format(ccdphot_url).split('/')[-1]
            elif data.data_product_type == 'fits_file' and fit is not None:
                ccdphot_url = str(fit.photometry_file)
                ccdphot_name = format(ccdphot_url).split('/')[-1]

            tabData.append([fit_id, data.id, format(data.data), format(data.data).split('/')[-1],
                            ccdphot_url, ccdphot_name, filter,
                            observatory, status_message, mjd, expTime,
                            data.data_product_type, data.featured, data_user])

        except Exception as e:
            logger.error('dataproduct_list error: ' + str(e) + str(data.data))

    return {
        'tabData': tabData,
        'target': target,
        'user': user
    }
