from django.shortcuts import render

#based on https://github.com/TOMToolkit/tom_base/blob/master/tom_dataproducts/views.py
from urllib.parse import urlparse
from io import StringIO

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.management import call_command
from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.safestring import mark_safe
from django.views.generic import View, ListView
from django.views.generic.base import RedirectView
from django.views.generic.detail import DetailView
from django.views.generic.edit import FormView, DeleteView
from django.views.generic.edit import CreateView
from django_filters.views import FilterView
from guardian.shortcuts import get_objects_for_user

from tom_common.hints import add_hint

from bhtom.models import BHTomUser


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
        # user_id = request.user.id

        gaia_out: StringIO = StringIO()
        # aavso_out: StringIO = StringIO()
        if target_id:
            call_command('updatereduceddata_gaia', target_id=target_id, stdout=gaia_out)
            # call_command('updatereduceddata_aavso', target_id=target_id, stdout=aavso_out, user_id=user_id)
        else:
            call_command('updatereduceddata_gaia', stdout=gaia_out)
            # call_command('updatereduceddata_aavso', stdout=aavso_out, user_id=user_id)
            
        def print_message(buffer: StringIO):
            status, message = decode_message(buffer.getvalue())
            if status == MessageStatus.INFO:
                messages.info(request, message)
            elif status == MessageStatus.ERROR:
                messages.error(request, message)
            elif status == MessageStatus.SUCCESS:
                messages.success(request, message)

        print_message(gaia_out)
        # print_message(aavso_out)

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