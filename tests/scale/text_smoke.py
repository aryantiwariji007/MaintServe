"""
Text-Only Smoke Test for Qwen3-VL
Verifies the model handles pure text prompts (no images) correctly.

4 test cases:
  1. Basic Q&A        — simple factual question
  2. Reasoning / Math — multi-step word problem
  3. Long Context     — summarize a passage
  4. Multi-turn Chat  — context retention across message history

Usage:
    python text_smoke.py
"""

import sys
import time
import requests
from config import BASE_URL, MODEL, SYNC_TIMEOUT, auth_headers

URL = f"{BASE_URL}/api/v1/chat/completions" 

LONG_PASSAGE = """
The Industrial Revolution, which began in Britain in the late 18th century and spread
across Europe and North America through the 19th century, fundamentally transformed
human society. Prior to industrialisation, the majority of people lived in rural areas
and worked in agriculture, producing goods by hand using traditional tools. The advent
of mechanised manufacturing, powered first by water and later by steam, changed this
entirely.

Factories emerged in cities, drawing workers from the countryside in search of wages.
Urbanisation accelerated rapidly: cities like Manchester, Birmingham, and Leeds grew
from small towns to major industrial centres within a few decades. The population of
Manchester, for instance, grew from around 25,000 in 1772 to over 300,000 by 1850.

The revolution brought both opportunity and hardship. On one hand, it created new
industries, generated wealth, and eventually raised living standards for much of the
population. It enabled mass production of goods that had previously been luxury items,
making them accessible to ordinary people. On the other hand, early industrial conditions
were often brutal: factory workers, including children, laboured for 12 to 16 hours a
day in dangerous conditions for low wages. Housing in industrial cities was frequently
overcrowded and unsanitary, contributing to disease outbreaks.

Technological innovation drove the revolution. The steam engine, refined by James Watt
in the 1760s, became the defining technology of the era, powering factories, locomotives,
and steamships. The railway network that expanded across Britain and then the world
transformed transportation, enabling goods and people to move faster and more cheaply
than ever before. The telegraph, developed in the 1830s and 1840s, allowed near-instant
communication across long distances for the first time in history.

The social consequences were profound. A new industrial working class — the proletariat —
emerged, living in cities and dependent on wages. A growing middle class of factory owners,
merchants, and professionals also arose. Labour movements and trade unions formed in
response to poor working conditions, eventually driving reforms such as limits on working
hours, child labour laws, and improved safety standards. The political landscape shifted
as urbanised, industrialised societies demanded greater representation and rights.
"""

TESTS = [
    {
        "name": "Basic Q&A",
        "messages": [
            {
                "role": "user",
                "content": "What is the capital of France, and what is it famous for?"
            }
        ],
        "max_tokens": 256,
        "temperature": 0.3,
        "pass_fn": lambda content, tokens: (
            len(content) > 0 and tokens > 0,
            "non-empty response with tokens > 0"
        ),
    },
    {
        "name": "Reasoning / Math",
        "messages": [
            {
                "role": "user",
                "content": (
                    "A train leaves a station at 9:00am travelling at 80 km/h. "
                    "A second train leaves the same station at 10:00am travelling "
                    "in the same direction at 120 km/h. At what time does the second "
                    "train overtake the first? Show your working step by step."
                )
            }
        ],
        "max_tokens": 512,
        "temperature": 0.0,
        "pass_fn": lambda content, tokens: (
            len(content) > 0 and any(c.isdigit() for c in content),
            "response contains a numeric answer"
        ),
    },
    {
        "name": "Long Context",
        "messages": [
            {
                "role": "user",
                "content": (
                    LONG_PASSAGE.strip() +
                    "\n\nBased on the passage above, provide a summary in exactly 3 bullet points."
                )
            }
        ],
        "max_tokens": 300,
        "temperature": 0.3,
        "pass_fn": lambda content, tokens: (
            len(content) > 50,
            "response length > 50 chars (non-trivial summary)"
        ),
    },
    {
        "name": "Multi-turn Chat",
        "messages": [
            {"role": "system",    "content": "You are a helpful assistant."},
            {"role": "user",      "content": "My name is Alex."},
            {"role": "assistant", "content": "Hello Alex! How can I help you today?"},
            {"role": "user",      "content": "What is my name?"},
        ],
        "max_tokens": 128,
        "temperature": 0.0,
        "pass_fn": lambda content, tokens: (
            "alex" in content.lower(),
            'response contains "Alex" (context retention confirmed)'
        ),
    },
]


