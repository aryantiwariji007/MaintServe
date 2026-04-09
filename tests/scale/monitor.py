"""
Live Metrics Monitor
Scrapes raw Prometheus metrics from the MaintServe /metrics endpoint.
Run in a separate terminal during all test phases.

Usage:
    python monitor.py
    python monitor.py --interval 15
"""

import time
import argparse
import requests
from datetime import datetime
from config import BASE_URL, auth_headers

METRICS_URL = f"{BASE_URL}/metrics"

# Metric names to extract from the raw Prometheus text
METRICS = [
    "maintserve_active_requests",
    "maintserve_vllm_healthy",
    "maintserve_queue_depth",
    "maintserve_request_latency_seconds",
    "maintserve_requests_total",
    "maintserve_tokens_total",
    "maintserve_jobs_enqueued_total",
]

WARN_THRESHOLDS = {
    "maintserve_vllm_healthy":    lambda v: v < 1,
    "maintserve_active_requests": lambda v: v > 10,
}


def fetch_metrics() -> dict[str, list[tuple[dict, float]]]:
    """Fetch and parse /metrics into {metric_name: [(labels, value), ...]}."""
    try:
        r = requests.get(METRICS_URL, timeout=10)
        r.raise_for_status()
    except Exception as e:
        return {"_error": str(e)}

    parsed: dict[str, list[tuple[dict, float]]] = {}

    for line in r.text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Split metric name+labels from value
        try:
            if "{" in line:
                name_labels, value_str = line.rsplit("} ", 1)
                name, labels_str = name_labels.split("{", 1)
                labels = {}
                for pair in labels_str.split(","):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        labels[k.strip()] = v.strip().strip('"')
            else:
                parts = line.split()
                if len(parts) < 2:
                    continue
                name, value_str = parts[0], parts[1]
                labels = {}
            value = float(value_str.split()[0])
            parsed.setdefault(name, []).append((labels, value))
        except (ValueError, IndexError):
            continue

    return parsed


def get_scalar(parsed: dict, name: str, filter_labels: dict = None) -> float | None:
    """Get a single metric value, optionally filtered by labels."""
    entries = parsed.get(name)
    if not entries:
        return None
    if filter_labels:
        for labels, value in entries:
            if all(labels.get(k) == v for k, v in filter_labels.items()):
                return value
        return None
    # Sum all matching entries
    return sum(v for _, v in entries)


def print_snapshot(parsed: dict):
    now = datetime.now().strftime("%H:%M:%S")
    print(f"\n[{now}] ── Metrics Snapshot ──────────────────────────────")

    if "_error" in parsed:
        print(f"  ERROR fetching metrics: {parsed['_error']}")
        print("  ───────────────────────────────────────────────────")
        print("  STATUS: UNREACHABLE")
        return

    def fmt(v, suffix=""):
        return f"{v:.0f}{suffix}" if v is not None else "N/A"

    active   = get_scalar(parsed, "maintserve_active_requests")
    vllm_ok  = get_scalar(parsed, "maintserve_vllm_healthy")
    q_normal = get_scalar(parsed, "maintserve_queue_depth", {"queue": "normal", "state": "queued"})
    q_urgent = get_scalar(parsed, "maintserve_queue_depth", {"queue": "urgent", "state": "queued"})
    q_failed = get_scalar(parsed, "maintserve_queue_depth", {"state": "failed"})
    if q_failed is None:
        # sum all failed across queues
        entries = parsed.get("maintserve_queue_depth", [])
        failed_vals = [v for lbl, v in entries if lbl.get("state") == "failed"]
        q_failed = sum(failed_vals) if failed_vals else None
    enqueued  = get_scalar(parsed, "maintserve_jobs_enqueued_total")
    req_total = get_scalar(parsed, "maintserve_requests_total")

    rows = [
        ("active_requests",  fmt(active)),
        ("vllm_healthy",     fmt(vllm_ok)),
        ("queue_normal",     fmt(q_normal)),
        ("queue_urgent",     fmt(q_urgent)),
        ("queue_failed",     fmt(q_failed)),
        ("jobs_enqueued",    fmt(enqueued)),
        ("requests_total",   fmt(req_total)),
    ]

    warnings = []
    for key, display in rows:
        metric_key = f"maintserve_{key}"
        raw_val = get_scalar(parsed, metric_key)
        warn = ""
        if metric_key in WARN_THRESHOLDS and raw_val is not None:
            if WARN_THRESHOLDS[metric_key](raw_val):
                warn = "  ⚠ WARNING"
                warnings.append(key)
        print(f"  {key:<22}: {display}{warn}")

    print("  ───────────────────────────────────────────────────")
    if vllm_ok is not None and vllm_ok < 1:
        print("  STATUS: vLLM UNHEALTHY — stop tests, check GPU")
    elif q_failed is not None and q_failed > 20:
        print("  STATUS: HIGH FAILURE RATE — check worker logs")
    else:
        print("  STATUS: OK")


def main():
    parser = argparse.ArgumentParser(description="MaintServe live metrics monitor")
    parser.add_argument("--interval", type=int, default=30, help="Poll interval in seconds")
    args = parser.parse_args()

    print(f"MaintServe Monitor — polling {METRICS_URL} every {args.interval}s")
    print("Press Ctrl+C to stop\n")

    # Test connectivity
    try:
        r = requests.get(METRICS_URL, timeout=5)
        r.raise_for_status()
        print("Metrics endpoint: OK\n")
    except Exception as e:
        print(f"WARNING: Cannot reach metrics endpoint: {e}\n")

    while True:
        try:
            parsed = fetch_metrics()
            print_snapshot(parsed)
            time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nMonitor stopped.")
            break


if __name__ == "__main__":
    main()
