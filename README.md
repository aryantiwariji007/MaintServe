# MaintServe

Internal Vision LLM API Gateway for serving Qwen3-VL-8B-Instruct via vLLM with authentication, rate limiting, usage tracking, load management, and monitoring.

## Architecture

```
Client VMs → MaintServe API Gateway → vLLM (Qwen3-VL-8B-Instruct)
                    ↓
         PostgreSQL + Redis + Prometheus/Grafana
```

---

## Quick Start

### Prerequisites

- Docker and Docker Compose
- vLLM running on port 8001:

```bash
cd qwen3-vllm
source .venv/bin/activate
vllm serve Qwen/Qwen3-VL-8B-Instruct \
  --host 0.0.0.0 \
  --port 8001 \
  --max-model-len 32768 \
  --max-num-seqs 12 \
  --gpu-memory-utilization 0.95 \
  --limit-mm-per-prompt.video 0
```

### Start Services

```bash
# Copy and configure environment
cp .env.example .env

# Start all services (PostgreSQL, Redis, Prometheus, Grafana, API)
docker compose up -d

# Run migrations
docker compose exec api alembic upgrade head

# View logs
docker compose logs -f api
```

### Access Points

| Service    | URL                          | Credentials |
|------------|------------------------------|-------------|
| API        | http://localhost:8000        | -           |
| API Docs   | http://localhost:8000/docs   | -           |
| Status     | http://localhost:8000/status | -           |
| Grafana    | http://localhost:3000        | admin/admin |
| Prometheus | http://localhost:9090        | -           |

---

## API Usage

### Authentication

All requests require an `X-API-Key` header. The default admin key is:

```
ms_admin_default_key_change_me
```

Create additional keys via the Admin API (see below).

---

## Text-Only Prompts

Use this when you want to send plain text questions or instructions — no images involved.

### curl

```bash
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ms_admin_default_key_change_me" \
  -d '{
    "model": "Qwen/Qwen3-VL-8B-Instruct",
    "messages": [
      {"role": "user", "content": "Explain what a transformer model is in simple terms."}
    ],
    "max_tokens": 512
  }'
```

### Python

```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/chat/completions",
    headers={"X-API-Key": "ms_admin_default_key_change_me"},
    json={
        "model": "Qwen/Qwen3-VL-8B-Instruct",
        "messages": [
            {"role": "user", "content": "What is the capital of France?"}
        ],
        "max_tokens": 256,
    }
)
print(response.json()["choices"][0]["message"]["content"])
```

### Multi-turn chat (text)

```python
json={
    "model": "Qwen/Qwen3-VL-8B-Instruct",
    "messages": [
        {"role": "system",    "content": "You are a helpful assistant."},
        {"role": "user",      "content": "My name is Alex."},
        {"role": "assistant", "content": "Hello Alex! How can I help you today?"},
        {"role": "user",      "content": "What is my name?"},
    ],
    "max_tokens": 128,
}
```

---

## Image + Text Prompts

Use this when you want the model to analyse one or more images alongside a text question.
Images are passed as base64-encoded data URLs.

### curl (single image)

```bash
# 1. Download a test image
curl -s "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Cat03.jpg/320px-Cat03.jpg" \
  -o /tmp/cat.jpg

# 2. Base64 encode
# Linux:
BASE64_IMG=$(base64 -w 0 /tmp/cat.jpg)
# Mac:
# BASE64_IMG=$(base64 -i /tmp/cat.jpg | tr -d '\n')

# 3. Send to MaintServe
curl -X POST "http://localhost:8000/api/v1/chat/completions" \
  -H "X-API-Key: ms_admin_default_key_change_me" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"Qwen/Qwen3-VL-8B-Instruct\",
    \"messages\": [{
      \"role\": \"user\",
      \"content\": [
        {\"type\": \"image_url\", \"image_url\": {\"url\": \"data:image/jpeg;base64,${BASE64_IMG}\"}},
        {\"type\": \"text\", \"text\": \"What is in this image?\"}
      ]
    }],
    \"max_tokens\": 200
  }"
```

### Python (single image)

```python
import base64
import requests

with open("/path/to/image.jpg", "rb") as f:
    b64 = base64.b64encode(f.read()).decode()

response = requests.post(
    "http://localhost:8000/api/v1/chat/completions",
    headers={"X-API-Key": "ms_admin_default_key_change_me"},
    json={
        "model": "Qwen/Qwen3-VL-8B-Instruct",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                {"type": "text", "text": "Describe this image in detail."}
            ]
        }],
        "max_tokens": 512,
    }
)
print(response.json()["choices"][0]["message"]["content"])
```

### Python (multiple images)

```python
content = []
for path in ["/path/img1.jpg", "/path/img2.jpg"]:
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

content.append({"type": "text", "text": "Compare these two images."})

response = requests.post(
    "http://localhost:8000/api/v1/chat/completions",
    headers={"X-API-Key": "ms_admin_default_key_change_me"},
    json={
        "model": "Qwen/Qwen3-VL-8B-Instruct",
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 512,
    }
)
```

### Using OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/api/v1",
    api_key="dummy",
    default_headers={"X-API-Key": "ms_admin_default_key_change_me"}
)

# Text-only
response = client.chat.completions.create(
    model="Qwen/Qwen3-VL-8B-Instruct",
    messages=[{"role": "user", "content": "Hello!"}]
)

# With image
response = client.chat.completions.create(
    model="Qwen/Qwen3-VL-8B-Instruct",
    messages=[{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,<B64>"}},
            {"type": "text", "text": "What is in this image?"}
        ]
    }]
)
```

---

## Async Job Submission

For batch processing, submit jobs asynchronously and poll for results.

```bash
# Submit a job
curl -X POST http://localhost:8000/api/v1/chat/completions/async \
  -H "X-API-Key: ms_admin_default_key_change_me" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-VL-8B-Instruct",
    "messages": [{"role": "user", "content": "Describe this image."}],
    "priority": "urgent"
  }'
