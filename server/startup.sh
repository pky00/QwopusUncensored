#!/bin/bash
# Launched by systemd on every boot

LOG=/var/log/qwopus-startup.log
exec > $LOG 2>&1

echo "$(date): Starting Qwopus services..."

docker start searxng 2>/dev/null || true
echo "$(date): SearXNG started"

MODEL_PATH="/home/ubuntu/models/qwopus-27b"

python -m vllm.entrypoints.openai.api_server \
  --model $MODEL_PATH \
  --quantization awq_marlin \
  --max-model-len 16384 \
  --host 0.0.0.0 \
  --port 8000 \
  --gpu-memory-utilization 0.90 \
  --trust-remote-code \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  > /tmp/vllm.log 2>&1 &

VLLM_PID=$!
echo "$(date): vLLM started (PID: $VLLM_PID)"

/home/ubuntu/QwopusUncensored/server/request-tracker.sh &
echo "$(date): Request tracker started"

touch /tmp/last_api_request

echo "$(date): All services started"
