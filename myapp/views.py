from django_filters.views import FilterView

from astropy.coordinates import get_moon, get_sun, SkyCoord, AltAz
from astropy import units as u
from astropy.time import Time
from datetime import datetime
from datetime import timedelta
import json
import copy
import os

from django.views.generic.edit import CreateView, UpdateView, DeleteView
from tom_targets.models import Target, TargetList, TargetExtra
from tom_targets.filters import TargetFilter
from tom_targets.views import TargetCreateView
from tom_targets.forms import TargetExtraFormset, TargetNamesFormset
from tom_targets.templatetags.targets_extras import target_extra_field

from rest_framework import viewsets, status
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticatedOrReadOnly
from myapp.models import BHTomFits, Cpcs_user, Catalogs
from myapp.serializers import BHTomFitsCreateSerializer, BHTomFitsResultSerializer, BHTomFitsStatusSerializer
from myapp.hooks import send_to_cpcs
from django.db.models import Case, When
import logging
from tom_dataproducts.models import ReducedDatum, DataProduct
from tom_observations.models import ObservationRecord
from django.http import HttpResponseServerError
import os.path
import numpy as np
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.edit import FormView, DeleteView
from myapp.forms import DataProductUploadForm, ObservatoryCreationForm
from tom_common.hooks import run_hook
from tom_dataproducts.data_processor import run_data_processor
from tom_dataproducts.exceptions import InvalidFileFormatException
from django.contrib import messages
from django.shortcuts import redirect
from django.views.generic.detail import DetailView
from guardian.shortcuts import get_objects_for_user
from tom_dataproducts.forms import AddProductToGroupForm
from tom_observations.facility import get_service_class
from django.urls import reverse
from guardian.mixins import PermissionRequiredMixin, PermissionListMixin
from io import StringIO
from django.core.management import call_command
from django.utils.safestring import mark_safe
from tom_common.hints import add_hint
from rest_framework.response import Response
from django.urls import reverse_lazy
from django.views.generic.list import ListView


logger = logging.getLogger(__name__)

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

#computes priority based on dt and expected cadence
#if observed within the cadence, then returns just the pure target priority
#if not, then priority increases
def computePriority(dt, priority, cadence):
    ret = 0
    # if (dt<cadence): ret = 1 #ok
    # else:
    #     if (cadence!=0 and dt/cadence>1 and dt/cadence<2): ret = 2
    #     if (cadence!=0 and dt/cadence>2): ret = 3

    #alternative - linear scale
    if (cadence!=0):
        ret = dt/cadence
    return ret*priority


class BlackHoleListView(FilterView):
    paginate_by = 20
    strict = False
    model = Target
    filterset_class = TargetFilter
    permission_required = 'tom_targets.view_target' #or remove if want it freely visible
            
    def get_queryset(self, *args, **kwargs):
        qs = super().get_queryset(*args, **kwargs)

        jd_now = Time(datetime.utcnow()).jd

        prioritylist = []
        pklist = []

        for target in qs:
            try:
                #if empty
                last = float(target_extra_field(target=target, name='jdlastobs'))
                target.dt = (jd_now - last)
                dt = (jd_now - last)
            except:
                dt = 10
                target.dt = -1.

            try:
                priority = float(target_extra_field(target=target, name='priority'))
                cadence = float(target_extra_field(target=target, name='cadence'))
            except:
                priority = 1
                cadence = 1 

            target.cadencepriority = computePriority(dt, priority, cadence)
            prioritylist.append(target.cadencepriority)
            pklist.append(target.pk)
        
        prioritylist = np.array(prioritylist)
        idxs = list(prioritylist.argsort())
        sorted_pklist = np.array(pklist)[idxs]
    
        clauses = ' '.join(['WHEN tom_targets_target.id=%s THEN %s' % (pk, i) for i, pk in enumerate(sorted_pklist)])
        ordering = '(CASE %s END)' % clauses
        qsnew= qs.extra(
            select={'ordering': ordering}, order_by=('-ordering',))

        return qsnew


    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['target_count'] = context['paginator'].count
        context['groupings'] = (TargetList.objects.all()
                                if self.request.user.is_authenticated
                                else TargetList.objects.none())
        context['query_string'] = self.request.META['QUERY_STRING']
    
        jd_now = Time(datetime.utcnow()).jd

        prioritylist = []

        for target in context['object_list']:
            try:
                #if empty
                last = float(target_extra_field(target=target, name='jdlastobs'))
                target.dt = (jd_now - last)
                dt = (jd_now - last)
            except:
                dt = 10
                target.dt = -1.

            try:
                priority = float(target_extra_field(target=target, name='priority'))
                cadence = float(target_extra_field(target=target, name='cadence'))
            except:
                priority = 1
                cadence = 1 

            target.cadencepriority = computePriority(dt, priority, cadence)
            prioritylist.append(target.cadencepriority)

        return context


