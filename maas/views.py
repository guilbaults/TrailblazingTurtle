import functools
import secrets
import uuid
from datetime import timedelta

from django.db.models import Count, F, Sum
from django.db.models.functions import TruncHour
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden, HttpResponseNotFound, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from userportal.common import parse_start_end

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from maas.models import MAASProvider, MAASApiKey, MAASUsageRecord, sha256_key
from maas.serializers import (
    MAASUsageSubmitSerializer,
    MAASUsageRecordSerializer,
    MAASVerifyRequestSerializer,
)


# --- Permissions ---

def key_owner_or_staff(func):
    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        if request.user.username == kwargs['username']:
            return func(request, *args, **kwargs)
        elif request.user.is_staff:
            return func(request, *args, **kwargs)
        else:
            return HttpResponseForbidden(_('Access denied'))
    return wrapper


# --- Bearer Key Authentication ---

class BearerKeyAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return None

        raw_key = auth_header[7:]
        if not raw_key:
            raise AuthenticationFailed(_('Invalid authorization header'))

        key_hash = sha256_key(raw_key)
        try:
            candidate = MAASApiKey.objects.get(is_active=True, key_hash=key_hash)
        except MAASApiKey.DoesNotExist:
            raise AuthenticationFailed(_('Invalid API key'))

        if not check_password(raw_key, candidate.key):
            raise AuthenticationFailed(_('Invalid API key'))

        if candidate.is_expired:
            raise AuthenticationFailed(_('API key has expired'))

        return (candidate.user, candidate)

    def authenticate_header(self, request):
        return 'Bearer'


# --- Helper ---

def lookup_provider(provider_key):
    """Find an active provider by its plaintext API key."""
    key_hash = sha256_key(provider_key)
    try:
        candidate = MAASProvider.objects.get(is_active=True, key_hash=key_hash)
    except MAASProvider.DoesNotExist:
        return None
    if not check_password(provider_key, candidate.key):
        return None
    return candidate


# --- API Endpoints ---

