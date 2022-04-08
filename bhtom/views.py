from astropy.time import Time
from datetime import datetime, timedelta
from io import StringIO
import json
import os
import os.path
import numpy as np
import logging
import requests
import base64

import time
import hashlib

from abc import ABC, abstractmethod

from tom_targets.views import TargetCreateView
from tom_targets.templatetags.targets_extras import target_extra_field
from tom_targets.models import Target, TargetList
from bhtom.forms import (SiderealTargetCreateForm, NonSiderealTargetCreateForm, TargetExtraFormset, TargetNamesFormset)
from tom_common.hooks import run_hook
from tom_common.hints import add_hint

from tom_dataproducts.data_processor import run_data_processor
from tom_dataproducts.exceptions import InvalidFileFormatException
from tom_dataproducts.models import ReducedDatum, DataProduct

from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from bhtom.filters import TargetFilter
from bhtom.models import BHTomFits, Observatory, Instrument, BHTomUser, refresh_reduced_data_view, BHTomData
from bhtom.serializers import BHTomFitsCreateSerializer, BHTomFitsResultSerializer
from bhtom.hooks import send_to_cpcs, delete_point_cpcs, create_target_in_cpcs
from bhtom.forms import DataProductUploadForm, ObservatoryCreationForm, ObservatoryUpdateForm
from bhtom.forms import InstrumentCreationForm, CustomUserCreationForm, InstrumentUpdateForm
from bhtom.group import add_all_to_grouping, add_selected_to_grouping, remove_all_from_grouping, \
    remove_selected_from_grouping

from django.http import HttpResponseServerError, Http404, FileResponse, HttpResponseForbidden
from django.views.generic.edit import FormView
from django.views.generic import View
from django.conf import settings
from django.contrib import messages
from django.core.cache.utils import make_template_fragment_key
from django.core.cache import cache
from django_comments.models import Comment

from django.contrib.auth.models import User, Group
from django.contrib.auth import update_session_auth_hash
from django.core.management import call_command
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse_lazy, reverse
from django.utils.safestring import mark_safe
from django.utils import timezone
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django_filters.views import FilterView

from django.http import HttpResponseRedirect, QueryDict
from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin
from guardian.shortcuts import get_objects_for_user

from bhtom.utils.photometry_and_spectroscopy_data_utils import save_photometry_data_for_target_to_csv_file, \
    get_photometry_data_stats, save_spectroscopy_data_for_target_to_csv_file, \
    get_photometry_stats_latex

from sentry_sdk import capture_exception

try:
    from settings import local_settings as secret
except ImportError:
    secret = None


def read_secret(secret_key: str, default_value: str = '') -> str:
    return getattr(secret, secret_key, default_value) if secret else default_value


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
        mag=mag,
        filt=filt,
        time=diff)
    return mag_recent


# computes priority based on dt and expected cadence
# if observed within the cadence, then returns just the pure target priority
# if not, then priority increases
def computePriority(dt, priority, cadence):
    ret = 0
    # if (dt<cadence): ret = 1 #ok
    # else:
    #     if (cadence!=0 and dt/cadence>1 and dt/cadence<2): ret = 2
    #     if (cadence!=0 and dt/cadence>2): ret = 3

    # alternative - linear scale
    if (cadence != 0):
        ret = dt / cadence
    return ret * priority

def deleteFits(dp):
    try:
        logger.info('try remove fits' + str(dp.data))
        BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        url_base = BASE + '/data/'
        url_result = os.path.join(url_base, str(dp.data))
        os.remove(url_result)
    except Exception as e:
        logger.info(e)

