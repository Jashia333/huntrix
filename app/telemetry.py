"""
OpenTelemetry setup: metrics (Prometheus endpoint) and tracing.
Run with OTEL_EXPORTER_OTLP_ENDPOINT set to export traces to a collector (optional).
"""
import os
from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from prometheus_client import start_http_server

METRICS_PORT = 9464


def setup_telemetry(app=None):
    """Initialize OpenTelemetry and optionally instrument FastAPI."""
    resource = Resource.create({SERVICE_NAME: "huntrix-practice"})

    # ----- Metrics (Prometheus) -----
    # Expose /metrics on METRICS_PORT for Prometheus to scrape
    start_http_server(port=METRICS_PORT, addr="0.0.0.0")
    prometheus_reader = PrometheusMetricReader()
    meter_provider = MeterProvider(resource=resource, metric_readers=[prometheus_reader])
    metrics.set_meter_provider(meter_provider)

    # ----- Tracing -----
    tracer_provider = TracerProvider(resource=resource)
    # Console exporter so you see spans in the app logs
    tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    # Optional: OTLP exporter if you run a collector (e.g. Jaeger/OTLP)
    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otlp_endpoint:
        tracer_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True))
        )
    trace.set_tracer_provider(tracer_provider)

    if app is not None:
        FastAPIInstrumentor.instrument_app(app)

    return trace.get_tracer(__name__, "1.0.0"), metrics.get_meter(__name__, "1.0.0")
