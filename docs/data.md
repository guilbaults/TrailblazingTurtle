# Data sources
Some features will not be available if the exporter required to gather the stats is not configured.

## slurm-job-exporter
[slurm-job-exporter](https://github.com/guilbaults/slurm-job-exporter) is used to capture informations from cgroup managed by slurm on each compute nodes. This gather CPU, memory and GPU utilization.

The following recorder rules are used to pre-aggregate stats shown in the user portal.

```
---
groups:
- name: recorder.rules
  rules:
  - record: slurm_job:allocated_core:count
    expr: count(slurm_job_core_usage_total) by (cluster)
  - record: slurm_job:allocated_core:count_user_account
    expr: count(slurm_job_core_usage_total) by (user,account,cluster)
  - record: slurm_job:used_core:sum
    expr: sum(rate(slurm_job_core_usage_total{}[2m]) / 1000000000) by (cluster)
  - record: slurm_job:used_core:sum_user_account
    expr: sum(rate(slurm_job_core_usage_total{}[2m]) / 1000000000) by (user,account, cluster)
  - record: slurm_job:allocated_memory:sum
    expr: sum(slurm_job_memory_limit{}) by (cluster)
  - record: slurm_job:allocated_memory:sum_user_account
    expr: sum(slurm_job_memory_limit{}) by (user,account,cluster)
  - record: slurm_job:rss_memory:sum
    expr: sum(slurm_job_memory_rss) by (cluster)
  - record: slurm_job:rss_memory:sum_user_account
    expr: sum(slurm_job_memory_rss) by (user, account, cluster)
  - record: slurm_job:max_memory:sum_user_account
    expr: sum(slurm_job_memory_max) by (user, account, cluster)
  - record: slurm_job:allocated_gpu:count
    expr: count(slurm_job_utilization_gpu) by (cluster)
  - record: slurm_job:allocated_gpu:count_user_account
    expr: count(slurm_job_utilization_gpu) by (user, account, cluster)
  - record: slurm_job:used_gpu:sum
    expr: sum(slurm_job_utilization_gpu) by (cluster)/ 100
  - record: slurm_job:used_gpu:sum_user_account
    expr: sum(slurm_job_utilization_gpu) by (user,account,cluster) / 100
  - record: slurm_job:non_idle_gpu:sum_user_account
    expr: count(slurm_job_utilization_gpu > 0) by (user,account,cluster)
  - record: slurm_job:power_gpu:sum
    expr: sum(slurm_job_power_gpu) by (cluster)
  - record: slurm_job:power_gpu:sum_user_account
    expr: sum(slurm_job_power_gpu) by (user,account,cluster)
```

## slurm-exporter
[slurm-exporter](https://github.com/guilbaults/prometheus-slurm-exporter/tree/osc) is used to capture informations from slurm like the priority of each users. This portal is using a fork, branch `osc` in the linked repository. This fork support GPU reporting and sshare stats.

## Access to the database of slurmacct
This mysql database is accessed with a read only user. It does not need to be in the same database server where django is storing its data.

## lustre\_exporter and lustre\_exporter\_slurm
Those 2 exporters are used to gather information about Lustre usage.

* [lustre\_exporter](https://github.com/HewlettPackard/lustre_exporter) capture information on Lustre MDS and OSS but will only use \$SLURM\_JOBID as a tag on the metrics.
* [lustre\_exporter\_slurm](https://github.com/guilbaults/lustre_exporter_slurm) is used as a proxy between Prometheus and lustre_exporter to improve the content of the tags. This will match the \$SLURM\_JOBID to a job in slurm and will add the username and slurm account in the tags.

The following recorder rules are used to pre-aggregate stats shown in the user portal.

```
---
groups:
- name: recorder.rules
  rules:
  - record: lustre:read_bytes:rate3m
    expr: sum(label_replace(rate(lustre_read_bytes_total{component="ost"}[3m]), "fs", "$1", "target", "(.*)-OST.*")) by (fs, cluster)
  - record: lustre:write_bytes:rate3m
    expr: sum(label_replace(rate(lustre_write_bytes_total{component="ost"}[3m]), "fs", "$1", "target", "(.*)-OST.*")) by (fs, cluster)
  - record: lustre:read_bytes:rate3m_user
    expr: sum by (user,fs,cluster,account) (rate(lustre_job_read_bytes_total{}[3m]))
  - record: lustre:write_bytes:rate3m_user
    expr: sum by (user,fs,cluster,account) (rate(lustre_job_write_bytes_total{}[3m]))
  - record: lustre:metadata:rate3m
    expr: sum(label_replace(rate(lustre_stats_total{component="mdt"}[3m]), "fs", "$1", "target", "(.*)-MDT.*")) by (fs,operation,cluster)
  - record: lustre:metadata:rate3m_user
    expr: sum by (user,fs,cluster,account) (rate(lustre_job_stats_total{}[3m]))
```

## redfish\_exporter
[redfish\_exporter](https://github.com/jenningsloy318/redfish_exporter) is used to gather the power usage of the nodes. This information is used to compute the energy used by a job and related metrics like CO2 emmissions.

## node\_exporter
[node\_exporter](https://github.com/prometheus/node_exporter) is used to gather generic information about the nodes. This is the default exporter used by most Prometheus installations. That information is used to show metrics like local disk IO of the nodes within the job.

## libvirtd\_exporter
[libvirtd\_exporter](https://github.com/guilbaults/libvirtd_exporter/tree/metadata) is used to gather information about the VM running on Openstack.

## Database used by Robinhood
The information in this database is used to show the current utilization per user within a group.

## Slurm jobscript
The script `slurm_jobscript/slurm_jobscripts_userportal.py` can be used to add the submited script to the database of the portal. This should run on the slurm server, it will collect the scripts from `/var/spool/slurmctld`. This script use the REST API of Django to push to job script. A user with a token need to be created, check the [installation documentation](install.md) on how to create this API token.