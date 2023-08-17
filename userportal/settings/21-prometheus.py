PROMETHEUS = {
    'url': 'https://thanos.dant.computecanada.ca',
    'headers': {'Authorization': 'Basic changeme_base64'},
    'filter': "cluster='narval'",
}

PROM_NODE_HOSTNAME_LABEL = 'instance'