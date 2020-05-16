"""
WSGI config for settings project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/2.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application
from django.conf import settings
from django.contrib.staticfiles.handlers import StaticFilesHandler

from whitenoise import WhiteNoise
 
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings.settings')

# if settings.DEBUG:
#     application = StaticFilesHandler(get_wsgi_application())
# else:
#     application = get_wsgi_application()

BASE_DIR = os.path.join(settings.BASE_DIR, 'bhtom/static')

application = get_wsgi_application()
application = WhiteNoise(application, root=BASE_DIR)
#application.add_files('/path/to/more/static/files', prefix='more-files/')