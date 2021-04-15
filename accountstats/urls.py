from django.urls import path
from . import views

urlpatterns = [
    path('', views.index),
    path('<str:account>/', views.account),
    path('<str:account>/graph/cpu_used.json', views.graph_cpu_used),
    path('<str:account>/graph/cpu_allocated.json', views.graph_cpu_allocated),
    path('<str:account>/graph/cpu_wasted.json', views.graph_cpu_wasted),
    path('<str:account>/graph/mem_used.json', views.graph_mem_used),
    path('<str:account>/graph/mem_allocated.json', views.graph_mem_allocated),
    path('<str:account>/graph/mem_wasted.json', views.graph_mem_wasted),
    path('<str:account>/graph/lustre_mdt.json', views.graph_lustre_mdt),
    path('<str:account>/graph/lustre_ost.json', views.graph_lustre_ost),
    path('<str:account>/graph/gpu_allocated.json', views.graph_gpu_allocated),
    path('<str:account>/graph/gpu_used.json', views.graph_gpu_used),
    path('<str:account>/graph/gpu_wasted.json', views.graph_gpu_wasted),
    # path('<str:account>/graph/gpu_power.json', views.graph_gpu_power_account),
]