class IsAuthenticatedOrReadOnlyOrCreation(IsAuthenticatedOrReadOnly):
    """Allows Read only operations and Creation of new data (no modify or delete)"""

    def has_permission(self, request, view):
        return request.method == 'POST' or super().has_permission(request, view)

'''class fits_upload(viewsets.ModelViewSet):

    queryset = BHTomFits.objects.all()
    permission_classes = [IsAuthenticatedOrReadOnlyOrCreation]

    def pre_save(self, obj):
        # obj.samplesheet = self.request.FILES.get('file')
        pass

    def create(self, request, *args, **kwargs):
        self.check_permissions(request)
        ret = super().create(request, *args, **kwargs)
        #execute_daophot.send(ret.data['icd'])
        return ret

    def list(self, request, *args, **kwargs):
        ret = super().list(request, *args, **kwargs)
        return ret'''

class result_fits(viewsets.ModelViewSet):

    queryset = BHTomFits.objects.all()
    serializer_class = BHTomFitsResultSerializer
    permission_classes = [IsAuthenticatedOrReadOnlyOrCreation]

    def create(self, request, *args, **kwargs):

        #fits_id = request.data['fits_id']
        fits_id = request.query_params.get('job_id')
        logger.error(request.build_absolute_uri())

        try:
            instance = BHTomFits.objects.get(fits_id=fits_id)
            logger.info(request.query_params.get('status'))
            if request.query_params.get('status') == 'D' or request.query_params.get('status') == 'F':
                ccdphot_result = request.FILES["ccdphot_result_upload"]
                instance.status = 'R'
                instance.cpcs_time = datetime.now()
                instance.ccdphot_result = ccdphot_result.name
                instance.status_message = 'Result from ccdphot'
                instance.mjd = request.query_params.get('fits_mjd')
                instance.expTime = request.query_params.get('fits_exp')
                instance.save()

            else:
                ccdphot_result = request.FILES["ccdphot_result_upload"]
                instance.status = 'E'
                instance.cpcs_time = datetime.now()
                instance.ccdphot_result = ccdphot_result.name
                if request.query_params.get('status_message'):
                    instance.status_message = request.query_params.get('status_message')
                else:
                    instance.status_message = 'Result from ccdphot with error'
                instance.save()
        except Exception as e:
            logger.error('error: ' + str(e))
            return HttpResponseServerError(e)

        BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        target = Target.objects.get(id=DataProduct.objects.get(id=instance.dataproduct_id).target_id)

        url_result = BASE + '/data/' + format(target.name) +'/photometry/'

        if not os.path.exists(url_result):
            os.makedirs(url_result)

        with open(os.path.join(url_result, ccdphot_result.name), 'wb') as file:
            for chunk in ccdphot_result:
                file.write(chunk)

        if instance.status == 'R':

            send_to_cpcs(ccdphot_result, instance, target.extra_fields['calib_server_name'])

        return Response(status=status.HTTP_201_CREATED)

    def list(self, request, *args, **kwargs):
        ret = super().list(request, *args, **kwargs)
        return ret


class status_fits(viewsets.ModelViewSet):

    queryset = BHTomFits.objects.all()
    serializer_class = BHTomFitsStatusSerializer
    permission_classes = [IsAuthenticatedOrReadOnlyOrCreation]

    def update(self, request, *args, **kwargs):

        try:
            instance = self.get_object()
            instance.status = request.data.get("status")
            instance.save()
        except Exception as e:
            logger.error('error: ' + str(e))
            return HttpResponseServerError(e)

        ret = super().update(request, *args, **kwargs)
        return ret

    def list(self, request, *args, **kwargs):
        ret = super().list(request, *args, **kwargs)
        return ret

