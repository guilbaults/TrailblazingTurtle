from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('<int:user_id>/', views.user, name='user'),
    path('<int:user_id>/<int:job_id>/', views.job, name='job'),
    path('<int:user_id>/<int:job_id>/graph/cpu.json', views.graph_cpu, name='graph_cpu'),
]
