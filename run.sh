#!/usr/bin/env bash

# Resolve project root
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# Ensure common paths (Anaconda, Homebrew) are in PATH
export PATH="/opt/homebrew/bin:/opt/anaconda3/bin:/usr/local/bin:$PATH"

# Load project environment variables from backend/.env (overriding any stale variables in parent shell)
if [ -f "$ROOT_DIR/backend/.env" ]; then
  set -a
  source "$ROOT_DIR/backend/.env"
  set +a
fi
if [ -z "$OPENAI_API_KEY" ]; then
  export OPENAI_API_KEY=""
fi

echo "=========================================================="
echo "           🚀 Starting CareerProof System                 "
echo "=========================================================="

kill_port() {
  local port=$1
  for pid in $(lsof -ti :"$port" 2>/dev/null); do
    kill -9 "$pid" 2>/dev/null
  done
}

# 1. Clean up any existing instances on ports 8000 & 3001
echo "→ Cleaning up old processes on ports 8000, 3001..."
kill_port 8000
kill_port 3001
pkill -f "celery -A app.worker.tasks" 2>/dev/null
pkill -f "uvicorn app.main:app" 2>/dev/null
pkill -f "next-server" 2>/dev/null
sleep 1

# 2. Check/Start Redis
if ! nc -z localhost 6379 2>/dev/null; then
  echo "→ Starting Redis..."
  brew services start redis 2>/dev/null || redis-server --daemonize yes 2>/dev/null
  sleep 1
fi

# 3. Check/Start PostgreSQL
if ! nc -z localhost 5433 2>/dev/null; then
  echo "→ Starting PostgreSQL (port 5433)..."
  brew services start postgresql@18 2>/dev/null
  sleep 1
fi

# 4. Locate Python binary with required dependencies installed
PYTHON_BIN=""
for candidate in \
  "/opt/anaconda3/bin/python3" \
  "$ROOT_DIR/backend/venv/bin/python3" \
  "$ROOT_DIR/venv/bin/python3" \
  "$(which python3 2>/dev/null)"; do
  if [ -n "$candidate" ] && [ -x "$candidate" ]; then
    if "$candidate" -c "import sqlalchemy" 2>/dev/null; then
      PYTHON_BIN="$candidate"
      break
    fi
  fi
done

if [ -z "$PYTHON_BIN" ]; then
  echo "❌ Error: Could not find a Python interpreter with 'sqlalchemy' installed."
  echo "   Please activate your Anaconda or virtual environment."
  exit 1
fi

echo "→ Using Python: $PYTHON_BIN"

# Trap cleanup on exit so Ctrl+C stops all processes cleanly
cleanup() {
  echo ""
  echo "=========================================================="
  echo "  Shutting down services...                               "
  echo "=========================================================="
  kill_port 8000
  kill_port 3001
  pkill -f "celery -A app.worker.tasks" 2>/dev/null
  pkill -f "uvicorn app.main:app" 2>/dev/null
  pkill -f "next-server" 2>/dev/null
  kill $(jobs -p) 2>/dev/null
  exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# 5. Start Celery Worker
echo "→ Starting Celery Worker..."
(cd "$ROOT_DIR/backend" && OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES "$PYTHON_BIN" -m celery -A app.worker.tasks.celery_app worker --pool=solo --loglevel=info) &
WORKER_PID=$!

# 6. Start FastAPI Backend
echo "→ Starting FastAPI Backend on http://localhost:8000..."
(cd "$ROOT_DIR/backend" && "$PYTHON_BIN" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload) &
BACKEND_PID=$!

# 7. Start Next.js Frontend
echo "→ Starting Next.js Frontend on http://localhost:3001..."
(cd "$ROOT_DIR/frontend" && npm run dev -- -p 3001) &
FRONTEND_PID=$!

echo ""
echo "=========================================================="
echo "  ✅ All services started successfully!                   "
echo "  - Frontend: http://localhost:3001                       "
echo "  - Backend:  http://localhost:8000                       "
echo "  - API Docs: http://localhost:8000/docs                  "
echo "  Press Ctrl+C to stop all services.                      "
echo "=========================================================="
echo ""

# Wait for background jobs
wait
