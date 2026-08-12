#!/bin/bash
set -e

cd /app/backend
uvicorn src.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

cd /app/frontend
PORT="${PORT:-3000}" node_modules/.bin/next start -p "${PORT:-3000}" &
FRONTEND_PID=$!

trap 'kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true' TERM INT

wait -n "$BACKEND_PID" "$FRONTEND_PID"
EXIT_CODE=$?
kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
exit $EXIT_CODE
