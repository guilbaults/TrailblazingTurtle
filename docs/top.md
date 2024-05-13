# Top
These pages are only available to staff and are meant to visualize poor cluster utilization:

* Largest compute users, CPU cores, and GPUs
* Jobs on large memory nodes (ranked by worst to best)
* Top users on Lustre

## Screenshots
### Top compute user (CPU)
![Top compute user (CPU)](top_compute.png)

### Top compute user (GPU)
![Top compute user (GPU)](top_compute_gpu.png)

### Jobs on large memory nodes
![Jobs on large memory nodes](top_largemem.png)

### Top users on Lustre
![Top users on Lustre](top_lustre.png)

## Requirements
* Access to the database of Slurm
* slurm-job-exporter

Optional:

* lustre\_exporter and lustre\_exporter\_slurm (show Lustre information)
