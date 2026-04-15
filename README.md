# Qwopus 27B — Self-Hosted AI Coding Agent

A private, uncensored 27B coding agent running on RunPod with web search, API key security, rate limiting, and auto-shutdown.

**Model**: [Huihui-Qwen3.5-27B-Claude-4.6-Opus-abliterated](https://huggingface.co/groxaxo/Huihui-Qwen3.5-27B-Claude-4.6-Opus-abliterated-gptq-w4g128) (GPTQ 4-bit)
**Inference**: vLLM 0.19.0 with 32k context
**GPU**: Any 48+ GB VRAM (A40, A6000, L40, L40S, etc.)

## Prerequisites

- [RunPod](https://runpod.io) account with funds (~$25 to start)
- Bash shell (WSL, Git Bash, or native Linux/macOS)
- `curl`, `python3` on PATH
- Node.js + [OpenCode](https://opencode.ai) (`npm install -g opencode-ai`) — optional, any OpenAI-compatible client works

## First-Time Setup

### 1. Clone the repo

```bash
git clone https://github.com/pky00/QwopusUncensored.git
cd QwopusUncensored
```

### 2. Create `.env`

```bash
cp .env.example .env
```

Edit `.env` and fill in:

| Variable | Where to get it |
|---|---|
| `RUNPOD_API_KEY` | RunPod → Settings → API Keys → Create |
| `QWOPUS_API_KEY` | Generate one: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `RUNPOD_TEMPLATE_ID` | Created in step 3 below |
| `RUNPOD_VOLUME_ID` | Created in step 4 below |

### 3. Create a RunPod Pod Template

RunPod console → Templates → New Template:

| Field | Value |
|---|---|
| Name | `qwopus-27b` |
| Container Image | `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04` |
| Docker Command | `bash /workspace/QwopusUncensored/server/entrypoint.sh` |
| Expose HTTP Ports | `8000, 8080` |
| Container Disk | `10` GB |
| Volume Mount Path | `/workspace` |

Environment Variables:

| Key | Value |
|---|---|
| `QWOPUS_API_KEY` | Same value as in your `.env` |
| `RUNPOD_API_KEY` | Same value as in your `.env` |

Save the template. Copy the **Template ID** into your `.env`.

### 4. Create a Network Volume

RunPod console → Storage → Create Network Volume:

- Name: `qwopus-data`
- Size: **20 GB**
- Region: Pick one with A40/A6000 availability

Copy the **Volume ID** into your `.env`.

### 5. First Deploy — Download the Model

```bash
chmod +x client/qwopus client/qwopus-stop client/qwopus-status
./client/qwopus
```

This creates a pod, installs everything, and waits for the model to load. On first run, it downloads the model (~15 GB) to the network volume. This takes ~15-20 minutes. Subsequent starts take ~10 minutes (install deps + load model).

### 6. Verify

```bash
# From another terminal
./client/qwopus-status
```

Or test directly:
```bash
source .env
curl -s "https://${RUNPOD_POD_ID}-8000.proxy.runpod.net/v1/chat/completions" \
  -H "Authorization: Bearer $QWOPUS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "/workspace/models/qwopus-27b", "messages": [{"role": "user", "content": "Hello"}], "max_tokens": 50}'
```

## Daily Use

### Start a session

```bash
./client/qwopus
```

Shows available GPUs with secure cloud pricing, lets you pick one, creates a pod, waits for everything to be ready, and configures OpenCode automatically.

### Check status

```bash
./client/qwopus-status
```

Shows pod status, GPU utilization, VRAM usage, uptime, and whether vLLM and SearXNG are responding.

### Stop (terminate pod)

```bash
./client/qwopus-stop
```

Terminates the pod. Billing stops immediately. Network volume (model + code) is preserved.

### Auto-shutdown

If you walk away, the pod automatically terminates after **30 minutes of no API activity**. No action needed.

## Using with OpenCode

The `qwopus` script auto-configures OpenCode on each start. Just open OpenCode in any project:

```bash
# Windows cmd
cd C:\Projects\MyProject
opencode

# WSL
cd /mnt/c/Projects/MyProject
opencode
```

Select the **Qwopus 27B** model from the model list (under the "Qwopus" provider).

## Using with Other Clients

Any OpenAI-compatible client works. Use these settings:

| Setting | Value |
|---|---|
| API Base | `https://{pod-id}-8000.proxy.runpod.net/v1` |
| API Key | Your `QWOPUS_API_KEY` |
| Model | `/workspace/models/qwopus-27b` |

The pod ID changes each session. Run `./client/qwopus-status` or check your `.env` for the current value.

## Repository Structure

```
QwopusUncensored/
├── .env.example              # Template — copy to .env
├── .gitignore                # Excludes .env, auth.json, generated configs
├── plan.md                   # Architecture and decisions log
├── README.md                 # This file
├── server/                   # Runs on RunPod pod
│   ├── entrypoint.sh         # Pod startup: installs deps, launches all services
│   ├── download-model.sh     # First-time model download to network volume
│   ├── install-searxng.sh    # First-time SearXNG install (called by entrypoint)
│   ├── auto-shutdown.sh      # Terminates pod after 30 min idle
│   ├── request-tracker.sh    # Tracks API activity for auto-shutdown
│   ├── rate_limiter.py       # vLLM middleware: 50 req/min, auto-ban after 3 failures
│   ├── searxng_proxy.py      # API key proxy in front of SearXNG
│   └── searxng/settings.yml  # SearXNG engine configuration
└── client/                   # Runs on your laptop (bash)
    ├── qwopus                # Start: create pod, pick GPU, wait, configure OpenCode
    ├── qwopus-stop           # Stop: terminate pod, clear pod ID
    └── qwopus-status         # Status: pod, GPU, vLLM, SearXNG health
```

## What Happens on Pod Start

The `entrypoint.sh` runs automatically and does:

1. **Waits for network** (RunPod pods sometimes take a minute to get connectivity)
2. **Installs vLLM 0.19.0 + transformers 5.5+** (container disk is fresh each start)
3. **Installs SearXNG from git** (cloned to network volume, pip install each start)
4. **Checks model exists** on network volume
5. **Starts SearXNG** on localhost:8877
6. **Starts SearXNG proxy** on port 8080 (validates API key, forwards to SearXNG)
7. **Starts request tracker** (touches activity file on each API request)
8. **Starts auto-shutdown monitor** (checks every 5 min, terminates after 30 min idle)
9. **Starts vLLM** on port 8000 with API key auth + rate limiting middleware

## Security

- **HTTPS**: RunPod proxy provides automatic TLS on all `*.proxy.runpod.net` URLs
- **API Key**: vLLM's built-in `--api-key` flag — every request needs `Authorization: Bearer <key>`
- **Rate Limiting**: 50 requests/minute per IP. Auto-ban for 1 hour after 3 failed auth attempts
- **SearXNG Proxy**: SearXNG has no auth — the proxy validates the same API key before forwarding

## Sharing Access

Give someone:
- **URL**: `https://{pod-id}-8000.proxy.runpod.net/v1`
- **API Key**: your `QWOPUS_API_KEY`

They can use it from any OpenAI-compatible client. No VPN, no installs. The pod ID changes each session — share the current one from `./client/qwopus-status`.

## Cost

| Component | Monthly (3 hrs/day) |
|---|---|
| A40 Secure (~$0.76/hr) | ~$68 |
| RTX A6000 Secure (~$0.49/hr) | ~$44 |
| L40S Secure (~$0.74/hr) | ~$67 |
| Network Volume (20 GB) | ~$1.40 |
| **Total** | **~$45-70/month** |

## Troubleshooting

| Issue | Fix |
|---|---|
| `No GPUs available` | All GPUs busy — try again in a few minutes or pick a different GPU |
| `Model timeout` | Check RunPod logs tab. The install may take longer on first start (~20 min) |
| vLLM OOM | Lower `MAX_MODEL_LEN` in .env (try 16384) |
| SearXNG not responding | Check `/workspace/logs/searxng.log` on the pod. Some search engines fail — this is normal |
| `opencode: command not found` | Install with `npm install -g opencode-ai` |
| OpenCode can't find model | Run `./client/qwopus` first — it auto-configures OpenCode |
| API key rejected | Check the key matches between `.env`, RunPod template env vars, and the request header |
| Pod terminated unexpectedly | Auto-shutdown triggered after 30 min idle, or RunPod reclaimed a spot instance |
| Network timeout on pod start | Normal — RunPod pods take 1-3 min to get network. The entrypoint retries automatically |

## Updating

```bash
# Push changes from laptop
git add -A && git commit -m "..." && git push

# On next pod start, pull latest
# (or SSH into running pod and pull manually)
ssh root@{pod-ip} -p {port}
cd /workspace/QwopusUncensored && git pull
```
