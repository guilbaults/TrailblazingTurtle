# Database
# https://docs.djangoproject.com/en/3.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'userportaldev',
        'USER': 'userportaldev',
        'PASSWORD': 'changeme',
        'HOST': 'dbserver',
        'PORT': '3128',
        'OPTIONS': {
        }
    },
    'slurm': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'slurmdb',
        'USER': 'slurm-stats',
        'PASSWORD': 'changeme',
        'HOST': 'dbserver',
        'PORT': '3128',
        'OPTIONS': {
        },
    },
    'ldap': {
        'ENGINE': 'ldapdb.backends.ldap',
        'NAME': 'ldaps://lproxy01',
        'USER': 'cn=ldapuser,dc=computecanada,dc=ca',
        'PASSWORD': 'changeme',
    },
}

WATCHMAN_DATABASES = ['default', 'slurm']

DATABASE_ROUTERS = ['database_routers.dbrouters.DbRouter']