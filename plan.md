# Qwopus 27B — Self-Hosted AI Stack

A private, uncensored, Claude Opus 4.6-distilled 27B model on RunPod with coding agent, web search, and auto-shutdown.

> **Status (2026-04-13)**: Pivoted from AWS to RunPod. AWS had two blockers: no g6 instances in eu-west-1, and A10G (22 GB) couldn't fit the multimodal model + KV cache. RunPod A6000/A40 (48 GB) solves both. Implementation pending.

## Current progress

**Done:**
- Repo scaffolded: server scripts, client scripts, rate limiter, SearXNG proxy
- Model repo: `groxaxo/Huihui-Qwen3.5-27B-Claude-4.6-Opus-abliterated-gptq-w4g128` (GPTQ 4-bit, ~15 GB)
- Model downloaded locally to `C:\Projects\QwopusUncensoredAgent\QwopusUncensored-model`
- Qwen3.5 architecture verified: vLLM 0.19.0 has day-0 support
- Domain: `qwopus.peteryamout.com` A record exists (needs updating to RunPod proxy or removal)
- Security: vLLM `--api-key` + `--ssl-*` + rate limiter middleware all written and tested concepts
- AWS fully cleaned up: Spot instance terminated, EIP released, no ongoing charges

**In progress:**
- Rework scripts for RunPod (entrypoint, auto-shutdown, client start/stop)
- SearXNG pip install instead of Docker
- Switch client configs to RunPod proxy URLs

**Pending (manual):**
- Create RunPod account + add funds
- Create a network volume (~20 GB)
- Create the GPU pod template
- First deploy

## Environment

- **Laptop OS**: Windows 11 with WSL2 running Fedora Linux 42
- **Project path (Windows)**: `c:\Projects\QwopusUncensored`
- **Project path (WSL)**: `/mnt/c/Projects/QwopusUncensored`
- **GitHub repo**: https://github.com/pky00/QwopusUncensored (public)
- **GPU provider**: RunPod (A6000 or A40, 48 GB VRAM)
- **Domain**: `qwopus.peteryamout.com` (Namecheap DNS)

## Architecture

```
Windows laptop / WSL2                    RunPod (A6000/A40 48 GB VRAM)
┌──────────────────────┐                 ┌──────────────────────────────┐
│  OpenCode (agent)    │───HTTPS────────▶│  vLLM (model serving)        │
│  ├── local files     │   via RunPod    │  ├── Qwopus 27B (GPTQ)       │
│  ├── terminal/bash   │◀──proxy URL─────│  ├── --api-key (auth)        │
│  ├── git             │                 │  └── --ssl-* (TLS via proxy)  │
│  └── MCP: SearXNG ───│───HTTPS────────▶│                              │
│                      │                 │  SearXNG (pip, localhost)     │
│  qwopus CLI          │                 │  SearXNG proxy (FastAPI)     │
│  └── start/stop pod  │                 │  └── same API key auth       │
│      via RunPod API  │                 │                              │
│                      │                 │  Rate limiting middleware    │
│                      │                 │  ├── 50 req/min per IP       │
│                      │                 │  └── auto-ban after 3 fails  │
│                      │                 │                              │
│                      │                 │  Auto-shutdown (30m idle)    │
│                      │                 │  └── calls RunPod API stop   │
└──────────────────────┘                 └──────────────────────────────┘
  Endpoints (stable across restarts):
    vLLM:    https://{pod-id}-8000.proxy.runpod.net
    SearXNG: https://{pod-id}-8889.proxy.runpod.net
```

## Repository layout

```
QwopusUncensored/
├── .gitattributes            # *.sh text eol=lf
├── .gitignore                # .env, *.pem, test.sh
├── .env.example              # copy to .env, fill in values
├── plan.md                   # this file
├── README.md
├── server/
│   ├── entrypoint.sh         # pod startup: launches all services
│   ├── download-model.sh     # HF model pull (first run only, saves to network volume)
│   ├── install-searxng.sh    # one-time SearXNG pip install
│   ├── auto-shutdown.sh      # 30-min idle shutdown via RunPod API
│   ├── request-tracker.sh    # tails vllm.log, touches activity file
│   ├── rate_limiter.py       # vLLM middleware: per-IP rate limiting + auto-ban
│   ├── searxng_proxy.py      # API key proxy in front of SearXNG
│   └── searxng/settings.yml
└── client/                   # runs on laptop (WSL)
    ├── qwopus                # start pod + wait for health + launch opencode
    ├── qwopus-stop           # stop pod
    ├── qwopus-status         # quick health check
    ├── opencode-config.json
    └── mcp-config.json
```

