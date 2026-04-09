"""
Phase 2 — Async Batch Scale Tests
Submits jobs via the async endpoint, then polls for completion.
Uses rate pacing to stay within the 100 req/60s server limit.

Usage:
    python phase2_async.py --jobs 100 --images 1 --output results_100.json
    python phase2_async.py --jobs 200 --images 2 --priority mixed --output results_200_mixed.json
    python phase2_async.py --jobs 2000 --images 1 --output results_2000.json

Scaling ladder (run in order, check report.py before advancing):
    2a:  100 jobs, 1 image,  normal   -> results_100.json
    2b:  200 jobs, 1 image,  normal   -> results_200.json
    2c:  200 jobs, 2 images, mixed    -> results_200_mixed.json
    2d:  500 jobs, 1 image,  normal   -> results_500.json
    2e: 2000 jobs, 1 image,  normal   -> results_2000.json  (overnight)
"""

import asyncio
import argparse
import json
import time
import sys
import httpx
from config import (
    BASE_URL, MODEL, SUBMIT_RATE, RATE_LIMIT_WINDOW,
    POLL_TIMEOUT, POLL_INTERVAL, auth_headers
)
from images import get_test_images


def build_async_payload(n_images: int, priority: str = "normal") -> dict:
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
        "priority": priority,
    }


async def submit_jobs(client: httpx.AsyncClient, total: int, n_images: int, priority: str) -> list[str]:
    """Submit all jobs with rate pacing. Returns list of job IDs."""
    job_ids = []
    url = f"{BASE_URL}/api/v1/chat/completions/async"
    priorities = ["normal", "urgent"] if priority == "mixed" else [priority]

    print(f"Submitting {total} jobs ({n_images} image(s), priority={priority})...")
    start = time.time()

    for i in range(total):
        pri = priorities[i % len(priorities)] if priority == "mixed" else priority
        payload = build_async_payload(n_images, pri)

        # Rate pacing: stay below 100 req/60s
        await asyncio.sleep(RATE_LIMIT_WINDOW / SUBMIT_RATE)

        # Full window reset every SUBMIT_RATE submissions
        if i > 0 and i % SUBMIT_RATE == 0:
            elapsed = time.time() - start
            print(f"  [{i}/{total}] Submitted {i} jobs. Pausing for rate window reset...")
            await asyncio.sleep(max(0, RATE_LIMIT_WINDOW - (elapsed % RATE_LIMIT_WINDOW)))
            start = time.time()

        try:
            r = await client.post(url, json=payload, headers=auth_headers(), timeout=30)
            if r.status_code == 200:
                data = r.json()
                job_id = data.get("job_id") or data.get("id")
                if job_id:
                    job_ids.append(job_id)
                else:
                    print(f"  WARNING [{i}]: No job_id in response: {data}")
            elif r.status_code == 429:
                print(f"  WARNING [{i}]: Rate limited (429). Sleeping 60s...")
                await asyncio.sleep(60)
                # Retry once
                r2 = await client.post(url, json=payload, headers=auth_headers(), timeout=30)
                if r2.status_code == 200:
                    data = r2.json()
                    job_id = data.get("job_id") or data.get("id")
                    if job_id:
                        job_ids.append(job_id)
            else:
                print(f"  ERROR [{i}]: HTTP {r.status_code}: {r.text[:200]}")
        except httpx.RequestError as e:
            print(f"  ERROR [{i}]: Request failed: {e}")

        if (i + 1) % 50 == 0:
            print(f"  [{i+1}/{total}] {len(job_ids)} jobs submitted successfully")

    print(f"  Submission complete: {len(job_ids)}/{total} jobs submitted\n")
    return job_ids


