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

        try:
            filter, fit_id, status_message, mjd, expTime, observatory, data_user = None, None, None, None, None, None, None

            fit = BHTomFits.objects.get(dataproduct_id=data)

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
                bhtomData = BHTomData.objects.get(dataproduct_id=data)
                data_user = bhtomData.user_id

            if data.data_product_type == 'photometry_cpcs':
                ccdphot_url = format(data.data)
                logger.error(ccdphot_url)
            else:
                ccdphot_url = str(fit.photometry_file)

            tabData.append([fit_id, data.id, format(data.data), format(data.data).split('/')[-1],
                            ccdphot_url, format(ccdphot_url).split('/')[-1], filter,
                            observatory, status_message, mjd, expTime,
                            data.data_product_type, data.featured, data_user])

        except Exception as e:
            logger.error('error: ' + str(e))

    return {
        'tabData': tabData,
        'target': target,
        'user': user
    }