def run_test(test: dict) -> dict:
    """Run a single test case. Returns result dict."""
    payload = {
        "model": MODEL,
        "messages": test["messages"],
        "max_tokens": test["max_tokens"],
        "temperature": test["temperature"],
    }

    sep = "=" * 60
    print(f"\n{sep}")
    print(f"Test: {test['name']}")
    print(sep)

    start = time.time()
    try:
        r = requests.post(URL, json=payload, headers=auth_headers(), timeout=SYNC_TIMEOUT)
        latency_ms = (time.time() - start) * 1000
    except requests.exceptions.Timeout:
        print(f"  -> FAILED: Request timed out after {SYNC_TIMEOUT}s")
        return {"name": test["name"], "passed": False, "reason": "timeout"}
    except requests.exceptions.RequestException as e:
        print(f"  -> FAILED: {e}")
        return {"name": test["name"], "passed": False, "reason": str(e)}

    trace_id = r.headers.get("X-Trace-ID", "N/A")
    print(f"  HTTP Status   : {r.status_code}")
    print(f"  X-Trace-ID    : {trace_id}")
    print(f"  Latency       : {latency_ms:.0f} ms")

    if r.status_code != 200:
        print(f"  -> FAILED: Expected 200, got {r.status_code}: {r.text[:200]}")
        return {"name": test["name"], "passed": False, "reason": f"HTTP {r.status_code}",
                "latency_ms": latency_ms}

    data = r.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    usage = data.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    total_tokens = usage.get("total_tokens", 0)
    finish_reason = data.get("choices", [{}])[0].get("finish_reason", "unknown")

    print(f"  Content       : {content[:200]}{'...' if len(content) > 200 else ''}")
    print(f"  Tokens        : prompt={prompt_tokens}  completion={completion_tokens}  total={total_tokens}")
    print(f"  Finish reason : {finish_reason}")

    passed, reason = test["pass_fn"](content, total_tokens)

    if passed:
        print(f"  -> PASSED")
    else:
        print(f"  -> FAILED: {reason}")

    return {
        "name": test["name"],
        "passed": passed,
        "reason": reason,
        "latency_ms": latency_ms,
        "total_tokens": total_tokens,
        "finish_reason": finish_reason,
    }


def main():
    print("MaintServe — Text-Only Smoke Tests")
    print(f"Server : {BASE_URL}")
    print(f"Model  : {MODEL}")

    # Health check
    try:
        r = requests.get(f"{BASE_URL}/api/v1/health/detailed",
                         headers=auth_headers(), timeout=10)
        health = r.json()
        if health.get("status") != "healthy":
            print(f"\nWARNING: System not fully healthy: {health}")
        else:
            print("\nHealth check: OK")
    except Exception as e:
        print(f"\nWARNING: Health check failed: {e}")

    results = [run_test(t) for t in TESTS]

    # Summary
    sep = "=" * 60
    print(f"\n{sep}")
    print("Text-Only Smoke Summary")
    print(sep)

    all_passed = True
    for r in results:
        status = "PASSED" if r["passed"] else "FAILED"
        if not r["passed"]:
            all_passed = False
        latency = f"{r['latency_ms']:.0f}ms" if "latency_ms" in r else "N/A"
        tokens  = f"{r['total_tokens']} tokens" if "total_tokens" in r else ""
        detail  = f"  ({latency}, {tokens})" if tokens else f"  ({latency})"
        print(f"  {r['name']:<20}: {status}{detail}")

    print()
    if all_passed:
        print("  RESULT: All 4 tests PASSED — model handles text-only prompts correctly")
        sys.exit(0)
    else:
        failed = [r["name"] for r in results if not r["passed"]]
        print(f"  RESULT: {len(failed)} test(s) FAILED: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
