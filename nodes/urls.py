from django.urls import path
from . import views

urlpatterns = [
    path('', views.index),
    path('<str:node>/', views.node),
    path('<str:node>/gantt.json', views.node_gantt),
]