## Configuration (`.env`)

```bash
# RunPod
RUNPOD_API_KEY=...
RUNPOD_POD_ID=...

# Security
QWOPUS_API_KEY=LdiOHxeTFEK1hv-1eJkg0hscCbj0RuhDbWHzBoO0f5Q

# Endpoints (filled in after pod creation)
VLLM_URL=https://{pod-id}-8000.proxy.runpod.net
SEARXNG_URL=https://{pod-id}-8889.proxy.runpod.net

# Model
MODEL_REPO=groxaxo/Huihui-Qwen3.5-27B-Claude-4.6-Opus-abliterated-gptq-w4g128
MODEL_PATH=/workspace/models/qwopus-27b
MAX_MODEL_LEN=32768
GPU_MEMORY_UTILIZATION=0.90
```

## Security model

1. **HTTPS** — RunPod's built-in proxy terminates TLS automatically. All `*.proxy.runpod.net` URLs are HTTPS. No certbot needed.
2. **API key** — vLLM's built-in `--api-key` flag. Every request must include `Authorization: Bearer <key>`.
3. **Rate limiting** — Python middleware (`rate_limiter.py`): 50 requests/minute per IP, auto-ban IP for 1 hour after 3 failed auth attempts.
4. **SearXNG proxy** — FastAPI proxy (`searxng_proxy.py`) validates the same API key and forwards to SearXNG on localhost.
5. **RunPod proxy** — only exposed ports are routed through the proxy. vLLM on 8000 and SearXNG proxy on 8889 are exposed. SearXNG itself (8888) is localhost only.

## Deployment flow

### Phase 1 — RunPod account

1. Sign up at runpod.io
2. Add payment method + deposit funds (~$25 to start)
3. Go to Settings → API Keys → generate one → save as `RUNPOD_API_KEY` in `.env`

### Phase 2 — Network volume

RunPod console → Storage → Create Network Volume:
- Name: `qwopus-data`
- Region: pick one with A6000/A40 availability (e.g. US-TX-3, EU-RO-1)
- Size: **20 GB** (model is ~15 GB without .bak files)
- Mount path: `/workspace` (default)

Cost: ~$1.40/month

### Phase 3 — Create pod template

RunPod console → Pods → Templates → New Template:
- Name: `qwopus-27b`
- Image: `vllm/vllm-openai:latest` (or pin a version like `v0.8.3`)
- GPU: **1x A6000** or **1x A40** (48 GB)
- Container disk: **10 GB** (OS/packages, not model)
- Network volume: `qwopus-data` mounted at `/workspace`
- Expose ports: `8000/http, 8889/http`
- Docker command: `bash /workspace/QwopusUncensored/server/entrypoint.sh`
- Environment variables:
  - `QWOPUS_API_KEY=LdiOHxeTFEK1hv-1eJkg0hscCbj0RuhDbWHzBoO0f5Q`
  - `RUNPOD_API_KEY=<your-runpod-api-key>`
  - `RUNPOD_POD_ID=<filled-after-creation>`
  - `MAX_MODEL_LEN=32768`
  - `GPU_MEMORY_UTILIZATION=0.90`

### Phase 4 — First deploy

1. Launch the pod from the template (Spot or On-Demand)
2. SSH into the pod (RunPod provides a web terminal or SSH command)
3. Clone the repo and download the model:
```bash
cd /workspace
git clone https://github.com/pky00/QwopusUncensored.git
bash QwopusUncensored/server/download-model.sh
bash QwopusUncensored/server/install-searxng.sh
```
4. Note the pod ID from the RunPod console
5. Update `.env` on your laptop with `RUNPOD_POD_ID` and the proxy URLs
6. Restart the pod — `entrypoint.sh` launches everything automatically

### Phase 5 — Laptop tooling (WSL)

```bash
# Install RunPod CLI (optional, API calls work via curl too)
pip install runpod

# Make client scripts executable
chmod +x /mnt/c/Projects/QwopusUncensored/client/qwopus{,-stop,-status}
```

### Phase 6 — First run

