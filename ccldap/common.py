from ccldap.models import LdapAllocation


def convert_ldap_to_allocation(ldap_object):
    computes = []
    for alloc in ldap_object:
        resources = alloc.parse_active_resources()
        for resource in resources:
            if 'cpu' in resource:
                computes.append({
                    'name': alloc.name + '_cpu',
                    'cpu': resource['cpu'],
                })
            if 'gpu' in resource:
                computes.append({
                    'name': alloc.name + '_gpu',
                    'gpu': resource['gpu'],
                })
            if alloc.name.startswith('def-'):
                computes.append({
                    'name': alloc.name + '_cpu',
                    'cpu': None,
                })
                computes.append({
                    'name': alloc.name + '_gpu',
                    'gpu': None,
                })
    return computes


def cc_storage_allocations(username):
    """
    Handle the default and allocated storage for a user.
    The allocation information is stored in the ldap database.
    """
    allocations = LdapAllocation.objects.filter(members=username, status='active').all()
    storage = []
    storage.append({
        'name': username,
        'type': 'home',
        'quota_bytes': int(50 * 1024 * 1024 * 1024),
        'quota_inodes': int(0.5 * 1000 * 1000),
    })
    storage.append({
        'name': username,
        'type': 'scratch',
        'quota_bytes': int(20.0 * 1024 * 1024 * 1024 * 1024),
        'quota_inodes': int(1 * 1000 * 1000),
    })
    for alloc in allocations:
        resources = alloc.parse_active_resources()
        for resource in resources:
            if 'project_storage_tb' in resource:
                storage_tb = resource['project_storage_tb']
            else:
                storage_tb = 1.0  # default to 1TB
            if 'inode_quota' in resource:
                inodes_quota = resource['inode_quota']
            else:
                inodes_quota = 0.5  # default to 500k inodes, specified in millions in ldap

            storage.append({
                'name': alloc.name,
                'type': 'project',
                'quota_bytes': int(storage_tb * 1024 * 1024 * 1024 * 1024),
                'quota_inodes': int(inodes_quota * 1000 * 1000),
            })

    return storage


def cc_compute_allocations_by_user(username):
    allocations = LdapAllocation.objects.filter(members=username, status='active').all()
    return convert_ldap_to_allocation(allocations)


def cc_compute_allocations_by_account(account):
    allocations = LdapAllocation.objects.filter(name=account, status='active').all()
    return convert_ldap_to_allocation(allocations)
