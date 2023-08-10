from django.shortcuts import render, redirect
from django.http import HttpResponseNotFound, HttpResponseForbidden, JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.conf import settings
from django.utils.translation import gettext as _


from userportal.common import user_or_staff, username_to_uid, query_time, staff
from ccldap.models import LdapUser, LdapCCAccount, LdapAllocation
from slurm.models import AcctTable
from userportal.common import Prometheus

prom = Prometheus(settings.PROMETHEUS)

@login_required
@staff
def index(request):
    return render(request, 'search/index.html')

@login_required
@staff
def query(request):
    querystring = request.GET.get('query')
    results = []

    # Return early for empty string or only whitespace
    if len(querystring.split()) == 0:
        return JsonResponse({'query': querystring, 'results': results})

    # Query LDAP for users
    users = (LdapUser.objects.filter(username__contains=querystring).all()) | (LdapUser.objects.filter(full_name__contains=querystring).all())

    for user in users:
        results.append({
            'typetext': _('User'),
            'typefeathericon': 'user',
            'name': user.full_name,
            'username': user.username,
            'hyperlink': f'{settings.BASE_URL}secure/usersummary/{user.username}'
        })

    # Query SlurmDB for accounts
    slurmaccounts = AcctTable.objects.filter(name__contains=querystring).all()
    for account in slurmaccounts:
        results.append({
            'typetext': _('Slurm Account'),
            'typefeathericon': 'users',
            'name': account.name,
            'username': account.description,
            'hyperlink': f'{settings.BASE_URL}secure/accountstats/{account.name}'
        })

    if len(results) > 25:
        results = results[0:25]
        results_truncated = True
    else:
        results_truncated = False

    resp = {
        'query': querystring,
        'results': results,
        'truncated': results_truncated
    }
    return JsonResponse(resp)