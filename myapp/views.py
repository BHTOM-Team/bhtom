from astropy.time import Time
from datetime import datetime
from io import StringIO
import json
import os
import os.path
import numpy as np
import logging

from tom_targets.views import TargetCreateView
from tom_targets.templatetags.targets_extras import target_extra_field
from tom_targets.models import Target, TargetList
from tom_targets.forms import (SiderealTargetCreateForm, NonSiderealTargetCreateForm, TargetExtraFormset, TargetNamesFormset)
from tom_targets.filters import TargetFilter
from tom_common.hooks import run_hook
from tom_common.hints import add_hint
from tom_dataproducts.data_processor import run_data_processor
from tom_dataproducts.exceptions import InvalidFileFormatException
from tom_dataproducts.models import ReducedDatum, DataProduct, DataProductGroup
from tom_dataproducts.filters import DataProductFilter
from rest_framework import viewsets, status
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from myapp.models import BHTomFits, Cpcs_user, Catalogs
from myapp.serializers import BHTomFitsCreateSerializer, BHTomFitsResultSerializer, BHTomFitsStatusSerializer
from myapp.hooks import send_to_cpcs
from myapp.forms import DataProductUploadForm, ObservatoryCreationForm

from django.http import HttpResponseServerError
from django.views.generic.edit import FormView, DeleteView
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse_lazy, reverse
from django.utils.safestring import mark_safe
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django_filters.views import FilterView

from guardian.mixins import PermissionRequiredMixin, PermissionListMixin
from guardian.shortcuts import get_objects_for_user, get_groups_with_perms, assign_perm

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

class TargetCreateView(LoginRequiredMixin, CreateView):
    """
    View for creating a Target. Requires authentication.
    """

    model = Target
    fields = '__all__'

    def get_default_target_type(self):
        """
        Returns the user-configured target type specified in ``settings.py``, if it exists, otherwise returns sidereal

        :returns: User-configured target type or global default
        :rtype: str
        """
        try:
            return settings.TARGET_TYPE
        except AttributeError:
            return Target.SIDEREAL

    def get_target_type(self):
        """
        Gets the type of the target to be created from the query parameters. If none exists, use the default target
        type specified in ``settings.py``.

        :returns: target type
        :rtype: str
        """
        obj = self.request.GET or self.request.POST
        target_type = obj.get('type')
        # If None or some invalid value, use default target type
        if target_type not in (Target.SIDEREAL, Target.NON_SIDEREAL):
            target_type = self.get_default_target_type()
        return target_type

    def get_initial(self):
        """
        Returns the initial data to use for forms on this view.

        :returns: Dictionary with the following keys:

                  `type`: ``str``: Type of the target to be created

                  `groups`: ``QuerySet<Group>`` Groups available to the current user

        :rtype: dict
        """
        return {
            'type': self.get_target_type(),
            'groups': self.request.user.groups.all(),
            **dict(self.request.GET.items())
        }

    def get_context_data(self, **kwargs):
        """
        Inserts certain form data into the context dict.

        :returns: Dictionary with the following keys:

                  `type_choices`: ``tuple``: Tuple of 2-tuples of strings containing available target types in the TOM

                  `extra_form`: ``FormSet``: Django formset with fields for arbitrary key/value pairs
        :rtype: dict
        """
        context = super(TargetCreateView, self).get_context_data(**kwargs)
        context['type_choices'] = Target.TARGET_TYPES
        context['names_form'] = TargetNamesFormset(initial=[{'name': new_name}
                                                            for new_name
                                                            in self.request.GET.get('names', '').split(',')])
        context['extra_form'] = TargetExtraFormset()
        return context

    def get_form_class(self):
        """
        Return the form class to use in this view.

        :returns: form class for target creation
        :rtype: subclass of TargetCreateForm
        """
        target_type = self.get_target_type()
        self.initial['type'] = target_type
        if target_type == Target.SIDEREAL:
            return SiderealTargetCreateForm
        else:
            return NonSiderealTargetCreateForm

    def form_valid(self, form):
        """
        Runs after form validation. Creates the ``Target``, and creates any ``TargetName`` or ``TargetExtra`` objects,
        then runs the ``target_post_save`` hook and redirects to the success URL.

        :param form: Form data for target creation
        :type form: subclass of TargetCreateForm
        """
        super().form_valid(form)
        extra = TargetExtraFormset(self.request.POST)
        names = TargetNamesFormset(self.request.POST)
        if extra.is_valid() and names.is_valid():
            extra.instance = self.object
            extra.save()
            names.instance = self.object
            names.save()
        else:
            form.add_error(None, extra.errors)
            form.add_error(None, extra.non_form_errors())
            form.add_error(None, names.errors)
            form.add_error(None, names.non_form_errors())
            return super().form_invalid(form)

        logger.info('Target post save hook: %s created: %s', self.object, True)
        run_hook('target_post_save', target=self.object, created=True)

        return redirect('bhlist_detail', pk=form.instance.id)

    def get_form(self, *args, **kwargs):
        """
        Gets an instance of the ``TargetCreateForm`` and populates it with the groups available to the current user.

        :returns: instance of creation form
        :rtype: subclass of TargetCreateForm
        """
        form = super().get_form(*args, **kwargs)
        if self.request.user.is_superuser:
            form.fields['groups'].queryset = Group.objects.all()
        else:
            form.fields['groups'].queryset = self.request.user.groups.all()
        return form


