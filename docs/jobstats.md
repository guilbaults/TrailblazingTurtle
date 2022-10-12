# Jobstats
Each user can see their current uses on the cluster and a few hours in the past. The stats for each job are also available. Information about CPU, GPU, memory, filesystem, infiniband, power, etc. is also available per job. The submitted jobscript can also be collected and displayed in this page. Some automatic recommendation are also given to the user, based on the content of their jobscript and the stats of their job.

<a href="user.png"><img src="user.png" alt="Stats per user" width="100"/></a>
<a href="job.png"><img src="job.png" alt="Stats per job" width="100"/></a>

## Requirements
* Access to the database of Slurm
* slurm-job-exporter

Optional:

* node\_exporter (show node information)
* redfish\_exporter (show power information)
* lustre\_exporter and lustre\_exporter\_slurm (show Lustre information)
* jobscript collector (show the submitted jobscript)