class BlackHoleListView(PermissionRequiredMixin, FilterView):
    paginate_by = 20
    strict = False
    model = Target
    filterset_class = TargetFilter

    def handle_no_permission(self):

        if self.request.META.get('HTTP_REFERER') is None:
            return HttpResponseRedirect('/')
        else:
            return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

    def has_permission(self):
        if not self.request.user.is_authenticated:
            messages.error(self.request, read_secret('NOT_AUTHENTICATED'))
            return False
        #       elif not BHTomUser.objects.get(user=self.request.user).is_activate:
        #           messages.error(self.request, read_secret('NOT_ACTIVATE'))
        #          return False
        elif not self.request.user.has_perm('tom_targets.view_target'):
            messages.error(self.request, read_secret('NOT_PERMISSION'))
            return False
        return True

    def get_queryset(self, *args, **kwargs):

        qs = super().get_queryset(*args, **kwargs)
        jd_now = Time(datetime.utcnow()).jd
        prioritylist = []
        pklist = []

        for target in qs:
            try:
                # if empty
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
        qsnew = qs.extra(
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
                # if empty
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


class TargetCreateView(PermissionRequiredMixin, CreateView):
    """
    View for creating a Target. Requires authentication.
    """
    model = Target
    fields = ('name', 'type', 'ra', 'dec', 'epoch', 'parallax',
              'pm_ra', 'pm_dec', 'galactic_lng', 'galactic_lat',
              'distance', 'distance_err', 'gaia_alert_name',
              'calib_server_name', 'ztf_alert_name', 'aavso_name',
              'gaiadr2_id', 'TNS_ID', 'classification', 'priority', 'cadence')

    def handle_no_permission(self):

        if self.request.META.get('HTTP_REFERER') is None:
            return HttpResponseRedirect('/')
        else:
            return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

    def has_permission(self):
        if not self.request.user.is_authenticated:
            messages.error(self.request, read_secret('NOT_AUTHENTICATED'))
            return False
        elif not BHTomUser.objects.get(user=self.request.user).is_activate:
            messages.error(self.request, read_secret('NOT_ACTIVATE'))
            return False
        elif not self.request.user.has_perm('tom_targets.add_target'):
            messages.error(self.request, read_secret('NOT_PERMISSION'))
            return False
        return True

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
        if super().form_valid(form):
            logger.info("Create Target: " + format(self.object) + ", user: " + format(self.request.user))
        else:
            return super().form_invalid(form)

        create_target_in_cpcs(self.request.user, self.object)
        return redirect('bhlist_detail', pk=form.instance.id)

    def get_form(self, *args, **kwargs):
        """
        Gets an instance of the ``TargetCreateForm`` and populates it with the groups available to the current user.
        :returns: instance of creation form
        :rtype: subclass of TargetCreateForm
        """
        form = super().get_form(*args, **kwargs)
        return form


class TargetUpdateView(PermissionRequiredMixin, UpdateView):
    """
    View that handles updating a target. Requires authorization.
    """

    model = Target
    fields = '__all__'

    def handle_no_permission(self):

        if self.request.META.get('HTTP_REFERER') is None:
            return HttpResponseRedirect('/')
        else:
            return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

    def has_permission(self):
        if not self.request.user.is_authenticated:
            messages.error(self.request, read_secret('NOT_AUTHENTICATED'))
            return False
        elif not BHTomUser.objects.get(user=self.request.user).is_activate:
            messages.error(self.request, read_secret('NOT_ACTIVATE'))
            return False
        elif not self.request.user.has_perm('tom_targets.change_target'):
            messages.error(self.request, read_secret('NOT_PERMISSION'))
            return False
        return True

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
        return initial

    def get_form(self, *args, **kwargs):
        """
        Gets an instance of the ``TargetCreateForm`` and populates it with the groups available to the current user.
        :returns: instance of creation form
        :rtype: subclass of TargetCreateForm
        """
        form = super().get_form(*args, **kwargs)
        return form


class TargetDeleteView(PermissionRequiredMixin, DeleteView):
    """
    View for deleting a target. Requires authorization.
    """
    success_url = reverse_lazy('bhlist')
    model = Target

    def handle_no_permission(self):

        if self.request.META.get('HTTP_REFERER') is None:
            return HttpResponseRedirect('/')
        else:
            return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

    def has_permission(self):
        if not self.request.user.is_authenticated:
            messages.error(self.request, read_secret('NOT_AUTHENTICATED'))
            return False
        elif not BHTomUser.objects.get(user=self.request.user).is_activate:
            messages.error(self.request, read_secret('NOT_ACTIVATE'))
            return False
        elif not self.request.user.has_perm('tom_targets.delete_target'):
            messages.error(self.request, read_secret('NOT_PERMISSION'))
            return False
        return True

    def get_object(self, queryset=None):
        """ Hook to ensure object is owned by request.user. """

        obj = super(TargetDeleteView, self).get_object()

        return obj


class TargetFileDetailView(PermissionRequiredMixin, ListView):
    template_name = 'tom_dataproducts/dataproduct_fits_detail.html'
    model = BHTomFits

    def handle_no_permission(self):

        if self.request.META.get('HTTP_REFERER') is None:
            return HttpResponseRedirect('/')
        else:
            return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

    def has_permission(self):
        if not self.request.user.is_authenticated:
            messages.error(self.request, read_secret('NOT_AUTHENTICATED'))
            return False
        elif not BHTomUser.objects.get(user=self.request.user).is_activate:
            messages.error(self.request, read_secret('NOT_ACTIVATE'))
            return False
        elif not self.request.user.has_perm('tom_dataproducts.view_dataproduct'):
            messages.error(self.request, read_secret('NOT_PERMISSION'))
            return False
        elif self.request.user != BHTomFits.objects.get(file_id=self.kwargs['pk_fit']).instrument_id.user_id:
            messages.error(self.request, read_secret('NOT_PERMISSION'))
            return False
        return True

    def get_context_data(self, *args, **kwargs):

        context = super().get_context_data(*args, **kwargs)

        try:
            target = Target.objects.get(id=self.kwargs['pk'])
            fits = BHTomFits.objects.get(file_id=self.kwargs['pk_fit'])
        except Exception as e:
            raise Http404

        instrument = Instrument.objects.get(id=fits.instrument_id.id)

        # if instrument.user_id.id != self.request.user.id:
        #     raise Http404

        observatory = Observatory.objects.get(id=instrument.observatory_id.id)
        data_product = DataProduct.objects.get(id=fits.dataproduct_id.id)
        tabData = {}
        filter = ''

        if fits.cpcs_plot is not None and fits.cpcs_plot != '':
            if fits.allow_upload == False:
                BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                url_base = BASE + '/data/png/'

                if not os.path.exists(url_base):
                    os.makedirs(url_base)
                url_base = url_base + str(fits.followupId) + '.png'

                try:
                    with open(url_base, "rb") as image_file:
                        encoded_string = base64.b64encode(image_file.read())
                        context['cpcs_plot'] = str(encoded_string, "utf-8")
                except IOError as e:
                    capture_exception(e)
                    logger.info('Get plot from cpcs %s' % url_base)
                    url_cpcs = fits.cpcs_plot
                    response = requests.get(url_cpcs, {'hashtag': instrument.hashtag})
                    if response.status_code == 200:
                        with open(url_base, 'wb') as f:
                            f.write(response.content)
                        with open(url_base, "rb") as f:
                            encoded_string = base64.b64encode(f.read())
                        context['cpcs_plot'] = str(encoded_string, "utf-8")
                    else:
                        context['cpcs_plot'] = None

            else:
                context['cpcs_plot'] = fits.cpcs_plot
        try:
            if data_product.data_product_type == 'photometry_cpcs':
                tabData['photometry'] = format(data_product.data).split('/')[-1]
                tabData['photometry_id'] = format(fits.file_id)
            else:
                tabData['fits'] = format(data_product.data).split('/')[-1]
                tabData['fits_id'] = format(data_product.id)
                tabData['fits_url'] = format("/".join(["/data", str(data_product.data)]))

                if fits.photometry_file != '':
                    tabData['photometry'] = format(str(fits.photometry_file).split('/')[-1])
                    tabData['photometry_id'] = format(fits.file_id)

            if fits.filter == 'no':
                filter = 'Auto'
            else:
                filter = fits.filter
        except Exception as e:
            capture_exception(e)
            logger.error('TargetFileDetailView error: ' + str(e))

        context['target'] = target
        context['fits'] = fits
        context['filter'] = filter
        context['Observatory'] = observatory
        context['data_product'] = data_product
        context['tabData'] = tabData
        context['data_stored'] = fits.data_stored

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
        t0 = time.time()
        self.check_permissions(request)
        observatory, MJD, ExpTime, dryRun, matchDist, comment = None, None, None, None, None, None
        fits_quantity = None

        try:
            observation_filter = request.data.get('filter')
        except Exception as e:
            observation_filter = None
        try:
            hashtag = request.data.get('hashtag')
            instrument = Instrument.objects.get(hashtag=hashtag)
        except Instrument.DoesNotExist:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        try:
            target = request.data.get('target')
            target_id = Target.objects.get(name=target)
        except Target.DoesNotExist:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        try:
            dp_type = request.data.get('data_product_type')
            if dp_type == 'photometry':
                dp_type = 'photometry_cpcs'
            user = User.objects.get(id=instrument.user_id.id)
            data_product_files = request.FILES.getlist("files")

            if data_product_files is None:
                return Response(status=status.HTTP_400_BAD_REQUEST)

            if dp_type == 'fits_file' or dp_type == 'photometry_cpcs':
                matchDist = request.data.get('matchDist')
                comment = request.data.get('comment')
                dryRun = request.data.get('dryRun')
                observatory = Observatory.objects.get(id=instrument.observatory_id.id)

                if matchDist is None:
                    matchDist = '0'
                if dryRun is None:
                    dryRun = 0
            if dp_type == 'photometry_cpcs':
                MJD = request.data.get('MJD')
                ExpTime = request.data.get('ExpTime')
                if MJD is None or ExpTime is None:
                    return Response(status=status.HTTP_400_BAD_REQUEST)
            if dp_type == 'fits_file':
                time_threshold = timezone.now() - timedelta(days=1)
                fits_quantity = BHTomFits.objects.filter(start_time__gte=time_threshold).count()
                fits_quantity = fits_quantity * 10
        except Exception as e:
            capture_exception(e)
            logger.error('data upload error: ' + str(e))
            return Response(status=status.HTTP_400_BAD_REQUEST)

        successful_uploads = []

       # BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        logger.info('number of files : %s' % (str(len(data_product_files))))

        for f in data_product_files:

            f.name = "{}_{}".format(user.id, f.name)

            logger.info(f.name)
            logger.info('len file presave: %s' % str(len(f)))
          #  if os.path.exists('{0}/data/{1}/none/{2}'.format(BASE, target, f.name)):
           #     messages.error(self.request, read_secret('FILE_EXIST'))
           #     logger.error('File exits: %s %s' % (str(f.name), str(target)))
           #     return Response(status=status.HTTP_201_CREATED)


            dp = DataProduct(
                target=target_id,
                data=f,
                product_id=None,
                data_product_type=dp_type
            )
            dp.save()
            logger.info('len file after save: %s' % str(len(dp.data)))
            try:
                run_hook('data_product_post_upload',
                         dp, target_id, observatory,
                         observation_filter, MJD, ExpTime,
                         dryRun, matchDist, comment,
                         user, fits_quantity,
                         hashtag=hashtag)

                run_data_processor(dp)
                successful_uploads.append(str(dp))

            except InvalidFileFormatException as iffe:
                deleteFits(dp)
                capture_exception(iffe)
                ReducedDatum.objects.filter(data_product=dp).delete()
                dp.delete()

            except Exception as e:
                deleteFits(dp)
                capture_exception(e)
                ReducedDatum.objects.filter(data_product=dp).delete()
                dp.delete()

        t1 = time.time()
        total = t1 - t0
        logger.info('time: ' + str(total))
        return Response(status=status.HTTP_201_CREATED)

    def list(self, request, *args, **kwargs):
        ret = super().list(request, *args, **kwargs)
        return ret


class result_fits(viewsets.ModelViewSet):
    queryset = BHTomFits.objects.all()
    serializer_class = BHTomFitsResultSerializer
    permission_classes = [IsAuthenticatedOrReadOnlyOrCreation]

    def create(self, request, *args, **kwargs):

        # file_id = request.data['fits_id']
        file_id = request.query_params.get('job_id')

        try:
            instance = BHTomFits.objects.get(file_id=file_id)

            if request.query_params.get('status') == 'D' or request.query_params.get('status') == 'F':
                ccdphot_result = request.FILES["ccdphot_result_upload"]

                instance.photometry_file = ccdphot_result
                instance.status = 'R'
                instance.cpcs_time = datetime.now()
                instance.status_message = 'Photometry result'
                instance.mjd = request.query_params.get('fits_mjd')
                instance.expTime = request.query_params.get('fits_exp')
                instance.ccdphot_filter = request.query_params.get('fits_filter')

                instance.save()

            else:
                ccdphot_result = request.FILES["ccdphot_result_upload"]
                instance.status = 'E'
                instance.cpcs_time = datetime.now()
                instance.photometry_file = ccdphot_result
                # if request.query_params.get('status_message'):
                #   instance.status_message = request.query_params.get('status_message')
                # else:
                instance.status_message = 'Photometry error'
                instance.save()
        except Exception as e:
            capture_exception(e)
            logger.error('result_fits error: ' + str(e))
            return HttpResponseServerError(e)

        if instance.status == 'R':
            target = Target.objects.get(id=instance.dataproduct_id.target_id)
            BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            url_base = BASE + '/data/' + format(target.name) + '/photometry/'
            url_result = os.path.join(url_base, ccdphot_result.name)
            send_to_cpcs(url_result, instance, target.extra_fields['calib_server_name'])

        return Response(status=status.HTTP_201_CREATED)

    def list(self, request, *args, **kwargs):
        ret = super().list(request, *args, **kwargs)
        return ret


'''class status_fits(viewsets.ModelViewSet):
    queryset = BHTomFits.objects.all()
    serializer_class = BHTomFitsStatusSerializer
    permission_classes = [IsAuthenticatedOrReadOnlyOrCreation]
    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            instance.status = request.TargetFileViewdata.get("status")
            instance.save()
        except Exception as e:
            logger.error('error: ' + str(e))
            return HttpResponseServerError(e)
        ret = super().update(request, *args, **kwargs)
        return ret
    def list(self, request, *args, **kwargs):
        ret = super().list(request, *args, **kwargs)
        return ret
'''


class DataProductUploadView(FormView):
    """
    View that handles manual upload of DataProducts. Requires authentication.
    """
    form_class = DataProductUploadForm

    MAX_FILES: int = 10

    def get_form_kwargs(self):
        kwargs = super(DataProductUploadView, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        """
        Runs after ``DataProductUploadForm`` is validated. Saves each ``DataProduct`` and calls ``run_data_processor``
        on each saved file. Redirects to the previous page.
        """
        t0 = time.time()
        if not self.request.user.has_perm('bhtom.add_bhtomfits'):
            logger.error('no permission to upload file: %s' % (str(target)))
            messages.error(self.request, 'You have no permission to upload file.')
            return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

        target = form.cleaned_data['target']
        if not target:
            observation_record = form.cleaned_data['observation_record']
            target = observation_record.target
        else:
            observation_record = None
        dp_type = form.cleaned_data['data_product_type']
        data_product_files = self.request.FILES.getlist('files')
        observatory = form.cleaned_data['observatory']
        observation_filter = form.cleaned_data['filter']
        MJD = form.cleaned_data['MJD']
        ExpTime = form.cleaned_data['ExpTime']
        matchDist = form.cleaned_data['matchDist']
        dryRun = form.cleaned_data['dryRun']
        comment = form.cleaned_data['comment']
        facility = form.cleaned_data['facility']
        observer = form.cleaned_data['observer']
        user = self.request.user

        if len(data_product_files) > self.MAX_FILES:
            logger.error('upload max: %s %s' % (str(f[0].name), str(target)))
            messages.error(self.request, f'You can upload max. {self.MAX_FILES} files at once')
            return redirect(form.cleaned_data.get('referrer', '/'))

        if dp_type == 'fits_file' and observatory.cpcsOnly == True:
            logger.error('observatory without ObsInfo: %s %s' % (str(f[0].name), str(target)))
            messages.error(self.request, 'Used Observatory without ObsInfo')
            return redirect(form.cleaned_data.get('referrer', '/'))

        successful_uploads = []
        logger.info(self.request.META)

        logger.info('number of files : %s' % (str(len(data_product_files))))
        #BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for f in data_product_files:
            f.name = "{}_{}".format(user.id, f.name)
            logger.info(f.name)
            logger.info('len file presave: %s' % str(len(f)))
          #  if os.path.exists('{0}/data/{1}/none/{2}'.format(BASE, target, f.name)):
          #      messages.error(self.request, read_secret('FILE_EXIST'))
           #     logger.error('File exits: %s %s' % (str(f.name), str(target)))
          #      return redirect(form.cleaned_data.get('referrer', '/'))


            dp = DataProduct(
                target=target,
                observation_record=observation_record,
                data=f,
                product_id=None,
                data_product_type=dp_type
            )
            dp.save()

            logger.info('len file after save: %s' % str(len(dp.data)))


            try:
                run_hook('data_product_post_upload',
                         dp=dp,
                         target=target,
                         observatory=observatory,
                         observation_filter=observation_filter,
                         MJD=MJD,
                         expTime=ExpTime,
                         dry_run=dryRun,
                         matchDist=matchDist,
                         comment=comment,
                         user=user,
                         facility_name=facility,
                         observer_name=observer,
                         priority=-100)

                run_data_processor(dp)

                successful_uploads.append(str(dp).split('/')[-1])
                refresh_reduced_data_view()
            except InvalidFileFormatException as iffe:
                deleteFits(dp)
                ReducedDatum.objects.filter(data_product=dp).delete()
                dp.delete()
                messages.error(
                    self.request,
                    'File format invalid for file {0} -- error was {1}'.format(str(dp), iffe)
                )
            except Exception as e:
                deleteFits(dp)
                ReducedDatum.objects.filter(data_product=dp).delete()
                dp.delete()
                logger.error(e)
                messages.error(self.request, 'There was a problem processing your file: {0}'.format(str(dp)))
        if successful_uploads:
            message: str = 'Successfully uploaded: {0}.'.format('\n'.join([p for p in successful_uploads]))
            if dp_type == 'fits_file' or dp_type == 'photometry_cpcs':
                message += 'Your file is processing. This might take several minutes'
            messages.success(
                self.request,
                message
            )
        t1 = time.time()
        total = t1 - t0
        logger.info('time: ' + str(total))
        return redirect(form.cleaned_data.get('referrer', '/'))

    def form_invalid(self, form):
        """
        Adds errors to Django messaging framework in the case of an invalid form and redirects to the previous page.
        """
        # TODO: Format error messages in a more human-readable way
        messages.error(self.request, 'There was a problem uploading your file: {}'.format(form.errors.as_json()))
        return redirect(form.cleaned_data.get('referrer', '/'))


class TargetDetailView(PermissionRequiredMixin, DetailView):
    model = Target

    def handle_no_permission(self):

        if self.request.META.get('HTTP_REFERER') is None:
            return HttpResponseRedirect('/')
        else:
            return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

    def has_permission(self):
        if not self.request.user.is_authenticated:
            messages.error(self.request, read_secret('NOT_AUTHENTICATED'))
            return False
        elif not BHTomUser.objects.get(user=self.request.user).is_activate:
            messages.error(self.request, read_secret('NOT_ACTIVATE'))
            return False
        elif not self.request.user.has_perm('tom_targets.view_target'):
            messages.error(self.request, read_secret('NOT_PERMISSION'))
            return False
        return True

    def get_context_data(self, *args, **kwargs):

        context = super().get_context_data(*args, **kwargs)

        data_product_upload_form = DataProductUploadForm(user=self.request.user,
                                                         initial={
                                                             'target': self.get_object(),
                                                             'referrer': reverse('bhlist_detail',
                                                                                 args=(self.get_object().id,))
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


class ObservatoryDetailView(PermissionRequiredMixin, DetailView):
    model = Observatory

    def handle_no_permission(self):
        if self.request.META.get('HTTP_REFERER') is None:
            return HttpResponseRedirect('/')
        else:
            return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

    def has_permission(self):
        if not self.request.user.is_authenticated:
            messages.error(self.request, read_secret('NOT_AUTHENTICATED'))
            return False
        elif not BHTomUser.objects.get(user=self.request.user).is_activate:
            messages.error(self.request, read_secret('NOT_ACTIVATE'))
            return False
        elif not self.request.user.has_perm('tom_targets.view_target'):
            messages.error(self.request, read_secret('NOT_PERMISSION'))
            return False
        return True

    # def get(self, request, *args, **kwargs):
    #     observatory_id = kwargs.get('pk', None)
    #     return redirect(reverse('observatory_detail', args=(observatory_id,)))


class TargetDownloadDataView(ABC, PermissionRequiredMixin, View):
    permission_required = 'tom_dataproducts.add_dataproduct'

    @abstractmethod
    def generate_data_method(self, target_id):
        pass

    def get(self, request, *args, **kwargs):
        import os
        from django.http import FileResponse

        target_id: int = kwargs.get('pk', None)
        logger.info(f'Generating photometry CSV file for target with id={target_id}...')

        tmp = None
        try:
            tmp, filename = self.generate_data_method(target_id)
            return FileResponse(open(tmp.name, 'rb'),
                                as_attachment=True,
                                filename=filename)
        except Exception as e:
            capture_exception(e)
            logger.error(f'Error while generating photometry CSV file for target with id={target_id}: {e}')
        finally:
            if tmp:
                os.remove(tmp.name)


class TargetDownloadPhotometryDataView(TargetDownloadDataView):
    def generate_data_method(self, target_id):
        return save_photometry_data_for_target_to_csv_file(target_id)


class TargetDownloadPhotometryStatsView(TargetDownloadDataView):
    def generate_data_method(self, target_id):
        return get_photometry_data_stats(target_id)


class TargetDownloadPhotometryStatsLatexTableView(TargetDownloadDataView):
    def generate_data_method(self, target_id):
        return get_photometry_stats_latex(target_id)


class TargetDownloadSpectroscopyDataView(TargetDownloadDataView):
    def generate_data_method(self, target_id):
        return save_spectroscopy_data_for_target_to_csv_file(target_id)


class TargetInteractivePhotometryView(PermissionRequiredMixin, DetailView):
    template_name = 'tom_targets/target_interactive_photometry.html'
    model = Target

    def handle_no_permission(self):

        if self.request.META.get('HTTP_REFERER') is None:
            return HttpResponseRedirect('/')
        else:
            return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

    def has_permission(self):
        if not self.request.user.is_authenticated:
            messages.error(self.request, read_secret('NOT_AUTHENTICATED'))
            return False
        elif not BHTomUser.objects.get(user=self.request.user).is_activate:
            messages.error(self.request, read_secret('NOT_ACTIVATE'))
            return False
        elif not self.request.user.has_perm('tom_targets.view_target'):
            messages.error(self.request, read_secret('NOT_PERMISSION'))
            return False
        return True


class TargetInteractiveDeletingPhotometryView(PermissionRequiredMixin, DetailView):
    template_name = 'tom_targets/target_interactive_deleting_photometry.html'
    model = Target

    def handle_no_permission(self):

        if self.request.META.get('HTTP_REFERER') is None:
            return HttpResponseRedirect('/')
        else:
            return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

    def has_permission(self):
        if not self.request.user.is_authenticated:
            messages.error(self.request, read_secret('NOT_AUTHENTICATED'))
            return False
        elif not BHTomUser.objects.get(user=self.request.user).is_activate:
            messages.error(self.request, read_secret('NOT_ACTIVATE'))
            return False
        elif not self.request.user.has_perm('tom_targets.view_target'):
            messages.error(self.request, read_secret('NOT_PERMISSION'))
            return False
        return True

    def get(self, request, *args, **kwargs):
        context = {'dash_context': {'target_id': {'value': kwargs.get('pk', -1)},
                                    'user_id': {'value': self.request.user.id}}}
        return self.render_to_response(context)


class TargetMicrolensingView(PermissionRequiredMixin, DetailView):
    template_name = 'tom_targets/target_microlensing.html'
    model = Target

    def get(self, request, *args, **kwargs):
        if request.GET.get('clevel', ''):
            clevel = request.GET.get('clevel', '')
            slevel = request.GET.get('slevel', '')
        else:
            clevel = str(0.05)
            slevel = str(0.05)
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        context['clevel'] = clevel
        context['slevel'] = slevel
        return self.render_to_response(context)

    def handle_no_permission(self):

        if self.request.META.get('HTTP_REFERER') is None:
            return HttpResponseRedirect('/')
        else:
            return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

    def has_permission(self):
        if not self.request.user.is_authenticated:
            messages.error(self.request, read_secret('NOT_AUTHENTICATED'))
            return False
        elif not BHTomUser.objects.get(user=self.request.user).is_activate:
            messages.error(self.request, read_secret('NOT_ACTIVATE'))
            return False
        elif not self.request.user.has_perm('tom_targets.view_target'):
            messages.error(self.request, read_secret('NOT_PERMISSION'))
            return False
        return True


class CreateInstrument(PermissionRequiredMixin, FormView):
    """
    View that handles manual upload of DataProducts. Requires authentication.
    """

    template_name = 'tom_common/instrument_create.html'
    form_class = InstrumentCreationForm
    success_url = reverse_lazy('observatory')

    def handle_no_permission(self):

        if self.request.META.get('HTTP_REFERER') is None:
            return HttpResponseRedirect('/')
        else:
            return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

    def has_permission(self):
        if not self.request.user.is_authenticated:
            messages.error(self.request, read_secret('NOT_AUTHENTICATED'))
            return False
        elif not BHTomUser.objects.get(user=self.request.user).is_activate:
            messages.error(self.request, read_secret('NOT_ACTIVATE'))
            return False
        elif not self.request.user.has_perm('bhtom.add_instrument'):
            messages.error(self.request, read_secret('NOT_PERMISSION'))
            return False
        return True

    def get_form_kwargs(self):
        kwargs = super(CreateInstrument, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):

        user = self.request.user
        observatoryID = form.cleaned_data['observatory']
        comment = form.cleaned_data['comment']

        try:
            instrument = Instrument.objects.create(
                user_id=user,
                observatory_id=observatoryID,
                isActive=True,
                comment=comment
            )
            # instrument.save()

            logger.info('Send mail, %s, %s' % (observatoryID.obsName, str(user)))
            send_mail('Stworzono nowy instrument',
                      read_secret('EMAILTEXT_CREATE_INSTRUMENT') + str(user) + ', ' + observatoryID.obsName,
                      settings.EMAIL_HOST_USER, read_secret('RECIPIENTEMAIL'), fail_silently=False)

        except Exception as e:
            capture_exception(e)
            logger.error('CreateInstrument error: ' + str(e))
            messages.error(self.request, 'Error with creating the instrument')
            instrument.delete()
            return redirect(self.get_success_url())

        messages.success(self.request, 'Successfully created')
        return redirect(self.get_success_url())


class DeleteInstrument(PermissionRequiredMixin, DeleteView):
    success_url = reverse_lazy('observatory')
    model = Instrument
    template_name = 'tom_common/instrument_delete.html'

    def handle_no_permission(self):

        if self.request.META.get('HTTP_REFERER') is None:
            return HttpResponseRedirect('/')
        else:
            return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

    def has_permission(self):
        if not self.request.user.is_authenticated:
            messages.error(self.request, read_secret('NOT_AUTHENTICATED'))
            return False
        elif not BHTomUser.objects.get(user=self.request.user).is_activate:
            messages.error(self.request, read_secret('NOT_ACTIVATE'))
            return False
        elif not self.request.user.has_perm('bhtom.delete_instrument'):
            messages.error(self.request, read_secret('NOT_PERMISSION'))
            return False
        return True

    def get_object(self, queryset=None):
        obj = super(DeleteInstrument, self).get_object()
        return obj

    @transaction.atomic
    def form_valid(self, form):
        super().form_valid(form)
        messages.success(self.request, 'Successfully delete')
        return redirect(self.get_success_url())


class UpdateInstrument(PermissionRequiredMixin, UpdateView):
    template_name = 'tom_common/instrument_create.html'
    form_class = InstrumentUpdateForm
    success_url = reverse_lazy('observatory')
    model = Instrument

    def handle_no_permission(self):

        if self.request.META.get('HTTP_REFERER') is None:
            return HttpResponseRedirect('/')
        else:
            return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

    def has_permission(self):
        if not self.request.user.is_authenticated:
            messages.error(self.request, read_secret('NOT_AUTHENTICATED'))
            return False
        elif not BHTomUser.objects.get(user=self.request.user).is_activate:
            messages.error(self.request, read_secret('NOT_ACTIVATE'))
            return False
        elif not self.request.user.has_perm('bhtom.change_instrument'):
            messages.error(self.request, read_secret('NOT_PERMISSION'))
            return False
        return True

    @transaction.atomic
    def form_valid(self, form):
        super().form_valid(form)
        messages.success(self.request, 'Successfully updated')
        return redirect(self.get_success_url())


class CreateObservatory(PermissionRequiredMixin, FormView):
    template_name = 'tom_common/observatory_create.html'
    form_class = ObservatoryCreationForm
    success_url = reverse_lazy('observatory')

    def handle_no_permission(self):

        if self.request.META.get('HTTP_REFERER') is None:
            return HttpResponseRedirect('/')
        else:
            return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

    def has_permission(self):
        if not self.request.user.is_authenticated:
            messages.error(self.request, read_secret('NOT_AUTHENTICATED'))
            return False
        elif not BHTomUser.objects.get(user=self.request.user).is_activate:
            messages.error(self.request, read_secret('NOT_ACTIVATE'))
            return False
        elif not self.request.user.has_perm('bhtom.add_observatory'):
            messages.error(self.request, read_secret('NOT_PERMISSION'))
            return False
        return True

    def form_valid(self, form):

        try:
            # super().form_valid(form)

            user = self.request.user

            obsName = form.cleaned_data['obsName']
            lon = form.cleaned_data['lon']
            lat = form.cleaned_data['lat']
            matchDist = form.cleaned_data['matchDist']
            cpcsOnly = form.cleaned_data['cpcsOnly']

            fits = self.request.FILES.get('fits')
            obsInfo = self.request.FILES.get('obsInfo')
            if cpcsOnly is True:
                prefix = obsName + "_CpcsOnly"
            else:
                prefix = obsName

            gain = form.cleaned_data['gain']

            readout_noise = form.cleaned_data['readout_noise']
            binning = form.cleaned_data['binning']
            saturation_level = form.cleaned_data['saturation_level']
            pixel_scale = form.cleaned_data['pixel_scale']
            readout_speed = form.cleaned_data['readout_speed']
            pixel_size = form.cleaned_data['pixel_size']
            approx_lim_mag = form.cleaned_data['approx_lim_mag']
            filters = form.cleaned_data['filters']
            comment = form.cleaned_data['comment']

            observatory = Observatory.objects.create(
                obsName=obsName,
                lon=lon,
                lat=lat,
                matchDist=matchDist,
                isVerified=False,
                prefix=prefix,
                cpcsOnly=cpcsOnly,
                fits=fits,
                obsInfo=obsInfo,
                user=user,
                gain=gain,
                readout_noise=readout_noise,
                binning=binning,
                saturation_level=saturation_level,
                pixel_scale=pixel_scale,
                readout_speed=readout_speed,
                pixel_size=pixel_size,
                approx_lim_mag=approx_lim_mag,
                filters=filters,
                comment=comment
            )

            observatory.save()
            logger.info('Send mail, create new obserwatory:  %s' % str(obsName))
            send_mail('Stworzono nowe obserwatorium', read_secret('EMAILTEXT_CREATE_OBSERVATORY') + str(obsName),
                      settings.EMAIL_HOST_USER,
                      read_secret('RECIPIENTEMAIL'), fail_silently=False)
        except Exception as e:
            logger.error('CreateObservatory error: ' + str(e))
            messages.error(self.request, 'Error with creating the instrument %s' % obsName)
            observatory.delete()
            return redirect(self.get_success_url())
        messages.success(self.request, 'Successfully created %s' % obsName)
        return redirect(self.get_success_url())


class ObservatoryList(PermissionRequiredMixin, ListView):
    template_name = 'tom_common/observatory_list.html'
    model = Observatory
    strict = False

    def handle_no_permission(self):

        if self.request.META.get('HTTP_REFERER') is None:
            return HttpResponseRedirect('/')
        else:
            return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

    def has_permission(self):
        if not self.request.user.is_authenticated:
            messages.error(self.request, read_secret('NOT_AUTHENTICATED'))
            return False
        elif not BHTomUser.objects.get(user=self.request.user).is_activate:
            messages.error(self.request, read_secret('NOT_ACTIVATE'))
            return False
        elif not self.request.user.has_perm('bhtom.view_observatory'):
            messages.error(self.request, read_secret('NOT_PERMISSION'))
            return False
        return True

    def get_context_data(self, *args, **kwargs):

        context = super().get_context_data(*args, **kwargs)
        instrument = Instrument.objects.filter(user_id=self.request.user).order_by('observatory_id__obsName')

        observatory_user_list = []
        for ins in instrument:
            observatory_user_list.append(
                [ins.id, ins.hashtag, ins.isActive, ins.comment, Observatory.objects.get(id=ins.observatory_id.id)])

        context['observatory_list'] = Observatory.objects.filter(isVerified=True).order_by('obsName')
        context['observatory_user_list'] = observatory_user_list

        return context


class UpdateObservatory(PermissionRequiredMixin, UpdateView):
    template_name = 'tom_common/observatory_create.html'
    form_class = ObservatoryUpdateForm
    success_url = reverse_lazy('observatory')
    model = Observatory

    def handle_no_permission(self):

        if self.request.META.get('HTTP_REFERER') is None:
            return HttpResponseRedirect('/')
        else:
            return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

    def has_permission(self):
        if not self.request.user.is_authenticated:
            messages.error(self.request, read_secret('NOT_AUTHENTICATED'))
            return False
        elif not BHTomUser.objects.get(user=self.request.user).is_activate:
            messages.error(self.request, read_secret('NOT_ACTIVATE'))
            return False
        elif not self.request.user.has_perm('bhtom.change_observatory'):
            messages.error(self.request, read_secret('NOT_PERMISSION'))
            return False
        return True

    @transaction.atomic
    def form_valid(self, form):
        super().form_valid(form)
        messages.success(self.request, 'Successfully updated %s' % form.cleaned_data['obsName'])
        return redirect(self.get_success_url())


class DeleteObservatory(PermissionRequiredMixin, DeleteView):
    success_url = reverse_lazy('observatory')
    model = Observatory
    template_name = 'tom_common/observatory_delete.html'

    def handle_no_permission(self):

        if self.request.META.get('HTTP_REFERER') is None:
            return HttpResponseRedirect('/')
        else:
            return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

    def has_permission(self):
        if not self.request.user.is_authenticated:
            messages.error(self.request, read_secret('NOT_AUTHENTICATED'))
            return False
        elif not BHTomUser.objects.get(user=self.request.user).is_activate:
            messages.error(self.request, read_secret('NOT_ACTIVATE'))
            return False
        elif not self.request.user.has_perm('bhtom.delete_observatory'):
            messages.error(self.request, read_secret('NOT_PERMISSION'))
            return False
        return True

    def get_object(self, queryset=None):

        obj = super(DeleteObservatory, self).get_object()
        return obj

    @transaction.atomic
    def form_valid(self, form):
        super().form_valid(form)
        messages.success(self.request, 'Successfully delete')
        return redirect(self.get_success_url())


class RegisterUser(CreateView):
    template_name = 'tom_common/register_user.html'
    success_url = reverse_lazy('home')
    form_class = CustomUserCreationForm

    def form_valid(self, form):

        super().form_valid(form)
        group, _ = Group.objects.get_or_create(name='Public')
        #this does not work!
        # group, _ = Group.objects.get_or_create(name='Show Targets')
        # group, _ = Group.objects.get_or_create(name='Upload File')
        # group, _ = Group.objects.get_or_create(name='Download Fits/Photometry')
        # group, _ = Group.objects.get_or_create(name='Add Target')
        # group, _ = Group.objects.get_or_create(name='Add Observatory')
        
        group.user_set.add(self.object)
        group.save()
        email_params = "'{0}', '{1}', '{2}', '{3}'".format(self.object.username, self.object.first_name,
                                                           self.object.last_name, self.object.email)

        try:
            send_mail(settings.EMAILTEXT_REGISTEADMIN_TITLE, settings.EMAILTEXT_REGISTEADMIN + email_params,
                      settings.EMAIL_HOST_USER,
                      settings.RECIPIENTEMAIL, fail_silently=False)

            send_mail(settings.EMAILTEXT_REGISTEUSER_TITLE, settings.EMAILTEXT_REGISTEUSER, settings.EMAIL_HOST_USER,
                      [self.object.email], fail_silently=False)
        except Exception as e:
            logger.error(f'Exception when sending registration confirmation: {e}')

        messages.success(self.request, settings.SUCCESSFULLY_REGISTERED)
        return redirect(self.get_success_url())


class UserUpdateView(LoginRequiredMixin, UpdateView):
    model = User
    success_url = reverse_lazy('home')
    template_name = 'tom_common/register_user.html'
    form_class = CustomUserCreationForm

    def get_success_url(self):

        if self.request.user.is_superuser:
            return reverse_lazy('user-list')
        else:
            return reverse_lazy('user-update', kwargs={'pk': self.request.user.id})

    def get_form(self):

        form = super().get_form()
        form.fields['password1'].required = False
        form.fields['password2'].required = False
        if not self.request.user.is_superuser:
            try:
                form.fields.pop('groups')
            except KeyError:
                logger.error(f'Tried to pop groups for user with id {self.request.user.id}')
        return form

    def dispatch(self, *args, **kwargs):

        if not self.request.user.is_superuser and self.request.user.id != self.kwargs['pk']:
            return redirect('user-update', self.request.user.id)
        else:
            return super().dispatch(*args, **kwargs)

    def form_valid(self, form):

        super().form_valid(form)
        if self.get_object() == self.request.user:
            update_session_auth_hash(self.request, self.object)
        messages.success(self.request, 'Profile updated')
        return redirect(self.get_success_url())


class DataProductFeatureView(View):
    """
    View that handles the featuring of ``DataProduct``s. A featured ``DataProduct`` is displayed on the
    ``TargetDetailView``.
    """

    def get(self, request, *args, **kwargs):
        """
        Method that handles the GET requests for this view. Sets all other ``DataProduct``s to unfeatured in the
        database, and sets the specified ``DataProduct`` to featured. Caches the featured image. Deletes previously
        featured images from the cache.
        """
        product_id = kwargs.get('pk', None)
        product = DataProduct.objects.get(pk=product_id)
        try:
            current_featured = DataProduct.objects.filter(
                featured=True,
                data_product_type=product.data_product_type,
                target=product.target
            )
            for featured_image in current_featured:
                featured_image.featured = False
                featured_image.save()
                featured_image_cache_key = make_template_fragment_key(
                    'featured_image',
                    str(featured_image.target.id)
                )
                cache.delete(featured_image_cache_key)
        except DataProduct.DoesNotExist:
            pass
        product.featured = True
        product.save()
        return redirect(reverse(
            'bhlist_detail',
            kwargs={'pk': request.GET.get('target_id')})
        )


class TargetGroupingView(PermissionRequiredMixin, ListView):

    def handle_no_permission(self):

        if self.request.META.get('HTTP_REFERER') is None:
            return HttpResponseRedirect('/')
        else:
            return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

    def has_permission(self):
        if not self.request.user.is_authenticated:
            messages.error(self.request, read_secret('NOT_AUTHENTICATED'))
            return False
        elif not BHTomUser.objects.get(user=self.request.user).is_activate:
            messages.error(self.request, read_secret('NOT_ACTIVATE'))
            return False
        elif not self.request.user.has_perm('tom_targets.view_targetlist'):
            messages.error(self.request, read_secret('NOT_PERMISSION'))
            return False
        return True

    template_name = 'tom_targets/target_grouping.html'
    model = TargetList
    paginate_by = 25


class DataProductDeleteView(PermissionRequiredMixin, DeleteView):
    model = DataProduct
    template_name = 'tom_dataproducts/data_delete.html'

    def handle_no_permission(self):

        if self.request.META.get('HTTP_REFERER') is None:
            return HttpResponseRedirect('/')
        else:
            return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

    def has_permission(self):
        if not self.request.user.is_authenticated:
            messages.error(self.request, read_secret('NOT_AUTHENTICATED'))
            return False
        elif not BHTomUser.objects.get(user=self.request.user).is_activate:
            messages.error(self.request, read_secret('NOT_ACTIVATE'))
            return False
        elif not self.request.user.has_perm('tom_dataproducts.delete_dataproduct'):
            messages.error(self.request, read_secret('NOT_PERMISSION'))
            return False
        return True

    def get_object(self, queryset=None):

        obj = super(DataProductDeleteView, self).get_object()
        return obj

    def get_context_data(self, *args, **kwargs):

        context = super().get_context_data(*args, **kwargs)
        obj = super(DataProductDeleteView, self).get_object()
        context['dataName'] = format(obj.data).split('/')[-1]

        return context

    def get_success_url(self):
        messages.success(self.request, 'Successfully delete')
        return reverse_lazy('bhlist_detail', kwargs={'pk': self.kwargs['pk_target']})

    def delete(self, request, *args, **kwargs):
        logger.info('Delete File, type: ' + self.get_object().data_product_type)
        if self.get_object().data_product_type == 'photometry_cpcs' or self.get_object().data_product_type == 'fits_file':
            fit = BHTomFits.objects.get(dataproduct_id=self.get_object())
            logger.info('status: ' + fit.status)
            if fit.status == 'F':
                delete_point_cpcs(self.get_object())
        ReducedDatum.objects.filter(data_product=self.get_object()).delete()
        deleteFits(self.get_object())
        self.get_object().data.delete()

        return super().delete(request, *args, **kwargs)


class fits_download(PermissionRequiredMixin, View):

    def handle_no_permission(self):
        if self.request.META.get('HTTP_REFERER') is None:
            return HttpResponseRedirect('/')
        else:
            return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

    def has_permission(self):
        if not self.request.user.is_authenticated:
            messages.error(self.request, read_secret('NOT_AUTHENTICATED'))
            return False
        elif not BHTomUser.objects.get(user=self.request.user).is_activate:
            messages.error(self.request, read_secret('NOT_ACTIVATE'))
            return False
        elif not self.request.user.has_perm('tom_dataproducts.view_dataproduct'):
            messages.error(self.request, read_secret('NOT_PERMISSION'))
            return False
        elif self.request.user != BHTomFits.objects.get(dataproduct_id=self.kwargs['file_id']).instrument_id.user_id \
                and not self.request.user.is_staff:
            messages.error(self.request, read_secret('NOT_PERMISSION'))
            return False
        return True

    def get(self, request, *args, **kwargs):
        try:
            file = DataProduct.objects.get(pk=self.kwargs['file_id'])
        except DataProduct.DoesNotExist:
            if self.request.META.get('HTTP_REFERER') is None:
                return HttpResponseRedirect('/')
            else:
                return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

        if file.data:
            address = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/data/' + format(file.data)
            return FileResponse(open(address, 'rb'), as_attachment=True)
        else:
            if self.request.META.get('HTTP_REFERER') is None:
                return HttpResponseRedirect('/')
            else:
                return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))


class photometry_download(PermissionRequiredMixin, View):

    def handle_no_permission(self):
        if self.request.META.get('HTTP_REFERER') is None:
            return HttpResponseRedirect('/')
        else:
            return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

    def has_permission(self):
        if not self.request.user.is_authenticated:
            messages.error(self.request, read_secret('NOT_AUTHENTICATED'))
            return False
        elif not BHTomUser.objects.get(user=self.request.user).is_activate:
            messages.error(self.request, read_secret('NOT_ACTIVATE'))
            return False
        elif not self.request.user.has_perm('tom_dataproducts.view_dataproduct'):
            messages.error(self.request, read_secret('NOT_PERMISSION'))
            return False
        elif self.request.user != BHTomFits.objects.get(file_id=self.kwargs['file_id']).instrument_id.user_id \
                and not self.request.user.is_staff:
            messages.error(self.request, read_secret('NOT_PERMISSION'))
            return False
        return True

    def get(self, request, *args, **kwargs):
        try:
            file = BHTomFits.objects.get(file_id=self.kwargs['file_id'])
        except DataProduct.DoesNotExist:
            if self.request.META.get('HTTP_REFERER') is None:
                return HttpResponseRedirect('/')
            else:
                return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

        if file.photometry_file:
            address = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/data/' + format(
                file.photometry_file)
            logger.info('Photometry download address: ' + address)
            try:
                open(address, 'r')
            except IOError:
                address = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/' + format(
                    file.photometry_file)
            return FileResponse(open(address, 'rb'), as_attachment=True)
        else:
            if self.request.META.get('HTTP_REFERER') is None:
                return HttpResponseRedirect('/')
            else:
                return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))


