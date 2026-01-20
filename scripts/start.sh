#!/bin/bash
set -e

# MaintServe Startup Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Load environment
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Wait for PostgreSQL
echo "Waiting for PostgreSQL..."
until pg_isready -h ${POSTGRES_HOST:-localhost} -p ${POSTGRES_PORT:-5432} -U ${POSTGRES_USER:-maintserve} 2>/dev/null; do
    sleep 1
done
echo "PostgreSQL is ready"

# Run migrations
echo "Running database migrations..."
alembic upgrade head

# Start the server
echo "Starting MaintServe..."
exec uvicorn app.main:app \
    --host ${HOST:-0.0.0.0} \
    --port ${PORT:-8000} \
    --workers ${WORKERS:-1} \
    --log-level ${LOG_LEVEL:-info}
