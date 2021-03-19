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

        if project_used['count'] is None:
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
        project['users'] = prepared_user_quota
        context['projects'].append(project)

        if nearline['nearline_storage_tb'] == float(0.0):
            continue

        nearline_user_on_disk = AcctStat.objects.using('rbh-lustre03')\
.filter(gid=alloc.name)\
.exclude(uid='root')\
.exclude(lhsm_status='')\
.exclude(lhsm_status='new')\
.exclude(lhsm_status='released')\
.annotate(Sum('count'))\
.annotate(Sum('blocks'))\
.filter(count__sum__gt=2)\
.order_by('-blocks__sum')\
.all()

        nearline_user_on_tape = AcctStat.objects.using('rbh-lustre03')\
.filter(gid=alloc.name)\
.exclude(uid='root')\
.filter(lhsm_status='released')\
.annotate(Sum('count'))\
.annotate(Sum('size'))\
.filter(size__sum__gt=2)\
.order_by('-size__sum')\
.all()

        nearline_on_disk = AcctStat.objects.using('rbh-lustre03')\
.all()\
.filter(gid=alloc.name)\
.exclude(lhsm_status='')\
.exclude(lhsm_status='new')\
.exclude(lhsm_status='released')\
.aggregate(count=Sum('count'), blocks=Sum('blocks'))
        nearline_on_tape = AcctStat.objects.using('rbh-lustre03')\
.all()\
.filter(gid=alloc.name)\
.filter(lhsm_status='released')\
.aggregate(count=Sum('count'), size=Sum('size'))

        nearline_per_user = {}
        for item in nearline_user_on_disk.iterator():
            name = item.uid_string()
            if name in nearline_per_user:
                nearline_per_user[name]['disk_inodes'] = item.count__sum
                nearline_per_user[name]['disk_bytes'] = item.bytes__sum
            else:
                nearline_per_user[name] = {
                    'disk_inodes': item.count__sum,
                    'disk_bytes': item.blocks__sum * 512,
                    'name': name,
                }
        for item in nearline_user_on_tape.iterator():
            # When on tape, blocks is 0, so we need to use the size
            name = item.uid_string()
            if name in nearline_per_user:
                nearline_per_user[name]['tape_inodes'] = item.count__sum
                nearline_per_user[name]['tape_bytes'] = item.size__sum
            else:
                nearline_per_user[name] = {
                    'tape_inodes': item.count__sum,
                    'tape_bytes': item.size__sum,
                    'name': name,
                }

        prepared_nearline_quota = []
        for key in nearline_per_user:
            prepared_nearline_quota.append(nearline_per_user[key])

        nearline['users'] = prepared_nearline_quota

        if nearline_on_disk['count'] is None:
            nearline_on_disk['count'] = 0
        if nearline_on_tape['count'] is None:
            nearline_on_tape['count'] = 0
        if nearline_on_disk['blocks'] is None:
            nearline_on_disk['blocks'] = 0
        if nearline_on_tape['size'] is None:
            nearline_on_tape['size'] = 0
        nearline_inodes = nearline_on_disk['count'] + nearline_on_tape['count'] 
        nearline_storage = (nearline_on_disk['blocks'] * 512) + (nearline_on_tape['size'])

        nearline['used'] = {
            'inodes': nearline_inodes,
            'total_bytes': nearline_storage,
            'bytes_on_disk': nearline_on_disk['blocks'] * 512,
            'bytes_on_tape': nearline_on_tape['size'],
            'bytes_ratio_disk': nearline_on_disk['blocks'] * 512 / (nearline['nearline_storage_tb'] * 1024 * 1024 * 1024 * 1024) * 100,
            'bytes_ratio_tape': nearline_on_tape['size'] / (nearline['nearline_storage_tb'] * 1024 * 1024 * 1024 * 1024) * 100,
        }

        context['nearlines'].append(nearline)

    return render(request, 'quotas/index.html', context)
