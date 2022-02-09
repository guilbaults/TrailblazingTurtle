from ccldap.models import LdapAllocation


def storage_allocations(username):
    allocations = LdapAllocation.objects.filter(members=username, status='active').all()
    projects = []
    nearlines = []
    for alloc in allocations:
        resources = alloc.parse_active_resources()
        project = {
            'project_storage_tb': 1.0,
            'inodes_quota': int(1.0 * 1000 * 1000),  # specified in millions in ldap
        }
        nearline = {
            'nearline_storage_tb': 0.0,
        }
        for resource in resources:
            if 'project_storage_tb' in resource or 'inode_quota' in resource:
                project['name'] = alloc.name
                if 'project_storage_tb' in resource:
                    project['project_storage_tb'] = resource['project_storage_tb']
                    project['project_storage_bytes'] = int(project['project_storage_tb'] * 1024 * 1024 * 1024 * 1024)
                if 'inode_quota' in resource:
                    project['inodes_quota'] = int(resource['inode_quota'] * 1000 * 1000)  # convert millions to integers
                projects.append(project)
            if 'nearline_storage_tb' in resource:
                nearline['name'] = alloc.name
                nearline['nearline_storage_tb'] = resource['nearline_storage_tb']
            if nearline['nearline_storage_tb'] != float(0.0):
                nearlines.append(nearline)
    return(projects, nearlines)
