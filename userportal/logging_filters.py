import logging


class SkipHandledPrometheusUnavailable(logging.Filter):
    """Drop Django's duplicate error log for handled Prometheus outages."""

    def filter(self, record):
        request = getattr(record, 'request', None)
        return not (getattr(record, 'status_code', None) == 503 and getattr(request, 'prometheus_unavailable', False))