class data_download(PermissionRequiredMixin, View):

    def handle_no_permission(self):
        if self.request.META.get('HTTP_REFERER') is None:
            return HttpResponseRedirect('/')
        else:
            return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

    def has_permission(self):
        if not self.request.user.is_authenticated:
            messages.error(self.request, read_secret('NOT_AUTHENTICATED'))
            return False
        elif not BHTomUser.objects.get(user=self.request.user).is_activate:
            messages.error(self.request, read_secret('NOT_ACTIVATE'))
            return False
        elif not self.request.user.has_perm('tom_dataproducts.view_dataproduct'):
            messages.error(self.request, read_secret('NOT_PERMISSION'))
            return False
        elif self.request.user != BHTomData.objects.get(dataproduct_id=self.kwargs['file_id']).user_id \
                and not self.request.user.is_staff:
            messages.error(self.request, read_secret('NOT_PERMISSION'))
            return False
        return True

    def get(self, request, *args, **kwargs):
        try:
            file = DataProduct.objects.get(pk=self.kwargs['file_id'])
        except DataProduct.DoesNotExist:
            if self.request.META.get('HTTP_REFERER') is None:
                return HttpResponseRedirect('/')
            else:
                return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))

        if file.data:
            address = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/data/' + format(file.data)
            return FileResponse(open(address, 'rb'), as_attachment=True)
        else:
            if self.request.META.get('HTTP_REFERER') is None:
                return HttpResponseRedirect('/')
            else:
                return HttpResponseRedirect(self.request.META.get('HTTP_REFERER'))