class UsageEndpoint(APIView):
    authentication_classes = [BearerKeyAuthentication]

    def post(self, request):
        serializer = MAASUsageSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated = serializer.validated_data
        api_key_obj = request.auth

        provider = lookup_provider(validated['provider_key'])
        if not provider:
            return Response(
                {'error': _('Invalid provider key')},
                status=status.HTTP_400_BAD_REQUEST
            )

        request_id = validated.get('request_id') or str(uuid.uuid4())

        record = MAASUsageRecord.objects.create(
            api_key=api_key_obj,
            provider=provider,
            request_id=request_id,
            model=validated['model'],
            endpoint=validated['endpoint'],
            input_tokens=validated['input_tokens'],
            output_tokens=validated['output_tokens'],
            cost=validated.get('cost'),
            latency_ms=validated['latency_ms'],
        )

        api_key_obj.last_used_at = timezone.now()
        api_key_obj.save(update_fields=['last_used_at'])

        return Response(
            MAASUsageRecordSerializer(record, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )

    def get(self, request):
        api_key_obj = getattr(request, 'auth', None)

        if not api_key_obj:
            return Response(
                {'error': _('Authentication required')},
                status=status.HTTP_401_UNAUTHORIZED
            )

        records = MAASUsageRecord.objects.filter(api_key=api_key_obj).select_related(
            'provider', 'api_key__user',
        )

        model = request.query_params.get('model')
        start = request.query_params.get('start')
        end = request.query_params.get('end')

        if model:
            records = records.filter(model=model)
        if start:
            records = records.filter(created_at__gte=start)
        if end:
            records = records.filter(created_at__lte=end)

        serializer = MAASUsageRecordSerializer(records, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class VerifyEndpoint(APIView):
    authentication_classes = [BearerKeyAuthentication]

    def post(self, request):
        serializer = MAASVerifyRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        provider = lookup_provider(serializer.validated_data['provider_key'])
        if not provider:
            return Response(
                {'error': _('Invalid provider key')},
                status=status.HTTP_400_BAD_REQUEST
            )

        api_key_obj = request.auth
        response_data = {
            'valid': True,
            'user': api_key_obj.user.username,
            'expires_at': api_key_obj.expires_at,
            'provider': {
                'id': provider.id,
                'name': provider.name,
                'url': provider.url,
            },
        }
        return Response(response_data, status=status.HTTP_200_OK)


class PublicKeyRevokeEndpoint(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            raw_key = auth_header[7:]
            if raw_key:
                key_hash = sha256_key(raw_key)
                try:
                    candidate = MAASApiKey.objects.get(is_active=True, key_hash=key_hash)
                    if check_password(raw_key, candidate.key):
                        candidate.is_active = False
                        candidate.save(update_fields=['is_active'])
                except MAASApiKey.DoesNotExist:
                    pass
        return Response({}, status=status.HTTP_200_OK)


# --- Web Views ---

@login_required
def redirect_to_user(request):
    return redirect('maas_user', username=request.user.username)


@login_required
@key_owner_or_staff
def user_page(request, username):
    from django.contrib.auth import get_user_model
    User = get_user_model()

    if username != request.user.username:
        try:
            target_user = User.objects.get(username=username)
        except User.DoesNotExist:
            return HttpResponseNotFound(_('User not found'))
    else:
        target_user = request.user

    key_qs = MAASApiKey.objects.filter(user=target_user).order_by('-created_at').only(
        'id', 'name', 'created_at', 'expires_at', 'is_active', 'last_used_at', 'user_id',
    )
    key_paginator = Paginator(key_qs, 10)
    keys_page = key_paginator.get_page(request.GET.get('page'))

    record_qs = MAASUsageRecord.objects.filter(api_key__user=target_user).order_by('-created_at').select_related(
        'provider', 'api_key',
    )
    record_paginator = Paginator(record_qs, 10)
    records_page = record_paginator.get_page(request.GET.get('records_page'))

    totals = MAASUsageRecord.objects.filter(api_key__user=target_user).aggregate(
        total_input=Sum('input_tokens'),
        total_output=Sum('output_tokens'),
        total_cost=Sum('cost', default=0),
    )

    context = {
        'target_user': target_user,
        'keys': keys_page,
        'records': records_page,
        'total_input_tokens': totals.get('total_input') or 0,
        'total_output_tokens': totals.get('total_output') or 0,
        'total_cost': totals.get('total_cost') or 0,
        'is_owner': request.user.username == target_user.username,
    }
    return render(request, 'maas/user_page.html', context)


@login_required
def key_new(request, username):
    if request.user.username != username and not request.user.is_staff:
        return HttpResponseForbidden(_('Access denied'))

    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        target_user = User.objects.get(username=username)
    except User.DoesNotExist:
        return HttpResponseNotFound(_('User not found'))

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        expires = request.POST.get('expires_at', '').strip()

        if not name:
            return render(request, 'maas/key_new.html', {
                'target_user': target_user,
                'error': _('Name is required'),
                'is_owner': request.user.username == target_user.username,
            })

        raw_key = secrets.token_urlsafe(48)
        hashed_key = make_password(raw_key)
        key_hash = sha256_key(raw_key)

        expires_at = None
        if expires:
            from datetime import datetime
            expires_at = datetime.strptime(expires, '%Y-%m-%d').replace(hour=23, minute=59, second=59)

        api_key = MAASApiKey.objects.create(
            user=target_user,
            name=name,
            key=hashed_key,
            key_hash=key_hash,
            expires_at=expires_at,
        )

        return render(request, 'maas/key_new.html', {
            'target_user': target_user,
            'created_key': api_key,
            'raw_key': raw_key,
            'is_owner': request.user.username == target_user.username,
        })

    return render(request, 'maas/key_new.html', {
        'target_user': target_user,
        'is_owner': request.user.username == target_user.username,
    })


@login_required
@require_POST
@key_owner_or_staff
def key_revoke(request, username, key_id):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        target_user = User.objects.get(username=username)
    except User.DoesNotExist:
        return HttpResponseNotFound(_('User not found'))

    api_key = get_object_or_404(MAASApiKey, id=key_id, user=target_user)
    api_key.is_active = False
    api_key.save(update_fields=['is_active'])
    return redirect('maas_user', username=username)


@login_required
@staff_member_required
def provider_list(request):
    providers = MAASProvider.objects.all().annotate(usage_count=Count('usagerecords'))
    return render(request, 'maas/provider_list.html', {'providers': providers})


@login_required
@staff_member_required
def provider_new(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        url = request.POST.get('url', '').strip()
        raw_key = request.POST.get('key', '').strip()

        if not name or not url or not raw_key:
            return render(request, 'maas/provider_new.html', {
                'error': _('All fields are required'),
            })

        hashed_key = make_password(raw_key)
        provider = MAASProvider.objects.create(
            name=name,
            url=url,
            key=hashed_key,
            key_hash=sha256_key(raw_key),
        )

        return render(request, 'maas/provider_new.html', {
            'created': True,
            'provider': provider,
            'raw_key': raw_key,
        })

    return render(request, 'maas/provider_new.html')


@login_required
@staff_member_required
def provider_detail(request, provider_id):
    provider = get_object_or_404(MAASProvider.objects.annotate(usage_count=Count('usagerecords')), id=provider_id)
    records = MAASUsageRecord.objects.filter(provider=provider).order_by('-created_at').select_related(
        'api_key__user', 'provider',
    )[:100]

    is_revoking = request.method == 'POST' and request.POST.get('action') == 'toggle_active'
    if is_revoking:
        provider.is_active = not provider.is_active
        provider.save(update_fields=['is_active'])

    return render(request, 'maas/provider_detail.html', {
        'provider': provider,
        'records': records,
    })


@login_required
@key_owner_or_staff
@parse_start_end(timedelta_start=timedelta(days=7))
def graph_tokens(request, username):
    from django.contrib.auth import get_user_model
    User = get_user_model()

    if username != request.user.username:
        try:
            target_user = User.objects.get(username=username)
        except User.DoesNotExist:
            return JsonResponse({'error': 'User not found'}, status=404)
    else:
        target_user = request.user

    records = MAASUsageRecord.objects.filter(
        api_key__user=target_user,
        created_at__gte=request.start,
        created_at__lte=request.end,
    ).annotate(
        hour=TruncHour('created_at'),
    ).values('hour', 'model').annotate(
        total=Sum(F('input_tokens') + F('output_tokens')),
    ).order_by('hour', 'model')

    models = sorted(set(r['model'] for r in records))
    hours = sorted(set(r['hour'] for r in records))

    if not records:
        return JsonResponse({'data': [], 'layout': {
            'yaxis': {'title': _('Tokens')},
            'xaxis': {'title': _('Hour')},
            'barmode': 'stack',
        }})

    data = []
    for model in models:
        y = {}
        for r in records:
            if r['model'] == model:
                y[r['hour']] = r['total']

        x = [h.strftime('%Y-%m-%d %H:%M:%S') for h in hours]
        y_vals = [y.get(h, 0) for h in hours]

        data.append({
            'x': x,
            'y': y_vals,
            'type': 'bar',
            'name': model,
            'hovertemplate': f'<b>{model}</b><br>%{{x}}<br>Tokens: %{{y:,.0f}}<extra></extra>',
        })

    return JsonResponse({'data': data, 'layout': {
        'barmode': 'stack',
        'yaxis': {'title': _('Tokens')},
        'xaxis': {'title': _('Hour')},
    }})
