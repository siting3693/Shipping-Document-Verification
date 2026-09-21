#!/bin/bash
set -e

echo "Starting pipeline..."
python main.py .

if [ -f "${GROUND_TRUTH:-/secrets/ground_truth.json}" ]; then
    echo "Ground truth found. Scoring locally..."
    python _score_local.py > score_result.json || true
else
    echo "No ground truth found. Skipping self-evaluation scoring."
fi

export PORT="${PORT:-8080}"
echo "Starting web server on port $PORT..."
uvicorn server.app:app --host 0.0.0.0 --port $PORT
