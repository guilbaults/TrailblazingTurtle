# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models
import datetime
from django.conf import settings
import re
import time
from userportal.common import uid_to_username

# regex to parse dependencies from the submit line
RE_DEPS = re.compile(r'(--depend=|--dependency=|-d )(afterok|afterany|afterburstbuffer|aftercorr|afternotok|after):([:\d]+)')


# from https://github.com/NERSC/slurm-helpers/blob/master/slurm_utils.py
def expand_nodelist(nlist: str, as_list=False) -> str:
    """ translate a nodelist like 'nid[02516-02575,02580-02635,02836]' into a
        list of explicitly-named nodes, eg 'nid02516 nid02517 ...'
    """
    nodes = []
    if nlist.count('[') != nlist.count(']'):
        raise Exception("Incomplete nodelist: {}".format(nlist))
    prefix, sep0, nl = nlist.partition('[')
    if sep0:
        for component in nl.rstrip(']').split(','):
            first, sep1, last = component.partition('-')
            width = '0{:d}'.format(len(first))
            if sep1:
                nodes += ['{0:s}{2:{1:s}d}'.format(prefix, width, i)
                          for i in range(int(first), int(last) + 1)]
            else:
                nodes += ['{0:s}{2:{1:s}d}'.format(prefix, width, int(first))]
    else:
        nodes += [prefix]
    if as_list:
        return nodes
    else:
        return ' '.join(nodes)


class AcctCoordTable(models.Model):
    creation_time = models.PositiveBigIntegerField()
    mod_time = models.PositiveBigIntegerField()
    deleted = models.IntegerField(blank=True, null=True)
    acct = models.TextField(primary_key=True)
    user = models.TextField()

    class Meta:
        managed = False
        db_table = 'acct_coord_table'
        unique_together = (('acct', 'user'),)


class AcctTable(models.Model):
    creation_time = models.PositiveBigIntegerField()
    mod_time = models.PositiveBigIntegerField()
    deleted = models.IntegerField(blank=True, null=True)
    name = models.TextField(primary_key=True)
    description = models.TextField()
    organization = models.TextField()

    class Meta:
        managed = False
        db_table = 'acct_table'


class AssocTable(models.Model):
    creation_time = models.PositiveBigIntegerField()
    mod_time = models.PositiveBigIntegerField()
    deleted = models.IntegerField()
    is_def = models.IntegerField()
    id_assoc = models.AutoField(primary_key=True)
    user = models.TextField()
    acct = models.TextField()
    partition = models.TextField()
    parent_acct = models.TextField()
    lft = models.IntegerField()
    rgt = models.IntegerField()
    shares = models.IntegerField()
    max_jobs = models.IntegerField(blank=True, null=True)
    max_jobs_accrue = models.IntegerField(blank=True, null=True)
    min_prio_thresh = models.IntegerField(blank=True, null=True)
    max_submit_jobs = models.IntegerField(blank=True, null=True)
    max_tres_pj = models.TextField()
    max_tres_pn = models.TextField()
    max_tres_mins_pj = models.TextField()
    max_tres_run_mins = models.TextField()
    max_wall_pj = models.IntegerField(blank=True, null=True)
    grp_jobs = models.IntegerField(blank=True, null=True)
    grp_jobs_accrue = models.IntegerField(blank=True, null=True)
    grp_submit_jobs = models.IntegerField(blank=True, null=True)
    grp_tres = models.TextField()
    grp_tres_mins = models.TextField()
    grp_tres_run_mins = models.TextField()
    grp_wall = models.IntegerField(blank=True, null=True)
    priority = models.PositiveIntegerField(blank=True, null=True)
    def_qos_id = models.IntegerField(blank=True, null=True)
    qos = models.TextField()
    delta_qos = models.TextField()

    class Meta:
        managed = False
        db_table = settings.CLUSTER_NAME + '_assoc_table'
        unique_together = (('user', 'acct', 'partition'),)


