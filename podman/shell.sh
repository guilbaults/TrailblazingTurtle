#!/bin/bash
TT_ENV=$1
TT_ENV_PATH=$HOME/TT_envs/$TT_ENV

# storing the port number in a file, this port is exposed by podman to the reverse proxy
source $TT_ENV_PATH/config

if [ -z "$TT_ENV" ]; then
    echo "TT_ENV is not set"
    exit 1
fi

if [ -z "$VERSION" ]; then
    echo "VERSION is not set in the config file, using latest"
    VERSION=latest
fi

podman run -it --pod TT-$TT_ENV --name=TT-$TT_ENV-django-shell \
    -v $TT_ENV_PATH/99-local.py:/secrets/settings/99-local.py:Z \
    -v $TT_ENV_PATH/private.key:/opt/userportal/private.key:Z \
    -v $TT_ENV_PATH/public.cert:/opt/userportal/public.cert:Z \
    -v $TT_ENV_PATH/proxysql-ca.pem:/opt/userportal/proxysql-ca.pem:Z \
    -v $TT_ENV_PATH/cloud.yml:/opt/userportal/cloud.yml:Z \
    -v $TT_ENV_PATH/idp_metadata.xml:/opt/userportal/idp_metadata.xml:Z \
    -v portail-$TT_ENV-static:/var/www/api/:Z \
    ghcr.io/guilbaults/userportal:$VERSION /bin/bash

# cp /secrets/settings/99-local.py userportal/settings/ && python3 manage.py migrate