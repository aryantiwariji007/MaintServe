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
curl -X POST http://localhost:8000/api/v1/v1/chat/completions \
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
    base_url="http://localhost:8000/api/v1/v1",
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
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `RATE_LIMIT_REQUESTS` | `100` | Requests per window |
| `RATE_LIMIT_WINDOW` | `60` | Window in seconds |
  # Run migrations                                                                                                                        
  docker compose exec api alembic upgrade head                                                                                            
                                                                                                                                          
  # Test health                                                                                                                           
  curl http://localhost:8000/api/v1/health                                                                                                
                                                                                                                                          
  # Test detailed health                                                                                                                  
  curl http://localhost:8000/api/v1/health/detailed     


    - Latency: 1.9 seconds                                                                                                                  
                                                                                                                                          
● ---                                                                                                                                     
  Summary - MaintServe is Running                                                                                                         
  ┌────────────┬────────────────────────────┬──────────────────┐                                                                          
  │  Service   │            URL             │      Status      │                                                                          
  ├────────────┼────────────────────────────┼──────────────────┤                                                                          
  │ API        │ http://localhost:8000      │ ✅ Running       │                                                                          
  ├────────────┼────────────────────────────┼──────────────────┤                                                                          
  │ API Docs   │ http://localhost:8000/docs │ ✅               │                                                                          
  ├────────────┼────────────────────────────┼──────────────────┤                                                                          
  │ Grafana    │ http://localhost:3000      │ ✅ (admin/admin) │                                                                          
  ├────────────┼────────────────────────────┼──────────────────┤                                                                          
  │ Prometheus │ http://localhost:9090      │ ✅               │                                                                          
  ├────────────┼────────────────────────────┼──────────────────┤                                                                          
  │ vLLM       │ http://localhost:8001      │ ✅ Connected     │                                                                          
  └────────────┴────────────────────────────┴──────────────────┘                                                                          
  Default API Key: ms_admin_default_key_change_me                                                                                         
                                                                                                                                          
  Quick Commands                                                                                                                          
                                                                                                                                          
  # Chat completion                                                                                                                       
  curl -X POST "http://localhost:8000/api/v1/chat/completions" \                                                                          
    -H "X-API-Key: ms_admin_default_key_change_me" \                                                                                      
    -H "Content-Type: application/json" \                                                                                                 
    -d '{"model": "Qwen/Qwen3-VL-8B-Instruct", "messages": [{"role": "user", "content": "Hello"}]}'                                       
                                                                                                                                          
  # Check usage stats                                                                                                                     
  curl "http://localhost:8000/api/v1/admin/me/usage" \                                                                                    
    -H "X-API-Key: ms_admin_default_key_change_me"                                                                                        
                                                                                                                                          
  # Create new user                                                                                                                       
  curl -X POST "http://localhost:8000/api/v1/admin/users" \                                                                               
    -H "X-API-Key: ms_admin_default_key_change_me" \                                                                                      
    -H "Content-Type: application/json" \                                                                                                 
    -d '{"name": "Team User", "email": "user@example.com", "team": "ML Team"}'                                                            
                                                                                                                                          
──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
❯ test it with an image                                                                                                            ↵ send 
──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
  ? for shortcuts                                                                                                                         
                                                                                                                                          
                                                                                                                                          Base64 encoded images (recommended over URLs) 
                                                                                                                                        