class AssocUsageDayTable(models.Model):
    creation_time = models.PositiveBigIntegerField()
    mod_time = models.PositiveBigIntegerField()
    deleted = models.IntegerField()
    id = models.PositiveIntegerField(primary_key=True)
    id_tres = models.IntegerField()
    time_start = models.PositiveBigIntegerField()
    alloc_secs = models.PositiveBigIntegerField()

    class Meta:
        managed = False
        db_table = settings.CLUSTER_NAME + '_assoc_usage_day_table'
        unique_together = (('id', 'id_tres', 'time_start'),)


class AssocUsageHourTable(models.Model):
    creation_time = models.PositiveBigIntegerField()
    mod_time = models.PositiveBigIntegerField()
    deleted = models.IntegerField()
    id = models.PositiveIntegerField(primary_key=True)
    id_tres = models.IntegerField()
    time_start = models.PositiveBigIntegerField()
    alloc_secs = models.PositiveBigIntegerField()

    class Meta:
        managed = False
        db_table = settings.CLUSTER_NAME + '_assoc_usage_hour_table'
        unique_together = (('id', 'id_tres', 'time_start'),)


class AssocUsageMonthTable(models.Model):
    creation_time = models.PositiveBigIntegerField()
    mod_time = models.PositiveBigIntegerField()
    deleted = models.IntegerField()
    id = models.PositiveIntegerField(primary_key=True)
    id_tres = models.IntegerField()
    time_start = models.PositiveBigIntegerField()
    alloc_secs = models.PositiveBigIntegerField()

    class Meta:
        managed = False
        db_table = settings.CLUSTER_NAME + '_assoc_usage_month_table'
        unique_together = (('id', 'id_tres', 'time_start'),)


class EventTable(models.Model):
    time_start = models.PositiveBigIntegerField()
    time_end = models.PositiveBigIntegerField()
    node_name = models.TextField(primary_key=True)
    cluster_nodes = models.TextField()
    reason = models.TextField()
    reason_uid = models.PositiveIntegerField()
    state = models.PositiveIntegerField()
    tres = models.TextField()

    class Meta:
        managed = False
        db_table = settings.CLUSTER_NAME + '_event_table'
        unique_together = (('node_name', 'time_start'),)

    def time_start_dt(self):
        if self.time_start == 0:
            return None
        return datetime.datetime.fromtimestamp(self.time_start)

    def time_end_dt(self):
        if self.time_end == 0:
            return None
        return datetime.datetime.fromtimestamp(self.time_end)

    def duration_dt(self):
        if self.time_end == 0:
            return None
        return self.time_end_dt() - self.time_start_dt()