class TargetUpdateView(PermissionRequiredMixin, UpdateView):
    """
    View that handles updating a target. Requires authorization.
    """
    permission_required = 'tom_targets.change_target'
    model = Target
    fields = '__all__'

    def get_context_data(self, **kwargs):
        """
        Adds formset for ``TargetName`` and ``TargetExtra`` to the context.

        :returns: context object
        :rtype: dict
        """
        extra_field_names = [extra['name'] for extra in settings.EXTRA_FIELDS]
        context = super().get_context_data(**kwargs)
        context['names_form'] = TargetNamesFormset(instance=self.object)
        context['extra_form'] = TargetExtraFormset(
            instance=self.object,
            queryset=self.object.targetextra_set.exclude(key__in=extra_field_names)
        )
        return context

    @transaction.atomic
    def form_valid(self, form):
        """
        Runs after form validation. Validates and saves the ``TargetExtra`` and ``TargetName`` formsets, then calls the
        superclass implementation of ``form_valid``, which saves the ``Target``. If any forms are invalid, rolls back
        the changes.

        Saving is done in this order to ensure that new names/extras are available in the ``target_post_save`` hook.

        :param form: Form data for target update
        :type form: subclass of TargetCreateForm
        """
        extra = TargetExtraFormset(self.request.POST, instance=self.object)
        names = TargetNamesFormset(self.request.POST, instance=self.object)
        if extra.is_valid() and names.is_valid():
            extra.save()
            names.save()
        else:
            form.add_error(None, extra.errors)
            form.add_error(None, extra.non_form_errors())
            form.add_error(None, names.errors)
            form.add_error(None, names.non_form_errors())
            return super().form_invalid(form)
        super().form_valid(form)
        return redirect('bhlist_detail', pk=form.instance.id)

    def get_queryset(self, *args, **kwargs):
        """
        Returns the queryset that will be used to look up the Target by limiting the result to targets that the user is
        authorized to modify.

        :returns: Set of targets
        :rtype: QuerySet
        """
        return get_objects_for_user(self.request.user, 'tom_targets.change_target')

    def get_form_class(self):
        """
        Return the form class to use in this view.

        :returns: form class for target update
        :rtype: subclass of TargetCreateForm
        """
        if self.object.type == Target.SIDEREAL:
            return SiderealTargetCreateForm
        elif self.object.type == Target.NON_SIDEREAL:
            return NonSiderealTargetCreateForm

    def get_initial(self):
        """
        Returns the initial data to use for forms on this view. For the ``TargetUpdateView``, adds the groups that the
        target is a member of.

        :returns:
        :rtype: dict
        """
        initial = super().get_initial()
        initial['groups'] = get_groups_with_perms(self.get_object())
        return initial

    def get_form(self, *args, **kwargs):
        """
        Gets an instance of the ``TargetCreateForm`` and populates it with the groups available to the current user.

        :returns: instance of creation form
        :rtype: subclass of TargetCreateForm
        """
        form = super().get_form(*args, **kwargs)
        if self.request.user.is_superuser:
            form.fields['groups'].queryset = Group.objects.all()
        else:
            form.fields['groups'].queryset = self.request.user.groups.all()
        return form


