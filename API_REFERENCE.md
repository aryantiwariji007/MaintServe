# MaintServe API Reference

Base URL: `http://69.19.137.118` (or your server IP)

## Authentication

All endpoints require an API key in the header:

```
X-API-Key: your_api_key_here
```

Default admin key: `ms_admin_default_key_change_me`

---

## Image Handling

### Supported Formats

| Format | MIME Type | Extension |
|--------|-----------|-----------|
| JPEG | `image/jpeg` | `.jpg`, `.jpeg` |
| PNG | `image/png` | `.png` |
| WebP | `image/webp` | `.webp` |
| GIF | `image/gif` | `.gif` (first frame) |

### Image Requirements

| Requirement | Value |
|-------------|-------|
| Max file size | 20 MB |
| Recommended resolution | 512px - 2048px |
| Max images per request | 5 |
| Encoding | Base64 |

### Converting Images to Base64

#### macOS / Linux

```bash
# Basic conversion
base64 -i image.jpg | tr -d '\n'

# Store in variable
BASE64_IMG=$(base64 -i image.jpg | tr -d '\n')

# With MIME type prefix (for API)
echo "data:image/jpeg;base64,$(base64 -i image.jpg | tr -d '\n')"
```

#### Windows (PowerShell)

```powershell
# Basic conversion
[Convert]::ToBase64String([IO.File]::ReadAllBytes("image.jpg"))

# Store in variable
$BASE64_IMG = [Convert]::ToBase64String([IO.File]::ReadAllBytes("image.jpg"))

# With MIME type prefix
"data:image/jpeg;base64," + [Convert]::ToBase64String([IO.File]::ReadAllBytes("image.jpg"))
```

#### Python

```python
import base64

def image_to_base64(image_path: str) -> str:
    """Convert image file to base64 data URL."""
    # Detect MIME type
    ext = image_path.lower().split('.')[-1]
    mime_types = {
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'webp': 'image/webp',
        'gif': 'image/gif'
    }
    mime = mime_types.get(ext, 'image/jpeg')

    with open(image_path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode('utf-8')

    return f"data:{mime};base64,{b64}"

# Usage
data_url = image_to_base64("photo.jpg")
# Returns: "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
```

#### JavaScript/Node.js

```javascript
const fs = require('fs');
const path = require('path');

function imageToBase64(imagePath) {
  const ext = path.extname(imagePath).toLowerCase().slice(1);
  const mimeTypes = {
    jpg: 'image/jpeg',
    jpeg: 'image/jpeg',
    png: 'image/png',
    webp: 'image/webp',
    gif: 'image/gif'
  };
  const mime = mimeTypes[ext] || 'image/jpeg';

  const buffer = fs.readFileSync(imagePath);
  const b64 = buffer.toString('base64');

  return `data:${mime};base64,${b64}`;
}

// Usage
const dataUrl = imageToBase64('photo.jpg');
// Returns: "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
```

#### Browser JavaScript

```javascript
// From file input
async function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

// Usage with <input type="file">
const input = document.querySelector('input[type="file"]');
input.addEventListener('change', async (e) => {
  const file = e.target.files[0];
  const dataUrl = await fileToBase64(file);
  // Returns: "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
});

// From URL (same origin or CORS enabled)
async function urlToBase64(url) {
  const response = await fetch(url);
  const blob = await response.blob();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}
```

### Resizing Images (Recommended)

Large images use more tokens and slow down processing. Resize before sending.

#### Python (Pillow)

```python
from PIL import Image
import base64
from io import BytesIO

def resize_and_encode(image_path: str, max_size: int = 1024) -> str:
    """Resize image and convert to base64."""
    img = Image.open(image_path)

    # Resize if larger than max_size
    if max(img.size) > max_size:
        ratio = max_size / max(img.size)
        new_size = tuple(int(dim * ratio) for dim in img.size)
        img = img.resize(new_size, Image.LANCZOS)

    # Convert to JPEG
    buffer = BytesIO()
    img.convert('RGB').save(buffer, format='JPEG', quality=85)
    b64 = base64.b64encode(buffer.getvalue()).decode()

    return f"data:image/jpeg;base64,{b64}"
```

#### macOS (sips)

```bash
# Resize to max 1024px
sips -Z 1024 image.jpg --out resized.jpg
BASE64_IMG=$(base64 -i resized.jpg | tr -d '\n')
```

#### Linux (ImageMagick)

```bash
# Resize to max 1024px
convert image.jpg -resize 1024x1024\> resized.jpg
BASE64_IMG=$(base64 resized.jpg | tr -d '\n')
```

