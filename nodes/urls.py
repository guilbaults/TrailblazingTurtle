from django.urls import path
from . import views

urlpatterns = [
    path('', views.index),
    path('<str:node>/', views.node),
    path('<str:node>/gantt_cpu.json', views.node_gantt_cpu),
    path('<str:node>/gantt_gpu.json', views.node_gantt_gpu),
    path('<str:node>/graph_disk_used.json', views.graph_disk_used),
    path('<str:node>/graph_cpu_jobstats.json', views.graph_cpu_jobstats),
    path('<str:node>/graph_cpu_node.json', views.graph_cpu_node),
    path('<str:node>/graph_memory_jobstats.json', views.graph_memory_jobstats),
    path('<str:node>/graph_memory_node.json', views.graph_memory_node),
    path('<str:node>/graph_ethernet_bdw.json', views.graph_ethernet_bdw),
    path('<str:node>/graph_infiniband_bdw.json', views.graph_infiniband_bdw),
    path('<str:node>/graph_disk_iops.json', views.graph_disk_iops),
    path('<str:node>/graph_disk_bdw.json', views.graph_disk_bdw),
]
