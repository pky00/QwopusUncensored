#!/bin/bash
# Launched by systemd on every boot

LOG=/var/log/qwopus-startup.log
exec > $LOG 2>&1

echo "$(date): Starting Qwopus services..."

set -a
source /etc/qwopus.env
set +a

docker start searxng 2>/dev/null || true
echo "$(date): SearXNG started"

MODEL_PATH="/home/ubuntu/models/qwopus-27b"
export PYTHONPATH="/home/ubuntu/QwopusUncensored/server:$PYTHONPATH"
CERT="/etc/letsencrypt/live/$QWOPUS_DOMAIN/fullchain.pem"
KEY="/etc/letsencrypt/live/$QWOPUS_DOMAIN/privkey.pem"

python3 -m vllm.entrypoints.openai.api_server \
  --model $MODEL_PATH \
  --quantization gptq_marlin \
  --max-model-len 16384 \
  --host 0.0.0.0 \
  --port 8000 \
  --gpu-memory-utilization 0.90 \
  --trust-remote-code \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  --api-key "$QWOPUS_API_KEY" \
  --ssl-keyfile "$KEY" \
  --ssl-certfile "$CERT" \
  --middleware rate_limiter.RateLimiterMiddleware \
  > /tmp/vllm.log 2>&1 &

VLLM_PID=$!
echo "$(date): vLLM started (PID: $VLLM_PID)"

python3 /home/ubuntu/QwopusUncensored/server/searxng_proxy.py \
  > /var/log/searxng-proxy.log 2>&1 &

echo "$(date): SearXNG proxy started"

/home/ubuntu/QwopusUncensored/server/request-tracker.sh &
echo "$(date): Request tracker started"

/home/ubuntu/QwopusUncensored/server/gpu_metrics.sh &
echo "$(date): GPU metrics collector started"

touch /tmp/last_api_request

echo "$(date): All services started"