class JobTable(models.Model):
    class StatesJob(models.IntegerChoices):
        PENDING = 0
        RUNNING = 1
        SUSPENDED = 2
        COMPLETE = 3
        CANCELED = 4
        FAILED = 5
        TIMEOUT = 6
        NODE_FAIL = 7
        PREEMPTED = 8
        BOOT_FAIL = 9
        END = 10
        OOM = 11

    job_db_inx = models.BigAutoField(primary_key=True)
    mod_time = models.PositiveBigIntegerField()
    deleted = models.IntegerField()
    account = models.TextField(blank=True, null=True)
    admin_comment = models.TextField(blank=True, null=True)
    array_task_str = models.TextField(blank=True, null=True)
    array_max_tasks = models.PositiveIntegerField()
    array_task_pending = models.PositiveIntegerField()
    constraints = models.TextField(blank=True, null=True)
    cpus_req = models.PositiveIntegerField()
    derived_ec = models.PositiveIntegerField()
    derived_es = models.TextField(blank=True, null=True)
    exit_code = models.PositiveIntegerField()
    flags = models.PositiveIntegerField()
    job_name = models.TextField()
    id_assoc = models.ForeignKey(AssocTable, on_delete=models.PROTECT, db_column='id_assoc')
    id_array_job = models.PositiveIntegerField()
    id_array_task = models.PositiveIntegerField()
    id_block = models.TextField(blank=True, null=True)
    id_job = models.PositiveIntegerField()
    id_qos = models.PositiveIntegerField()
    id_resv = models.PositiveIntegerField()
    id_wckey = models.PositiveIntegerField()
    id_user = models.PositiveIntegerField()
    id_group = models.PositiveIntegerField()
    kill_requid = models.IntegerField()
    state_reason_prev = models.PositiveIntegerField()
    mcs_label = models.TextField(blank=True, null=True)
    mem_req = models.PositiveBigIntegerField()
    nodelist = models.TextField(blank=True, null=True)
    nodes_alloc = models.PositiveIntegerField()
    node_inx = models.TextField(blank=True, null=True)
    partition = models.TextField()
    priority = models.PositiveIntegerField()
    state = models.PositiveIntegerField(choices=StatesJob.choices)
    timelimit = models.PositiveIntegerField()
    time_submit = models.PositiveBigIntegerField()
    time_eligible = models.PositiveBigIntegerField()
    time_start = models.PositiveBigIntegerField()
    time_end = models.PositiveBigIntegerField()
    time_suspended = models.PositiveBigIntegerField()
    gres_used = models.TextField()
    wckey = models.TextField()
    work_dir = models.TextField()
    system_comment = models.TextField(blank=True, null=True)
    tres_alloc = models.TextField()
    tres_req = models.TextField()
    submit_line = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = settings.CLUSTER_NAME + '_job_table'
        unique_together = (('id_job', 'time_submit'),)

    def time_submit_dt(self):
        if self.time_submit == 0:
            return None
        return datetime.datetime.fromtimestamp(self.time_submit)

    def time_eligible_dt(self):
        if self.time_eligible == 0:
            return None
        return datetime.datetime.fromtimestamp(self.time_eligible)

    def time_start_dt(self):
        if self.time_start == 0:
            return None
        return datetime.datetime.fromtimestamp(self.time_start)

    def time_end_dt(self):
        if self.time_end == 0:
            return None
        return datetime.datetime.fromtimestamp(self.time_end)

    def time_suspended_dt(self):
        if self.time_suspended == 0:
            return None
        return datetime.datetime.fromtimestamp(self.time_suspended)

    def time_in_queue_dt(self):
        if self.time_start == 0:
            # job hasn't started yet, return difference from now
            return datetime.datetime.now() - self.time_submit_dt()
        return self.time_start_dt() - self.time_submit_dt()

    def used_time(self):
        if self.time_start != 0 and self.time_end != 0:
            # job started and finished
            return self.time_end - self.time_start
        elif self.time_start != 0 and self.time_end == 0:
            # job started but not finished
            return time.time() - self.time_start
        else:
            return None

    def used_time_display(self):
        used = self.used_time()
        if used is not None:
            t = used / 60
            if t > 60 * 4:
                return '{:.1f}h'.format(t / 60)
            else:
                return '{:.1f}m'.format(t)
        return None

    def timelimit_display(self):
        if self.timelimit > 60 * 4:
            return '{:.1f}h'.format(self.timelimit / 60)
        else:
            return '{:.1f}m'.format(self.timelimit)

    def status(self):
        status = ['Pending', 'Running', 'Suspended', 'Complete', 'Cancelled',
                  'Failed', 'Timeout', 'Node failed', 'Preempted',
                  'Boot failed', 'End', 'OOM']
        return status[self.state]

    def status_badge(self):
        status = ['info', 'primary', 'warning', 'success', 'danger',
                  'danger', 'danger', 'danger', 'warning', 'danger',
                  'sucess', 'danger']
        return '{}'.format(status[self.state])

    def gpu_count(self):
        __gpu_count = 0
        for key in settings.SLURM_TRES:
            gpu_match = re.match(r".*%s(\d+)" % key, self.tres_alloc)
            if gpu_match:
                __gpu_count += int(gpu_match.group(1))
        return __gpu_count

    def gpu_type(self):
        for key in settings.SLURM_TRES:
            if key in self.tres_alloc:
                return settings.SLURM_TRES[key]
        return None

    def wallclock_progress(self):
        if self.time_start == 0:
            return 0
        elif self.time_end != 0:
            return 100
        else:
            delta = datetime.datetime.now() - self.time_start_dt()
            return (delta.total_seconds() / (self.timelimit * 60)) * 100

    def parse_tres_req(self):
        info = {}
        for item in self.tres_req.split(','):
            key, value = item.split('=')
            if key == '1':
                info['total_cores'] = int(value)
            elif key == '2':
                info['total_mem'] = int(value)
            elif key == '4':
                info['nb_nodes'] = int(value)

        # Sometime the total_mem is not in TRES, so we use the other column
        # in the DB
        if 'total_mem' not in info:
            info['total_mem'] = self.mem_req
        return info

    def nodes(self):
        return expand_nodelist(self.nodelist, as_list=True)

    def username(self):
        # convert user id to username from ldap database
        return uid_to_username(self.id_user)

    # internal function to parse dependencies
    def parse_deps(self, submit_line):
        # parse dependencies from the submit line
        deps = []
        for match in re.findall(RE_DEPS, submit_line):
            params = match[2].split(':')
            jobs = JobTable.objects.filter(id_user=self.id_user)\
                .filter(id_job__in=params)
            for job in jobs:
                deps.append({
                    'type': match[1],
                    'job': job,
                })
        return deps

    # dependencies of this job
    def dependencies(self):
        return self.parse_deps(self.submit_line)

    # jobs that depend on this job
    def depends_on_this(self):
        deps = []
        # basic filtering with a regex in the database
        jobs = JobTable.objects\
            .filter(submit_line__regex='.*{}.*'.format(self.id_job))\
            .filter(id_user=self.id_user)
        for job in jobs:
            for depend in job.parse_deps(job.submit_line):
                # found a dependency on this job
                if depend['job'].id_job == self.id_job:
                    deps.append({
                        'type': depend['type'],
                        'job': job,
                    })
        return deps


