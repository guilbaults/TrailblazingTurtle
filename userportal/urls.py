"""userportal URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.urls import include, path
from django.contrib import admin
from django.views.decorators.http import last_modified
from django.utils import timezone
from django.views.i18n import JavaScriptCatalog
import debug_toolbar
from rest_framework import routers
from django.conf import settings
if 'jobstats' in settings.INSTALLED_APPS:
    from jobstats.views import JobScriptViewSet

router = routers.DefaultRouter()

last_modified_date = timezone.now()

if 'jobstats' in settings.INSTALLED_APPS:
    router.register(r'jobscripts', JobScriptViewSet)

urlpatterns = [
    path('', include('pages.urls')),
    path('i18n/', include('django.conf.urls.i18n')),
    path('jsi18n/',
         last_modified(lambda req, **kw: last_modified_date)(JavaScriptCatalog.as_view()),
         name='javascript-catalog'),
    path('__debug__/', include(debug_toolbar.urls)),
    path('admin/', admin.site.urls),
    path('api/', include((router.urls, 'app_name'))),
    path('api-auth/', include('rest_framework.urls')),
]

if 'jobstats' in settings.INSTALLED_APPS:
    urlpatterns.append(path('secure/jobstats/', include('jobstats.urls')))

if 'accountstats' in settings.INSTALLED_APPS:
    urlpatterns.append(path('secure/accountstats/', include('accountstats.urls')))

if 'cloudstats' in settings.INSTALLED_APPS:
    urlpatterns.append(path('secure/cloudstats/', include('cloudstats.urls')))

if 'quotas' in settings.INSTALLED_APPS:
    urlpatterns.append(path('secure/quotas/', include('quotas.urls')))

if 'top' in settings.INSTALLED_APPS:
    urlpatterns.append(path('secure/top/', include('top.urls')))

if 'usersummary' in settings.INSTALLED_APPS:
    urlpatterns.append(path('secure/usersummary/', include('usersummary.urls')))
