from django.urls import path
from . import views

urlpatterns = [
    path('', views.index),
    path('filesystems/', views.filesystem),
    path('filesystems/graph/lustre/<str:fs>/mdt.json', views.graph_lustre_mdt),
    path('filesystems/graph/lustre/<str:fs>/ost.json', views.graph_lustre_ost),
    path('logins/', views.logins),
    path('logins/graph/cpu/<str:login>.json', views.graph_login_cpu),
    path('logins/graph/memory/<str:login>.json', views.graph_login_memory),
    path('logins/graph/load/<str:login>.json', views.graph_login_load),
    path('logins/graph/network/<str:login>.json', views.graph_login_network),
    path('dtns/', views.dtns),
    path('dtns/graph/network/<str:dtn>.json', views.graph_dtn_network),
    path('scheduler/', views.scheduler),
    path('scheduler/graph/allocated_cpu.json', views.graph_scheduler_cpu),
    path('scheduler/graph/allocated_gpu.json', views.graph_scheduler_gpu),
    path('software/', views.software),
    path('software/graph/software.json', views.graph_software_processes),
    path('software/graph/software_stack.json', views.graph_software_stack),
    path('software/graph/software_cvmfs.json', views.graph_software_processes_cvmfs),
    path('software/graph/software_not_cvmfs.json', views.graph_software_processes_not_cvmfs),
    path('software/graph/software_gpu.json', views.graph_software_gpu),
    path('software/graph/software_cores_with_gpu.json', views.graph_software_cores_with_gpu),
]
