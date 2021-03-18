from django.urls import path
from . import views

urlpatterns = [
    path('', views.index),
    path('<str:username>/', views.user),
    path('<str:username>/graph/cpu.json', views.graph_cpu_user),
    path('<str:username>/graph/mem.json', views.graph_mem_user),
    path('<str:username>/graph/lustre_mdt.json', views.graph_lustre_mdt_user),
    path('<str:username>/graph/lustre_ost.json', views.graph_lustre_ost_user),
    path('<str:username>/graph/gpu_utilization.json', views.graph_gpu_utilization_user),
    path('<str:username>/<int:job_id>/', views.job),
    path('<str:username>/<int:job_id>/graph/cpu.json', views.graph_cpu),
    path('<str:username>/<int:job_id>/graph/mem.json', views.graph_mem),
    path('<str:username>/<int:job_id>/graph/lustre_mdt.json', views.graph_lustre_mdt),
    path('<str:username>/<int:job_id>/graph/lustre_ost.json', views.graph_lustre_ost),
    path('<str:username>/<int:job_id>/graph/gpu_utilization.json', views.graph_gpu_utilization),
    path('<str:username>/<int:job_id>/graph/gpu_memory_utilization.json', views.graph_gpu_memory_utilization),
    path('<str:username>/<int:job_id>/graph/gpu_memory.json', views.graph_gpu_memory),
    path('<str:username>/<int:job_id>/graph/gpu_power.json', views.graph_gpu_power),
    path('<str:username>/<int:job_id>/graph/gpu_pcie.json', views.graph_gpu_pcie),
]