class TargetDeleteView(PermissionRequiredMixin, DeleteView):
    """
    View for deleting a target. Requires authorization.
    """
    permission_required = 'tom_targets.delete_target'
    success_url = reverse_lazy('bhlist')
    model = Target

    def get_object(self, queryset=None):
        """ Hook to ensure object is owned by request.user. """
        obj = super(TargetDeleteView, self).get_object()

        return obj

class TargetFileView(LoginRequiredMixin, ListView):

    permission_required = 'tom_targets.view_target'
    template_name = 'tom_dataproducts/dataproduct_list.html'
    model = BHTomFits

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)

        context['object_list']

        user = Cpcs_user.objects.filter(user=self.request.user).values_list('id')
        data_product = DataProduct.objects.filter(target_id=self.kwargs['pk']).values_list('id')
        fits = BHTomFits.objects.filter(dataproduct_id__in=data_product)

        tabFits = []

        for fit in fits:
            try:
                data_product = DataProduct.objects.get(id=fit.dataproduct_id)

                tabFits.append([format(data_product.data), format(data_product.data).split('/')[-1],
                                format(fit.ccdphot_result), format(fit.ccdphot_result).split('/')[-1],
                                format(fit.cpcs_result), format(fit.cpcs_result).split('/')[-1],
                                fit.filter, Cpcs_user.objects.get(id=fit.user_id).obsName,
                                fit.status, fit.mjd, fit.expTime,
                                DataProduct.objects.get(id=fit.dataproduct_id).data_product_type])

            except Exception as e:
                logger.error('error: ' + str(e))

        context['fits']=tabFits
        return context


class IsAuthenticatedOrReadOnlyOrCreation(IsAuthenticatedOrReadOnly):
    """Allows Read only operations and Creation of new data (no modify or delete)"""

    def has_permission(self, request, view):
        return request.method == 'POST' or super().has_permission(request, view)

class fits_upload(viewsets.ModelViewSet):

    queryset = BHTomFits.objects.all()
    serializer_class = BHTomFitsCreateSerializer
    permission_classes = [IsAuthenticatedOrReadOnlyOrCreation]

    def create(self, request, *args, **kwargs):

        self.check_permissions(request)

        try:
            observation_filter = request.data.get('filter')
        except:
            observation_filter = None
        try:
            target = request.data['target']
            data_product_files = request.FILES.getlist("files")
            hashtag = request.data.get('hashtag')
            dp_type = request.data.get('data_product_type')
            user = Cpcs_user.objects.get(cpcs_hashtag=hashtag)
            target_id = Target.objects.get(name=target)

            if user is None or target_id is None:
                return Response(status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error('error1: ' + str(e))
            return Response(status=status.HTTP_400_BAD_REQUEST)

        successful_uploads = []

        for f in data_product_files:
            dp = DataProduct(
                target=target_id,
                data=f,
                product_id=None,
                data_product_type=dp_type
            )
            dp.save()

            try:
                run_hook('data_product_post_upload', dp, hashtag, observation_filter)
                run_data_processor(dp)
                successful_uploads.append(str(dp))

            except InvalidFileFormatException as iffe:

                ReducedDatum.objects.filter(data_product=dp).delete()
                dp.delete()

            except Exception:
                ReducedDatum.objects.filter(data_product=dp).delete()
                dp.delete()

        return Response(status=status.HTTP_201_CREATED)

    def list(self, request, *args, **kwargs):
        ret = super().list(request, *args, **kwargs)
        return ret

class result_fits(viewsets.ModelViewSet):

    queryset = BHTomFits.objects.all()
    serializer_class = BHTomFitsResultSerializer
    permission_classes = [IsAuthenticatedOrReadOnlyOrCreation]

    def create(self, request, *args, **kwargs):

        #fits_id = request.data['fits_id']
        fits_id = request.query_params.get('job_id')

        try:
            instance = BHTomFits.objects.get(fits_id=fits_id)

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

        url_base = BASE + '/data/' + format(target.name) +'/photometry/'

        if not os.path.exists(url_base):
            os.makedirs(url_base)

        url_resalt = os.path.join(url_base, ccdphot_result.name)

        with open(url_resalt, 'wb') as file:
            for chunk in ccdphot_result:
                file.write(chunk)

        if instance.status == 'R':

            send_to_cpcs(url_resalt, instance, target.extra_fields['calib_server_name'])

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
