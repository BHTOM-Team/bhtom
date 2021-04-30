from django import forms
from django.conf import settings

from tom_targets.models import Target
from tom_observations.models import ObservationRecord
from bhtom.models import Observatory, Instrument, Catalogs, BHTomUser
from django.contrib.auth.models import User, Group
from django.contrib.auth.forms import UserCreationForm, UsernameField

from astropy.coordinates import Angle
from astropy import units as u
from django.forms import ValidationError, inlineformset_factory
from guardian.shortcuts import assign_perm, get_groups_with_perms, remove_perm

from tom_targets.models import (
    Target, TargetExtra, TargetName, SIDEREAL_FIELDS, NON_SIDEREAL_FIELDS, REQUIRED_SIDEREAL_FIELDS,
    REQUIRED_NON_SIDEREAL_FIELDS, REQUIRED_NON_SIDEREAL_FIELDS_PER_SCHEME
)

from captcha.fields import ReCaptchaField

import logging
logger = logging.getLogger(__name__)

class ObservatoryChoiceField(forms.ModelChoiceField):

    def label_from_instance(self, obj):
        if obj.cpcsOnly == True:
            return '{obsName} (Only Instrumental photometry file)'.format(obsName=obj.obsName)
        else:
            return '{obsName}'.format(obsName=obj.obsName)

class FilterChoiceField(forms.ModelChoiceField):

    def label_from_instance(self, obj):

        name = obj.name
        filters = obj.filters
        hash = {}
        for v, f in enumerate(filters):
            hash[v] = name + '/' + f

        return hash

class DataProductUploadForm(forms.Form):

    MATCHING_RADIUS = [
        ('0', 'Default for the Observatory'),
        ('1', '1 arcsec'),
        ('2', '2 arcsec'),
        ('4', '4 arcsec'),
        ('6', '6 arcsec')
    ]

    observation_record = forms.ModelChoiceField(
        ObservationRecord.objects.all(),
        widget=forms.HiddenInput(),
        required=False
    )
    target = forms.ModelChoiceField(
        Target.objects.all(),
        widget=forms.HiddenInput(),
        required=False
    )

    files = forms.FileField(
        widget=forms.ClearableFileInput(
            attrs={'multiple': True}
        )
     )

    data_product_type = forms.ChoiceField(
        choices=[v for k, v in settings.DATA_PRODUCT_TYPES.items()],
        initial='photometry_cpcs',
        widget=forms.RadioSelect(attrs={'onclick' : "dataProductSelect();"}),
        required=True
    )

    MJD = forms.DecimalField(
        label="MJD OBS",
        widget=forms.NumberInput(attrs={'id': 'mjd', 'disable': 'none'}),
        required=False
    )

    ExpTime = forms.IntegerField(
        label='Exposure time (sec)',
        widget=forms.NumberInput(attrs={'id': 'ExpTime'}),
        required=False
    )

    matchDist = forms.ChoiceField(
        choices=MATCHING_RADIUS,
        widget=forms.Select(),
        label='Matching radius',
        initial='0',
        required=False
    )

    dryRun = forms.BooleanField(
        label='Dry Run (no data will be stored in the database)',
        required=False
    )

    referrer = forms.CharField(
        widget=forms.HiddenInput()
    )

    observer = forms.CharField(
        label='Observer\'s Name',
        required=False
    )

    facility = forms.CharField(
        label='Facility Name'
    )

    def __init__(self, *args, **kwargs):

        user = kwargs.pop('user')
        filter = {}
        filter['no'] = 'Auto'
        catalogs = Catalogs.objects.all().values_list('name', 'filters')
        for curval in catalogs:
            curname, filters = curval
            for i, f in enumerate(filters):
                filter[curname + '/' + f] = curname + '/' + f

        super(DataProductUploadForm, self).__init__(*args, **kwargs)

        instrument = Instrument.objects.filter(user_id=user)
        insTab = []

        for ins in instrument:
            insTab.append(ins.observatory_id.id)

        self.fields['observatory'] = ObservatoryChoiceField(

            queryset=Observatory.objects.filter(id__in=insTab, isVerified=True),
            widget=forms.Select(),
            required=False
        )

        self.fields['filter'] = forms.ChoiceField(
            choices=[v for v in filter.items()],
            widget=forms.Select(),
            required=False,
            label='Force filter'
        )

        self.fields['comment'] = forms.CharField(
            widget=forms.Textarea,
            required=False,
            label='Comment',
        )

        self.fields['observer'].initial = f'{user.first_name} {user.last_name}'

