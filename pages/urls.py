from django.urls import path
from . import views

urlpatterns = [
    path('', views.index),
    path('filesystem/', views.filesystem),
    path('filesystem/graph/lustre/<str:fs>/mdt.json', views.graph_lustre_mdt),
    path('filesystem/graph/lustre/<str:fs>/ost.json', views.graph_lustre_ost),
    path('logins/', views.logins),
    path('logins/graph/cpu/<str:login>.json', views.graph_login_cpu),
    path('logins/graph/memory/<str:login>.json', views.graph_login_memory),
    path('logins/graph/load/<str:login>.json', views.graph_login_load),
    path('logins/graph/network/<str:login>.json', views.graph_login_network),
]
