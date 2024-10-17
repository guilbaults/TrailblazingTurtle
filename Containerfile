FROM ubuntu:24.04

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install -y tzdata && apt install -y python3.12 python3-pip python3-dev python3.12-venv libpq-dev nginx libmysqlclient-dev pkg-config build-essential libsasl2-dev libldap2-dev libssl-dev xmlsec1 gettext git

WORKDIR /opt/userportal

COPY requirements.txt ./

RUN python3 -m venv /opt/userportal-env && \
    /opt/userportal-env/bin/pip install --upgrade pip && \
    /opt/userportal-env/bin/pip install --no-cache-dir -r requirements.txt

COPY . .

RUN patch /opt/userportal-env/lib/python3.12/site-packages/ldapdb/backends/ldap/base.py < /opt/userportal/ldapdb.patch

# Temporarily remove db version check to support mariadb server on EL8 without appstream enabled
RUN patch /opt/userportal-env/lib/python3.12/site-packages/django/db/backends/base/base.py < /opt/userportal/dbcheck.patch

RUN /opt/userportal-env/bin/python manage.py collectstatic --noinput && /opt/userportal-env/bin/python manage.py compilemessages

EXPOSE 8000
CMD ["./run-django-production.sh"]
