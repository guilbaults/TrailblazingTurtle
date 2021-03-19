from django.shortcuts import render
from .models import LdapAllocation, AcctStat
from django.db.models import Q, Avg, Count, Min, Sum

def index(request):
    context = {}
    allocations = LdapAllocation.objects.filter(members='poq', status='active').all()
    context['projects'] = []
    context['nearlines'] = []
    for alloc in allocations:
        resources = alloc.parse_active_resources()
        project = {
            'project_storage_tb': 1.0,
            'inode_quota': 1.0,
        }
        nearline = {
            'nearline_storage_tb': 0.0,
        }
        for resource in resources:
            if 'project_storage_tb' in resource or inode_quota in resource:
                project['name'] = alloc.name
                if 'project_storage_tb' in resource:
                    project['project_storage_tb'] = resource['project_storage_tb']
                if 'inode_quota' in resource:
                    project['inode_quota'] = resource['inode_quota']

            if 'nearline_storage_tb' in resource:
                nearline['name'] = alloc.name
                nearline['nearline_storage_tb'] = resource['nearline_storage_tb']

        project_user_quota = AcctStat.objects.using('rbh-lustre03')\
.filter(gid=alloc.name)\
.exclude(uid='root')\
.filter(Q(lhsm_status='') | Q(lhsm_status='new'))\
.annotate(Sum('count'))\
.annotate(Sum('blocks'))\
.filter(count__sum__gt=2)\
.order_by('-blocks__sum')\
.all()
        prepared_user_quota = []
        for item in project_user_quota.iterator():
            prepared_user_quota.append({
                'uid_string': item.uid_string,
                'count__sum': item.count__sum,
                'bytes__sum': item.blocks__sum * 512
            })
        project['users'] = prepared_user_quota

        project_used = AcctStat.objects.using('rbh-lustre03')\
.all()\
.filter(gid=alloc.name)\
.filter(Q(lhsm_status='') | Q(lhsm_status='new'))\
.aggregate(count=Sum('count'), blocks=Sum('blocks'))

        nearline_on_disk = AcctStat.objects.using('rbh-lustre03')\
.all()\
.filter(gid=alloc.name)\
.exclude(lhsm_status='')\
.exclude(lhsm_status='new')\
.exclude(lhsm_status='released')\
.aggregate(count=Sum('count'), blocks=Sum('blocks'))
        nearline_released = AcctStat.objects.using('rbh-lustre03')\
.all()\
.filter(gid=alloc.name)\
.exclude(lhsm_status='')\
.exclude(lhsm_status='new')\
.exclude(lhsm_status='released')\
.aggregate(count=Sum('count'), size=Sum('size'))

        if project_used['count'] is None or project_used['blocks'] is None:
            project['used'] = {
                'inodes': 0,
                'TBs': 0,
                'bytes_ratio': 0.0,
                'inode_ratio': 0.0,
            }
        else:
            project['used'] = {
                'inodes': project_used['count'],
                'TBs': project_used['blocks'] * 512 / 1024 / 1024 / 1024 / 1024,
                'bytes_ratio': project_used['blocks'] * 512 / (project['project_storage_tb'] * 1024 * 1024 * 1024 * 1024) * 100,
                'inodes_ratio':  project_used['count'] / (project['inode_quota'] * 1000000) * 100,
            }

        context['projects'].append(project)
        context['nearlines'].append(nearline)

    return render(request, 'quotas/index.html', context)
