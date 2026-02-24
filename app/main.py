"""
Minimal FastAPI app for practicing OpenTelemetry, Prometheus, and Grafana.
- GET / : hello
- GET /slow : simulated slow request (trace + metric)
- GET /random : random status (for success/error rate in Grafana)
- POST /genai : call a Gen AI model (OpenAI or Ollama), record latency and token usage
Metrics are exposed on port 9464 (Prometheus scrape). Traces go to console (and OTLP if configured).
"""
from dotenv import load_dotenv
load_dotenv()

import os
import random
import time
from fastapi import FastAPI, HTTPException
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

# Gen AI metrics
genai_request_count = meter.create_counter(
    "huntrix_genai_requests_total",
    description="Total Gen AI requests by status",
    unit="1",
)
genai_request_duration = meter.create_histogram(
    "huntrix_genai_request_duration_seconds",
    description="Gen AI request duration in seconds",
    unit="s",
)
genai_tokens = meter.create_counter(
    "huntrix_genai_tokens_total",
    description="Total tokens used by type (input/output)",
    unit="1",
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


# --- Gen AI endpoint ---

def _get_openai_client():
    """OpenAI client: uses OPENAI_BASE_URL for Ollama, else OpenAI."""
    from openai import OpenAI
    base_url = os.environ.get("OPENAI_BASE_URL")  # e.g. http://localhost:11434/v1 for Ollama
    api_key = os.environ.get("OPENAI_API_KEY", "not-needed")  # Ollama doesn't need a key
    return OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI()


@app.post("/genai")
def genai_chat(body: dict):
    """
    Call a Gen AI model (OpenAI or Ollama). Send {"prompt": "your question", "model": "optional"}.
    Records: request count, latency, input/output token usage.
    Set OPENAI_API_KEY for OpenAI; set OPENAI_BASE_URL=http://localhost:11434/v1 for Ollama.
    """
    prompt = body.get("prompt") or "Say hello in one sentence."
    model = body.get("model") or os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo")
    start = time.perf_counter()
    try:
        client = _get_openai_client()
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        elapsed = time.perf_counter() - start
        choice = resp.choices[0] if resp.choices else None
        usage = getattr(resp, "usage", None)
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0
        genai_request_duration.record(elapsed, {"model": model})
        genai_request_count.add(1, {"status": "200", "model": model})
        genai_tokens.add(input_tokens, {"type": "input", "model": model})
        genai_tokens.add(output_tokens, {"type": "output", "model": model})
        return {
            "message": choice.message.content if choice else "",
            "model": model,
            "latency_seconds": round(elapsed, 3),
            "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
        }
    except Exception as e:
        elapsed = time.perf_counter() - start
        genai_request_duration.record(elapsed, {"model": model})
        genai_request_count.add(1, {"status": "500", "model": model})
        raise HTTPException(status_code=500, detail=str(e))
