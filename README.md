# Huntrix

Practice project for **OpenTelemetry**, **Prometheus**, and **Grafana**.

## What’s in this repo

- **App** (`app/`): FastAPI app with OpenTelemetry metrics and tracing, exposing Prometheus metrics on port `9464`.
- **Prometheus**: Scrapes the app’s `/metrics` and stores time-series.
- **Grafana**: Uses Prometheus as a datasource so you can build dashboards.

## Quick start

### 1. Install deps with uv

```bash
cd d:\huntrix
uv sync
```

### 2. Run the app (on the host)

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0
```

- API: http://localhost:8000  
- OpenAPI: http://localhost:8000/docs  
- Metrics (for Prometheus): http://localhost:9464/metrics  

### 3. Start Prometheus and Grafana

If the Docker engine isn’t running, start it from the CLI (Docker Desktop 4.37+):

```bash
docker desktop start
```

If image pulls fail with “authentication required”, run **once** (credentials persist):

```bash
docker login
```

Use your Docker Hub username and password (or a [Personal Access Token](https://hub.docker.com/settings/security)). Docker Desktop stores them so you shouldn’t need to log in again. Stay signed in to Docker Desktop (profile icon) so CLI and Desktop share the same credentials.

Then start the stack:

```bash
docker compose up -d
```

- **Prometheus**: http://localhost:9090 (check *Status → Targets*; `huntrix` should be UP).  
- **Grafana**: http://localhost:3000 — login `admin` / `admin`. Prometheus is already set as the default datasource.

### 4. Generate some traffic and explore

Hit the app a few times:

```powershell
# Normal and slow requests
Invoke-WebRequest http://localhost:8000/
Invoke-WebRequest http://localhost:8000/slow
Invoke-WebRequest http://localhost:8000/random
```

Then in **Grafana**:

1. **Explore** → choose **Prometheus** → try queries:
   - `huntrix_requests_total` — request count by path/status  
   - `rate(huntrix_requests_total[1m])` — requests per second  
   - `huntrix_request_duration_seconds_bucket` — latency histogram  

2. **Dashboards** → **New** → **Import** (or create panels by hand):
   - Add a **Time series** panel with `rate(huntrix_requests_total[1m])` and group by `path`.  
   - Add a panel for `histogram_quantile(0.95, rate(huntrix_request_duration_seconds_bucket[5m]))` to see p95 latency.

**OpenTelemetry traces** are printed in the app’s console (where you ran `uvicorn`). For a full trace UI you can add Jaeger or Grafana Tempo and point the app’s OTLP exporter at it (see `app/telemetry.py` and `OTEL_EXPORTER_OTLP_ENDPOINT`).

## App endpoints

| Endpoint      | Description |
|---------------|-------------|
| `GET /`       | Hello + stack info |
| `GET /slow`   | Simulated 1–3 s delay (good for latency and traces) |
| `GET /random` | ~70% 200, ~30% 500 (good for error rate in Grafana) |
| `GET /metrics-info` | Explains where metrics are exposed |

## Files

- `app/main.py` — FastAPI app and custom OTel metrics.  
- `app/telemetry.py` — OpenTelemetry setup (Prometheus metrics + console traces).  
- `prometheus.yml` — Scrape config for the app (port 9464).  
- `docker-compose.yml` — Prometheus + Grafana.  
- `grafana/provisioning/datasources/datasources.yml` — Grafana datasource for Prometheus.

## Optional: run the app in Docker

To run the app in Docker too (so you don’t need the host on 9464), you can add an `app` service to `docker-compose.yml` that runs `uvicorn` and expose port 9464, then change `prometheus.yml` to scrape `app:9464` instead of `host.docker.internal:9464`.
