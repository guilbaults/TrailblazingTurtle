PROMETHEUS = {
    'url': 'https://thanos.dant.computecanada.ca',
    'headers': {'Authorization': 'Basic changeme_base64'},
    'filter': {
        'default': "cluster='narval'",
        'cloudstats': "cluster='narval', instance=~'blg.*'" # example to override the default filter for a specific module
    },
}

PROM_NODE_HOSTNAME_LABEL = 'instance'