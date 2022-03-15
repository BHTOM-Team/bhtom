from rest_framework import serializers
from bhtom.models import BHTomFits


class BHTomFitsCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = BHTomFits
        fields = '__all__'


class BHTomFitsResultSerializer(serializers.ModelSerializer):

    class Meta:
        model = BHTomFits
        fields = ('photometry_file', 'status', 'cpcs_time', 'status_message', 'mjd', 'expTime', 'ccdphot_filter')

class BHTomFitsStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = BHTomFits
        fields = '__all__'

