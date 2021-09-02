from django.urls import path
from . import views

urlpatterns = [
    path('project/<str:project>/', views.project),
    path('project/<str:project>/graph/cpu.json', views.project_graph_cpu),
    path('project/<str:project>/graph/memory.json', views.project_graph_memory),
    path('project/<str:project>/graph/disk_bandwidth.json', views.project_graph_disk_bandwidth),
    path('project/<str:project>/graph/disk_iops.json', views.project_graph_disk_iops),
    path('project/<str:project>/graph/network_bandwidth.json', views.project_graph_network_bandwidth),
]
