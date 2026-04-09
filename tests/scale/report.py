"""
Results Reporter
Parses a results JSON file from phase2_async.py and prints a pass/fail summary.

Usage:
    python report.py results_100.json
    python report.py results_200.json
    python report.py results_2000.json
"""

import json
import sys
import argparse
from collections import Counter


# Pass thresholds per run (job count -> min completion %)
PASS_THRESHOLDS = {
    100:  95.0,   # 2a
    200:  95.0,   # 2b, 2c
    500:  90.0,   # 2d
    2000: 85.0,   # 2e
}
DEFAULT_THRESHOLD = 90.0


def get_threshold(total_jobs: int) -> float:
    return PASS_THRESHOLDS.get(total_jobs, DEFAULT_THRESHOLD)


def compute_latency_stats(jobs: dict) -> dict:
    """Extract latency stats from finished jobs if the server returns timing."""
    latencies = []
    for data in jobs.values():
        if data.get("status") == "finished":
            # Try common field names the server might return
            lat = (data.get("latency_ms")
                   or data.get("processing_time_ms")
                   or data.get("duration_ms"))
            if lat:
                latencies.append(float(lat))
    if not latencies:
        return {}
    latencies.sort()
    n = len(latencies)
    return {
        "count": n,
        "min_ms": round(latencies[0], 1),
        "avg_ms": round(sum(latencies) / n, 1),
        "p50_ms": round(latencies[n // 2], 1),
        "p95_ms": round(latencies[int(n * 0.95)], 1),
        "p99_ms": round(latencies[int(n * 0.99)], 1),
        "max_ms": round(latencies[-1], 1),
    }


def analyze_failures(jobs: dict) -> list[str]:
    """Extract unique error patterns from failed jobs."""
    errors = []
    for data in jobs.values():
        if data.get("status") == "failed":
            err = (data.get("error")
                   or data.get("detail")
                   or data.get("message")
                   or "unknown error")
            errors.append(str(err)[:120])
    counter = Counter(errors)
    return [f"{count}x — {msg}" for msg, count in counter.most_common(10)]


def main():
    parser = argparse.ArgumentParser(description="MaintServe Phase 2 results report")
    parser.add_argument("file", help="results JSON file from phase2_async.py")
    parser.add_argument("--advance", action="store_true",
                        help="Print explicit advance/hold decision")
    args = parser.parse_args()

    try:
        with open(args.file) as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: File not found: {args.file}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON: {e}")
        sys.exit(1)

    cfg = data.get("config", {})
    summary = data.get("summary", {})
    jobs = data.get("jobs", {})

    total_jobs = cfg.get("total_jobs", len(jobs))
    submitted = cfg.get("submitted", len(jobs))
    n_images = cfg.get("n_images", "?")
    priority = cfg.get("priority", "?")
    elapsed_s = summary.get("elapsed_seconds", 0)

    finished = summary.get("finished", 0)
    failed = summary.get("failed", 0)
    timeout = summary.get("timeout", 0)
    not_found = summary.get("not_found", 0)
    completion_pct = summary.get("completion_rate_pct",
                                 round(finished / total_jobs * 100, 1) if total_jobs else 0)

    threshold = get_threshold(total_jobs)
    passed = completion_pct >= threshold

    lat = compute_latency_stats(jobs)
    failure_patterns = analyze_failures(jobs)

    print(f"\n{'=' * 60}")
    print(f"MaintServe Phase 2 — Results Report")
    print(f"{'=' * 60}")
    print(f"  File       : {args.file}")
    print(f"  Jobs       : {total_jobs} requested, {submitted} submitted")
    print(f"  Images     : {n_images}  Priority: {priority}")
    print(f"  Elapsed    : {elapsed_s:.0f}s ({elapsed_s/3600:.2f}h)")
    print()
    print(f"  Finished   : {finished}  ({completion_pct}%)")
    print(f"  Failed     : {failed}")
    print(f"  Timeout    : {timeout}")
    print(f"  Not found  : {not_found}")
    print()
    print(f"  Threshold  : {threshold}%  ({'PASS' if passed else 'FAIL'})")

    if lat:
        print(f"\n  Latency (finished jobs):")
        print(f"    min={lat['min_ms']}ms  avg={lat['avg_ms']}ms  "
              f"p50={lat['p50_ms']}ms  p95={lat['p95_ms']}ms  "
              f"p99={lat['p99_ms']}ms  max={lat['max_ms']}ms")

    if failure_patterns:
        print(f"\n  Top failure patterns:")
        for pattern in failure_patterns:
            print(f"    {pattern}")

    print(f"\n{'=' * 60}")
    if passed:
        print(f"  RESULT: PASS ({completion_pct}% >= {threshold}%)")
        if args.advance:
            print(f"  DECISION: Safe to advance to next phase")
    else:
        print(f"  RESULT: FAIL ({completion_pct}% < {threshold}%)")
        if args.advance:
            print(f"  DECISION: DO NOT advance — investigate failures first")
            print(f"  Suggested actions:")
            if failed > 0:
                print(f"    - Check docker logs maintserve-worker-1 for exceptions")
            if timeout > 0:
                print(f"    - Queue may be draining slowly — check queue_depth metric")
            if not_found > 0:
                print(f"    - Result TTL may have expired (3600s) — reduce poll interval")
    print(f"{'=' * 60}\n")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
