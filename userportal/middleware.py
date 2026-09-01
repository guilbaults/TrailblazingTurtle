import logging

from django.http import HttpResponse, JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.utils.translation import gettext as _

from userportal.exceptions import PrometheusUnavailable


logger = logging.getLogger(__name__)


class PrometheusUnavailableMiddleware(MiddlewareMixin):
    """Turn Prometheus connectivity failures into controlled 503 responses."""

    def process_exception(self, request, exception):
        if not isinstance(exception, PrometheusUnavailable):
            return None

        cause = exception.__cause__ or exception
        cause_description = type(cause).__name__
        if exception.status_code is not None:
            cause_description = f"{cause_description}, HTTP {exception.status_code}"
        logger.warning(
            "Prometheus unavailable for %s (%s)",
            request.path,
            cause_description,
        )
        request.prometheus_unavailable = True

        message = _("Metrics are temporarily unavailable")
        if request.path.endswith('.json') or 'application/json' in request.headers.get('Accept', ''):
            response = JsonResponse({'error': message}, status=503)
        else:
            response = HttpResponse(message, status=503, content_type='text/plain')
        response['Retry-After'] = '30'
        return response
