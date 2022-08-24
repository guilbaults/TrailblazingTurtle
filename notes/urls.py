from django.urls import path
from . import views

urlpatterns = [
    path('', views.index),
    path('<int:note_id>/', views.note),
    path('new/', views.new),
]