class DataProductUploadView(LoginRequiredMixin, FormView):
    """
    View that handles manual upload of DataProducts. Requires authentication.
    """

    form_class = DataProductUploadForm

    def get_form_kwargs(self):
        kwargs = super(DataProductUploadView, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        """
        Runs after ``DataProductUploadForm`` is validated. Saves each ``DataProduct`` and calls ``run_data_processor``
        on each saved file. Redirects to the previous page.
        """

        target = form.cleaned_data['target']
        if not target:
            observation_record = form.cleaned_data['observation_record']
            target = observation_record.target
        else:
            observation_record = None
        dp_type = form.cleaned_data['data_product_type']
        data_product_files = self.request.FILES.getlist('files')
        observation_instrument = form.cleaned_data['instrument']
        observation_filter = form.cleaned_data['filter']

        successful_uploads = []
        for f in data_product_files:
            dp = DataProduct(
                target=target,
                observation_record=observation_record,
                data=f,
                product_id=None,
                data_product_type=dp_type
            )
            dp.save()
            try:
                run_hook('data_product_post_upload', dp, observation_instrument, observation_filter)
                run_data_processor(dp)
                successful_uploads.append(str(dp))
            except InvalidFileFormatException as iffe:
                ReducedDatum.objects.filter(data_product=dp).delete()
                dp.delete()
                messages.error(
                    self.request,
                    'File format invalid for file {0} -- error was {1}'.format(str(dp), iffe)
                )
            except Exception:
                ReducedDatum.objects.filter(data_product=dp).delete()
                dp.delete()
                messages.error(self.request, 'There was a problem processing your file: {0}'.format(str(dp)))
        if successful_uploads:
            messages.success(
                self.request,
                'Successfully uploaded: {0}'.format('\n'.join([p for p in successful_uploads]))
            )

        return redirect(form.cleaned_data.get('referrer', '/'))

    def form_invalid(self, form):
        """
        Adds errors to Django messaging framework in the case of an invalid form and redirects to the previous page.
        """
        # TODO: Format error messages in a more human-readable way
        messages.error(self.request, 'There was a problem uploading your file: {}'.format(form.errors.as_json()))
        return redirect(form.cleaned_data.get('referrer', '/'))


class TargetDetailView(PermissionRequiredMixin, DetailView):

    permission_required = 'tom_targets.view_target'
    model = Target

    def get_context_data(self, *args, **kwargs):

        context = super().get_context_data(*args, **kwargs)
        data_product_upload_form = DataProductUploadForm(user=self.request.user,
            initial={
                'target': self.get_object(),
                'referrer': reverse('bhlist_detail', args=(self.get_object().id,))
            },

        )
        context['data_product_form_from_user'] = data_product_upload_form
        return context

    def get(self, request, *args, **kwargs):

        update_status = request.GET.get('update_status', False)
        if update_status:
            if not request.user.is_authenticated:
                return redirect(reverse('login'))
            target_id = kwargs.get('pk', None)
            out = StringIO()
            call_command('updatestatus', target_id=target_id, stdout=out)
            messages.info(request, out.getvalue())
            add_hint(request, mark_safe(
                              'Did you know updating observation statuses can be automated? Learn how in'
                              '<a href=https://tom-toolkit.readthedocs.io/en/stable/customization/automation.html>'
                              ' the docs.</a>'))
            return redirect(reverse('bhlist_detail', args=(target_id,)))
        return super().get(request, *args, **kwargs)


class CreateObservatory(LoginRequiredMixin, FormView):
    """
    View that handles manual upload of DataProducts. Requires authentication.
    """

    template_name = 'tom_common/observatory_create.html'
    form_class = ObservatoryCreationForm
    success_url = reverse_lazy('observatory')


    def form_valid(self, form):

        #super().form_valid(form)

        user = self.request.user
        obsName = form.cleaned_data['obsName']
        lon = form.cleaned_data['lon']
        lat = form.cleaned_data['lat']
        allow_upload = form.cleaned_data['allow_upload']
        prefix = form.cleaned_data['prefix']
        matchDist = form.cleaned_data['matchDist']

        fits = self.request.FILES.getlist('fits')

        for f in fits:
            Cpcs_user.objects.create(
                user=user,
                obsName=obsName,
                lon=lon,
                lat=lat,
                allow_upload=allow_upload,
                prefix=prefix,
                matchDist=matchDist,
                user_activation=False,
                fits=f
            )
        return redirect(self.get_success_url())


class ObservatoryList(LoginRequiredMixin, ListView):

    template_name = 'tom_common/observatory_list.html'
    model = Cpcs_user
    strict = False

    def get_queryset(self, *args, **kwargs):

        return Cpcs_user.objects.filter(user=self.request.user)

