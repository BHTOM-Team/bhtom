from myapp.models import BHTomFits, Cpcs_user
from django import template
from tom_dataproducts.models import DataProduct, ReducedDatum, ObservationRecord

import logging
logger = logging.getLogger(__name__)

register = template.Library()

@register.inclusion_tag('tom_dataproducts/partials/dataproduct_list_for_target.html')
def dataproduct_list_for_target(target):
    """
    Given a ``Target``, returns a list of ``DataProduct`` objects associated with that ``Target``
    """
    return {
        'products': target.dataproduct_set.all(),
        'target': target
    }

@register.inclusion_tag('tom_dataproducts/partials/detail_fits_upload.html')
def detail_fits_upload(target, user):
    """
    Given a ``Target``, returns a list of ``Upload Fits``
    """
    user = Cpcs_user.objects.filter(user=user).values_list('id')
    data_product = DataProduct.objects.filter(target_id=target.id).values_list('id')
    fits = BHTomFits.objects.filter(user_id__in=user, dataproduct_id__in=data_product)
    tabFits=[]

    for fit in fits:
        try:
            tabFits.append([fit.status.split('/')[-1], fit.status_message, format(DataProduct.objects.get(id=fit.dataproduct_id).data).split('/')[-1]])
        except Exception as e:
            logger.error('error: ' + str(e))

    return {
        'fits': tabFits,
        'target': target

    }