### Data URL Format

Images must be sent as data URLs in the format:

```
data:{mime_type};base64,{base64_encoded_data}
```

**Examples:**

```
data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD...
data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA...
data:image/webp;base64,UklGRlYAAABXRUJQVlA4IEoAAADQ...
```

### Complete Example

```bash
#!/bin/bash

# 1. Resize image (optional but recommended)
sips -Z 1024 original.jpg --out resized.jpg 2>/dev/null || \
  convert original.jpg -resize 1024x1024\> resized.jpg 2>/dev/null || \
  cp original.jpg resized.jpg

# 2. Convert to base64
BASE64_IMG=$(base64 -i resized.jpg | tr -d '\n')

# 3. Send to API
curl -X POST "http://69.19.137.118/api/v1/chat/completions" \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"Qwen/Qwen3-VL-8B-Instruct\",
    \"messages\": [{
      \"role\": \"user\",
      \"content\": [
        {\"type\": \"image_url\", \"image_url\": {\"url\": \"data:image/jpeg;base64,${BASE64_IMG}\"}},
        {\"type\": \"text\", \"text\": \"Describe this image\"}
      ]
    }],
    \"max_tokens\": 300
  }"

# 4. Cleanup
rm -f resized.jpg
```

---

## Endpoints

### Health Check

#### `GET /health`
Quick health check (no auth required).

```bash
curl http://69.19.137.118/health
```

**Response:**
```json
{"status": "healthy"}
```

#### `GET /api/v1/health/detailed`
Detailed health check with component status.

```bash
curl http://69.19.137.118/api/v1/health/detailed \
  -H "X-API-Key: your_api_key"
```

**Response:**
```json
{
  "status": "healthy",
  "components": {
    "database": {"status": "healthy"},
    "redis": {"status": "healthy"},
    "vllm": {"status": "healthy"}
  }
}
```

---

### Chat Completions

#### `POST /api/v1/chat/completions`
OpenAI-compatible chat completion endpoint. Supports text and vision (images).

**Headers:**
```
X-API-Key: your_api_key
Content-Type: application/json
```

##### Text-only Request

```bash
curl -X POST "http://69.19.137.118/api/v1/chat/completions" \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-VL-8B-Instruct",
    "messages": [
      {"role": "user", "content": "Hello, how are you?"}
    ],
    "max_tokens": 100
  }'
```

##### Vision Request (with image)

```bash
# First encode your image
BASE64_IMG=$(base64 -i /path/to/image.jpg | tr -d '\n')

curl -X POST "http://69.19.137.118/api/v1/chat/completions" \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"Qwen/Qwen3-VL-8B-Instruct\",
    \"messages\": [
      {
        \"role\": \"user\",
        \"content\": [
          {
            \"type\": \"image_url\",
            \"image_url\": {\"url\": \"data:image/jpeg;base64,${BASE64_IMG}\"}
          },
          {
            \"type\": \"text\",
            \"text\": \"What is in this image?\"
          }
        ]
      }
    ],
    \"max_tokens\": 200
  }"
```

##### Multiple Images

```bash
curl -X POST "http://69.19.137.118/api/v1/chat/completions" \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"Qwen/Qwen3-VL-8B-Instruct\",
    \"messages\": [
      {
        \"role\": \"user\",
        \"content\": [
          {\"type\": \"image_url\", \"image_url\": {\"url\": \"data:image/jpeg;base64,${IMG1_B64}\"}},
          {\"type\": \"image_url\", \"image_url\": {\"url\": \"data:image/jpeg;base64,${IMG2_B64}\"}},
          {\"type\": \"text\", \"text\": \"Compare these two images\"}
        ]
      }
    ],
    \"max_tokens\": 300
  }"
```

**Response:**
```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1768907051,
  "model": "Qwen/Qwen3-VL-8B-Instruct",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! I'm doing well, thank you for asking."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 15,
    "total_tokens": 25
  },
  "request_id": "req_xyz789",
  "latency_ms": 1234.56
}
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `model` | string | Yes | - | Model name: `Qwen/Qwen3-VL-8B-Instruct` |
| `messages` | array | Yes | - | Array of message objects |
| `max_tokens` | int | No | 2048 | Maximum tokens to generate |
| `temperature` | float | No | 0.7 | Sampling temperature (0-2) |
| `top_p` | float | No | 1.0 | Nucleus sampling parameter |
| `stream` | bool | No | false | Enable streaming response |

---

### Async Jobs

For long-running or batch requests.

#### `POST /api/v1/chat/completions/async`
Submit an async job. Returns immediately with job ID.

```bash
curl -X POST "http://69.19.137.118/api/v1/chat/completions/async" \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-VL-8B-Instruct",
    "messages": [{"role": "user", "content": "Write a long essay about AI"}],
    "max_tokens": 1000
  }'
