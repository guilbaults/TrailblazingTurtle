from django.urls import path
from . import views

urlpatterns = [
    path('', views.index),
    path('project/<str:project>/', views.project),
    path('project/<str:project>/graph/cpu.json', views.project_graph_cpu),
    path('project/<str:project>/graph/memory.json', views.project_graph_memory),
    path('project/<str:project>/graph/disk_bandwidth.json', views.project_graph_disk_bandwidth),
    path('project/<str:project>/graph/disk_iops.json', views.project_graph_disk_iops),
    path('project/<str:project>/graph/network_bandwidth.json', views.project_graph_network_bandwidth),
    path('project/<str:project>/<str:uuid>/', views.instance),
    path('project/<str:project>/<str:uuid>/graph/cpu.json', views.instance_graph_cpu),
    path('project/<str:project>/<str:uuid>/graph/memory.json', views.instance_graph_memory),
    path('project/<str:project>/<str:uuid>/graph/disk_bandwidth.json', views.instance_graph_disk_bandwidth),
    path('project/<str:project>/<str:uuid>/graph/disk_iops.json', views.instance_graph_disk_iops),
    path('project/<str:project>/<str:uuid>/graph/network_bandwidth.json', views.instance_graph_network_bandwidth),

]
