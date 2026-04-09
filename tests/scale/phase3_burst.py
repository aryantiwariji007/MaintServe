"""
Phase 3 — Sync Burst Tests
Fires N concurrent sync requests simultaneously via asyncio.gather().
Verifies that the vllm_max_concurrency=10 semaphore queues gracefully
and that 429s appear correctly above the rate limit.

Usage:
    python phase3_burst.py --concurrency 5
    python phase3_burst.py --concurrency 10
    python phase3_burst.py --concurrency 20
"""

import asyncio
import argparse
import time
import httpx
from config import BASE_URL, MODEL, SYNC_TIMEOUT, auth_headers
from images import get_test_images


def build_payload() -> dict:
    """Single image sync payload."""
    image_urls = get_test_images(1)
    content = [
        {"type": "image_url", "image_url": {"url": image_urls[0]}},
        {"type": "text", "text": "Describe what you see in detail."},
    ]
    return {
        "model": MODEL,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 128,
        "temperature": 0.3,
    }


async def single_request(client: httpx.AsyncClient, idx: int) -> dict:
    """Fire a single sync request. Returns result dict."""
    url = f"{BASE_URL}/api/v1/chat/completions"
    payload = build_payload()
    start = time.time()
    try:
        r = await client.post(url, json=payload, headers=auth_headers(),
                              timeout=SYNC_TIMEOUT)
        latency_ms = (time.time() - start) * 1000
        trace_id = r.headers.get("X-Trace-ID", "N/A")

        if r.status_code == 200:
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens", 0)
            return {
                "idx": idx, "status": "success", "http_code": 200,
                "latency_ms": latency_ms, "trace_id": trace_id,
                "tokens": tokens, "content_len": len(content),
            }
        elif r.status_code == 429:
            return {
                "idx": idx, "status": "rate_limited", "http_code": 429,
                "latency_ms": latency_ms, "trace_id": trace_id,
            }
        else:
            return {
                "idx": idx, "status": "error", "http_code": r.status_code,
                "latency_ms": latency_ms, "body": r.text[:200],
            }
    except httpx.TimeoutException:
        return {"idx": idx, "status": "timeout", "latency_ms": SYNC_TIMEOUT * 1000}
    except httpx.RequestError as e:
        return {"idx": idx, "status": "request_error", "error": str(e)}


async def run_burst(concurrency: int):
    """Fire `concurrency` simultaneous requests and report results."""
    print(f"\nMaintServe Phase 3 — Sync Burst")
    print(f"  Concurrency : {concurrency}")
    print(f"  Server      : {BASE_URL}")
    print(f"  Note        : vllm_max_concurrency=10; requests above this queue\n")

    async with httpx.AsyncClient() as client:
        print(f"Firing {concurrency} concurrent requests simultaneously...")
        start = time.time()
        tasks = [single_request(client, i) for i in range(concurrency)]
        results = await asyncio.gather(*tasks)
        total_elapsed = (time.time() - start) * 1000

    # Summarize
    success = [r for r in results if r["status"] == "success"]
    rate_limited = [r for r in results if r["status"] == "rate_limited"]
    timeouts = [r for r in results if r["status"] == "timeout"]
    errors = [r for r in results if r["status"] not in ("success", "rate_limited", "timeout")]

    latencies = [r["latency_ms"] for r in success]
    avg_lat = sum(latencies) / len(latencies) if latencies else 0
    max_lat = max(latencies) if latencies else 0
    min_lat = min(latencies) if latencies else 0

    print(f"\n{'=' * 60}")
    print(f"Burst Results — concurrency={concurrency}")
    print(f"{'=' * 60}")
    print(f"  Success      : {len(success)}/{concurrency}")
    print(f"  Rate limited : {len(rate_limited)}  (429)")
    print(f"  Timeouts     : {len(timeouts)}")
    print(f"  Errors       : {len(errors)}")
    print(f"  Latency      : min={min_lat:.0f}ms  avg={avg_lat:.0f}ms  max={max_lat:.0f}ms")
    print(f"  Total elapsed: {total_elapsed:.0f}ms")

    if concurrency <= 10:
        # All should succeed — semaphore queues them
        expected_success = concurrency
        if len(success) == expected_success:
            print(f"\n  -> PASSED: All {concurrency} requests completed (within vllm_max_concurrency)")
        else:
            print(f"\n  -> WARNING: Only {len(success)}/{expected_success} succeeded")
    else:
        # Above concurrency=10, some may queue or 429
        print(f"\n  -> INFO: concurrency={concurrency} > vllm_max_concurrency=10")
        print(f"     Queuing/429s are expected. Check monitor.py for active_requests metric.")

    if rate_limited:
        print(f"\n  Rate limit behaviour confirmed: {len(rate_limited)} request(s) got 429")

    print()
    return results


def main():
    parser = argparse.ArgumentParser(description="MaintServe Phase 3 sync burst test")
    parser.add_argument("--concurrency", type=int, default=10,
                        help="Number of simultaneous requests (try 5, 10, 20)")
    args = parser.parse_args()
    asyncio.run(run_burst(args.concurrency))


if __name__ == "__main__":
    main()
