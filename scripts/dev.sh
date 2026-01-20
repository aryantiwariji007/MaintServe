#!/bin/bash
set -e

# MaintServe Development Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Load environment
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Start with hot reload
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port ${PORT:-8000} \
    --reload \
    --log-level debug