class LastRanTable(models.Model):
    hourly_rollup = models.PositiveBigIntegerField(primary_key=True)
    daily_rollup = models.PositiveBigIntegerField()
    monthly_rollup = models.PositiveBigIntegerField()

    class Meta:
        managed = False
        db_table = settings.CLUSTER_NAME + '_last_ran_table'
        unique_together = (('hourly_rollup', 'daily_rollup', 'monthly_rollup'),)


class ResvTable(models.Model):
    id_resv = models.PositiveIntegerField(primary_key=True)
    deleted = models.IntegerField()
    assoclist = models.TextField()
    flags = models.PositiveBigIntegerField()
    nodelist = models.TextField()
    node_inx = models.TextField()
    resv_name = models.TextField()
    time_start = models.PositiveBigIntegerField()
    time_end = models.PositiveBigIntegerField()
    tres = models.TextField()
    unused_wall = models.FloatField()

    class Meta:
        managed = False
        db_table = settings.CLUSTER_NAME + '_resv_table'
        unique_together = (('id_resv', 'time_start'),)


class StepTable(models.Model):
    job_db_inx = models.PositiveBigIntegerField(primary_key=True)
    deleted = models.IntegerField()
    exit_code = models.IntegerField()
    id_step = models.IntegerField()
    kill_requid = models.IntegerField()
    nodelist = models.TextField()
    nodes_alloc = models.PositiveIntegerField()
    node_inx = models.TextField(blank=True, null=True)
    state = models.PositiveSmallIntegerField()
    step_name = models.TextField()
    task_cnt = models.PositiveIntegerField()
    task_dist = models.SmallIntegerField()
    time_start = models.PositiveBigIntegerField()
    time_end = models.PositiveBigIntegerField()
    time_suspended = models.PositiveBigIntegerField()
    user_sec = models.PositiveIntegerField()
    user_usec = models.PositiveIntegerField()
    sys_sec = models.PositiveIntegerField()
    sys_usec = models.PositiveIntegerField()
    act_cpufreq = models.FloatField()
    consumed_energy = models.PositiveBigIntegerField()
    req_cpufreq_min = models.PositiveIntegerField()
    req_cpufreq = models.PositiveIntegerField()
    req_cpufreq_gov = models.PositiveIntegerField()
    tres_alloc = models.TextField()
    tres_usage_in_ave = models.TextField()
    tres_usage_in_max = models.TextField()
    tres_usage_in_max_taskid = models.TextField()
    tres_usage_in_max_nodeid = models.TextField()
    tres_usage_in_min = models.TextField()
    tres_usage_in_min_taskid = models.TextField()
    tres_usage_in_min_nodeid = models.TextField()
    tres_usage_in_tot = models.TextField()
    tres_usage_out_ave = models.TextField()
    tres_usage_out_max = models.TextField()
    tres_usage_out_max_taskid = models.TextField()
    tres_usage_out_max_nodeid = models.TextField()
    tres_usage_out_min = models.TextField()
    tres_usage_out_min_taskid = models.TextField()
    tres_usage_out_min_nodeid = models.TextField()
    tres_usage_out_tot = models.TextField()

    class Meta:
        managed = False
        db_table = settings.CLUSTER_NAME + '_step_table'
        unique_together = (('job_db_inx', 'id_step'),)


