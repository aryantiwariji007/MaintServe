"""
Phase 2 — Parallel Final Scale Test
Runs two async batches simultaneously:
  - Batch A: 1800 jobs, 1 image, normal priority  -> results_1800.json
  - Batch B: 2200 jobs, 1 image, normal priority  -> results_2200.json

Server rate limit: 2000 req/60s
Each batch submits at 500 req/60s (combined 1000, well under limit).

Usage:
    python phase2_parallel.py
    python phase2_parallel.py --jobs-a 1800 --jobs-b 2200
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


def build_payload(n_images: int, priority: str = "normal") -> dict:
    image_urls = get_test_images(n_images)
    content = []
    for url in image_urls:
        content.append({"type": "image_url", "image_url": {"url": url}})
    content.append({"type": "text", "text": "Describe what you see in detail."})
    return {
        "model": MODEL,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 256,
        "temperature": 0.3,
        "priority": priority,
    }


async def submit_batch(client: httpx.AsyncClient, total: int, n_images: int,
                       priority: str, label: str) -> list[str]:
    """Submit a batch of jobs with rate pacing. Returns list of job IDs."""
    job_ids = []
    url = f"{BASE_URL}/api/v1/chat/completions/async"
    sleep_between = RATE_LIMIT_WINDOW / SUBMIT_RATE  # seconds per request

    print(f"[{label}] Submitting {total} jobs ({n_images} image(s), priority={priority})...")

    for i in range(total):
        await asyncio.sleep(sleep_between)

        # Full window pause every SUBMIT_RATE submissions
        if i > 0 and i % SUBMIT_RATE == 0:
            print(f"[{label}] [{i}/{total}] Rate window pause...")
            await asyncio.sleep(RATE_LIMIT_WINDOW * 0.1)  # short pause (10% of window)

        payload = build_payload(n_images, priority)
        try:
            r = await client.post(url, json=payload, headers=auth_headers(), timeout=30)
            if r.status_code == 200:
                data = r.json()
                job_id = data.get("job_id") or data.get("id")
                if job_id:
                    job_ids.append(job_id)
                else:
                    print(f"[{label}] WARNING [{i}]: No job_id in response: {data}")
            elif r.status_code == 429:
                print(f"[{label}] WARNING [{i}]: Rate limited (429). Sleeping 10s...")
                await asyncio.sleep(10)
                r2 = await client.post(url, json=payload, headers=auth_headers(), timeout=30)
                if r2.status_code == 200:
                    data = r2.json()
                    job_id = data.get("job_id") or data.get("id")
                    if job_id:
                        job_ids.append(job_id)
            else:
                print(f"[{label}] ERROR [{i}]: HTTP {r.status_code}: {r.text[:200]}")
        except httpx.RequestError as e:
            print(f"[{label}] ERROR [{i}]: {e}")

        if (i + 1) % 200 == 0:
            print(f"[{label}] [{i+1}/{total}] {len(job_ids)} submitted")

    print(f"[{label}] Submission complete: {len(job_ids)}/{total} jobs submitted")
    return job_ids


async def poll_batch(client: httpx.AsyncClient, job_ids: list[str], label: str) -> dict:
    """Poll all jobs until finished/failed or timeout."""
    pending = set(job_ids)
    results = {}
    deadline = time.time() + POLL_TIMEOUT
    poll_rounds = 0

    print(f"[{label}] Polling {len(job_ids)} jobs (timeout={POLL_TIMEOUT}s)...")

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
                    if data.get("status") in ("finished", "failed"):
                        results[job_id] = data
                        pending.discard(job_id)
                elif r.status_code == 404:
                    results[job_id] = {"status": "not_found"}
                    pending.discard(job_id)
            except httpx.RequestError:
                pass

        if poll_rounds % 20 == 0:
            remaining_s = deadline - time.time()
            print(f"[{label}] Poll {poll_rounds}: {len(results)}/{len(job_ids)} done, "
                  f"{len(pending)} pending, {remaining_s:.0f}s remaining")

    for job_id in pending:
        results[job_id] = {"status": "timeout"}

    return results


def save_results(results: dict, job_ids: list[str], output_file: str,
                 total_jobs: int, n_images: int, priority: str,
                 elapsed_s: float, label: str):
    finished  = sum(1 for r in results.values() if r.get("status") == "finished")
    failed    = sum(1 for r in results.values() if r.get("status") == "failed")
    timeout   = sum(1 for r in results.values() if r.get("status") == "timeout")
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

    print(f"\n[{label}] Results saved to: {output_file}")
    print(f"[{label}]   Finished  : {finished}")
    print(f"[{label}]   Failed    : {failed}")
    print(f"[{label}]   Timeout   : {timeout}")
    print(f"[{label}]   Not found : {not_found}")
    print(f"[{label}]   Completion: {output['summary']['completion_rate_pct']}%")
    print(f"[{label}]   Elapsed   : {elapsed_s:.0f}s")


async def run_batch(client: httpx.AsyncClient, total: int, n_images: int,
                    priority: str, output_file: str, label: str):
    """Full lifecycle for one batch: submit → poll → save."""
    start = time.time()
    job_ids = await submit_batch(client, total, n_images, priority, label)
    if not job_ids:
        print(f"[{label}] ERROR: No jobs submitted. Skipping poll.")
        return
    results = await poll_batch(client, job_ids, label)
    elapsed = time.time() - start
    save_results(results, job_ids, output_file, total, n_images, priority, elapsed, label)


async def main():
    parser = argparse.ArgumentParser(description="MaintServe parallel final scale test")
    parser.add_argument("--jobs-a", type=int, default=1800, help="Jobs for batch A")
    parser.add_argument("--jobs-b", type=int, default=2200, help="Jobs for batch B")
    parser.add_argument("--images", type=int, default=1, choices=[1, 2, 3])
    parser.add_argument("--priority", default="normal", choices=["normal", "urgent"])
    args = parser.parse_args()

    out_a = f"results_{args.jobs_a}.json"
    out_b = f"results_{args.jobs_b}.json"

    print(f"\nMaintServe Phase 2 — Parallel Final Scale Test")
    print(f"  Batch A  : {args.jobs_a} jobs -> {out_a}")
    print(f"  Batch B  : {args.jobs_b} jobs -> {out_b}")
    print(f"  Images   : {args.images} per job")
    print(f"  Priority : {args.priority}")
    print(f"  Server   : {BASE_URL}")
    print(f"  Submit rate: {SUBMIT_RATE} req/60s per batch ({SUBMIT_RATE*2} combined)")
    print(f"  Poll timeout: {POLL_TIMEOUT}s ({POLL_TIMEOUT//3600}h {(POLL_TIMEOUT%3600)//60}m)\n")

    # Health check
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{BASE_URL}/api/v1/health/detailed",
                                 headers=auth_headers(), timeout=30)
            health = r.json()
            if health.get("status") != "healthy":
                print(f"WARNING: System not fully healthy: {health}")
            else:
                print("Health check: OK\n")
        except Exception as e:
            print(f"WARNING: Health check failed: {e}\n")

        # Run both batches concurrently
        await asyncio.gather(
            run_batch(client, args.jobs_a, args.images, args.priority, out_a, "A-1800"),
            run_batch(client, args.jobs_b, args.images, args.priority, out_b, "B-2200"),
        )

    print(f"\n{'='*60}")
    print("Both batches complete. Run report:")
    print(f"  python report.py {out_a} --advance")
    print(f"  python report.py {out_b} --advance")


if __name__ == "__main__":
    asyncio.run(main())
