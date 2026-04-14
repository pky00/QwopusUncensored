#!/bin/bash
# Pod entrypoint — launches all services
# Runs every time the pod starts

LOG=/workspace/logs/startup.log
mkdir -p /workspace/logs

exec > >(tee -a $LOG) 2>&1

echo "$(date): Starting Qwopus services..."

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MODEL_PATH="${MODEL_PATH:-/workspace/models/qwopus-27b}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-32768}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.90}"

if [ ! -d "$MODEL_PATH" ] || [ -z "$(ls -A $MODEL_PATH 2>/dev/null)" ]; then
  echo "$(date): Model not found. Run download-model.sh first."
  echo "  bash /workspace/QwopusUncensored/server/download-model.sh"
  sleep infinity
fi

if ! command -v searxng-run &> /dev/null; then
  echo "$(date): SearXNG not installed. Run install-searxng.sh first."
  echo "  bash /workspace/QwopusUncensored/server/install-searxng.sh"
fi

export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

echo "$(date): Starting SearXNG..."
SEARXNG_SETTINGS_PATH="$SCRIPT_DIR/searxng/settings.yml" \
  python3 -m searx.webapp &
SEARXNG_PID=$!
echo "$(date): SearXNG started (PID: $SEARXNG_PID)"

echo "$(date): Starting SearXNG proxy..."
python3 "$SCRIPT_DIR/searxng_proxy.py" > /workspace/logs/searxng-proxy.log 2>&1 &
echo "$(date): SearXNG proxy started"

echo "$(date): Starting vLLM..."
python3 -m vllm.entrypoints.openai.api_server \
  --model "$MODEL_PATH" \
  --quantization gptq_marlin \
  --max-model-len "$MAX_MODEL_LEN" \
  --host 0.0.0.0 \
  --port 8000 \
  --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" \
  --trust-remote-code \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  --api-key "$QWOPUS_API_KEY" \
  --middleware rate_limiter.RateLimiterMiddleware \
  > /workspace/logs/vllm.log 2>&1 &

VLLM_PID=$!
echo "$(date): vLLM started (PID: $VLLM_PID)"

echo "$(date): Starting request tracker..."
"$SCRIPT_DIR/request-tracker.sh" &

touch /tmp/last_api_request

echo "$(date): Starting auto-shutdown monitor..."
while true; do
  "$SCRIPT_DIR/auto-shutdown.sh"
  sleep 300
done &

echo "$(date): All services started. Waiting for vLLM..."

while true; do
  HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null)
  if [ "$HEALTH" == "200" ]; then
    echo "$(date): vLLM is ready and serving requests."
    break
  fi
  sleep 5
done

wait $VLLM_PID
