# quotasgpfs

`quotasgpfs` is a optional module for TrailblazingTurtle, developed by [ACENET](https://www.ace-net.ca) for use on their [Siku](https://wiki.ace-net.ca/wiki/Siku) cluster.

To enable, you must add `quotasgpfs` to `INSTALLED_APPS`

## gpfs_exporter

`quotasgpfs` uses data from [gpfs_exporter](https://github.com/treydock/gpfs_exporter)'s `mmrepquota` module. Use the `--collector.mmrepquota.quota-types` option to enable collection of user and group quotas. It is assumed that quota names are uid/gid numbers.