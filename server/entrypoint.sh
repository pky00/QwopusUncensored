#!/bin/bash
# Pod entrypoint — installs all deps and launches all services
# Set as Docker Command in RunPod pod settings

mkdir -p /workspace/logs

exec > >(tee -a /workspace/logs/startup.log) 2>&1

echo "$(date): ========================================"
echo "$(date): Starting Qwopus 27B setup..."
echo "$(date): ========================================"

SCRIPT_DIR="/workspace/QwopusUncensored/server"
MODEL_PATH="${MODEL_PATH:-/workspace/models/qwopus-27b}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-32768}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.90}"
SEARXNG_DIR="/workspace/searxng"

# ---- Step 1: Install vLLM + transformers ----
echo "$(date): [1/4] Installing vLLM + transformers..."
pip3 install "vllm>=0.19.0" --break-system-packages -q 2>&1 | tail -3
pip3 install "transformers>=5.5" "huggingface-hub>=1.5" --break-system-packages -q --no-deps 2>&1 | tail -3
pip3 install httpx fastapi uvicorn --break-system-packages -q 2>&1 | tail -3

# ---- Step 2: Install SearXNG from git ----
echo "$(date): [2/4] Installing SearXNG..."
apt-get update -qq && apt-get install -y -qq libxslt1-dev zlib1g-dev libffi-dev libssl-dev > /dev/null 2>&1

if [ ! -d "$SEARXNG_DIR" ]; then
  git clone https://github.com/searxng/searxng.git "$SEARXNG_DIR" -q
fi

cd "$SEARXNG_DIR"
git pull -q 2>/dev/null
pip3 install --break-system-packages -q -e . 2>&1 | tail -3

mkdir -p /etc/searxng
cp "$SCRIPT_DIR/searxng/settings.yml" /etc/searxng/settings.yml

cd /

# ---- Step 3: Check model ----
echo "$(date): [3/4] Checking model..."
if [ ! -d "$MODEL_PATH" ] || [ -z "$(ls -A $MODEL_PATH 2>/dev/null)" ]; then
  echo "$(date): ERROR: Model not found at $MODEL_PATH"
  echo "$(date): Run: bash $SCRIPT_DIR/download-model.sh"
  sleep infinity
fi
echo "$(date): Model found at $MODEL_PATH"

# ---- Step 4: Launch services ----
echo "$(date): [4/4] Launching services..."

export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"
chmod +x "$SCRIPT_DIR"/*.sh 2>/dev/null

# SearXNG
echo "$(date): Starting SearXNG on port 8888..."
SEARXNG_SETTINGS_PATH=/etc/searxng/settings.yml \
  python3 -m searx.webapp > /workspace/logs/searxng.log 2>&1 &
SEARXNG_PID=$!
echo "$(date): SearXNG started (PID: $SEARXNG_PID)"

# SearXNG proxy (API key auth on port 8889)
echo "$(date): Starting SearXNG proxy on port 8889..."
python3 "$SCRIPT_DIR/searxng_proxy.py" > /workspace/logs/searxng-proxy.log 2>&1 &
echo "$(date): SearXNG proxy started"

# Request tracker
"$SCRIPT_DIR/request-tracker.sh" &
touch /tmp/last_api_request

# Auto-shutdown monitor
echo "$(date): Starting auto-shutdown monitor (30 min idle)..."
while true; do
  "$SCRIPT_DIR/auto-shutdown.sh" >> /workspace/logs/auto-shutdown.log 2>&1
  sleep 300
done &

# vLLM (runs in foreground, output to both stdout and log file)
echo "$(date): Starting vLLM on port 8000..."
echo "$(date): ========================================"
echo "$(date): All services launching. Waiting for vLLM model load..."
echo "$(date): ========================================"

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
  2>&1 | tee -a /workspace/logs/vllm.log
