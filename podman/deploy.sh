#!/bin/bash
TT_ENV=$1
TT_ENV_PATH=$HOME/TT_envs/$TT_ENV

# storing the port number in a file, this port is exposed by podman to the reverse proxy
source $TT_ENV_PATH/config

if [ -z "$TT_ENV" ]; then
    echo "TT_ENV is not set"
    exit 1
fi

if [ -z "$PORT" ]; then
    echo "PORT is not set in the config file"
    exit 1
fi

if [ -z "$VERSION" ]; then
    echo "VERSION is not set in the config file, using latest"
    VERSION=latest
fi

podman pod stop TT-$TT_ENV
podman pod rm -f TT-$TT_ENV
podman volume rm -f TT-$TT_ENV-static

podman pod create -p $PORT:80 --name TT-$TT_ENV
podman volume create TT-$TT_ENV-static

podman run --detach --pod TT-$TT_ENV --name=TT-$TT_ENV-django \
    -v $TT_ENV_PATH/99-local.py:/secrets/settings/99-local.py:Z \
    -v $TT_ENV_PATH/private.key:/opt/userportal/private.key:Z \
    -v $TT_ENV_PATH/public.cert:/opt/userportal/public.cert:Z \
    -v $TT_ENV_PATH/proxysql-ca.pem:/opt/userportal/proxysql-ca.pem:Z \
    -v $TT_ENV_PATH/cloud.yml:/opt/userportal/cloud.yml:Z \
    -v $TT_ENV_PATH/idp_metadata.xml:/opt/userportal/idp_metadata.xml:Z \
    -v portail-$TT_ENV-static:/var/www/api/:Z \
    ghcr.io/guilbaults/userportal:$VERSION

podman run --detach --pod TT-$TT_ENV --name=TT-$TT_ENV-nginx \
    -v ../kubernetes/api.conf:/etc/nginx/conf.d/default.conf:Z \
    -v portail-$TT_ENV-static:/var/www/api/:Z \
    docker.io/library/nginx:stable
