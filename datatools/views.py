#based on https://github.com/TOMToolkit/tom_base/blob/master/tom_dataproducts/views.py
from io import StringIO
import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.management import call_command
from django.http import HttpResponseRedirect, FileResponse
from django.views.generic.base import RedirectView
from tom_targets.models import Target

from bhtom.models import BHTomUser, Observatory
from typing import List, Dict, Optional

from sentry_sdk import capture_exception

try:
    from settings import local_settings as secret
except ImportError:
    pass

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
        user_id = request.user.id

        gaia_out: StringIO = StringIO()
        aavso_out: StringIO = StringIO()
        ztf_out: StringIO = StringIO()
        cpcs_out: StringIO = StringIO()

        if target_id:
            call_command('updatereduceddata_gaia', target_id=target_id, stdout=gaia_out, user_id=user_id)
            call_command('updatereduceddata_aavso', target_id=target_id, stdout=aavso_out, user_id=user_id)
            call_command('update_reduced_data_ztf', target_id=target_id, stdout=ztf_out, user_id=user_id)
            call_command('update_reduced_data_cpcs', target_id=target_id, stdout=cpcs_out, user_id=user_id)
        else:
            call_command('updatereduceddata_gaia', stdout=gaia_out)
            call_command('updatereduceddata_aavso', stdout=aavso_out, user_id=user_id)
            call_command('update_reduced_data_ztf', stdout=ztf_out, user_id=user_id)
            call_command('update_reduced_data_cpcs', stdout=cpcs_out, user_id=user_id)
            
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
        print_message(ztf_out)
        print_message(cpcs_out)

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
        from .utils.catalog_name_lookup import get_tns_id, get_tns_internal, query_simbad_for_names, \
            TNSReplyError, TNSConnectionError

        target_id = request.GET.get('target_id', None)
        try:
            target: Target = Target.objects.get(pk=target_id)

            tns_id: Optional[str] = target.extra_fields.get('TNS_ID')
            gaia_alert_name: Optional[str] = target.extra_fields.get('gaia_alert_name')
            ztf_alert_name: Optional[str] = target.extra_fields.get('ztf_alert_name')
            aavso_name: Optional[str] = target.extra_fields.get(alert_name_keys['AAVSO'])
            gaia_dr_2_id: Optional[str] = target.extra_fields.get(alert_name_keys['GAIA DR2'])

            extras_to_update: Dict[str, str] = {}

            # If there is no TNS ID, it can be fetched from Gaia Alerts website
            # based on the internal name
            if not tns_id:
                try:
                    tns_id: Optional[str] = get_tns_id(target)
                    if tns_id:
                        extras_to_update['TNS_ID'] = tns_id
                except TNSConnectionError as e:
                    messages.error(self.request, e.message)
                except TNSReplyError as e:
                    messages.error(self.request, e.message)

            # If there is either no Gaia Alerts or ZTF name, these can be fetched from the TNS server
            if tns_id and not (gaia_alert_name and ztf_alert_name):
                try:
                    tns_response: Dict[str, str] = get_tns_internal(tns_id)
                    if not gaia_alert_name and tns_response.get('Gaia'):
                        extras_to_update['gaia_alert_name'] = tns_response['Gaia']
                    if not ztf_alert_name and tns_response.get('ZTF'):
                        extras_to_update['ztf_alert_name'] = tns_response['ZTF']

                except TNSConnectionError as e:
                    capture_exception(e)
                    messages.error(self.request, e.message)
                except TNSReplyError as e:
                    capture_exception(e)
                    messages.error(self.request, e.message)

            # If there is no AAVSO or Gaia DR2, query Simbad
            if not (aavso_name and gaia_dr_2_id):
                simbad_response: Dict[str, str] = query_simbad_for_names(target)

                if not aavso_name and simbad_response.get(alert_name_keys['AAVSO']):
                    extras_to_update[alert_name_keys['AAVSO']] = simbad_response[alert_name_keys['AAVSO']]
                if not gaia_dr_2_id and simbad_response.get(alert_name_keys['GAIA DR2']):
                    extras_to_update[alert_name_keys['GAIA DR2']] = simbad_response[alert_name_keys['GAIA DR2']]

            # If anything was updated
            if extras_to_update:
                target.save(extras=extras_to_update)
                messages.success(self.request, f'Updated target names')

        except Exception as e:
            capture_exception(e)
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

class obsInfo_download(RedirectView):

    def handle_no_permission(self):
        if self.request.META.get('HTTP_REFERER') is None:
            return HttpResponseRedirect('/')
        else:
            return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

    def has_permission(self):
        if not self.request.user.is_authenticated or not request.user.is_staff:
            messages.error(self.request, secret.NOT_PERMISSION)
            return False
        return True

    def get(self, request, *args, **kwargs):
        try:
            obs = Observatory.objects.get(id=self.kwargs['id'])
        except Observatory.DoesNotExist:
            if self.request.META.get('HTTP_REFERER') is None:
                return HttpResponseRedirect('/')
            else:
                return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

        if obs.obsInfo:
            address = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/data/' + format(obs.obsInfo)
            return FileResponse(open(address, 'rb'), as_attachment=True)
        else:
            if self.request.META.get('HTTP_REFERER') is None:
                return HttpResponseRedirect('/')
            else:
                return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

class observatory_fits_download(RedirectView):

    def handle_no_permission(self):
        if self.request.META.get('HTTP_REFERER') is None:
            return HttpResponseRedirect('/')
        else:
            return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

    def has_permission(self):
        if not self.request.user.is_authenticated or not request.user.is_staff:
            messages.error(self.request, secret.NOT_PERMISSION)
            return False
        return True

    def get(self, request, *args, **kwargs):
        try:
            obs = Observatory.objects.get(obsName=self.kwargs['id'])
        except Observatory.DoesNotExist:
            if self.request.META.get('HTTP_REFERER') is None:
                return HttpResponseRedirect('/')
            else:
                return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

        if obs.obsInfo:
            address = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/data/' + format(obs.fits)
            return FileResponse(open(address, 'rb'), as_attachment=True)
        else:
            if self.request.META.get('HTTP_REFERER') is None:
                return HttpResponseRedirect('/')
            else:
                return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))