class SuspendTable(models.Model):
    job_db_inx = models.PositiveBigIntegerField(primary_key=True)
    id_assoc = models.IntegerField()
    time_start = models.PositiveBigIntegerField()
    time_end = models.PositiveBigIntegerField()

    class Meta:
        managed = False
        db_table = settings.CLUSTER_NAME + '_suspend_table'
        unique_together = (('job_db_inx', 'time_start'),)


class UsageDayTable(models.Model):
    creation_time = models.PositiveBigIntegerField()
    mod_time = models.PositiveBigIntegerField()
    deleted = models.IntegerField()
    id_tres = models.IntegerField(primary_key=True)
    time_start = models.PositiveBigIntegerField()
    count = models.PositiveBigIntegerField()
    alloc_secs = models.PositiveBigIntegerField()
    down_secs = models.PositiveBigIntegerField()
    pdown_secs = models.PositiveBigIntegerField()
    idle_secs = models.PositiveBigIntegerField()
    resv_secs = models.PositiveBigIntegerField()
    over_secs = models.PositiveBigIntegerField()

    class Meta:
        managed = False
        db_table = settings.CLUSTER_NAME + '_usage_day_table'
        unique_together = (('id_tres', 'time_start'),)


class UsageHourTable(models.Model):
    creation_time = models.PositiveBigIntegerField()
    mod_time = models.PositiveBigIntegerField()
    deleted = models.IntegerField()
    id_tres = models.IntegerField(primary_key=True)
    time_start = models.PositiveBigIntegerField()
    count = models.PositiveBigIntegerField()
    alloc_secs = models.PositiveBigIntegerField()
    down_secs = models.PositiveBigIntegerField()
    pdown_secs = models.PositiveBigIntegerField()
    idle_secs = models.PositiveBigIntegerField()
    resv_secs = models.PositiveBigIntegerField()
    over_secs = models.PositiveBigIntegerField()

    class Meta:
        managed = False
        db_table = settings.CLUSTER_NAME + '_usage_hour_table'
        unique_together = (('id_tres', 'time_start'),)


class UsageMonthTable(models.Model):
    creation_time = models.PositiveBigIntegerField()
    mod_time = models.PositiveBigIntegerField()
    deleted = models.IntegerField()
    id_tres = models.IntegerField(primary_key=True)
    time_start = models.PositiveBigIntegerField()
    count = models.PositiveBigIntegerField()
    alloc_secs = models.PositiveBigIntegerField()
    down_secs = models.PositiveBigIntegerField()
    pdown_secs = models.PositiveBigIntegerField()
    idle_secs = models.PositiveBigIntegerField()
    resv_secs = models.PositiveBigIntegerField()
    over_secs = models.PositiveBigIntegerField()

    class Meta:
        managed = False
        db_table = settings.CLUSTER_NAME + '_usage_month_table'
        unique_together = (('id_tres', 'time_start'),)


