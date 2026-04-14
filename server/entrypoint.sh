#!/bin/bash
# Pod entrypoint — installs deps and launches vLLM
# Set as Docker Command in RunPod pod settings

LOG=/workspace/logs/startup.log
mkdir -p /workspace/logs

exec > >(tee -a $LOG) 2>&1

echo "$(date): Starting Qwopus setup..."

SCRIPT_DIR="/workspace/QwopusUncensored/server"
MODEL_PATH="${MODEL_PATH:-/workspace/models/qwopus-27b}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-32768}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.90}"

echo "$(date): Installing vLLM + transformers..."
pip3 install "vllm>=0.19.0" --break-system-packages -q 2>&1 | tail -3
pip3 install "transformers>=5.5" "huggingface-hub>=1.5" --break-system-packages -q --no-deps 2>&1 | tail -3

echo "$(date): Checking model..."
if [ ! -d "$MODEL_PATH" ] || [ -z "$(ls -A $MODEL_PATH 2>/dev/null)" ]; then
  echo "$(date): Model not found at $MODEL_PATH"
  sleep infinity
fi

export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"
chmod +x "$SCRIPT_DIR"/*.sh 2>/dev/null

echo "$(date): Starting request tracker..."
"$SCRIPT_DIR/request-tracker.sh" &

touch /tmp/last_api_request

echo "$(date): Starting auto-shutdown monitor..."
while true; do
  "$SCRIPT_DIR/auto-shutdown.sh" >> /workspace/logs/auto-shutdown.log 2>&1
  sleep 300
done &

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
  2>&1 | tee -a /workspace/logs/vllm.log