```

**Response:**
```json
{
  "job_id": "3c2ebbb7-1e93-42b6-8764-1d684c907212",
  "status": "queued",
  "status_url": "/api/v1/jobs/3c2ebbb7-1e93-42b6-8764-1d684c907212",
  "message": "Job submitted successfully. Poll status_url for results."
}
```

#### `GET /api/v1/jobs/{job_id}`
Check job status and get result.

```bash
curl "http://69.19.137.118/api/v1/jobs/3c2ebbb7-1e93-42b6-8764-1d684c907212" \
  -H "X-API-Key: your_api_key"
```

**Response (queued):**
```json
{
  "job_id": "3c2ebbb7-1e93-42b6-8764-1d684c907212",
  "status": "queued",
  "created_at": "2026-01-20T10:44:12.449611+00:00"
}
```

**Response (finished):**
```json
{
  "job_id": "3c2ebbb7-1e93-42b6-8764-1d684c907212",
  "status": "finished",
  "created_at": "2026-01-20T10:44:12.449611+00:00",
  "started_at": "2026-01-20T10:44:12.467254+00:00",
  "ended_at": "2026-01-20T10:44:12.983574+00:00",
  "result": {
    "id": "chatcmpl-xxx",
    "choices": [...],
    "usage": {...}
  }
}
```

**Job Status Values:**
- `queued` - Waiting in queue
- `started` - Being processed
- `finished` - Complete (result included)
- `failed` - Error occurred (error message included)

#### `GET /api/v1/queue/stats`
Get queue statistics.

```bash
curl "http://69.19.137.118/api/v1/queue/stats" \
  -H "X-API-Key: your_api_key"
```

**Response:**
```json
{
  "inference": {
    "queued": 0,
    "started": 1,
    "finished": 42,
    "failed": 2
  },
  "high_priority": {
    "queued": 0,
    "started": 0,
    "finished": 5,
    "failed": 0
  }
}
```

---

### Admin Endpoints

#### User Management

##### `GET /api/v1/admin/me`
Get current user info.

```bash
curl "http://69.19.137.118/api/v1/admin/me" \
  -H "X-API-Key: your_api_key"
```

##### `GET /api/v1/admin/me/usage`
Get your usage statistics.

```bash
curl "http://69.19.137.118/api/v1/admin/me/usage" \
  -H "X-API-Key: your_api_key"
```

**Response:**
```json
{
  "total_requests": 50,
  "total_tokens": 12500,
  "total_prompt_tokens": 5000,
  "total_completion_tokens": 7500,
  "avg_latency_ms": 3500.5,
  "error_count": 2,
  "period_start": "2025-12-21T00:00:00",
  "period_end": "2026-01-20T23:59:59"
}
```

##### `POST /api/v1/admin/users` (Admin only)
Create a new user.

```bash
curl -X POST "http://69.19.137.118/api/v1/admin/users" \
  -H "X-API-Key: admin_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "email": "john@example.com",
    "team": "ML Team"
  }'
```

##### `GET /api/v1/admin/users` (Admin only)
List all users.

##### `GET /api/v1/admin/users/{user_id}` (Admin only)
Get user details.

##### `PATCH /api/v1/admin/users/{user_id}` (Admin only)
Update user.

##### `DELETE /api/v1/admin/users/{user_id}` (Admin only)
Delete user.

#### API Key Management

##### `POST /api/v1/admin/users/{user_id}/keys` (Admin only)
Create API key for user.

```bash
curl -X POST "http://69.19.137.118/api/v1/admin/users/2/keys" \
  -H "X-API-Key: admin_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production Key",
    "description": "Key for production server"
  }'
```

**Response:**
```json
{
  "id": 5,
  "user_id": 2,
  "key": "ms_abc123xyz...",
  "name": "Production Key",
  "is_active": true,
  "created_at": "2026-01-20T12:00:00"
}
```

> ⚠️ The `key` value is only shown once. Save it immediately.

##### `GET /api/v1/admin/users/{user_id}/keys` (Admin only)
List user's API keys.

##### `DELETE /api/v1/admin/keys/{key_id}` (Admin only)
Revoke an API key.

#### Usage Logs

##### `GET /api/v1/admin/usage/logs` (Admin only)
Get usage logs.

```bash
curl "http://69.19.137.118/api/v1/admin/usage/logs?limit=10" \
  -H "X-API-Key: admin_api_key"
