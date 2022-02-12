"""
Django settings for your TOM project.

Originally generated by 'django-admin startproject' using Django 2.1.1.
Generated by ./manage.py tom_setup on Nov. 14, 2019, 11:18 p.m.

For more information on this file, see
https://docs.djangoproject.com/en/2.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.1/ref/settings/
"""

import os
import tempfile

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

from typing import Any

# Reads all secret settings and apis, which will not be stored in git repo
try:
    from . import local_settings as secret
except ImportError:
    secret = None


# This is required by Heroku, as they setup environment variables instead of using local_settings (not on github)

# Helper function to read either from secrets file or os

def read_secret(secret_key: str, default_value: Any = '') -> Any:
    if secret:
        return getattr(secret, secret_key, default_value)
    else:
        return os.environ.get(secret_key, default_value)


LCO_APIKEY: str = read_secret('LCO_APIKEY')
SECRET_KEY: str = read_secret('SECRET_KEY')
ANTARES_KEY: str = read_secret('ANTARES_KEY')
ANTARES_SECRET: str = read_secret('ANTARES_SECRET')
TWITTER_APIKEY: str = read_secret('TWITTER_APIKEY')
TWITTER_SECRET: str = read_secret('TWITTER_SECRET')
TWITTER_ACCESSTOKEN: str = read_secret('TWITTER_ACCESSTOKEN')
TWITTER_ACCESSSECRET: str = read_secret('TWITTER_ACCESSSECRET')
TOMEMAIL: str = read_secret('TOMEMAIL')
TOMEMAILPASSWORD: str = read_secret('TOMEMAILPASSWORD')
SNEXBOT_APIKEY = read_secret('TNSBOT_APIKEY')
black_tom_DB_NAME: str = read_secret('black_tom_DB_NAME')
black_tom_DB_USER: str = read_secret('black_tom_DB_USER')
black_tom_DB_PASSWORD: str = read_secret('black_tom_DB_PASSWORD')
CPCS_DATA_ACCESS_HASHTAG: str = read_secret('CPCS_DATA_ACCESS_HASHTAG')
GEMINI_S_API_KEY: str = read_secret('GEMINI_S_API_KEY')
GEMINI_N_API_KEY: str = read_secret('GEMINI_N_API_KEY')
LT_PROPOSAL_ID: str = read_secret('LT_PROPOSAL_ID')
LT_PROPOSAL_NAME: str = read_secret('LT_PROPOSAL_NAME')
LT_PROPOSAL_USER: str = read_secret('LT_PROPOSAL_USER')
LT_PROPOSAL_PASS: str = read_secret('LT_PROPOSAL_PASS')
LT_PROPOSAL_HOST: str = read_secret('LT_PROPOSAL_HOST')
LT_PROPOSAL_PORT: str = read_secret('LT_PROPOSAL_PORT')
RECAPTCHA_PUBLIC_KEY: str = read_secret('RECAPTCHA_PUBLIC_KEY')
RECAPTCHA_PRIVATE_KEY: str = read_secret('RECAPTCHA_PRIVATE_KEY')
TNS_API_KEY: str = read_secret('TNS_API_KEY')
TNS_USER_AGENT: str = read_secret('TNS_USER_AGENT')

# E-mail Messages

EMAILTEXT_REGISTEADMIN_TITLE: str = read_secret('EMAILTEXT_REGISTEADMIN_TITLE')
EMAILTEXT_REGISTEADMIN: str = read_secret('EMAILTEXT_REGISTEADMIN')
RECIPIENTEMAIL: str = read_secret('RECIPIENTEMAIL')
SUCCESSFULLY_REGISTERED: str = read_secret('SUCCESSFULLY_REGISTERED')
EMAILTEXT_REGISTEUSER_TITLE: str = read_secret('EMAILTEXT_REGISTEUSER_TITLE')
EMAILTEXT_REGISTEUSER: str = read_secret('EMAILTEXT_REGISTEUSER_TITLE')

ALLOWED_HOST: str = read_secret('ALLOWED_HOST', 'localhost')
ALLOWED_HOST_IP: str = read_secret('ALLOWED_HOST_IP', '127.0.0.1')
SITE_ID: int = int(read_secret('SITE_ID', 1))

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.1/howto/deployment/checklist/

EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = TOMEMAIL
EMAIL_HOST_PASSWORD = TOMEMAILPASSWORD

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False
ALLOWED_HOSTS = [ALLOWED_HOST, ALLOWED_HOST_IP]
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10240

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django_cron',
    'django_extensions',
    'guardian',
    'tom_common',
    'django_comments',
    'bootstrap4',
    'crispy_forms',
    'django_filters',
    'django_gravatar',
    'django_pgviews',
    'tom_targets',
    'tom_alerts',
    'tom_catalogs',
    'tom_observations',
    'tom_dataproducts',
    'bhtom',
    'datatools',
    'rest_framework',
    'tom_publications',
    'captcha',
    'django_plotly_dash.apps.DjangoPlotlyDashConfig',
]

