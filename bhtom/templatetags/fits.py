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
from bhtom.models import BHTomFits, Observatory, Instrument, BHTomUser

import logging

register = template.Library()
logger = logging.getLogger(__name__)

@register.inclusion_tag('tom_dataproducts/partials/dataproduct_list.html', takes_context=True)
def dataproduct_list(context, target):

    user = context['request'].user
    data_product = DataProduct.objects.filter(target=target, data_product_type__in=['fits_file','photometry_cpcs'])
    fits = BHTomFits.objects.filter(dataproduct_id__in=data_product).order_by('-start_time')
    tabFits = []

    for fit in fits:
        try:
            data_product = DataProduct.objects.get(id=fit.dataproduct_id.id)
            instrument = Instrument.objects.get(id=fit.instrument_id.id)

            if fit.filter == 'no':
                   filter = 'Auto'
            else:
                filter = fit.filter
            if data_product.data_product_type == 'photometry_cpcs':
                ccdphot_url = format(data_product.data)
                logger.error(ccdphot_url)
            else:
                ccdphot_url = str(fit.photometry_file)

            tabFits.append([fit.file_id, fit.start_time,
                            format(data_product.data), format(data_product.data).split('/')[-1],
                            ccdphot_url, format(ccdphot_url).split('/')[-1], filter,
                            Observatory.objects.get(id=instrument.observatory_id.id).obsName,
                            fit.status_message, fit.mjd, fit.expTime,
                            DataProduct.objects.get(id=fit.dataproduct_id.id).data_product_type, instrument.user_id.id])

        except Exception as e:
            logger.error('error: ' + str(e))

    return {
        'tabFits': tabFits,
        'target': target
    }

