from django.urls import path
from . import views

urlpatterns = [
    path('', views.redirect_to_user, name='maas_redirect'),
    path('<str:username>/', views.user_page, name='maas_user'),
    path('<str:username>/keys/new/', views.key_new, name='maas_key_new'),
    path('<str:username>/keys/<int:key_id>/revoke/', views.key_revoke, name='maas_key_revoke'),
    path('providers/', views.provider_list, name='maas_providers'),
    path('providers/new/', views.provider_new, name='maas_provider_new'),
    path('providers/<int:provider_id>/', views.provider_detail, name='maas_provider_detail'),
]

api_urls = [
    path('api/maas/usage/', views.UsageEndpoint.as_view(), name='maas_usage'),
    path('api/maas/verify/', views.VerifyEndpoint.as_view(), name='maas_verify'),
    path('api/maas/key/revoke/', views.PublicKeyRevokeEndpoint.as_view(), name='maas_key_revoke_public'),
]