```

---

## Error Responses

### 401 Unauthorized
```json
{"detail": "Missing API key"}
```
```json
{"detail": "Invalid API key"}
```

### 429 Too Many Requests
```json
{"detail": "Rate limit exceeded"}
```

### 502 Bad Gateway
```json
{"detail": "vLLM backend error: ..."}
```

---

## Rate Limits

| Limit | Default |
|-------|---------|
| Requests per minute | 100 |
| Max request body | 50 MB |
| Request timeout | 5 minutes |

---

## Code Examples

### Python

```python
import httpx
import base64

API_URL = "http://69.19.137.118"
API_KEY = "your_api_key"

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

# Text completion
def chat(message: str) -> str:
    response = httpx.post(
        f"{API_URL}/api/v1/chat/completions",
        headers=headers,
        json={
            "model": "Qwen/Qwen3-VL-8B-Instruct",
            "messages": [{"role": "user", "content": message}],
            "max_tokens": 500
        }
    )
    return response.json()["choices"][0]["message"]["content"]

# Vision completion
def analyze_image(image_path: str, prompt: str) -> str:
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    response = httpx.post(
        f"{API_URL}/api/v1/chat/completions",
        headers=headers,
        json={
            "model": "Qwen/Qwen3-VL-8B-Instruct",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    {"type": "text", "text": prompt}
                ]
            }],
            "max_tokens": 500
        },
        timeout=120.0
    )
    return response.json()["choices"][0]["message"]["content"]

# Usage
print(chat("Hello!"))
print(analyze_image("/path/to/image.jpg", "Describe this image"))
```

### JavaScript/Node.js

```javascript
const fs = require('fs');

const API_URL = 'http://69.19.137.118';
const API_KEY = 'your_api_key';

async function chat(message) {
  const response = await fetch(`${API_URL}/api/v1/chat/completions`, {
    method: 'POST',
    headers: {
      'X-API-Key': API_KEY,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      model: 'Qwen/Qwen3-VL-8B-Instruct',
      messages: [{ role: 'user', content: message }],
      max_tokens: 500
    })
  });
  const data = await response.json();
  return data.choices[0].message.content;
}

async function analyzeImage(imagePath, prompt) {
  const imageBuffer = fs.readFileSync(imagePath);
  const b64 = imageBuffer.toString('base64');

  const response = await fetch(`${API_URL}/api/v1/chat/completions`, {
    method: 'POST',
    headers: {
      'X-API-Key': API_KEY,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      model: 'Qwen/Qwen3-VL-8B-Instruct',
      messages: [{
        role: 'user',
        content: [
          { type: 'image_url', image_url: { url: `data:image/jpeg;base64,${b64}` } },
          { type: 'text', text: prompt }
        ]
      }],
      max_tokens: 500
    })
  });
  const data = await response.json();
  return data.choices[0].message.content;
}

// Usage
chat('Hello!').then(console.log);
analyzeImage('/path/to/image.jpg', 'Describe this image').then(console.log);
```

### cURL (Bash)

```bash
#!/bin/bash
API_URL="http://69.19.137.118"
API_KEY="your_api_key"

# Text chat
chat() {
  curl -s -X POST "$API_URL/api/v1/chat/completions" \
    -H "X-API-Key: $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{
      \"model\": \"Qwen/Qwen3-VL-8B-Instruct\",
      \"messages\": [{\"role\": \"user\", \"content\": \"$1\"}],
      \"max_tokens\": 500
    }" | jq -r '.choices[0].message.content'
}

# Image analysis
analyze_image() {
  local image_path=$1
  local prompt=$2
  local b64=$(base64 -i "$image_path" | tr -d '\n')

  curl -s -X POST "$API_URL/api/v1/chat/completions" \
    -H "X-API-Key: $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{
      \"model\": \"Qwen/Qwen3-VL-8B-Instruct\",
      \"messages\": [{
        \"role\": \"user\",
        \"content\": [
          {\"type\": \"image_url\", \"image_url\": {\"url\": \"data:image/jpeg;base64,$b64\"}},
          {\"type\": \"text\", \"text\": \"$prompt\"}
        ]
      }],
      \"max_tokens\": 500
    }" | jq -r '.choices[0].message.content'
}

# Usage
chat "Hello!"
analyze_image "/path/to/image.jpg" "What is in this image?"
```

---

## Support

For issues or questions, contact your system administrator.
