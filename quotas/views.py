from django.shortcuts import render
from .models import LdapAllocation

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

        context['projects'].append(project)
        context['nearlines'].append(nearline)

    return render(request, 'quotas/index.html', context)
