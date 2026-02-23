"""
Minimal FastAPI app for practicing OpenTelemetry, Prometheus, and Grafana.
- GET / : hello
- GET /slow : simulated slow request (trace + metric)
- GET /random : random status (for success/error rate in Grafana)
Metrics are exposed on port 9464 (Prometheus scrape). Traces go to console (and OTLP if configured).
"""
import random
import time
from fastapi import FastAPI
from opentelemetry import trace, metrics

from app.telemetry import setup_telemetry

app = FastAPI(title="Huntrix Observability Practice")
tracer, meter = setup_telemetry(app)

# Custom metrics (OpenTelemetry meters)
request_count = meter.create_counter(
    "huntrix_requests_total",
    description="Total requests by path and status",
    unit="1",
)
request_duration = meter.create_histogram(
    "huntrix_request_duration_seconds",
    description="Request duration in seconds",
    unit="s",
)


@app.get("/")
def root():
    """Simple health/hello endpoint."""
    with tracer.start_as_current_span("root_handler"):
        request_count.add(1, {"path": "/", "status": "200"})
        return {"message": "Huntrix observability practice", "stack": ["OpenTelemetry", "Prometheus", "Grafana"]}


@app.get("/slow")
def slow():
    """Simulate a slow request (1–3s) for tracing and latency metrics."""
    with tracer.start_as_current_span("slow_handler") as span:
        delay = random.uniform(1, 3)
        span.set_attribute("delay_seconds", delay)
        start = time.perf_counter()
        time.sleep(delay)
        elapsed = time.perf_counter() - start
        request_duration.record(elapsed, {"path": "/slow"})
        request_count.add(1, {"path": "/slow", "status": "200"})
        return {"message": "slow response", "delay_seconds": round(delay, 2)}


@app.get("/random")
def random_status():
    """Randomly return 200 or 500 for practicing success/error rate in Grafana."""
    with tracer.start_as_current_span("random_handler") as span:
        ok = random.random() > 0.3  # ~70% success
        status = "200" if ok else "500"
        span.set_attribute("http.status_code", int(status))
        request_count.add(1, {"path": "/random", "status": status})
        if ok:
            return {"message": "ok", "status": 200}
        from fastapi.responses import JSONResponse
        return JSONResponse(content={"error": "simulated error"}, status_code=500)


@app.get("/metrics-info")
def metrics_info():
    """Where to find Prometheus metrics (for humans)."""
    return {
        "prometheus_metrics_url": "http://localhost:9464/metrics",
        "note": "Prometheus scrapes this; Grafana uses Prometheus as datasource.",
    }
