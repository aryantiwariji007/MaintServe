"""
Phase 1 — Smoke Tests
Tests single sync requests with 1, 2, and 3 images.
Run this first. All 3 must pass before proceeding to Phase 2.

Usage:
    python phase1_smoke.py
"""

import time
import requests
from config import BASE_URL, MODEL, SYNC_TIMEOUT, auth_headers
from images import get_test_images, check_fixtures


def check_health():
    """Assert all components are healthy before running tests."""
    print("=" * 60)
    print("Health Check")
    print("=" * 60)
    url = f"{BASE_URL}/api/v1/health/detailed"
    r = requests.get(url, headers=auth_headers(), timeout=30)
    r.raise_for_status()
    data = r.json()
    print(f"  Status: {data.get('status')}")
    components = data.get("components", {})
    for name, info in components.items():
        status = info if isinstance(info, str) else info.get("status", info)
        print(f"  {name}: {status}")
    assert data.get("status") == "healthy", f"System not healthy: {data}"
    print("  -> All components healthy\n")


def build_payload(n_images: int) -> dict:
    """Build a chat/completions payload with n images + a text prompt."""
    image_urls = get_test_images(n_images)
    content = []
    for img_url in image_urls:
        content.append({"type": "image_url", "image_url": {"url": img_url}})
    content.append({"type": "text", "text": "Describe what you see in detail."})
    return {
        "model": MODEL,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 256,
        "temperature": 0.3,
    }


def run_smoke_test(n_images: int) -> dict:
    """Run a single sync request with n_images. Returns result dict."""
    print("=" * 60)
    print(f"Test: {n_images} image(s)")
    print("=" * 60)

    url = f"{BASE_URL}/api/v1/chat/completions"
    payload = build_payload(n_images)

    start = time.time()
    r = requests.post(url, json=payload, headers=auth_headers(), timeout=SYNC_TIMEOUT)
    latency_ms = (time.time() - start) * 1000

    trace_id = r.headers.get("X-Trace-ID", "N/A")
    print(f"  HTTP Status   : {r.status_code}")
    print(f"  X-Trace-ID    : {trace_id}")
    print(f"  Latency       : {latency_ms:.0f} ms")

    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"

    data = r.json()
    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})

    print(f"  Content       : {content[:300]}{'...' if len(content) > 300 else ''}")
    print(f"  Tokens        : prompt={usage.get('prompt_tokens')}  "
          f"completion={usage.get('completion_tokens')}  "
          f"total={usage.get('total_tokens')}")

    assert content.strip(), "Response content is empty"
    assert usage.get("total_tokens", 0) > 0, "total_tokens is 0"
    assert latency_ms < SYNC_TIMEOUT * 1000, f"Latency {latency_ms:.0f}ms exceeded timeout"

    print(f"  -> PASSED\n")
    return {"n_images": n_images, "trace_id": trace_id, "latency_ms": latency_ms,
            "total_tokens": usage.get("total_tokens"), "status": "passed"}


def verify_trace_in_logs(trace_ids: list[str]):
    """Check that trace IDs appear in admin usage logs."""
    print("=" * 60)
    print("Verifying trace IDs in usage logs (admin)")
    print("=" * 60)
    url = f"{BASE_URL}/api/v1/admin/usage/logs"
    r = requests.get(url, headers=auth_headers(admin=True), timeout=30)

    if r.status_code == 404:
        print("  WARNING: /admin/usage/logs not found — skipping trace verification")
        return

    r.raise_for_status()
    log_text = r.text
    for tid in trace_ids:
        if tid == "N/A":
            continue
        found = tid in log_text
        print(f"  {tid}: {'FOUND' if found else 'NOT FOUND'}")
    print()


def main():
    print("\nMaintServe Phase 1 — Smoke Tests")
    print(f"Server: {BASE_URL}\n")

    check_fixtures()
    print()
    check_health()

    results = []
    failures = []

    for n in [1, 2, 3]:
        try:
            result = run_smoke_test(n)
            results.append(result)
        except AssertionError as e:
            print(f"  -> FAILED: {e}\n")
            failures.append({"n_images": n, "error": str(e), "status": "failed"})
        except Exception as e:
            print(f"  -> ERROR: {e}\n")
            failures.append({"n_images": n, "error": str(e), "status": "error"})

    trace_ids = [r["trace_id"] for r in results]
    verify_trace_in_logs(trace_ids)

    print("=" * 60)
    print("Phase 1 Summary")
    print("=" * 60)
    for r in results:
        print(f"  {r['n_images']} image(s): PASSED  "
              f"({r['latency_ms']:.0f}ms, {r['total_tokens']} tokens)")
    for f in failures:
        print(f"  {f['n_images']} image(s): FAILED  ({f['error']})")

    if failures:
        print(f"\n  RESULT: {len(failures)} test(s) FAILED — do NOT proceed to Phase 2")
        raise SystemExit(1)
    else:
        print(f"\n  RESULT: All 3 tests PASSED — safe to proceed to Phase 2")


if __name__ == "__main__":
    main()
