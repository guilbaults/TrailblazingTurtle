from django.urls import path
from . import views

urlpatterns = [
    path('', views.index),
    path('compute/', views.compute),
    path('largemem/', views.largemem),
    path('lustre/', views.lustre),
    path('lustre/graph/lustre_mdt/<str:fs>.json', views.graph_lustre_mdt),
    path('lustre/graph/lustre_ost/<str:fs>.json', views.graph_lustre_ost),
]