async def poll_all(client: httpx.AsyncClient, job_ids: list[str]) -> dict:
    """Poll all jobs until finished/failed or timeout."""
    pending = set(job_ids)
    results = {}
    deadline = time.time() + POLL_TIMEOUT
    poll_rounds = 0

    print(f"Polling {len(job_ids)} jobs (timeout={POLL_TIMEOUT}s, interval={POLL_INTERVAL}s)...")

    while pending and time.time() < deadline:
        await asyncio.sleep(POLL_INTERVAL)
        poll_rounds += 1

        for job_id in list(pending):
            try:
                r = await client.get(
                    f"{BASE_URL}/api/v1/jobs/{job_id}",
                    headers=auth_headers(),
                    timeout=15
                )
                if r.status_code == 200:
                    data = r.json()
                    status = data.get("status")
                    if status in ("finished", "failed"):
                        results[job_id] = data
                        pending.discard(job_id)
                elif r.status_code == 404:
                    results[job_id] = {"status": "not_found"}
                    pending.discard(job_id)
            except httpx.RequestError:
                pass  # Will retry next round

        if poll_rounds % 10 == 0:
            completed = len(results)
            total = len(job_ids)
            elapsed = time.time() + POLL_TIMEOUT - deadline
            print(f"  Poll round {poll_rounds}: {completed}/{total} done, "
                  f"{len(pending)} pending, "
                  f"{POLL_TIMEOUT - (time.time() - (deadline - POLL_TIMEOUT)):.0f}s remaining")

    # Mark timed-out jobs
    for job_id in pending:
        results[job_id] = {"status": "timeout"}

    return results


def save_results(results: dict, job_ids: list[str], output_file: str,
                 total_jobs: int, n_images: int, priority: str, elapsed_s: float):
    """Save full results to JSON."""
    finished = sum(1 for r in results.values() if r.get("status") == "finished")
    failed = sum(1 for r in results.values() if r.get("status") == "failed")
    timeout = sum(1 for r in results.values() if r.get("status") == "timeout")
    not_found = sum(1 for r in results.values() if r.get("status") == "not_found")

    output = {
        "config": {
            "total_jobs": total_jobs,
            "submitted": len(job_ids),
            "n_images": n_images,
            "priority": priority,
        },
        "summary": {
            "finished": finished,
            "failed": failed,
            "timeout": timeout,
            "not_found": not_found,
            "completion_rate_pct": round(finished / total_jobs * 100, 1) if total_jobs > 0 else 0,
            "elapsed_seconds": round(elapsed_s, 1),
        },
        "jobs": results,
    }

    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nResults saved to: {output_file}")
    print(f"  Finished  : {finished}")
    print(f"  Failed    : {failed}")
    print(f"  Timeout   : {timeout}")
    print(f"  Not found : {not_found}")
    print(f"  Completion: {output['summary']['completion_rate_pct']}%")
    print(f"  Elapsed   : {elapsed_s:.0f}s")


async def main():
    parser = argparse.ArgumentParser(description="MaintServe Phase 2 async batch test")
    parser.add_argument("--jobs", type=int, default=100, help="Number of jobs to submit")
    parser.add_argument("--images", type=int, default=1, choices=[1, 2, 3],
                        help="Images per job")
    parser.add_argument("--priority", default="normal",
                        choices=["normal", "urgent", "mixed"],
                        help="Job priority (mixed alternates normal/urgent)")
    parser.add_argument("--output", default=None, help="Output JSON file")
    args = parser.parse_args()

    output_file = args.output or f"results_{args.jobs}.json"

    print(f"\nMaintServe Phase 2 — Async Batch Scale")
    print(f"  Jobs     : {args.jobs}")
    print(f"  Images   : {args.images}")
    print(f"  Priority : {args.priority}")
    print(f"  Output   : {output_file}")
    print(f"  Server   : {BASE_URL}\n")

    start = time.time()

    async with httpx.AsyncClient() as client:
        # Health check first
        try:
            r = await client.get(f"{BASE_URL}/api/v1/health/detailed",
                                 headers=auth_headers(), timeout=30)
            health = r.json()
            if health.get("status") != "healthy":
                print(f"WARNING: System not fully healthy: {health.get('status')}")
                print("Continuing anyway — check monitor.py output")
            else:
                print("Health check: OK\n")
        except Exception as e:
            print(f"WARNING: Health check failed: {e}")

        job_ids = await submit_jobs(client, args.jobs, args.images, args.priority)

        if not job_ids:
            print("ERROR: No jobs were submitted successfully. Aborting.")
            sys.exit(1)

        results = await poll_all(client, job_ids)

    elapsed = time.time() - start
    save_results(results, job_ids, output_file, args.jobs, args.images, args.priority, elapsed)


if __name__ == "__main__":
    asyncio.run(main())
