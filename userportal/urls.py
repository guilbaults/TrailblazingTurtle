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
import debug_toolbar
from rest_framework import routers
from jobstats.views import JobScriptViewSet

router = routers.DefaultRouter()
router.register(r'jobscripts', JobScriptViewSet)

urlpatterns = [
    path('', include('pages.urls')),
    path('secure/jobstats/', include('jobstats.urls')),
    path('secure/accountstats/', include('accountstats.urls')),
    path('secure/cloudstats/', include('cloudstats.urls')),
    path('secure/quotas/', include('quotas.urls')),
    path('secure/top/', include('top.urls')),
    path('secure/usersummary/', include('usersummary.urls')),
    path('__debug__/', include(debug_toolbar.urls)),
    path('admin/', admin.site.urls),
    path('api/', include((router.urls, 'app_name'))),
    path('api-auth/', include('rest_framework.urls')),
]
