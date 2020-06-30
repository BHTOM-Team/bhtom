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

class UpdateReducedDataView(LoginRequiredMixin, RedirectView):
    """
    View that handles the updating of reduced data tied to a ``DataProduct`` that was automatically ingested from a
    broker. Requires authentication.
    """
    def get(self, request, *args, **kwargs):
        """
        Method that handles the GET requests for this view. Calls the management command to update the reduced data and
        adds a hint using the messages framework about automation.
        """
        target_id = request.GET.get('target_id', None)
        out = StringIO()
        if target_id:
            call_command('updatereduceddata_gaia', target_id=target_id, stdout=out)
        else:
            call_command('updatereduceddata_gaia', stdout=out)
        messages.info(request, out.getvalue())
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