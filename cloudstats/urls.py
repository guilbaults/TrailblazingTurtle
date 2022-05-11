from django.urls import path
from . import views

urlpatterns = [
    path('', views.index),
    path('graph/cpu.json', views.projects_graph_cpu),
    path('graph/mem.json', views.projects_graph_mem),
    path('<str:project>/', views.project),
    path('<str:project>/graph/cpu.json', views.project_graph_cpu),
    path('<str:project>/graph/memory.json', views.project_graph_memory),
    path('<str:project>/graph/disk_bandwidth.json', views.project_graph_disk_bandwidth),
    path('<str:project>/graph/disk_iops.json', views.project_graph_disk_iops),
    path('<str:project>/graph/network_bandwidth.json', views.project_graph_network_bandwidth),
    path('<str:project>/<str:uuid>/', views.instance),
    path('<str:project>/<str:uuid>/graph/cpu.json', views.instance_graph_cpu),
    path('<str:project>/<str:uuid>/graph/memory.json', views.instance_graph_memory),
    path('<str:project>/<str:uuid>/graph/disk_bandwidth.json', views.instance_graph_disk_bandwidth),
    path('<str:project>/<str:uuid>/graph/disk_iops.json', views.instance_graph_disk_iops),
    path('<str:project>/<str:uuid>/graph/network_bandwidth.json', views.instance_graph_network_bandwidth),

]