class WckeyTable(models.Model):
    creation_time = models.PositiveBigIntegerField()
    mod_time = models.PositiveBigIntegerField()
    deleted = models.IntegerField()
    is_def = models.IntegerField()
    id_wckey = models.AutoField(primary_key=True)
    wckey_name = models.TextField()
    user = models.TextField()

    class Meta:
        managed = False
        db_table = settings.CLUSTER_NAME + '_wckey_table'
        unique_together = (('wckey_name', 'user'),)


class WckeyUsageDayTable(models.Model):
    creation_time = models.PositiveBigIntegerField()
    mod_time = models.PositiveBigIntegerField()
    deleted = models.IntegerField()
    id = models.PositiveIntegerField(primary_key=True)
    id_tres = models.IntegerField()
    time_start = models.PositiveBigIntegerField()
    alloc_secs = models.PositiveBigIntegerField()

    class Meta:
        managed = False
        db_table = settings.CLUSTER_NAME + '_wckey_usage_day_table'
        unique_together = (('id', 'id_tres', 'time_start'),)


class WckeyUsageHourTable(models.Model):
    creation_time = models.PositiveBigIntegerField()
    mod_time = models.PositiveBigIntegerField()
    deleted = models.IntegerField()
    id = models.PositiveIntegerField(primary_key=True)
    id_tres = models.IntegerField()
    time_start = models.PositiveBigIntegerField()
    alloc_secs = models.PositiveBigIntegerField()

    class Meta:
        managed = False
        db_table = settings.CLUSTER_NAME + '_wckey_usage_hour_table'
        unique_together = (('id', 'id_tres', 'time_start'),)


class WckeyUsageMonthTable(models.Model):
    creation_time = models.PositiveBigIntegerField()
    mod_time = models.PositiveBigIntegerField()
    deleted = models.IntegerField()
    id = models.PositiveIntegerField(primary_key=True)
    id_tres = models.IntegerField()
    time_start = models.PositiveBigIntegerField()
    alloc_secs = models.PositiveBigIntegerField()

    class Meta:
        managed = False
        db_table = settings.CLUSTER_NAME + '_wckey_usage_month_table'
        unique_together = (('id', 'id_tres', 'time_start'),)


class ClusResTable(models.Model):
    creation_time = models.PositiveBigIntegerField()
    mod_time = models.PositiveBigIntegerField()
    deleted = models.IntegerField(blank=True, null=True)
    cluster = models.TextField()
    res_id = models.IntegerField(primary_key=True)
    percent_allowed = models.PositiveIntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'clus_res_table'
        unique_together = (('res_id', 'cluster'), ('res_id', 'cluster'),)


class ClusterTable(models.Model):
    creation_time = models.PositiveBigIntegerField()
    mod_time = models.PositiveBigIntegerField()
    deleted = models.IntegerField(blank=True, null=True)
    name = models.TextField(primary_key=True)
    control_host = models.TextField()
    control_port = models.PositiveIntegerField()
    last_port = models.PositiveIntegerField()
    rpc_version = models.PositiveSmallIntegerField()
    classification = models.PositiveSmallIntegerField(blank=True, null=True)
    dimensions = models.PositiveSmallIntegerField(blank=True, null=True)
    plugin_id_select = models.PositiveSmallIntegerField(blank=True, null=True)
    flags = models.PositiveIntegerField(blank=True, null=True)
    federation = models.TextField()
    features = models.TextField()
    fed_id = models.PositiveIntegerField()
    fed_state = models.PositiveSmallIntegerField()

    class Meta:
        managed = False
        db_table = 'cluster_table'


class ConvertVersionTable(models.Model):
    mod_time = models.PositiveBigIntegerField()
    version = models.IntegerField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'convert_version_table'


class FederationTable(models.Model):
    creation_time = models.PositiveIntegerField()
    mod_time = models.PositiveIntegerField()
    deleted = models.IntegerField(blank=True, null=True)
    name = models.TextField(primary_key=True)
    flags = models.PositiveIntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'federation_table'