# Returns: { "job_id": "abc123", "status_url": "/api/v1/jobs/abc123" }

# Poll for result
curl http://localhost:8000/api/v1/jobs/abc123 \
  -H "X-API-Key: ms_admin_default_key_change_me"

# Check queue stats
curl http://localhost:8000/api/v1/queue/stats \
  -H "X-API-Key: ms_admin_default_key_change_me"
```

`priority` accepts `"urgent"` (high queue) or `"normal"` (default queue).

---

## Testing

Tests live in `tests/scale/`. All test scripts read config from `tests/scale/config.py`.

### Text-Only Smoke Test

Verifies the model handles pure text prompts with no images.
Runs 4 cases: basic Q&A, reasoning/math, long context summarisation, multi-turn chat.

```bash
cd tests/scale/fixtures
python text_smoke.py
```

Expected output:
```
  Basic Q&A           : PASSED  (1243ms, 87 tokens)
  Reasoning / Math    : PASSED  (2891ms, 201 tokens)
  Long Context        : PASSED  (3102ms, 156 tokens)
  Multi-turn Chat     : PASSED  (980ms, 42 tokens)

  RESULT: All 4 tests PASSED — model handles text-only prompts correctly
```

### Phase 1 — Image Smoke Test

Verifies single synchronous requests with 1, 2, and 3 images.
Must fully pass before running any scale tests.

```bash
cd tests/scale
python phase1_smoke.py
```

Expected output:
```
  1 image(s): PASSED  (8200ms, 312 tokens)
  2 image(s): PASSED  (14500ms, 498 tokens)
  3 image(s): PASSED  (21300ms, 651 tokens)

  RESULT: All 3 tests PASSED — safe to proceed to Phase 2
```

### Phase 2 — Parallel Scale Test

Submits large batches of async image jobs in parallel. Run only after Phase 1 passes.

```bash
cd tests/scale
python phase2_parallel.py
```

Monitor progress at `http://localhost:8000/status` while the test runs.

---

## Admin API

### Create User

```bash
curl -X POST http://localhost:8000/api/v1/admin/users \
  -H "X-API-Key: ms_admin_default_key_change_me" \
  -H "Content-Type: application/json" \
  -d '{"name": "John", "email": "john@example.com", "team": "ML Team"}'
```

### Create API Key for User

```bash
curl -X POST http://localhost:8000/api/v1/admin/users/2/keys \
  -H "X-API-Key: ms_admin_default_key_change_me" \
  -H "Content-Type: application/json" \
  -d '{"name": "Production Key"}'
```

Optionally set an expiry (naive datetime, no timezone):

```json
{
  "name": "Temporary Key",
  "description": "Expires end of year",
  "expires_at": "2026-12-31T23:59:59"
}
```

### Get Usage Stats

```bash
curl http://localhost:8000/api/v1/admin/users/2/usage \
  -H "X-API-Key: ms_admin_default_key_change_me"
```

---

## Monitoring

### Live Status

No auth required — monitor from any browser while tests run:

```
http://localhost:8000/status
```

Returns queue depth, finished/total count, and vLLM health.

### Grafana Dashboards

Pre-configured dashboard at http://localhost:3000 with 5 rows:

| Row | Panels |
|-----|--------|
| System Health | vLLM status, active requests, error rate, P95 latency, 24h totals |
| Load Management | Queue depth (urgent vs normal), failed jobs, enqueue rate |
| Latency & Performance | p50/p95/p99, request rate, error breakdown by status code |
| Usage by Team | Request/token rate by team, pie chart, rate limit hits |
| Traceability & Errors | 4xx/5xx breakdown, X-Trace-ID lookup guide |

### Prometheus Metrics

Available at http://localhost:8000/metrics:

| Metric | Description |
|--------|-------------|
| `maintserve_requests_total` | Total requests by method/endpoint/status |
| `maintserve_request_latency_seconds` | Latency histogram |
| `maintserve_tokens_total` | Tokens by type (prompt/completion) |
| `maintserve_active_requests` | Currently active requests |
| `maintserve_vllm_healthy` | vLLM health (1=up, 0=down) |
| `maintserve_queue_depth` | Jobs by queue and state |
| `maintserve_team_requests_total` | Requests by team |

### Traceability

Every response includes an `X-Trace-ID` header (UUID) that links the HTTP response to the database usage log and structured API logs.

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `VLLM_BASE_URL` | `http://localhost:8001` | vLLM server URL |
| `VLLM_TIMEOUT` | `600.0` | Max seconds to wait for vLLM response |
| `VLLM_MAX_CONCURRENCY` | `10` | Max simultaneous calls to vLLM |
| `RATE_LIMIT_REQUESTS` | `2000` | Requests allowed per window |
| `RATE_LIMIT_WINDOW` | `60` | Rate limit window in seconds |
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |

---

## Load Management & Priority Queuing

MaintServe protects the vLLM backend under high load:

1. **Concurrency Control** — max 10 simultaneous requests reach vLLM. Others wait in an internal semaphore queue.
2. **Priority Queuing** — async jobs marked `"priority": "urgent"` go to the `high` RQ queue and are processed before `"normal"` jobs.
3. **Queue Monitoring** — `GET /api/v1/queue/stats` or `/status` shows live queue depth.

```json
{
  "model": "Qwen/Qwen3-VL-8B-Instruct",
  "messages": [...],
  "priority": "urgent"
}
```