● Summary                                                                                                                                 
                                                                                                                                          
  What's Implemented                                                                                                                      
  ┌───────────────────┬────────┬───────────────────────────────────────────────────────┐                                                  
  │      Feature      │ Status │                        Details                        │                                                  
  ├───────────────────┼────────┼───────────────────────────────────────────────────────┤                                                  
  │ 4 Uvicorn Workers │ ✅     │ Handles ~4x more concurrent sync requests             │                                                  
  ├───────────────────┼────────┼───────────────────────────────────────────────────────┤                                                  
  │ RQ Job Queue      │ ✅     │ 2 workers processing inference + high priority queues │                                                  
  ├───────────────────┼────────┼───────────────────────────────────────────────────────┤                                                  
  │ Async Endpoint    │ ✅     │ POST /api/v1/chat/completions/async                   │                                                  
  ├───────────────────┼────────┼───────────────────────────────────────────────────────┤                                                  
  │ Job Status        │ ✅     │ GET /api/v1/jobs/{job_id}                             │                                                  
  ├───────────────────┼────────┼───────────────────────────────────────────────────────┤                                                  
  │ Queue Stats       │ ✅     │ GET /api/v1/queue/stats                               │                                                  
  └───────────────────┴────────┴───────────────────────────────────────────────────────┘                                                  
  Test Results                                                                                                                            
                                                                                                                                          
  Job submitted → queued → started → finished in ~500ms                                                                                   
  Queue: 1 finished, 0 failed                                                                                                             
                                                                                                                                          
  New Architecture                                                                                                                        
                                                                                                                                          
                      ┌─────────────────────────┐                                                                                         
                      │   MaintServe API        │                                                                                         
                      │   (4 Uvicorn workers)   │                                                                                         
                      └───────────┬─────────────┘                                                                                         
                                  │                                                                                                       
              ┌───────────────────┴───────────────────┐                                                                                   
              │                                       │                                                                                   
      Sync requests                           Async requests                                                                              
              │                                       │                                                                                   
              ▼                                       ▼                                                                                   
      ┌───────────────┐                      ┌───────────────┐                                                                            
      │     vLLM      │                      │  Redis Queue  │                                                                            
      │   (Direct)    │                      └───────┬───────┘                                                                            
      └───────────────┘                              │                                                                                    
                                            ┌────────┴────────┐                                                                           
                                            ▼                 ▼                                                                           
                                      ┌──────────┐      ┌──────────┐                                                                      
                                      │ Worker 1 │      │ Worker 2 │                                                                      
                                      └─────┬────┘      └─────┬────┘                                                                      
                                            └────────┬────────┘                                                                           
                                                     ▼                                                                                    
                                            ┌───────────────┐                                                                             
                                            │     vLLM      │                                                                             
                                            └───────────────┘                                                                             
                                                                                                                                          
  When to Use Each                                                                                                                        
  ┌──────────────────────────────┬───────────────────────────────────────────────┐                                                        
  │           Endpoint           │                   Use Case                    │                                                        
  ├──────────────────────────────┼───────────────────────────────────────────────┤                                                        
  │ POST /chat/completions       │ Real-time responses, interactive chat         │                                                        
  ├──────────────────────────────┼───────────────────────────────────────────────┤                                                        
  │ POST /chat/completions/async │ Batch processing, background jobs, long tasks │                                                        
  └──────────────────────────────┴───────────────────────────────────────────────┘                                                                                                                                                                                       
  Rule 1:                                                                                                                                 
    Protocol: TCP                                                                                                                         
    Port: 8000 - 8000                                                                                                                     
    Source: 0.0.0.0/0                                                                                                                     
                                                                                                                                          
  Rule 2:                                                                                                                                 
    Protocol: TCP                                                                                                                         
    Port: 443 - 443                                                                                                                       
    Source: 0.0.0.0/0                                                                                                                     
                                                                                                                                          
  Rule 3:                                                                                                                                 
    Protocol: TCP                                                                                                                         
    Port: 80 - 80                                                                                                                         
    Source: 0.0.0.0/0                           

     Request Comparison                                                                                                                      
  ┌─────────────┬──────────────────────────────────────────────┬───────────────────────────────────────────────┐                          
  │             │           Via MaintServe (Port 80)           │            Direct vLLM (Port 8001)            │                          
  ├─────────────┼──────────────────────────────────────────────┼───────────────────────────────────────────────┤                          
  │ URL         │ http://69.19.137.118/api/v1/chat/completions │ http://69.19.137.118:8001/v1/chat/completions │                          
  ├─────────────┼──────────────────────────────────────────────┼───────────────────────────────────────────────┤                          
  │ Status      │ ✅ Works                                     │ ❌ Connection refused                         │                          
  ├─────────────┼──────────────────────────────────────────────┼───────────────────────────────────────────────┤                          
  │ Auth Header │ X-API-Key                                    │ Authorization: Bearer                         │                          
  ├─────────────┼──────────────────────────────────────────────┼───────────────────────────────────────────────┤                          
  │ Why?        │ Port 80 open, Nginx → MaintServe → vLLM      │ Port 8001 not exposed (internal only)         │                          
  └─────────────┴──────────────────────────────────────────────┴───────────────────────────────────────────────┘                          
  Architecture                                                                                                                            
                                                                                                                                          
  External (Your Mac)                                                                                                                     
          │                                                                                                                               
          ▼                                                                                                                               
     ┌─────────────────────────────────────────────────┐                                                                                  
     │              Server (69.19.137.118)             │                                                                                  
     │                                                 │                                                                                  
     │   Port 80 ──→ Nginx ──→ MaintServe ──→ vLLM    │                                                                                   
     │   (open)              (port 8000)   (port 8001) │                                                                                  
     │                                      ▲          │                                                                                  
     │                                      │          │                                                                                  
     │                            localhost only       │                                                                                  
     │                                                 │                                                                                  
     │   Port 8001 ✗ (firewall blocks external)       │                                                                                   
     └─────────────────────────────────────────────────┘                                                                                  
                                                                                                                                          
  Why This is Good (Security)                                                                                                             
  ┌───────────────────┬────────────┬─────────────┐                                                                                        
  │      Feature      │ MaintServe │ Direct vLLM │                                                                                        
  ├───────────────────┼────────────┼─────────────┤                                                                                        
  │ API Key Auth      │ ✅         │ ❌          │                                                                                        
  ├───────────────────┼────────────┼─────────────┤                                                                                        
  │ Rate Limiting     │ ✅         │ ❌          │                                                                                        
  ├───────────────────┼────────────┼─────────────┤                                                                                        
  │ Usage Tracking    │ ✅         │ ❌          │                                                                                        
  ├───────────────────┼────────────┼─────────────┤                                                                                        
  │ Quota Enforcement │ ✅         │ ❌          │                                                                                        
  ├───────────────────┼────────────┼─────────────┤                                                                                        
  │ Request Logging   │ ✅         │ ❌          │                                                                                        
  └───────────────────┴────────────┴─────────────┘                                                                                        
  vLLM is intentionally internal-only — all external access goes through MaintServe for security and monitoring.  