class ObservatoryCreationForm(forms.ModelForm):

    cpcsOnly = forms.BooleanField(
        label='Only instrumental photometry file',
        required=False
    )

    class Meta:
        model = Observatory
        fields = ('obsName', 'lon', 'lat', 'matchDist', 'cpcsOnly', 'fits', 'obsInfo', 'comment')

class ObservatoryUpdateForm(forms.ModelForm):

    cpcsOnly = forms.BooleanField(
        label='Only instrumental photometry file',
        required=False
    )

    class Meta:
        model = Observatory
        fields = ('obsName', 'lon', 'lat', 'matchDist', 'prefix', 'cpcsOnly', 'fits', 'obsInfo', 'comment')

class InstrumentUpdateForm(forms.ModelForm):

    class Meta:
        model = Instrument
        fields = ('comment',)

class InstrumentCreationForm(forms.Form):

    observatory = forms.ChoiceField()

    comment = forms.CharField(
        widget=forms.Textarea,
        label="Comment",
        required=False
    )

    def __init__(self, *args, **kwargs):

        user = kwargs.pop('user')
        super(InstrumentCreationForm, self).__init__(*args, **kwargs)

        instrument = Instrument.objects.filter(user_id=user)
        insTab = []
        for ins in instrument:
            insTab.append(ins.observatory_id.id)

        self.fields['observatory'] = ObservatoryChoiceField(

            queryset=Observatory.objects.exclude(id__in=insTab).filter(isVerified=True).order_by('obsName'),
            widget=forms.Select(),
            required=True
        )

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    groups = forms.ModelMultipleChoiceField(Group.objects.all().exclude(name='Public'),
                                            required=False, widget=forms.CheckboxSelectMultiple)
    latex_name = forms.CharField(required=False)
    latex_affiliation = forms.CharField(required=False)
    address = forms.CharField(required=False)
    about_me = forms.CharField(
        widget=forms.Textarea,
        label="About_me",
        required=False
    )

    #captcha = ReCaptchaField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = "Login*"
        self.fields['email'].label = "Email*"
        self.fields['password1'].label = "Password*"
        self.fields['password2'].label = "Password confirmation*"

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'latex_name', 'latex_affiliation',
                  'address', 'password1', 'password2', 'groups', 'about_me')
        field_classes = {'username': UsernameField}

    def save(self, commit=True):
        user = super(forms.ModelForm, self).save(commit=False)
        if self.cleaned_data['password1']:
            user.set_password(self.cleaned_data["password1"])
        if commit:
            user.is_active = True
            user.save()
            self.save_m2m()

            dp, created = BHTomUser.objects.get_or_create(user=user)
            dp.user = user
            dp.latex_name = self.cleaned_data['latex_name']
            dp.latex_affiliation = self.cleaned_data['latex_affiliation']
            dp.address = self.cleaned_data['address']
            dp.about_me = self.cleaned_data['about_me']

            logger.info("Update/create user: %s" % user.username)
            if created:
                dp.is_activate = False

            dp.save()

        return user

def extra_field_to_form_field(field_type):
    if field_type == 'number':
        return forms.FloatField(required=False)
    elif field_type == 'boolean':
        return forms.BooleanField(required=False)
    elif field_type == 'datetime':
        return forms.DateTimeField(required=False)
    elif field_type == 'string':
        return forms.CharField(required=False, widget=forms.Textarea)
    else:
        raise ValueError(
            'Invalid field type {}. Field type must be one of: number, boolean, datetime string'.format(field_type)
        )

