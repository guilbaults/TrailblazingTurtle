#!/usr/bin/env bash

set -o errexit
set -o pipefail
set -o nounset

cp /secrets/settings/99-local.py /opt/userportal/userportal/settings/99-local.py
mkdir -p /var/www/api/static
cp -r /opt/userportal/collected-static/* /var/www/api/static/
gunicorn --bind :8000 --workers 1 --timeout 90 userportal.wsgi