class PrometheusUnavailable(Exception):
    """Raised when Prometheus cannot serve a metrics query."""

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code
