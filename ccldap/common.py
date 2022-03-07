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


def convert_ldap_to_allocation(ldap_object):
    computes = []
    for alloc in ldap_object:
        resources = alloc.parse_active_resources()
        for resource in resources:
            if 'cpu' in resource:
                compute = {
                    'name': alloc.name,
                    'cpu': resource['cpu'],
                    'core_equivalent': resource['core_equivalent'],
                }
                computes.append(compute)
            if 'gpu' in resource:
                compute = {
                    'name': alloc.name,
                    'gpu': resource['gpu'],
                    'gpu_equivalent': resource['gpu_equivalent'],
                }
                computes.append(compute)
    return(computes)


def compute_allocations_by_user(username):
    allocations = LdapAllocation.objects.filter(members=username, status='active').all()
    return convert_ldap_to_allocation(allocations)


def compute_allocation_by_account(account):
    allocations = LdapAllocation.objects.filter(name=account, status='active').all()
    return convert_ldap_to_allocation(allocations)


def compute_allocations_by_slurm_account(account):
    # takes a slurm account name and return the number of cpu or gpu allocated to that account
    account_name = account.rstrip('_gpu').rstrip('_cpu')
    allocations = compute_allocation_by_account(account_name)
    if account.endswith('_gpu'):
        for alloc in allocations:
            if 'gpu' in alloc:
                return alloc['gpu']
    else:
        for alloc in allocations:
            if 'cpu' in alloc:
                return alloc['cpu']
    return None
