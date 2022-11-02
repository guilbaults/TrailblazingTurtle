import pwd


"""
This example is using MagicCastle and FreeIPA
https://github.com/ComputeCanada/magic_castle/
"""


def compute_allocations_by_user(username):
    """
    return the compute allocations for a user as a list of dictionaries with the following keys:
    - name: the name of the allocation
    - cpu: the number of cpu allocated to the user (optional)
    - gpu: the number of gpu allocated to the user (optional)
    """
    return [{'name': 'def-sponsor00', 'cpu': 1, }]


def compute_allocations_by_account(account):
    """
    return the compute allocations for a user as a list of dictionaries with the following keys:
    - name: the name of the allocation
    - cpu: the number of cpu allocated to the user (optional)
    - gpu: the number of gpu allocated to the user (optional)
    """
    return [{'name': 'def-sponsor00', 'cpu': 1, }]


def storage_allocations(username):
    """
    return the storage allocations for a user as a list of dictionaries with the following keys:
    - name: the name of the allocation
    - type: the type of the allocation (home, scratch, project or nearline as an example)
    - quota_bytes: the size of the allocation in bytes
    - quota_inodes: the inodes quota of the allocation
    """
    return [{'name': 'def-sponsor00', 'type': 'home', 'quota_bytes': 1000000000000, 'quota_inodes': 1000000}]


def username_to_uid(username):
    """return the uid of a username"""
    return int(pwd.getpwnam(username).pw_uid)


def uid_to_username(uid):
    """return the username of a uid"""
    return pwd.getpwuid(uid).pw_name