```bash
cd /mnt/c/Projects/QwopusUncensored
./client/qwopus-status     # should show pod running + model loaded
./client/qwopus            # starts pod and launches opencode
```

## Daily use

- `./client/qwopus ~/some/project` — start pod, wait for vLLM, launch OpenCode in that dir
- `./client/qwopus-status` — quick health check
- `./client/qwopus-stop` — stop pod (or walk away, auto-shutdown handles it after 30 min)

## Sharing access

Give someone the URL + API key:
- Endpoint: `https://{pod-id}-8000.proxy.runpod.net/v1`
- API key: the value from `.env`
- They can use it from any OpenAI-compatible client
- No VPN, no client install, no IP whitelisting

## Updates

```bash
# laptop
git add <files> && git commit -m "..." && git push

# pod (via SSH or web terminal)
cd /workspace/QwopusUncensored && git pull
# restart the pod from RunPod console or API
```

## Teardown

1. Stop the pod
2. Delete the pod
3. Delete the network volume (or keep it for ~$1.40/month)

## Cost estimate

| Component | Monthly |
|---|---|
| A6000 Spot (~3 hrs/day) | ~$22 |
| Network volume (20 GB) | ~$1.40 |
| **Total** | **~$23/month** |

On-demand instead of Spot: ~$30/month. Still cheaper than AWS was.

## Known issues / decisions

1. **Context length**: starting at 32k (`--max-model-len 32768`). Can go up to 64k+ on 48 GB VRAM. Changing it is a one-line edit + pod restart.

2. **SearXNG without Docker**: needs pip install + manual config. May have dependency issues on the vLLM base image. Fallback: use a free web search API instead.

3. **Auto-shutdown timing**: RunPod Spot pods can be reclaimed AND auto-shutdown. If the cron script stops the pod, and then Spot reclaims it simultaneously, there's no conflict — both result in a stopped pod.

4. **Model .bak files**: not copying to network volume. Only the main safetensors + configs. If multimodal is needed later, re-download.

5. **vLLM base image version**: need to verify which version ships with transformers 5.5+ for Qwen3.5 support. May need a custom Dockerfile.

## Troubleshooting

| Issue | Fix |
|---|---|
| vLLM OOM | Lower `MAX_MODEL_LEN` (try 16384) or `GPU_MEMORY_UTILIZATION` |
| Slow first response | Normal — KV cache warmup |
| Tool calls failing | Try `--chat-template` flag |
| SearXNG no results | Check settings.yml has `formats: - json` |
| Can't connect | Check pod is running in RunPod console, verify proxy URL |
| API key rejected | Check `Authorization: Bearer <key>` header |
| Rate limited yourself | Wait 1 min, or SSH in and restart entrypoint |
| Auto-shutdown too aggressive | Raise `IDLE_LIMIT` in auto-shutdown.sh |
| Model download failed | SSH in, re-run download-model.sh |
| Spot reclaim | Pod stops, network volume preserved. Start pod again. |
| Pod won't start (Spot) | No capacity. Try a different GPU type or switch to On-Demand. |

## Decisions log

| Date | Decision | Reason |
|---|---|---|
| 2026-04-11 | Switched from BF16 to GPTQ 4-bit | Original model is 60 GB BF16, won't fit in 24 GB VRAM |
| 2026-04-11 | Changed `--quantization awq_marlin` → `gptq_marlin` | No AWQ variant exists |
| 2026-04-13 | Dropped Tailscale | HTTPS + API key solves IP rotation and access sharing more simply |
| 2026-04-13 | Added HTTPS + API key + rate limiting | Security layer for public endpoint |
| 2026-04-13 | Switched from on-demand to Spot | ~60-70% cost reduction |
| 2026-04-13 | Pivoted from AWS to RunPod | A10G (22 GB) OOM with multimodal model. No g6 in eu-west-1. RunPod A6000 (48 GB) is cheaper and fits. |
| 2026-04-13 | Dropped CloudWatch | Using RunPod built-in logs instead. Simpler, free. |
| 2026-04-13 | Dropped certbot/Let's Encrypt | RunPod proxy provides automatic HTTPS with stable URLs |
| 2026-04-13 | SearXNG via pip instead of Docker | No Docker-in-Docker on RunPod pods |
| 2026-04-13 | Context length 32k | 48 GB VRAM supports 32k-64k comfortably |
| 2026-04-13 | Ditched .bak model files | Not needed, saves ~17 GB on network volume |
