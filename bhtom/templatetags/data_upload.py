from django import template
from tom_dataproducts.models import DataProduct

from bhtom.models import BHTomFits, Observatory, Instrument, BHTomData
from datatools.utils.logger.bhtom_logger import BHTOMLogger

register = template.Library()
logger: BHTOMLogger = BHTOMLogger(__name__, "[Data upload]")


@register.inclusion_tag('tom_dataproducts/partials/dataproduct_upload_list.html', takes_context=True)
def dataproduct_list(context, target):
    user = context['request'].user
    data_product = DataProduct.objects.filter(target=target).order_by('-created')
    tabData = []

    for data in data_product:
        filter, fit_id, status_message, mjd, expTime, observatory, data_user = None, None, None, None, None, None, None
        fit, data_user, ccdphot_url, ccdphot_name, data_stored, bhtomData = None, None, None, None, False, None

        if data.data_product_type == 'photometry_cpcs' or data.data_product_type == 'fits_file':
            try:
                fit = BHTomFits.objects.get(dataproduct_id=data)
            except BHTomFits.DoesNotExist:
                fit = None
        else:
            try:
                bhtomData = BHTomData.objects.get(dataproduct_id=data.id)
            except BHTomData.DoesNotExist:
                bhtomData = None

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
                data_stored = fit.data_stored
            else:
                if bhtomData is not None:
                    data_user = bhtomData.user_id.id
                    data_stored = bhtomData.data_stored
                else:
                    data_user = -1

            if data.data_product_type == 'photometry_cpcs':
                ccdphot_url = format(data.data)
                ccdphot_name = format(ccdphot_url).split('/')[-1]
            elif data.data_product_type == 'fits_file' and fit is not None:
                ccdphot_url = str(fit.photometry_file)
                ccdphot_name = format(ccdphot_url).split('/')[-1]


            tabData.append([fit_id, data.id, format(data.data).split('/')[-1],
                            ccdphot_url, ccdphot_name, filter,
                            observatory, status_message, mjd, expTime,
                            data.data_product_type, data.featured, data_user, data_stored])

        except Exception as e:
            logger.error('dataproduct_list error: ' + str(e))

    return {
        'tabData': tabData,
        'target': target,
        'user': user
    }
