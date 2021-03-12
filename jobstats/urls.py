from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('<int:user_id>/', views.user, name='user'),
    path('<int:user_id>/<int:job_id>/', views.job, name='job'),
    path('<int:user_id>/<int:job_id>/graph/cpu.json', views.graph_cpu, name='graph_cpu'),
    path('<int:user_id>/<int:job_id>/graph/mem.json', views.graph_mem, name='graph_mem'),
    path('<int:user_id>/<int:job_id>/graph/lustre_mdt.json', views.graph_lustre_mdt, name='graph_lustre_mdt'),
    path('<int:user_id>/<int:job_id>/graph/lustre_ost.json', views.graph_lustre_ost, name='graph_lustre_ost'),

]
