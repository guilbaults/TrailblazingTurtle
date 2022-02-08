from ccldap.models import LdapAllocation


def storage_allocations(username):
    allocations = LdapAllocation.objects.filter(members=username, status='active').all()
    projects = []
    nearlines = []
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
            if 'project_storage_tb' in resource or 'inode_quota' in resource:
                project['name'] = alloc.name
                if 'project_storage_tb' in resource:
                    project['project_storage_tb'] = resource['project_storage_tb']
                if 'inode_quota' in resource:
                    project['inode_quota'] = resource['inode_quota']
                projects.append(project)
            if 'nearline_storage_tb' in resource:
                nearline['name'] = alloc.name
                nearline['nearline_storage_tb'] = resource['nearline_storage_tb']
            if nearline['nearline_storage_tb'] != float(0.0):
                nearlines.append(nearline)
    return(projects, nearlines)
