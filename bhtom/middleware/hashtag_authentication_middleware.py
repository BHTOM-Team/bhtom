from django.contrib.auth.mixins import AccessMixin
from django.contrib.auth.models import User
from rest_framework import authentication
from rest_framework import exceptions

from bhtom.models import Instrument


class HashtagAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        hashtag = request.headers.get('hashtag')
        if not hashtag:
            return None

        try:
            instrument: Instrument = Instrument.objects.get(hashtag=hashtag)
            user: User = instrument.user_id
        except Instrument.DoesNotExist:
            raise exceptions.AuthenticationFailed('No instrument with given hashtag')
        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed('No user with given hashtag')

        return user, None