CRON_CLASSES = [
    'datatools.jobs.update_all_lightcurves.UpdateAllLightcurvesJob'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'bhtom.middleware.external_service_middleware.ExternalServiceMiddleware',
]

ROOT_URLCONF = 'bhtom.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'bhtom/templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

CRISPY_TEMPLATE_PACK = 'bootstrap4'

X_FRAME_OPTIONS = 'SAMEORIGIN'

WSGI_APPLICATION = 'settings.wsgi.application'
black_tom_DB_BACKEND = 'postgres'

# Database
# https://docs.djangoproject.com/en/2.1/ref/settings/#databases
if black_tom_DB_BACKEND == 'postgres':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': black_tom_DB_NAME,
            'USER': black_tom_DB_USER,
            'PASSWORD': black_tom_DB_PASSWORD,
            'HOST': 'localhost',
            'PORT': 5432,
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
        }
    }

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [(read_secret("REDIS_HOST", '127.0.0.1'), read_secret("REDIS_PORT", 6379))],
        },
    },
}

# Password validation
# https://docs.djangoproject.com/en/2.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'guardian.backends.ObjectPermissionBackend',
)

# Internationalization
# https://docs.djangoproject.com/en/2.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = False

USE_TZ = True

DATETIME_FORMAT = 'Y-m-d H:m:s'
DATE_FORMAT = 'Y-m-d'

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.1/howto/static-files/

STATIC_URL = '/bhtom/static/'

STATIC_ROOT = os.path.join(BASE_DIR, '_static/')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'bhtom/static')]

MEDIA_ROOT = os.path.join(BASE_DIR, 'data')
MEDIA_URL = '/data/'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'console': {
            'format': '%(name)-12s %(levelname)-8s %(message)s'
        },
        'file': {
            'format': '%(asctime)s %(name)-12s %(levelname)-8s %(message)s'
        }
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'log/debug.log',
            'formatter': 'file'
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'console'
        }
    },
    'loggers': {
        '': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# Caching
# https://docs.djangoproject.com/en/dev/topics/cache/#filesystem-caching

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': tempfile.gettempdir()
    }
}

# TOM Specific configuration
TARGET_TYPE = 'SIDEREAL'

FACILITIES = {
    'LCO': {
        'portal_url': 'https://observe.lco.global',
        'api_key': LCO_APIKEY,
    },
    'GEM': {
        'portal_url': {
            'GS': 'https://gsodb.gemini.edu:8443',
            'GN': 'https://gnodb.gemini.edu:8443',
        },
        'api_key': {
            'GS': GEMINI_S_API_KEY,
            'GN': GEMINI_N_API_KEY,
        },
        'user_email': 'kruszynskakat@gmail.com',
        'programs': {
            'GS-2020A-DD-104': {
                '8': 'GMOS Aquisiton 0.75arcsec',
                '9': 'Std: R400 LongSlit 0.75arcsec for Blue Objects',
                '12': 'Std: B600 LongSlit 0.75arcsec for Red Objects',
            },
            'GN-2020A-DD-104': {
                '8': 'GMOS Aquisiton 0.75arcsec',
                '9': 'Std: R400 LongSlit 0.75arcsec for Red Objects',
                '17': 'Std: B600 LongSlit 0.75arcsec for Blue Objects',
            },

        },
    },
    ### configuration of LT remote telescope access, requires local_settings variables:
    'LT': {
        'proposalIDs': ((LT_PROPOSAL_ID, LT_PROPOSAL_NAME),),
        'username': LT_PROPOSAL_USER,
        'password': LT_PROPOSAL_PASS,
        'LT_HOST': LT_PROPOSAL_HOST,
        'LT_PORT': LT_PROPOSAL_PORT,
        'DEBUG': False,
    },
}

# Define the valid data product types for your TOM. Be careful when removing items, as previously valid types will no
# longer be valid, and may cause issues unless the offending records are modified.
DATA_PRODUCT_TYPES = {
    'photometry_cpcs': ('photometry_cpcs', 'Instrumental photometry file (SExtractor format)'),
    'fits_file': ('fits_file', 'Fits image for photometric processing'),
    'spectroscopy': ('spectroscopy', 'Spectrum as ASCII'),
    'photometry': ('photometry', 'Photometric time-series (CSV)'),
    'photometry_asassn': ('photometry_asassn', 'Photometric time-series (ASAS-SN format)')
}

DATA_PROCESSORS = {
    'photometry': 'datatools.processors.photometry_processor.PhotometryProcessor',
    'spectroscopy': 'tom_dataproducts.processors.spectroscopy_processor.SpectroscopyProcessor',
    'photometry_asassn': 'datatools.processors.asassn_photometry.ASASSNPhotometryProcessor'
}

