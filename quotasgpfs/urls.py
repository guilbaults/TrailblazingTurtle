from django.urls import path
from . import views

urlpatterns = [
    path('', views.index),
    path('user/<str:username>/', views.user),
    path('user/<str:username>/getgraph', views.user_getgraph),
    path('project/<str:project>/', views.project),
    path('project/<str:project>/getgraph', views.project_getgraph)
]
