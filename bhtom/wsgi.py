"""
WSGI config for bhtom project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/2.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application
from django.conf import settings
from django.contrib.staticfiles.handlers import StaticFilesHandler

from whitenoise import WhiteNoise
 
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bhtom.settings')

# if settings.DEBUG:
#     application = StaticFilesHandler(get_wsgi_application())
# else:
#     application = get_wsgi_application()

application = get_wsgi_application()
application = WhiteNoise(application, root='/Users/wyrzykow/bhtom/myapp/static')
#application.add_files('/path/to/more/static/files', prefix='more-files/')