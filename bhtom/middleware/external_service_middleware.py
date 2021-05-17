from django.urls import reverse
from django.shortcuts import redirect
from django.contrib import messages

from tom_common.exceptions import ImproperCredentialsException
from bhtom.exceptions.external_service import NoResultException


def home_with_error_msg(request, msg: str, redirect_to: str = 'home'):
    messages.error(request, msg)
    return redirect(reverse(redirect_to))


class ExternalServiceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_exception(self, request, exception):
        if isinstance(exception, ImproperCredentialsException):
            msg = (
                'There was a problem authenticating with {}. Please check that you have the correct '
                'credentials in the corresponding settings variable. '
                'https://tom-toolkit.readthedocs.io/en/stable/customization/customsettings.html '
            ).format(
                str(exception)
            )
            return home_with_error_msg(request, msg)
        elif isinstance(exception, NoResultException):
            msg = (
                'There was no result for input query.'
            )
            return home_with_error_msg(request, msg, 'tom_catalogs:query')
        raise exception
