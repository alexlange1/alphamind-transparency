#!/bin/zsh
set -euo pipefail

ROOT="/Users/alexanderlange/alphamind"
VENV_BIN="/Users/alexanderlange/.venvs/alphamind/bin"
PORT=8003

# Start API if not already listening
if ! lsof -i TCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; then
  PYTHONPATH="$ROOT" "$VENV_BIN/uvicorn" subnet.validator.api:app --host 127.0.0.1 --port $PORT >/tmp/tao20_api.log 2>&1 &
  API_PID=$!
  echo "Started validator API on :$PORT (pid $API_PID)"
  # Wait for health
  for i in {1..30}; do
    if curl -s http://127.0.0.1:$PORT/healthz | grep -q '"ok":true'; then
      break
    fi
    sleep 1
  done
fi

# Emit reports (miner)
PYTHONPATH="$ROOT" python3 -m subnet.miner.loop || true

# Aggregate to produce weights and init vault
curl -s -X POST http://127.0.0.1:$PORT/aggregate \
  -H 'content-type: application/json' \
  -d '{"in_dir":"'"$ROOT/subnet/out"'","out_file":"'"$ROOT/subnet/out/weights.json"'","top_n":20}' >/dev/null || true

# Open dashboard
if command -v open >/dev/null 2>&1; then
  open "http://127.0.0.1:$PORT/dashboard" || true
else
  echo "Dashboard: http://127.0.0.1:$PORT/dashboard"
fi

echo "Done. API on :$PORT. Logs: /tmp/tao20_api.log"

