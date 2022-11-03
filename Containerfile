FROM ubuntu:20.04

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install -y tzdata && apt install -y python3.8 python3-pip python3-dev libpq-dev nginx libmysqlclient-dev build-essential libsasl2-dev libldap2-dev libssl-dev xmlsec1 gettext

WORKDIR /opt/userportal

COPY requirements.txt ./

RUN pip3 install --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

COPY . .

RUN patch /usr/local/lib/python3.8/dist-packages/ldapdb/backends/ldap/base.py < /opt/userportal/ldapdb.patch
RUN python3 manage.py collectstatic --noinput && python3 manage.py compilemessages

EXPOSE 8000
CMD ["./run-django-production.sh"]
