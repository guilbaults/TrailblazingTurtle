
To test localy without having to use the SSO
`REMOTE_USER=sigui4@computecanada.ca affiliation=staff@computecanada.ca python manage.py runserver`

RPMs required for production
* `shibboleth`
* `python36-virtualenv` 
* `python3-mod_wsgi`
* `openldap-devel`
* `gcc`
* `mariadb-devel`


Apache virtualhost config
```
WSGIDaemonProcess userportal python-home=/var/www/django-env python-path=/var/www/django/userportal/
WSGIProcessGroup userportal
WSGIApplicationGroup %{GLOBAL}
WSGIScriptAlias / /var/www/django/userportal/userportal/wsgi.py

<Directory /var/www/django/userportal/>
    Require all granted
</Directory>

<Location />
  AuthType shibboleth
  ShibRequestSetting requireSession 1
  require shib-session
</Location>

<Location /Shibboleth.sso>
  SetHandler shib
</Location>
```
