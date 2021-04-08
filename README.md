
To test localy without having to use the SSO
`REMOTE_USER=sigui4@computecanada.ca affiliation=staff@computecanada.ca python manage.py runserver`

RPMs required for production
* `shibboleth`
* `python36-virtualenv` 
* `python3-mod_wsgi`
* `openldap-devel`
* `gcc`
* `mariadb-devel`

A file in the python env need to be patched, check the diff in `ldapdb.patch`

Apache virtualhost config
```
<VirtualHost *:443>
  ServerName userportal.int.ets1.calculquebec.ca

  ## Vhost docroot
  DocumentRoot "/var/www/userportal"
  ## Alias declarations for resources outside the DocumentRoot
  Alias /static "/var/www/userportal-static"
  Alias /favicon.ico "/var/www/userportal-static/favicon.ico"

  ## Directories, there should at least be a declaration for /var/www/userportal

  <Directory "/var/www/userportal/">
    AllowOverride None
    Require all granted
  </Directory>

  <Directory "/var/www/userportal/static">
    AllowOverride None
    Require all granted
  </Directory>

  <Location "/secure">
    Require shib-session
    AuthType shibboleth
    ShibRequestSetting requireSession 1
  </Location>

  <Location "/Shibboleth.sso">
    Require all granted
    SetHandler shib
  </Location>

  ## Logging
  ErrorLog "/var/log/httpd/userportal.int.ets1.calculquebec.ca_error_ssl.log"
  ServerSignature Off
  CustomLog "/var/log/httpd/userportal.int.ets1.calculquebec.ca_access_ssl.log" combined

  ## SSL directives
  SSLEngine on
  SSLCertificateFile      "/etc/pki/tls/certs/userportal.int.ets1.calculquebec.ca.crt"
  SSLCertificateKeyFile   "/etc/pki/tls/private/userportal.int.ets1.calculquebec.ca.key"
  WSGIApplicationGroup %{GLOBAL}
  WSGIDaemonProcess userportal python-home=/var/www/userportal-env python-path=/var/www/userportal/
  WSGIProcessGroup userportal
  WSGIScriptAlias / "/var/www/userportal/userportal/wsgi.py"
  ## Shibboleth
</VirtualHost>
```

## Translation
Create the .po files for french: `python manage.py makemessages -l fr`

Update all message files for all languages: `python manage.py makemessages -a`

Compile messages: `python manage.py compilemessages`

