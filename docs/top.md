# Top
These pages are only available to staff and are meant to visualize poor cluster utilization:

* Largest compute users, CPU cores, and GPUs
* Jobs on large memory nodes (ranked by worst to best)
* Top users on Lustre

<a href="top_compute.png"><img src="top_compute.png" alt="Top compute user (CPU)" width="100"/></a>
<a href="top_compute_gpu.png"><img src="top_compute_gpu.png" alt="Top compute user(GPU)" width="100"/></a>
<a href="top_largemem.png"><img src="top_largemem.png" alt="Jobs on large memory nodes" width="100"/></a>
<a href="top_lustre.png"><img src="top_lustre.png" alt="Top users on Lustre" width="100"/></a>

## Requirements
* Access to the database of Slurm
* slurm-job-exporter

Optional:

* lustre\_exporter and lustre\_exporter\_slurm (show Lustre information)
