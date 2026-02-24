# Huntrix

Practice project for **OpenTelemetry**, **Prometheus**, and **Grafana** — observability stack for interviews and learning.

---

## Architecture

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                      YOUR HOST                             │
                    │                                                           │
                    │   ┌──────────────┐         ┌─────────────────────────┐   │
                    │   │  FastAPI app │         │  Metrics HTTP server    │   │
                    │   │  :8000       │         │  :9464  (/metrics)       │   │
                    │   │              │         │  Prometheus text format │   │
                    │   │  • meter     │────────▶│  ← PrometheusMetricReader   │
                    │   │  • tracer    │         └────────────┬────────────┘   │
                    │   │  • FastAPI   │                      │                 │
                    │   │  Instrumentor│                      │ scrape          │
                    │   └──────────────┘                      │ (GET /metrics)  │
                    │         │                               │                 │
                    │         │ spans                         │                 │
                    │         ▼                               │                 │
                    │   Console ( + optional OTLP )           │                 │
                    └────────────────────────────────────────┼─────────────────┘
                                                             │
                                       host.docker.internal:9464
                                                             ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         DOCKER (docker compose)                                   │
│                                                                                  │
│   ┌─────────────────────┐                    ┌─────────────────────┐          │
│   │  Prometheus          │                    │  Grafana              │          │
│   │  :9090               │   PromQL queries   │  :3000                │          │
│   │                       │ ◀──────────────────│                       │          │
│   │  • Scrapes :9464      │                    │  • Datasource:       │          │
│   │  • Stores time-series │                    │    Prometheus        │          │
│   │  • prometheus.yml     │                    │  • Dashboards        │          │
│   └─────────────────────┘                    │    (provisioned)     │          │
│                                              └─────────────────────┘          │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Flow:** App exposes metrics on :9464 → Prometheus scrapes them → Grafana queries Prometheus and shows dashboards. Traces go to console (and optionally OTLP/Jaeger), not to Prometheus.

---

## Quick start

### 1. Install deps (uv)

```bash
cd d:\huntrix
uv sync
```

### 2. Run the app

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0
```

- API: http://localhost:8000 | Docs: http://localhost:8000/docs | Metrics: http://localhost:9464/metrics

### 3. Start Prometheus and Grafana

```bash
docker desktop start   # if needed
docker login           # if pulls fail (once)
docker compose up -d
```

- **Prometheus**: http://localhost:9090 (Status → Targets)  
- **Grafana**: http://localhost:3000 (admin / admin)

### 4. Generate traffic and explore

```powershell
Invoke-WebRequest http://localhost:8000/
Invoke-WebRequest http://localhost:8000/slow
Invoke-WebRequest http://localhost:8000/random
```

Then in Grafana: **Dashboards** → **Huntrix** → **Huntrix practice**. Traces appear in the app terminal.

---

## App endpoints

| Endpoint        | Description |
|-----------------|-------------|
| `GET /`         | Hello + stack info |
| `GET /slow`     | 1–3 s delay (latency / traces) |
| `GET /random`   | ~70% 200, ~30% 500 (error rate) |
| `POST /genai`   | Call a Gen AI model (OpenAI or Ollama); records request count, latency, token usage |
| `GET /metrics-info` | Where metrics are exposed |

### Gen AI (`POST /genai`)

- **Body:** `{"prompt": "your question", "model": "optional model name"}`.
- **Metrics recorded:** request count (`huntrix_genai_requests_total` by status/model), request duration (`huntrix_genai_request_duration_seconds`), token usage (`huntrix_genai_tokens_total` by type=input|output and model).
- **OpenAI (no Ollama needed):** set `OPENAI_API_KEY`. Optional: `OPENAI_MODEL` (default `gpt-3.5-turbo`). Don’t set `OPENAI_BASE_URL` — the app will use OpenAI’s API.
- **Ollama (local):** only if you use it — set `OPENAI_BASE_URL=http://localhost:11434/v1` and run Ollama. No API key needed. Use `OPENAI_MODEL=llama2` (or your model) if needed.

