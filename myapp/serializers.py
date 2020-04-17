from rest_framework import serializers
from myapp.models import BHTomFits


class BHTomFitsCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = BHTomFits
        fields = '__all__'


class BHTomFitsResultSerializer(serializers.ModelSerializer):

    class Meta:
        model = BHTomFits
        fields = '__all__'

class BHTomFitsStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = BHTomFits
        fields = '__all__'

