#!/bin/bash

# piping into kubectl apply -f - will create or update the content

kubectl create secret generic settings --from-file=../userportal/settings.py.dev -o yaml --dry-run=client | kubectl apply -f -
kubectl create secret generic private-key --from-file=../idp/private.key -o yaml --dry-run=client | kubectl apply -f -

kubectl create configmap sql-ca --from-file=../proxysql-ca.pem -o yaml --dry-run=client | kubectl apply -f -
kubectl create configmap idp --from-file=../idp/idp_metadata.xml --from-file=../idp/public.cert -o yaml --dry-run=client | kubectl apply -f -
kubectl create configmap allocations --from-file=../projects-rac2022.yaml -o yaml --dry-run=client | kubectl apply -f -
kubectl create configmap backend-api-nginx --from-file=api.conf -o yaml --dry-run=client | kubectl apply -f -