class QosTable(models.Model):
    id = models.AutoField(primary_key=True, null=False)
    creation_time = models.PositiveBigIntegerField()
    mod_time = models.PositiveBigIntegerField()
    deleted = models.IntegerField(blank=True, null=True)
    name = models.TextField(unique=True)
    description = models.TextField(blank=True, null=True)
    flags = models.PositiveIntegerField(blank=True, null=True)
    grace_time = models.PositiveIntegerField(blank=True, null=True)
    max_jobs_pa = models.IntegerField(blank=True, null=True)
    max_jobs_per_user = models.IntegerField(blank=True, null=True)
    max_jobs_accrue_pa = models.IntegerField(blank=True, null=True)
    max_jobs_accrue_pu = models.IntegerField(blank=True, null=True)
    min_prio_thresh = models.IntegerField(blank=True, null=True)
    max_submit_jobs_pa = models.IntegerField(blank=True, null=True)
    max_submit_jobs_per_user = models.IntegerField(blank=True, null=True)
    max_tres_pa = models.TextField()
    max_tres_pj = models.TextField()
    max_tres_pn = models.TextField()
    max_tres_pu = models.TextField()
    max_tres_mins_pj = models.TextField()
    max_tres_run_mins_pa = models.TextField()
    max_tres_run_mins_pu = models.TextField()
    min_tres_pj = models.TextField()
    max_wall_duration_per_job = models.IntegerField(blank=True, null=True)
    grp_jobs = models.IntegerField(blank=True, null=True)
    grp_jobs_accrue = models.IntegerField(blank=True, null=True)
    grp_submit_jobs = models.IntegerField(blank=True, null=True)
    grp_tres = models.TextField()
    grp_tres_mins = models.TextField()
    grp_tres_run_mins = models.TextField()
    grp_wall = models.IntegerField(blank=True, null=True)
    preempt = models.TextField()
    preempt_mode = models.IntegerField(blank=True, null=True)
    preempt_exempt_time = models.PositiveIntegerField(blank=True, null=True)
    priority = models.PositiveIntegerField(blank=True, null=True)
    usage_factor = models.FloatField()
    usage_thres = models.FloatField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'qos_table'


class ResTable(models.Model):
    id = models.AutoField(primary_key=True, null=False)
    creation_time = models.PositiveBigIntegerField()
    mod_time = models.PositiveBigIntegerField()
    deleted = models.IntegerField(blank=True, null=True)
    name = models.TextField()
    description = models.TextField(blank=True, null=True)
    manager = models.TextField()
    server = models.TextField()
    count = models.PositiveIntegerField(blank=True, null=True)
    type = models.PositiveIntegerField(blank=True, null=True)
    flags = models.PositiveIntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'res_table'
        unique_together = (('name', 'server', 'type'),)


class TableDefsTable(models.Model):
    creation_time = models.PositiveIntegerField()
    mod_time = models.PositiveIntegerField()
    table_name = models.TextField(primary_key=True)
    definition = models.TextField()

    class Meta:
        managed = False
        db_table = 'table_defs_table'


class TresTable(models.Model):
    id = models.AutoField(primary_key=True, null=False)
    creation_time = models.PositiveBigIntegerField()
    deleted = models.IntegerField()
    type = models.TextField()
    name = models.TextField()

    class Meta:
        managed = False
        db_table = 'tres_table'
        unique_together = (('type', 'name'),)


class TxnTable(models.Model):
    id = models.AutoField(primary_key=True, null=False)
    timestamp = models.PositiveBigIntegerField()
    action = models.SmallIntegerField()
    name = models.TextField()
    actor = models.TextField()
    cluster = models.TextField()
    info = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'txn_table'


class UserTable(models.Model):
    creation_time = models.PositiveBigIntegerField()
    mod_time = models.PositiveBigIntegerField()
    deleted = models.IntegerField(blank=True, null=True)
    name = models.TextField(primary_key=True)
    admin_level = models.SmallIntegerField()

    class Meta:
        managed = False
        db_table = 'user_table'
