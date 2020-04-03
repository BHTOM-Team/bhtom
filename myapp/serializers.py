from rest_framework import serializers
from myapp.models import BHTomFits


class BHTomFitsCreateSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = BHTomFits
        fields = '__all__'


class BHTomFitsResultSerializer(serializers.ModelSerializer):

    class Meta:
        model = BHTomFits
        fields = '__all__'

class BHTomFitsStatusSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = BHTomFits
        fields = '__all__'

