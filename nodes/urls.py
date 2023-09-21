from django.urls import path
from . import views

urlpatterns = [
    path('', views.index),
    path('<str:node>/', views.node),
    path('<str:node>/gantt_cpu.json', views.node_gantt_cpu),
    path('<str:node>/gantt_gpu.json', views.node_gantt_gpu),
]
