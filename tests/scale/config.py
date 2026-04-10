# MaintServe Scale Test Configuration

SERVER_IP = "69.19.136.124"
SERVER_PORT = 8000
BASE_URL = f"http://{SERVER_IP}:{SERVER_PORT}"

# Normal user key — used for all image/chat testing
API_KEY = "ms_fbdGF70mC18yTnCRspBkB6ngN1y7a9FcbeU3vVKcmW4"

# Admin key — used only for usage logs, metrics, traceability
ADMIN_API_KEY = "ms_admin_default_key_change_me"

# Model
MODEL = "Qwen/Qwen3-VL-8B-Instruct"

# Rate limiting (matches server: 2000 req / 60s window)
RATE_LIMIT_REQUESTS = 2000
RATE_LIMIT_WINDOW = 60
SUBMIT_RATE = 500  # per-script submit rate; two parallel scripts = 1000 combined (well under 2000)

# Timeouts
SYNC_TIMEOUT = 120       # seconds for sync /chat/completions
POLL_TIMEOUT = 7200      # seconds to wait for async job completion (2h for large parallel runs)
POLL_INTERVAL = 3        # seconds between poll cycles

# vLLM concurrency (matches server vllm_max_concurrency)
VLLM_MAX_CONCURRENCY = 10

# Fixtures
import os
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
TEST_IMAGES = [
    os.path.join(FIXTURES_DIR, "img1.jpg"),
    os.path.join(FIXTURES_DIR, "img2.jpg"),
    os.path.join(FIXTURES_DIR, "img3.jpg"),
]

def auth_headers(admin: bool = False) -> dict:
    key = ADMIN_API_KEY if admin else API_KEY
    return {"X-API-Key": key, "Content-Type": "application/json"}
