# Trailblazing Turtle
🐢🚀

This web portal is intended to give HPC users a view of the overall use of the HPC cluster and their own use. This portal is using the information collected on compute nodes and management servers to produce the information in the various modules:

* [jobstats](docs/jobstats.md)
* [accountstats](docs/accountstats.md)
* [cloudstats](docs/cloudstats.md)
* [quotas](docs/quotas.md)
* [top](docs/top.md)
* [usersummary](docs/usersummary.md)

Some example of the available graphs are displayed in the documentation of each module. 

This portal is made to be modular, some modules can be disabled if the data required is not needed or collected. Some modules have optional dependencies, if the dependencies are not met some graphs will not be displayed.

This portal also support Openstack, the users are able to see their own use without having to install a monitoring agent in their VM in their Openstack VMs.

Staff members can also see the use of any users to help them optimize their use of HPC and openstack clusters.

Some information collected are also avaiable for the general public like the number of cores used, the performance of the filesystem and the load on the login nodes.
[Here is an example of this portal for the Narval Cluster at Calcul Quebec](https://portail.narval.calculquebec.ca/)

## Design
Performance metrics are stored in Prometheus, multiple exporters are used to get this data, most are optional.

The Django portal will also access various MySQL databases like the database of Slurm and Robinhood (if installed) to gather some informations. Timeseries are stored with Prometheus for better performance. Compatible alternative to Prometheus like Thanos, VictoriaMetrics and Grafana Mimir should work without any problems (Thanos is used in production). Recorder rules in Prometheus are used to pre-aggregate some stats for the portal.

![Architecture diagram](docs/userportal.png)

## Data sources
Various data dources are used to populate the content of this portal. Most of are optionals and their usefulness depends on the modules enabled.

[Data sources documentation](docs/data.md)

## Test environment
There is a minimal config example in the example directory. This example only enable the `jobstats` and `top` module. Those modules only require the `slurm-job-exporter` exporter and a connection to the slurm database.

Copy the 2 following files and edit them to your needs.
The first file is the config file for the django application, databases connections, the name of the enabled exporters and other settings are defined here.

The second file need to be modified so site specific information like where the allocations are stored can be used. The functions provided are meant to be examples, you can use them or create your own. Our production functions are located in `userportal/common.py`, some leftover are included in the comments of the `example/common.py` file. The functions to modify are indicated in the file with the comment `# IMPLEMENTATION`.

```
cp example/settings.py.dist example/settings.py
cp example/common.py userportal/common.py
```

Then you can launch the example server:
```
python manage.py runserver --settings example.settings
```

This will start the server on port 8000 and remove the requirement to authenticate using the SSO. You should test with your own username instead of "myuser" so the access to slurm can find some of your previous jobs.

## Production install
The portal can be installed directly on a centos/rocky Apache webserver, or in a container. The various recommandation on Django in production can be followed.

[Install documentation](docs/install.md)