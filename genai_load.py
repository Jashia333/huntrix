"""Simple script to send repeated requests to the FastAPI `/genai` endpoint.

Usage (from project root):

    uv run python genai_load.py --requests 20 --sleep 1.0

This will:
- POST to http://localhost:8000/genai
- use different prompts
- print each response's latency and token usage
- help you see Gen AI metrics move in Prometheus / Grafana
"""

import argparse
import os
import time
from typing import List

import requests


def build_prompts() -> List[str]:
    return [
        "Say hello in one sentence.",
        "Explain OpenTelemetry in one short paragraph.",
        "Explain Prometheus and the pull model in one short paragraph.",
        "Explain Grafana in one short paragraph.",
        "Explain what latency p50 and p95 mean.",
        "Explain what a counter and a histogram are in metrics.",
        "Explain why observability is important for Gen AI systems.",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Send load to /genai for observability practice.")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("GENAI_BASE_URL", "http://localhost:8000"),
        help="Base URL of the FastAPI app (default: http://localhost:8000).",
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=20,
        help="Number of requests to send (default: 20).",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=1.0,
        help="Seconds to sleep between requests (default: 1.0).",
    )
    args = parser.parse_args()

    url = args.base_url.rstrip("/") + "/genai"
    prompts = build_prompts()

    print(f"Sending {args.requests} requests to {url} ...")
    successes = 0
    failures = 0

    for i in range(args.requests):
        prompt = prompts[i % len(prompts)]
        payload = {"prompt": prompt}
        start = time.perf_counter()
        try:
            resp = requests.post(url, json=payload, timeout=120)
            elapsed = time.perf_counter() - start
            if resp.status_code == 200:
                data = resp.json()
                usage = data.get("usage", {})
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)
                print(
                    f"[{i+1}/{args.requests}] {resp.status_code} "
                    f"latency={elapsed:.2f}s "
                    f"in={input_tokens} out={output_tokens}"
                )
                successes += 1
            else:
                print(f"[{i+1}/{args.requests}] ERROR status={resp.status_code} body={resp.text[:200]!r}")
                failures += 1
        except Exception as exc:  # pragma: no cover - simple helper script
            elapsed = time.perf_counter() - start
            print(f"[{i+1}/{args.requests}] EXCEPTION after {elapsed:.2f}s: {exc}")
            failures += 1

        if i != args.requests - 1:
            time.sleep(args.sleep)

    print(f"\nDone. Successes={successes}, Failures={failures}")


if __name__ == "__main__":
    main()

