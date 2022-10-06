#!/usr/bin/env bash

set -o errexit
set -o pipefail
set -o nounset

cp /secrets/settings/* /opt/userportal/userportal/settings.py
mkdir -p /var/www/api/
python3 manage.py collectstatic --noinput
gunicorn --bind :8000 --workers 1 --timeout 90 userportal.wsgi