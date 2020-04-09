from django import forms
from django.conf import settings

from tom_targets.models import Target
from tom_observations.models import ObservationRecord
from myapp.models import Cpcs_user, Catalogs
from django.contrib.auth.models import User
from django.contrib.postgres.forms import SimpleArrayField
import logging
logger = logging.getLogger(__name__)
class InstrumentChoiceField(forms.ModelChoiceField):

    def label_from_instance(self, obj):
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
        widget=forms.RadioSelect(),
        required=True
    )

    referrer = forms.CharField(
        widget=forms.HiddenInput()
    )

    def __init__(self, *args, **kwargs):

        user = kwargs.pop('user')
        filter = {}
        filter['None'] = 'None'
        catalogs = Catalogs.objects.all().values_list('name', 'filters')
        for curval in catalogs:
            curname, filters = curval
            for i, f in enumerate(filters):
                filter[curname + '/' + f] = curname + '/' + f

        super(DataProductUploadForm, self).__init__(*args, **kwargs)

        self.fields['instrument']=InstrumentChoiceField(
                queryset=Cpcs_user.objects.filter(user=user, user_activation=True),
                widget=forms.Select(),
                required=False,
        )

        self.fields['filter']=forms.ChoiceField(
                choices=[v for v in filter.items()],
                widget=forms.Select(),
                required=False,
        )

class ObservatoryCreationForm(forms.ModelForm):

    class Meta:
        model = Cpcs_user
        fields = ('obsName', 'lon', 'lat', 'allow_upload', 'prefix', 'matchDist', 'fits')

