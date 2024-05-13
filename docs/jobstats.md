# Jobstats
Each user can see their current uses on the cluster and a few hours in the past. The stats for each job are also available. Information about CPU, GPU, memory, filesystem, InfiniBand, power, etc. is also available per job. The submitted job script can also be collected from the Slurm server and then stored and displayed in the portal. Some automatic recommendations are also given to the user, based on the content of their job script and the stats of their job.

## Screenshots
### User stats
![Stats per user](user.png)
### Job stats
![Stats per job](job.png)

## Requirements
* Access to the database of Slurm
* slurm-job-exporter

Optional:

* node\_exporter (show node information)
* redfish\_exporter (show power information)
* lustre\_exporter and lustre\_exporter\_slurm (show Lustre information)
* slurm_jobscripts.py (show the submitted jobscript)
* pcm-sensor-server from Intel PCM (show CPU information like memory bandwidth, cache misses, etc.)