**Example (PowerShell — use this; `curl` is an alias and won’t work):**

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/genai -ContentType "application/json" -Body '{"prompt":"What is 2+2?"}'
```

Grafana dashboard **Huntrix practice** includes panels: **Gen AI request rate**, **Gen AI request duration (p50, p95)**, **Gen AI total tokens**, **Gen AI token rate (tokens/min)**.

**GPU and memory usage:** This app records *request-level* metrics (count, latency, tokens). GPU and memory usage come from the *model server* (e.g. Ollama, vLLM) or the host. To observe them in Prometheus/Grafana you can add [node_exporter](https://github.com/prometheus/node_exporter) for host CPU/memory and [DCGM exporter](https://github.com/NVIDIA/dcgm-exporter) or [nvidia_gpu_exporter](https://github.com/utkuozdemir/nvidia_gpu_exporter) for GPU, then scrape them in `prometheus.yml` and add panels in Grafana.

---

## What I learned (interview-ready)

### OpenTelemetry

- **Meter** = records **metrics** (numbers over time): counters, histograms. In this app: `huntrix_requests_total`, `huntrix_request_duration_seconds`. Data goes to **PrometheusMetricReader** → `/metrics` on port 9464 → Prometheus scrapes it.
- **Tracer** = records **traces** (spans per request): who did what, how long. Data goes to **ConsoleSpanExporter** (and optionally **OTLPSpanExporter** for Jaeger/Tempo). **Traces are not sent to Prometheus** — Prometheus is metrics-only.
- **FastAPIInstrumentor** = auto-instruments FastAPI: one span per HTTP request (method, path, status). It uses the **global** tracer/meter; we don’t pass them in. We can add custom spans with `tracer.start_as_current_span("name")` and custom metrics with `meter.create_counter` / `create_histogram` and `.add()` / `.record()`.
- **Global setup**: `trace.set_tracer_provider()` and `metrics.set_meter_provider()` in `setup_telemetry()`. The returned `tracer` and `meter` are from those globals; the instrumentor uses the same globals.
- **Labels** on metrics (e.g. `path`, `status`) become Prometheus labels so we can query by path/status in Grafana. **Unit**: `unit="1"` = dimensionless count; `unit="s"` = seconds.

### Prometheus

- **Pull model**: Prometheus **scrapes** (HTTP GET) targets; applications **expose** `/metrics`. No push from the app to Prometheus.
- **prometheus.yml** = Prometheus config (not Docker). **scrape_configs** = list of jobs. Each job has `job_name`, `targets` (where to scrape), `scrape_interval`, `scrape_timeout`. Our jobs: `huntrix` → `host.docker.internal:9464`, `prometheus` → `localhost:9090`.
- **Stores** time-series: metric name + labels + (timestamp, value). Query with **PromQL** (e.g. `rate(huntrix_requests_total[1m])`, `histogram_quantile(0.95, rate(huntrix_request_duration_seconds_bucket[5m]))`).

### Grafana

- **Role**: queries datasources (here, Prometheus) and visualizes results. It does **not** scrape or store metrics.
- **Provisioning**: datasources and dashboards are loaded from files on startup so no manual “Add datasource” or “Import dashboard” in the UI. Our files: `grafana/provisioning/datasources/datasources.yml` (Prometheus at `http://prometheus:9090`), `grafana/provisioning/dashboards/` (Huntrix folder + JSON dashboards).
- **Dashboard panels** run PromQL against the Prometheus datasource and display time-series or tables.

### Docker

- **docker-compose.yml** does **not** build images; it **pulls** and **runs** two images: `prom/prometheus` and `grafana/grafana`. So we run **two containers** with `docker compose up -d`.
- **Volumes**: `prometheus.yml` and `grafana/provisioning` are **bind-mounted** so config lives on the host. `grafana_data` is a **named volume** for Grafana’s DB (persists across restarts).
- **Network**: containers can reach each other by service name (`prometheus`, `grafana`). Prometheus reaches the app on the host via `host.docker.internal`.

---

## Files

| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI app; custom metrics (counter, histogram) and optional spans. |
| `app/telemetry.py` | OpenTelemetry setup: meter → Prometheus reader; tracer → console/OTLP; FastAPI instrumentor. |
| `prometheus.yml` | Prometheus scrape config (huntrix + self). |
| `docker-compose.yml` | Runs Prometheus and Grafana (pull, no build). |
| `grafana/provisioning/datasources/datasources.yml` | Pre-configure Prometheus datasource. |
| `grafana/provisioning/dashboards/` | Dashboard provider + JSON (Huntrix practice). |

---

## Interview talking points

- **Observability**: metrics (counts, rates, latency) + traces (per-request story). This project does both with OpenTelemetry; metrics go to Prometheus/Grafana, traces to console/OTLP.
- **Why OpenTelemetry**: vendor-neutral standard for metrics and traces; one SDK, multiple backends (Prometheus, Jaeger, etc.).
- **Why Prometheus**: industry-standard metrics store and PromQL; pull model keeps apps simple (expose HTTP endpoint).
- **Why Grafana**: separate visualization layer; can add more datasources (logs, other metrics) and build dashboards without changing Prometheus.
- **Why Docker for Prometheus/Grafana**: same setup everywhere; no local install; mirrors how these run in production.

---

## Optional: run app in Docker

Add an `app` service to `docker-compose.yml` that runs `uv run uvicorn app.main:app --host 0.0.0.0`, expose 8000 and 9464, and set Prometheus target to `app:9464` instead of `host.docker.internal:9464`.