TOM_FACILITY_CLASSES = [
    'tom_observations.facilities.lco.LCOFacility',
    'tom_observations.facilities.gemini.GEMFacility',
    'tom_lt.lt.LTFacility',
]

TOM_ALERT_CLASSES = [
    'tom_alerts.brokers.mars.MARSBroker',
    'tom_alerts.brokers.lasair.LasairBroker',
    'tom_alerts.brokers.scout.ScoutBroker',
    'tom_alerts.brokers.tns.TNSBroker',
    'tom_antares.antares.AntaresBroker',
]

BROKER_CREDENTIALS = {
    'antares': {
        'api_key': ANTARES_KEY,
        'api_secret': ANTARES_SECRET
    }
}

ALERT_NAME_KEYS = {
    'GAIA': 'gaia_alert_name',
    'ZTF': 'ztf_alert_name',
    'CPCS': 'calib_server_name',
    'AAVSO': 'aavso_name',
    'GAIA DR2': 'gaiadr2_id',
    'TNS': 'TNS_ID'
}

# Define extra target fields here. Types can be any of "number", "string", "boolean" or "datetime"
# See https://tomtoolkit.github.io/docs/target_fields for documentation on this feature
# For example:
# EXTRA_FIELDS = [
#     {'name': 'redshift', 'type': 'number'},
#     {'name': 'discoverer', 'type': 'string'}
#     {'name': 'eligible', 'type': 'boolean'},
#     {'name': 'dicovery_date', 'type': 'datetime'}
# ]
EXTRA_FIELDS = [
    {'name': 'gaia_alert_name', 'type': 'string'},
    {'name': 'calib_server_name', 'type': 'string'},
    {'name': 'ztf_alert_name', 'type': 'string'},
    {'name': 'aavso_name', 'type': 'string'},
    {'name': 'gaiadr2_id', 'type': 'string'},
    {'name': 'TNS_ID', 'type': 'string'},
    {'name': 'classification', 'type': 'string'},
    {'name': 'tweet', 'type': 'boolean'},
    {'name': 'jdlastobs', 'type': 'number', 'default': 0.0},
    {'name': 'maglast', 'type': 'number'},
    {'name': 'priority', 'type': 'number'},
    {'name': 'dicovery_date', 'type': 'datetime'},
    {'name': 'cadence', 'type': 'number'},
    {'name': 'Sun_separation', 'type': 'number'},
    {'name': 'dont_update_me', 'type': 'boolean'}
]

# Authentication strategy can either be LOCKED (required login for all views)
# or READ_ONLY (read only access to views)
AUTH_STRATEGY = 'READ_ONLY'

# URLs that should be allowed access even with AUTH_STRATEGY = LOCKED
# for example: OPEN_URLS = ['/', '/about']
OPEN_URLS = []

HOOKS = {
    'target_pre_save': 'bhtom.hooks.target_pre_save',
    'observation_change_state': 'tom_common.hooks.observation_change_state',
    'data_product_post_upload': 'bhtom.hooks.data_product_post_upload',
}

# Gaia Alerts added by LW
# others are copied from default AbstractHarvester
TOM_HARVESTER_CLASSES = [
    'bhtom.harvesters.gaia_alerts_harvester.GaiaAlertsHarvester',
    'tom_catalogs.harvesters.simbad.SimbadHarvester',
    'tom_catalogs.harvesters.ned.NEDHarvester',
    'tom_catalogs.harvesters.jplhorizons.JPLHorizonsHarvester',
    'tom_catalogs.harvesters.mpc.MPCHarvester',
    'bhtom.harvesters.tns.TNSHarvester',
]

REST_FRAMEWORK = {
    # Use Django's standard `django.contrib.auth` permissions,
    # or allow read-only access for unauthenticated users.
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny'
    ]
}

AUTO_THUMBNAILS = False

THUMBNAIL_MAX_SIZE = (0, 0)

THUMBNAIL_DEFAULT_SIZE = (200, 200)

HINTS_ENABLED = True
HINT_LEVEL = 20

# TOM Toolkit 1.4 requires
TARGET_PERMISSIONS_ONLY = True

CPCS_BASE_URL = "https://cpcs.astrolabs.pl/cgi/"
CPCS_DATA_FETCH_URL = "https://cpcs.astrolabs.pl/"
AAVSO_DATA_FETCH_URL = "https://www.aavso.org/vsx/index.php"
GAIA_ALERT_URL = "http://gsaweb.ast.cam.ac.uk/alerts/alert"
TNS_URL = "https://www.wis-tns.org/api/get"

SILENCED_SYSTEM_CHECKS = ['captcha.recaptcha_test_key_error']

sentry_sdk.init(
    dsn=read_secret('SENTRY_SDK_DSN', ''),
    integrations=[DjangoIntegration()],
    traces_sample_rate=1.0,
    send_default_pii=True
)