class CommentDeleteView(LoginRequiredMixin, DeleteView):
    """
    View that handles deletion of a ``Comment``. Requires authentication to call, and authorization to delete.
    """
    model = Comment
    template_name = 'tom_common/partials/comment_confirm_delete.html'

    def get_success_url(self):
        messages.success(self.request, 'Successfully delete')
        return reverse_lazy('bhlist_detail', kwargs={'pk': self.kwargs['pk_target']})

    def delete(self, request, *args, **kwargs):

        if request.user == self.get_object().user or request.user.is_superuser:
            return super().delete(request, *args, **kwargs)
        else:
            return HttpResponseForbidden('Not authorized')


class TargetAddRemoveGroupingView(LoginRequiredMixin, View):
    """
    View that handles addition and removal of targets to target groups. Requires authentication.
    """

    def post(self, request, *args, **kwargs):
        """
        Handles the POST requests to this view. Routes the information from the request and query parameters to the
        appropriate utility method in ``groups.py``.

        :param request: the request object passed to this view
        :type request: HTTPRequest
        """

        query_string = request.POST.get('query_string', '')
        grouping_id = request.POST.get('grouping')
        filter_data = QueryDict(query_string)

        try:
            grouping_object = TargetList.objects.get(pk=grouping_id)
        except Exception as e:
            capture_exception(e)
            messages.error(request, 'Cannot find the target group with id={}; {}'.format(grouping_id, e))
            return redirect(reverse('bhlist'))
        if not request.user.has_perm('tom_targets.view_targetlist', grouping_object):
            messages.error(request, 'Permission denied.')
            return redirect(reverse('bhlist'))

        if 'add' in request.POST:
            if request.POST.get('isSelectAll') == 'True':
                add_all_to_grouping(filter_data, grouping_object, request)
            else:
                targets_ids = request.POST.getlist('selected-target')
                add_selected_to_grouping(targets_ids, grouping_object, request)
        if 'remove' in request.POST:
            if request.POST.get('isSelectAll') == 'True':
                remove_all_from_grouping(filter_data, grouping_object, request)
            else:
                targets_ids = request.POST.getlist('selected-target')
                remove_selected_from_grouping(targets_ids, grouping_object, request)
        return redirect(reverse('bhlist'))
