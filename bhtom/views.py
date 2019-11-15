from django_filters.views import FilterView


from astropy.coordinates import SkyCoord
from astropy import units as u
from astropy.time import Time
from datetime import datetime
from datetime import timedelta
import json
import copy

from django.views.generic.edit import CreateView, UpdateView, DeleteView
from tom_targets.models import Target, TargetList, TargetExtra
from tom_targets.filters import TargetFilter
from tom_targets.views import TargetCreateView
from tom_targets.forms import TargetExtraFormset, TargetNamesFormset
from tom_targets.templatetags.targets_extras import target_extra_field

from django.db.models import Case, When


def make_magrecent(all_phot, jd_now):
    all_phot = json.loads(all_phot)
    recent_jd = max([all_phot[obs]['jd'] for obs in all_phot])
    recent_phot = [all_phot[obs] for obs in all_phot if
        all_phot[obs]['jd'] == recent_jd][0]
    mag = float(recent_phot['flux'])
    filt = recent_phot['filters']['name']
    diff = jd_now - float(recent_jd)
    mag_recent = '{mag:.2f} ({filt}: {time:.2f})'.format(
        mag = mag,
        filt = filt,
        time = diff)
    return mag_recent

class BlackHoleListView(FilterView):
    template_name = 'tom_common/bhlist.html'
    paginate_by = 10
    strict = False
    model = Target
    filterset_class = TargetFilter
    permission_required = 'tom_targets.view_target' #or remove if want it freely visible

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['target_count'] = context['paginator'].count
        context['groupings'] = (TargetList.objects.all()
                                if self.request.user.is_authenticated
                                else TargetList.objects.none())
        context['query_string'] = self.request.META['QUERY_STRING']

        jd_now = Time(datetime.utcnow()).jd
        for target in context['object_list']:
            last = float(target_extra_field(target=target, name='jdlastobs'))
            target.dt = (jd_now - last)
        #     target.mag_recent = make_magrecent(target.all_phot, jd_now)
        return context

    # def get_queryset(self):
    #         qs = super().get_queryset()
    #         return qs.annotate(jdlastobs=Case(When(targetextra__key__icontains='jdlastobs', then='targetextra__value'))).order_by('-jdlastobs')