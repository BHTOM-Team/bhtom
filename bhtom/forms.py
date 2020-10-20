from django import forms
from django.conf import settings

from tom_targets.models import Target
from tom_observations.models import ObservationRecord
from bhtom.models import Observatory, Instrument, Catalogs
from django.contrib.auth.models import User, Group
from django.contrib.auth.forms import UserCreationForm, UsernameField

from captcha.fields import ReCaptchaField

import logging
logger = logging.getLogger(__name__)
class InstrumentChoiceField(forms.ModelChoiceField):

    def label_from_instance(self, obj):
        return '{insName}'.format(insName=obj.insName)

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

    MATCHING_RADIUS = {
        ('0', 'Auto'),
        ('1', '1 arcsec'),
        ('2', '2 arcsec'),
        ('4', '4 arcsec'),
        ('6', '6 arcsec')
    }

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
        fields = ('hashtag', 'comment')

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

            queryset=Observatory.objects.exclude(id__in=insTab).filter(isVerified=True),
            widget=forms.Select(),
            required=True
        )

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    groups = forms.ModelMultipleChoiceField(Group.objects.all().exclude(name='Public'),
                                            required=False, widget=forms.CheckboxSelectMultiple)
    captcha = ReCaptchaField()

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'groups')
        field_classes = {'username': UsernameField}


    def save(self, commit=True):
        user = super(forms.ModelForm, self).save(commit=False)
        if self.cleaned_data['password1']:
            user.set_password(self.cleaned_data["password1"])
        if commit:
            user.is_active = False
            user.save()
            self.save_m2m()

        return user
