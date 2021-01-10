#based on https://github.com/TOMToolkit/tom_base/blob/master/tom_dataproducts/views.py
from io import StringIO

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.management import call_command
from django.http import HttpResponseRedirect
from django.views.generic.base import RedirectView
from tom_targets.models import Target

from bhtom.models import BHTomUser
from typing import List, Dict, Optional


alert_name_keys: Dict[str, str] = settings.ALERT_NAME_KEYS


class UpdateReducedDataView(LoginRequiredMixin, RedirectView):
    """
    View that handles the updating of reduced data tied to a ``DataProduct`` that was automatically ingested from a
    broker. Requires authentication.
    """
    permission_required = 'tom_targets.view_target'

    def handle_no_permission(self):
        messages.error(self.request, secret.NOT_PERMISSION)
        if self.request.META.get('HTTP_REFERER') is None:
            return HttpResponseRedirect('/')
        else:
            return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

    def render_to_response(self, context, **response_kwargs):
        if context is None:
            messages.error(self.request, secret.NOT_ACTIVATE)
            if self.request.META.get('HTTP_REFERER') is None:
                return HttpResponseRedirect('/')
            else:
                return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

    def get_context_data(self, *args, **kwargs):
        if not BHTomUser.objects.get(user=self.request.user).is_activate:
            return None

    def get(self, request, *args, **kwargs):
        """
        Method that handles the GET requests for this view. Calls the management command to update the reduced data and
        adds a hint using the messages framework about automation.
        """
        from datatools.management.commands.utils.result_messages import MessageStatus, decode_message

        target_id = request.GET.get('target_id', None)
        user_id = request.user.pk

        gaia_out: StringIO = StringIO()
        aavso_out: StringIO = StringIO()
        if target_id:
            call_command('updatereduceddata_gaia', target_id=target_id, stdout=gaia_out)
            call_command('updatereduceddata_aavso', target_id=target_id, stdout=aavso_out, user_id=user_id)
        else:
            call_command('updatereduceddata_gaia', stdout=gaia_out)
            call_command('updatereduceddata_aavso', stdout=aavso_out, user_id=user_id)
            
        def print_message(buffer: StringIO):
            status, message = decode_message(buffer.getvalue())
            if status == MessageStatus.INFO:
                messages.info(request, message)
            elif status == MessageStatus.ERROR:
                messages.error(request, message)
            elif status == MessageStatus.SUCCESS:
                messages.success(request, message)

        print_message(gaia_out)
        print_message(aavso_out)

        # add_hint(request, mark_safe(
        #                   'Did you know updating observation statuses can be automated? Learn how in '
        #                   '<a href=https://tom-toolkit.readthedocs.io/en/stable/customization/automation.html>'
        #                   'the docs.</a>'))
        return HttpResponseRedirect(self.get_redirect_url(*args, **kwargs))

    def get_redirect_url(self):
        """
        Returns redirect URL as specified in the HTTP_REFERER field of the request.
        :returns: referer
        :rtype: str
        """
        referer = self.request.META.get('HTTP_REFERER', '/')
        return referer


class FetchTargetNames(LoginRequiredMixin, RedirectView):
    def handle_no_permission(self):
        messages.error(self.request, secret.NOT_PERMISSION)
        if self.request.META.get('HTTP_REFERER') is None:
            return HttpResponseRedirect('/')
        else:
            return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

    def render_to_response(self, context, **response_kwargs):
        if context is None:
            messages.error(self.request, secret.NOT_ACTIVATE)
            if self.request.META.get('HTTP_REFERER') is None:
                return HttpResponseRedirect('/')
            else:
                return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

    def get_context_data(self, *args, **kwargs):
        if not BHTomUser.objects.get(user=self.request.user).is_activate:
            return None

    def get(self, request, *args, **kwargs):
        from .utils.catalog_name_lookup import get_tns_id_from_gaia_name, get_gaia_ztf_names_for_tns_id, query_simbad_for_names

        def update_extra_data(target: Target,
                              result_dict: Dict[str, str],
                              extra_data: Dict[str, str],
                              alert_name_keys: List[str]) -> Dict[str, str]:
            for alert_key in alert_name_keys:
                if result_dict and result_dict.get(alert_key) and not target.extra_fields.get(alert_key):
                    extra_data[alert_key] = result_dict[alert_key]
            return extra_data


        target_id = request.GET.get('target_id', None)
        try:
            target: Target = Target.objects.get(pk=target_id)

            tns_id: Optional[str] = target.extra_fields.get('TNS_ID')
            gaia_alert_name: Optional[str] = target.extra_fields.get('gaia_alert_name')
            ztf_alert_name: Optional[str] = target.extra_fields.get('ztf_alert_name')

            extras_to_update: Dict[str, str] = {}

            # If there is a Gaia Alerts name, TNS ID can be fetched from Gaia Alerts website
            if gaia_alert_name and not tns_id:
                tns_id: Optional[str] = get_tns_id_from_gaia_name(target.extra_fields.get('gaia_alert_name'))
                if tns_id:
                    extras_to_update['TNS_ID'] = tns_id

            # If there is a TNS ID, but no Gaia Alerts name or ZTF Alerts name, both
            # can be fetched from the TNS server:
            if tns_id and not (gaia_alert_name and ztf_alert_name):

                tns_result: Dict[str, str] = get_gaia_ztf_names_for_tns_id(tns_id)
                extras_to_update = update_extra_data(target=target,
                                                     result_dict=tns_result,
                                                     extra_data=extras_to_update,
                                                     alert_name_keys=[alert_name_keys['GAIA'],
                                                                      alert_name_keys['ZTF']])

            # Query Simbad for AAVSO and GAIA DR2 ID if not yet present:
            if not (target.extra_fields.get(alert_name_keys['AAVSO']) and target.extra_fields.get(alert_name_keys['GAIA DR2'])):
                extras_to_update = update_extra_data(target=target,
                                                     result_dict=query_simbad_for_names(target.name),
                                                     extra_data=extras_to_update,
                                                     alert_name_keys=[alert_name_keys['AAVSO'],
                                                                      alert_name_keys['GAIA DR2']])

            target.save(extras=extras_to_update)

            messages.success(self.request, f'Updated target names')

        except Exception as e:
            messages.error(self.request, f'Error while fetching target names: {e}')

        return HttpResponseRedirect(self.get_redirect_url(*args, **kwargs))

    def get_redirect_url(self):
        """
        Returns redirect URL as specified in the HTTP_REFERER field of the request.
        :returns: referer
        :rtype: str
        """
        referer = self.request.META.get('HTTP_REFERER', '/')
        return referer
