#!/bin/bash
python manage.py migrate --noinput
gunicorn -b 0.0.0.0:8080 settings.wsgi --log-level debug --timeout 150 --workers 2 -k gevent --access-logfile gunicorn-access.log
