# QwopusUncensored

Self-hosted uncensored 27B coding agent on RunPod. See [plan.md](plan.md) for full architecture and deployment guide.

## Quick start

```bash
# Copy and fill in your values
cp .env.example .env

# Start the pod + launch OpenCode
./client/qwopus

# Check status
./client/qwopus-status

# Stop the pod
./client/qwopus-stop
```

## First-time setup

1. Create a RunPod account, add funds, generate an API key
2. Create a 20 GB network volume
3. Create a pod with A6000/A40 GPU, mount the volume, set env vars
4. SSH into the pod and run:
```bash
cd /workspace
git clone https://github.com/pky00/QwopusUncensored.git
bash QwopusUncensored/server/download-model.sh
bash QwopusUncensored/server/install-searxng.sh
```
5. Note the pod ID, update `.env` and client configs with the proxy URLs
6. Restart the pod — entrypoint.sh launches everything

See [plan.md](plan.md) for detailed steps.

## RunPod pod management

### Start pod via API
```bash
curl -s -X POST "https://api.runpod.io/graphql?api_key=$RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { podResume(input: { podId: \"'$RUNPOD_POD_ID'\", gpuCount: 1 }) { id } }"}'
```

### Stop pod via API
```bash
curl -s -X POST "https://api.runpod.io/graphql?api_key=$RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { podStop(input: { podId: \"'$RUNPOD_POD_ID'\" }) { id } }"}'
```

### Check pod status
```bash
curl -s "https://api.runpod.io/graphql?api_key=$RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ pod(input: { podId: \"'$RUNPOD_POD_ID'\" }) { desiredStatus } }"}'
```

## Endpoints

- **vLLM**: `https://{pod-id}-8000.proxy.runpod.net/v1`
- **SearXNG**: `https://{pod-id}-8889.proxy.runpod.net`
- Both require `Authorization: Bearer <QWOPUS_API_KEY>` header
