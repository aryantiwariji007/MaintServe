# MaintServe

Internal Vision LLM API Gateway for serving Qwen3-VL-8B-Instruct via vLLM with authentication, rate limiting, usage tracking, and monitoring.

## Architecture

```
Client VMs → MaintServe API Gateway → vLLM (Qwen3-VL-8B-Instruct)
                    ↓
         PostgreSQL + Redis + Prometheus/Grafana
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- vLLM running on port 8001:
  ```bash
  cd qwen3-vllm
  source .venv/bin/activate
  vllm serve Qwen/Qwen3-VL-8B-Instruct \
    --host 0.0.0.0 --port 8001 \
    --max-model-len 16384 \
    --gpu-memory-utilization 0.9 \
    --limit-mm-per-prompt.video 0

  vllm serve Qwen/Qwen3-VL-8B-Instruct \
    --host 0.0.0.0 \
    --port 8001 \
    --max-model-len 16384 \
    --max-num-seqs 12 \
    --gpu-memory-utilization 0.9 \
    --limit-mm-per-prompt.video 0

  ```

### Start Services

docker compose up --build
```bash
# Copy and configure environment
cp .env.example .env

# Start all services (PostgreSQL, Redis, Prometheus, Grafana, API)
docker-compose up -d

# Run migrations
docker-compose exec api alembic upgrade head

# View logs
docker-compose logs -f api
```

### Access Points

| Service | URL | Credentials |
|---------|-----|-------------|
| API | http://localhost:8000 | - |
| API Docs | http://localhost:8000/docs | - |
| Grafana | http://localhost:3000 | admin/admin |
| Prometheus | http://localhost:9090 | - |

## API Usage

### Default API Key
```
ms_admin_default_key_change_me
```

### Chat Completion (OpenAI-compatible)

```bash
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ms_admin_default_key_change_me" \
  -d '{
    "model": "Qwen/Qwen3-VL-8B-Instruct",
    "messages": [
      {
        "role": "user",
        "content": [
          {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."} },
          {"type": "text", "text": "What is in this image?"}
        ]
      }
    ],
    "max_tokens": 2048
  }'
```

### Python Client

```python
from client.python_client import MaintServeClient

client = MaintServeClient(
    base_url="http://localhost:8000",
    api_key="ms_admin_default_key_change_me"
)

# With image file
response = client.chat_with_image(
    prompt="Describe this image",
    image_path="/path/to/image.png"
)
print(response["choices"][0]["message"]["content"])
```

### Using OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/api/v1",
    api_key="dummy",  # Not used but required
    default_headers={"X-API-Key": "ms_admin_default_key_change_me"}
)

response = client.chat.completions.create(
    model="Qwen/Qwen3-VL-8B-Instruct",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

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

### Get Usage Stats
```bash
curl http://localhost:8000/api/v1/admin/users/2/usage \
  -H "X-API-Key: ms_admin_default_key_change_me"
```

## Development

### Local Setup (without Docker)

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Start PostgreSQL and Redis (via Docker)
docker-compose up -d postgres redis

# Copy env file
cp .env.example .env

# Run migrations
alembic upgrade head

# Start dev server
./scripts/dev.sh
```

### Run Tests

```bash
pytest
```

## Monitoring

### Grafana Dashboards

Pre-configured dashboards available at http://localhost:3000:
- Request rate by endpoint
- Latency percentiles (p50, p95, p99)
- Token usage
- Error rates
- Active requests

### Prometheus Metrics

Available at http://localhost:8000/metrics:
- `maintserve_requests_total` - Total requests by endpoint/status
- `maintserve_request_latency_seconds` - Request latency histogram
- `maintserve_tokens_total` - Total tokens by type (prompt/completion)
- `maintserve_active_requests` - Currently active requests

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `VLLM_BASE_URL` | `http://localhost:8001` | vLLM server URL |
| `VLLM_MAX_CONCURRENCY` | `10` | Max simultaneous calls to vLLM |
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `RATE_LIMIT_REQUESTS` | `100` | Requests per window |
| `RATE_LIMIT_WINDOW` | `60` | Window in seconds |

## Load Management & Priority

MaintServe provides robust load management to protect the vLLM backend:

1. **Concurrency Control**: Both synchronous and asynchronous requests are subject to `VLLM_MAX_CONCURRENCY`. If the limit is reached, requests wait in an internal queue.
2. **Priority Queuing**: Async jobs can be marked as `urgent` to move to the front of the background processing queue.
3. **Queue Monitoring**: Use `GET /api/v1/queue/stats` or the Prometheus metrics to monitor queue depth and waiting requests.

### Specifying Priority

Add the `priority` field to your request body:

```json
{
  "model": "Qwen/Qwen3-VL-8B-Instruct",
  "messages": [...],
  "priority": "urgent"
}
```

*Note: For synchronous requests, priority currently shares the same concurrency pool but ensures they are handled before lower priority background tasks.*

---

## Quick Test with Image

```bash
# 1. Download a test image
curl -s "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Cat03.jpg/320px-Cat03.jpg" \
  -o /tmp/cat.jpg

# 2. Base64 encode (Mac)
BASE64_IMG=$(base64 -i /tmp/cat.jpg | tr -d '\n')
# Linux: BASE64_IMG=$(base64 -w 0 /tmp/cat.jpg)

# 3. Send to MaintServe
curl -X POST "http://69.19.137.118/api/v1/chat/completions" \
  -H "X-API-Key: ms_admin_default_key_change_me" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"Qwen/Qwen3-VL-8B-Instruct\",
    \"messages\": [{
      \"role\": \"user\",
      \"content\": [
        {\"type\": \"image_url\", \"image_url\": {\"url\": \"data:image/jpeg;base64,\${BASE64_IMG}\"}},
        {\"type\": \"text\", \"text\": \"What is in this image?\"}
      ]
    }],
    \"max_tokens\": 200
  }"
```
