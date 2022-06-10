from django.urls import path
from . import views

urlpatterns = [
    path('', views.index),
    path('<str:username>/', views.user),
    path('<str:username>/graph/<str:fs>/inodes.json', views.graph_inodes),
    path('<str:username>/graph/<str:fs>/bytes.json', views.graph_bytes),
]
