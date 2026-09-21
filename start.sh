#!/bin/bash
set -e
export PORT="${PORT:-8080}"
echo "Starting Uvicorn on port $PORT..."
exec uvicorn server.app:app --host 0.0.0.0 --port $PORT