class CoordinateField(forms.CharField):
    def __init__(self, *args, **kwargs):
        c_type = kwargs.pop('c_type')
        self.c_type = c_type
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        try:
            a = float(value)
            return a
        except ValueError:
            try:
                if self.c_type == 'ra':
                    a = Angle(value, unit=u.hourangle)
                else:
                    a = Angle(value, unit=u.degree)
                return a.to(u.degree).value
            except Exception:
                raise ValidationError('Invalid format. Please use sexigesimal or degrees')


class TargetForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.extra_fields = {}
        for extra_field in settings.EXTRA_FIELDS:
            # Add extra fields to the form
            field_name = extra_field['name']
            self.extra_fields[field_name] = extra_field_to_form_field(extra_field['type'])
            # Populate them with initial values if this is an update
            if kwargs['instance']:
                te = TargetExtra.objects.filter(target=kwargs['instance'], key=field_name)
                if te.exists():
                    self.extra_fields[field_name].initial = te.first().typed_value(extra_field['type'])

            self.fields.update(self.extra_fields)

    def save(self, commit=True):
        instance = super().save(commit=commit)
        if commit:
            for field in settings.EXTRA_FIELDS:
                if self.cleaned_data.get(field['name']) is not None:
                    TargetExtra.objects.update_or_create(
                            target=instance,
                            key=field['name'],
                            defaults={'value': self.cleaned_data[field['name']]}
                    )

        return instance

    class Meta:
        abstract = True
        model = Target
        fields = '__all__'
        widgets = {'type': forms.HiddenInput()}


class SiderealTargetCreateForm(TargetForm):
    ra = CoordinateField(required=True, label='Right Ascension', c_type='ra',
                         help_text='Right Ascension, in decimal degrees or sexagesimal hours. See '
                                   'https://docs.astropy.org/en/stable/api/astropy.coordinates.Angle.html for '
                                   'supported sexagesimal inputs.')
    dec = CoordinateField(required=True, label='Declination', c_type='dec',
                          help_text='Declination, in decimal or sexagesimal degrees. See '
                                    ' https://docs.astropy.org/en/stable/api/astropy.coordinates.Angle.html for '
                                    'supported sexagesimal inputs.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in REQUIRED_SIDEREAL_FIELDS:
            self.fields[field].required = True

    class Meta(TargetForm.Meta):
        fields = SIDEREAL_FIELDS

class NonSiderealTargetCreateForm(TargetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in REQUIRED_NON_SIDEREAL_FIELDS:
            self.fields[field].required = True

    def clean(self):
        """
        Look at the 'scheme' field and check the fields required for the
        specified field have been given
        """
        cleaned_data = super().clean()
        scheme = cleaned_data['scheme']  # scheme is a required field, so this should be safe
        required_fields = REQUIRED_NON_SIDEREAL_FIELDS_PER_SCHEME[scheme]

        for field in required_fields:
            if not cleaned_data.get(field):
                # Get verbose names of required fields
                field_names = [
                    "'" + Target._meta.get_field(f).verbose_name + "'"
                    for f in required_fields
                ]
                scheme_name = dict(Target.TARGET_SCHEMES)[scheme]
                raise ValidationError(
                    "Scheme '{}' requires fields {}".format(scheme_name, ', '.join(field_names))
                )

    class Meta(TargetForm.Meta):
        fields = NON_SIDEREAL_FIELDS

class TargetVisibilityForm(forms.Form):
    start_time = forms.DateTimeField(required=True, label='Start Time', widget=forms.TextInput(attrs={'type': 'date'}))
    end_time = forms.DateTimeField(required=True, label='End Time', widget=forms.TextInput(attrs={'type': 'date'}))
    airmass = forms.DecimalField(required=False, label='Maximum Airmass')

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        target = self.data['target']
        if end_time < start_time:
            raise forms.ValidationError('Start time must be before end time')
        if target.type == 'NON_SIDEREAL':
            raise forms.ValidationError('Airmass plotting is only supported for sidereal targets')


TargetExtraFormset = inlineformset_factory(Target, TargetExtra, fields=('key', 'value'),
                                           widgets={'value': forms.TextInput()})
TargetNamesFormset = inlineformset_factory(Target, TargetName, fields=('name',), validate_min=False, can_delete=True,
                                           extra=3)
