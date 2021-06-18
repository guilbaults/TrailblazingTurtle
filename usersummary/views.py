from django.shortcuts import render, redirect
from ccldap.models import LdapAllocation
from userportal.common import user_or_staff
#from .models import AcctStat
from django.db.models import Q, Sum
from django.contrib.auth.decorators import login_required


@login_required
def index(request):
    return redirect('{}/'.format(request.user.username.split('@')[0]))

@login_required
@user_or_staff
def user(request, username):
    context = {}
    return render(request, 'usersummary/user.html', context)
