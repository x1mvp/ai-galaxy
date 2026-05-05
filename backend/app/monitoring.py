# app/monitoring.py
import time
from prometheus_client import Counter, Histogram, Gauge, start_http_server
from functools import wraps
import logging

logger = logging.getLogger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter('nlp_requests_total', 'Total NLP requests', ['model', 'status'])
REQUEST_DURATION = Histogram('nlp_request_duration_seconds', 'Request duration')
MODEL_LOAD_TIME = Histogram('model_load_duration_seconds', 'Model load duration')
ACTIVE_CONNECTIONS = Gauge('nlp_active_connections', 'Active connections')
MEMORY_USAGE = Gauge('nlp_memory_usage_bytes', 'Memory usage')


def monitor_predictions(func):
    """Decorator to monitor prediction performance."""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        start_time = time.time()
        status = "success"
        
        try:
            ACTIVE_CONNECTIONS.inc()
            result = func(self, *args, **kwargs)
            return result
        except Exception as e:
            status = "error"
            logger.error(f"Prediction error: {str(e)}")
            raise
        finally:
            duration = time.time() - start_time
            REQUEST_DURATION.observe(duration)
            REQUEST_COUNT.labels(model=self.model_name, status=status).inc()
            ACTIVE_CONNECTIONS.dec()
    
    return wrapper


def start_metrics_server(port: int = 8000):
    """Start Prometheus metrics server."""
    start_http_server(port)
    logger.info(f"Metrics server started on port {port}")
