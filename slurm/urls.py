from django.urls import path
from . import views

urlpatterns = [
    path('', views.index),
    path('account_priority/', views.account_priority),
    path('account_priority/account_priority.json', views.account_priority_json),
    path('job_length/', views.job_length),
    path('job_length/length.json', views.job_length_json),
    path('job_length/timeout.json', views.job_timeout_json),
    path('account_list.json', views.account_list),
]
