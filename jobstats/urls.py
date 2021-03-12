from django.urls import path
from . import views

urlpatterns = [
    path('', views.index),
    path('<int:user_id>/', views.user),
    path('<int:user_id>/<int:job_id>/', views.job),
    path('<int:user_id>/<int:job_id>/graph/cpu.json', views.graph_cpu),
    path('<int:user_id>/<int:job_id>/graph/mem.json', views.graph_mem),
    path('<int:user_id>/<int:job_id>/graph/lustre_mdt.json', views.graph_lustre_mdt),
    path('<int:user_id>/<int:job_id>/graph/lustre_ost.json', views.graph_lustre_ost),
    path('<int:user_id>/<int:job_id>/graph/gpu_utilization.json', views.graph_gpu_utilization),
    path('<int:user_id>/<int:job_id>/graph/gpu_memory_utilization.json', views.graph_gpu_memory_utilization),
    path('<int:user_id>/<int:job_id>/graph/gpu_memory.json', views.graph_gpu_memory),
    path('<int:user_id>/<int:job_id>/graph/gpu_power.json', views.graph_gpu_power),
    path('<int:user_id>/<int:job_id>/graph/gpu_pcie.json', views.graph_gpu_pcie),
]
