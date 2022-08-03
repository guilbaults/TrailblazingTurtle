from django.urls import path
from . import views

urlpatterns = [
    path('', views.index),
    path('<str:username>/', views.user),
    path('<str:username>/graph/storage/<str:resource_type>/<str:resource_name>/inodes.json', views.graph_inodes),
    path('<str:username>/graph/storage/<str:resource_type>/<str:resource_name>/bytes.json', views.graph_bytes),
]
