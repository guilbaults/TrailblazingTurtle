from .models import AcctStat
from django.db.models import Q, Sum


def project_user_quota(gid):
    query = (
        AcctStat.objects.using('rbh-lustre03')
        .filter(gid=gid)
        .exclude(uid='root')
        .filter(Q(lhsm_status='') | Q(lhsm_status='new'))
        .annotate(Sum('count'))
        .annotate(Sum('blocks'))
        .filter(count__sum__gt=2)
        .order_by('-blocks__sum')
        .all()
    )
    prepared_user_quota = []
    for item in query.iterator():
        prepared_user_quota.append({
            'uid_string': item.uid_string,
            'count__sum': item.count__sum,
            'bytes__sum': item.blocks__sum * 512
        })
    return prepared_user_quota


def nearline_user_quota(gid):
    prepared_nearline_quota = []
    nearline_user_on_disk = (
        AcctStat.objects.using('rbh-lustre03')
        .filter(gid=gid)
        .exclude(uid='root')
        .exclude(lhsm_status='')
        .exclude(lhsm_status='new')
        .exclude(lhsm_status='released')
        .annotate(Sum('count'))
        .annotate(Sum('blocks'))
        .filter(count__sum__gt=2)
        .order_by('-blocks__sum')
        .all()
    )

    nearline_user_on_tape = (
        AcctStat.objects.using('rbh-lustre03')
        .filter(gid=gid)
        .exclude(uid='root')
        .filter(lhsm_status='released')
        .annotate(Sum('count'))
        .annotate(Sum('size'))
        .filter(size__sum__gt=2)
        .order_by('-size__sum')
        .all()
    )

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

    for key in nearline_per_user:
        prepared_nearline_quota.append(nearline_per_user[key])

    return prepared_nearline_quota


def project_used(gid, project):
    # project parameter contains data about allocation of this project
    query = (
        AcctStat.objects.using('rbh-lustre03')
        .all()
        .filter(gid=gid)
        .filter(Q(lhsm_status='') | Q(lhsm_status='new'))
        .aggregate(count=Sum('count'), blocks=Sum('blocks'))
    )

    if query['count'] is None:
        return {
            'inodes': 0,
            'TBs': 0,
            'bytes_ratio': 0.0,
            'inode_ratio': 0.0,
        }
    else:
        return {
            'inodes': query['count'],
            'TBs': query['blocks'] * 512 / 1024 / 1024 / 1024 / 1024,
            'bytes_ratio': query['blocks'] * 512 / (project['project_storage_tb'] * 1024 * 1024 * 1024 * 1024) * 100,
            'inodes_ratio': query['count'] / (project['inode_quota'] * 1000000) * 100,
        }


def nearline_used(gid, nearline):
    # nearline parameter contains data about allocation
    nearline_on_disk = (
        AcctStat.objects.using('rbh-lustre03')
        .all()
        .filter(gid=gid)
        .exclude(lhsm_status='')
        .exclude(lhsm_status='new')
        .exclude(lhsm_status='released')
        .aggregate(count=Sum('count'), blocks=Sum('blocks'))
    )
    nearline_on_tape = (
        AcctStat.objects.using('rbh-lustre03')
        .all()
        .filter(gid=gid)
        .filter(lhsm_status='released')
        .aggregate(count=Sum('count'), size=Sum('size'))
    )

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

    return {
        'inodes': nearline_inodes,
        'total_bytes': nearline_storage,
        'bytes_on_disk': nearline_on_disk['blocks'] * 512,
        'bytes_on_tape': nearline_on_tape['size'],
        'bytes_ratio_disk': nearline_on_disk['blocks'] * 512 / (nearline['nearline_storage_tb'] * 1024 * 1024 * 1024 * 1024) * 100,
        'bytes_ratio_tape': nearline_on_tape['size'] / (nearline['nearline_storage_tb'] * 1024 * 1024 * 1024 * 1024) * 100,
    }
