# Qwopus 27B — Self-Hosted AI Stack

A private, uncensored, Claude Opus 4.6-distilled 27B model on AWS with coding agent, web search, and auto-shutdown.

> **Status (2026-04-13)**: AWS Spot quota approved (8 vCPUs, `eu-west-1`). Model downloaded locally. Implementation in progress: HTTPS + API key security, rate limiting, CloudWatch monitoring, SearXNG proxy. Next step: finish implementation, then deploy.

## Current progress

**Done:**
- Repo scaffolded: server scripts, client scripts, systemd unit, auto-shutdown, SearXNG config
- Server pinned to GPTQ quant (`gptq_marlin`) and `groxaxo/Huihui-Qwen3.5-27B-Claude-4.6-Opus-abliterated-gptq-w4g128`
- Model downloaded locally to `C:\Projects\QwopusUncensoredAgent\QwopusUncensored-model` (~17.8 GB GPTQ shards + ~17 GB `.bak` variant files)
- AWS console setup partially done: SSH key pair created, security group created, Elastic IP allocated (Phases 2-4)
- AWS Spot quota approved: 8 vCPUs for G and VT instances in `eu-west-1`
- Qwen3.5 architecture verified: vLLM has day-0 support (released Feb 16, 2026)

**In progress:**
- Security layer: HTTPS (Let's Encrypt via certbot) + vLLM `--api-key` + rate limiting middleware
- SearXNG proxy behind the same HTTPS + API key
- CloudWatch integration for all logging and monitoring
- Client scripts updated for HTTPS endpoints

**Pending (manual, in AWS console):**
- IAM role with `CloudWatchAgentServerPolicy` for the EC2 instance
- DNS: A record `qwopus.peteryamout.com` → Elastic IP (on Namecheap)
- AMI lookup for `eu-west-1`
- Launch Spot instance (persistent, interruption behavior = Stop)

### Model variants (`.bak` files)

The downloaded repo ships two parallel sets of files. These are NOT corruption — they're two views of the same weights:

| Variant | Architecture | Notes |
|---|---|---|
| Main (`config.json`, `model-*.safetensors`) | `Qwen3_5ForConditionalGeneration` | Multimodal wrapper. Produced by Unsloth. |
| Backup (`*.bak`) | `Qwen3_5ForCausalLM` | Text-only causal LM. |

Shards differ by ~6 KB each (metadata headers only). Do not delete `.bak` files until the server has loaded the model successfully.

## Environment

- **Laptop OS**: Windows 11 with WSL2 running Fedora Linux 42
- **Project path (Windows)**: `c:\Projects\QwopusUncensored`
- **Project path (WSL)**: `/mnt/c/Projects/QwopusUncensored`
- **GitHub repo**: https://github.com/pky00/QwopusUncensored (public)
- **AWS region**: `eu-west-1` (Ireland)
- **Domain**: `qwopus.peteryamout.com` (Namecheap DNS)
- **Why `/mnt/c`**: user wants to stay on Windows filesystem. SSH key lives on Linux side (`~/.ssh/`) for `chmod 600`.

## Architecture

```
Windows laptop / WSL2                 AWS eu-west-1, g6.2xlarge Spot (L4 24 GB)
┌──────────────────────┐              ┌──────────────────────────────┐
│  OpenCode (agent)    │──HTTPS+key──▶│  certbot (Let's Encrypt)     │
│  ├── local files     │   prompt     │  vLLM (model serving)        │
│  ├── terminal/bash   │◀─HTTPS+key──│  ├── Qwopus 27B (GPTQ)       │
│  ├── git             │   response   │  ├── --api-key (auth)        │
│  └── MCP: SearXNG ───│──HTTPS+key──▶│  └── --ssl-* (TLS)           │
│                      │   search     │                              │
│  qwopus CLI          │              │  SearXNG proxy (FastAPI)     │
│  └── start/stop AWS  │              │  └── same HTTPS + API key    │
│                      │              │                              │
│                      │              │  Rate limiting middleware    │
│                      │              │  ├── 50 req/min per IP       │
│                      │              │  └── auto-ban after 3 fails  │
│                      │              │                              │
│                      │              │  CloudWatch agent            │
│                      │              │  ├── vLLM logs               │
│                      │              │  ├── GPU/CPU/RAM metrics     │
│                      │              │  └── rate limit alerts       │
│                      │              │                              │
│                      │              │  Auto-shutdown (30m idle)    │
└──────────────────────┘              └──────────────────────────────┘
      HTTPS to qwopus.peteryamout.com:8000 (vLLM)
      HTTPS to qwopus.peteryamout.com:8888 (SearXNG proxy)
      Both protected by API key. No VPN/tunnel needed.
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
│   ├── setup.sh              # one-time install (docker, certbot, vllm, model, cloudwatch, systemd)
│   ├── startup.sh            # launched by systemd on every boot
│   ├── download-model.sh     # HF model pull
│   ├── auto-shutdown.sh      # 30-min idle shutdown (cron */5)
│   ├── request-tracker.sh    # tails vllm.log, touches activity file
│   ├── rate-limiter.py       # FastAPI middleware: per-IP rate limiting + auto-ban
│   ├── searxng-proxy.py      # HTTPS + API key proxy in front of SearXNG
│   ├── qwopus.service        # systemd unit
│   └── searxng/settings.yml
└── client/                   # runs on laptop (WSL)
    ├── qwopus                # start instance + wait for health + launch opencode
    ├── qwopus-stop           # stop instance
    ├── qwopus-status         # quick health check
    ├── opencode-config.json
    └── mcp-config.json
```

## Configuration (`.env`)

Copy `.env.example` to `.env` and fill in after AWS resources are created:

```bash
AWS_INSTANCE_ID=i-...
AWS_REGION=eu-west-1
AWS_ELASTIC_IP=...
AWS_SSH_KEY=/home/pky00/.ssh/qwopus-key.pem
AWS_SECURITY_GROUP_ID=sg-...
AWS_SUBNET_ID=subnet-...
AWS_KEY_PAIR_NAME=qwopus-key
QWOPUS_API_KEY=<generated-secret>
QWOPUS_DOMAIN=qwopus.peteryamout.com
VLLM_PORT=8000
SEARXNG_PORT=8888
SEARXNG_PROXY_PORT=8889
MODEL_REPO=groxaxo/Huihui-Qwen3.5-27B-Claude-4.6-Opus-abliterated-gptq-w4g128
MODEL_PATH=/home/ubuntu/models/qwopus-27b
MAX_MODEL_LEN=16384
GPU_MEMORY_UTILIZATION=0.90
```

## Security model

1. **HTTPS (Let's Encrypt)** — certbot generates a trusted TLS cert for `qwopus.peteryamout.com`. vLLM serves HTTPS directly via `--ssl-keyfile` / `--ssl-certfile`. Auto-renews via cron every 60 days.
2. **API key** — vLLM's built-in `--api-key` flag. Every request must include `Authorization: Bearer <key>`. No extra proxy needed for vLLM.
3. **Rate limiting** — Python middleware (`rate-limiter.py`) injected into vLLM: 50 requests/minute per IP, auto-ban IP for 1 hour after 3 failed auth attempts.
4. **SearXNG proxy** — SearXNG itself has no auth. A small FastAPI proxy (`searxng-proxy.py`) sits in front, validates the same API key, and forwards to SearXNG on localhost.
5. **Security group** — SSH (22) from My IP for bootstrap. Port 8000 (vLLM HTTPS) and 8889 (SearXNG proxy HTTPS) open to `0.0.0.0/0` — protected by API key + TLS. SearXNG port 8888 bound to localhost only.

## Monitoring (CloudWatch)

CloudWatch agent installed by `setup.sh`. Sends:
- **vLLM logs** (`/tmp/vllm.log`) → log group `/qwopus/vllm`
- **Auto-shutdown logs** (`/var/log/auto-shutdown.log`) → log group `/qwopus/auto-shutdown`
- **Startup logs** (`/var/log/qwopus-startup.log`) → log group `/qwopus/startup`
- **Rate limiter logs** → log group `/qwopus/rate-limiter`
- **System metrics** (CPU, RAM, disk) → custom namespace `Qwopus`
- **GPU metrics** (utilization, VRAM, temperature via `nvidia-smi`) → custom namespace `Qwopus`

## Deployment flow

### Phase 1 — Spot quota ✅

AWS console → Service Quotas → EC2 → `All G and VT Spot Instance Requests` → 8 vCPUs in `eu-west-1`. **Approved.**

### Phase 2 — SSH key pair ✅

AWS console → EC2 → Key Pairs → `qwopus-key` (RSA, .pem). **Done.**

### Phase 3 — Security group ✅ (needs update)

EC2 → Security Groups → `qwopus-sg`. Update inbound rules:
- **SSH (22)** — `Source = My IP`
- **HTTP (80)** — `Source = 0.0.0.0/0` (certbot Let's Encrypt challenge — needed for cert generation and renewal)
- **Custom TCP 8000** — `Source = 0.0.0.0/0` (vLLM HTTPS + API key)
- **Custom TCP 8889** — `Source = 0.0.0.0/0` (SearXNG proxy HTTPS + API key)

### Phase 4 — Elastic IP ✅

Allocated. Save the IPv4 address for `.env`.

### Phase 5 — DNS (Namecheap)

Namecheap → Domain → Advanced DNS → Add record:
- Type: **A Record**
- Host: `qwopus`
- Value: `<Elastic IP>`
- TTL: Automatic

Verify: `nslookup qwopus.peteryamout.com` should resolve to the Elastic IP.

### Phase 6 — IAM role for CloudWatch

IAM → Roles → Create role:
- Trusted entity: **EC2**
- Attach policy: `CloudWatchAgentServerPolicy`
- Name: `qwopus-ec2-role`

### Phase 7 — AMI lookup

EC2 → AMIs → Public images, owner `amazon`. Search: `Deep Learning OSS Nvidia Driver AMI GPU PyTorch Ubuntu 22.04`. Pick newest `eu-west-1` AMI.

### Phase 8 — Launch Spot instance

EC2 → Launch instances:
- Name: `qwopus-27b`
- AMI: from Phase 7
- Type: **g6.2xlarge**
- Key pair: `qwopus-key`
- Security group: `qwopus-sg`
- Storage: **100 GiB gp3**
- IAM instance profile: `qwopus-ec2-role`
- **Advanced details → Purchasing option → Request Spot Instances**
  - Request type: **Persistent**
  - Interruption behavior: **Stop**

### Phase 9 — Associate Elastic IP

EC2 → Elastic IPs → Actions → Associate → pick the instance.

### Phase 10 — Verify SSH

```bash
ssh -i ~/.ssh/qwopus-key.pem ubuntu@<elastic-ip>
```

### Phase 11 — Populate `.env` on laptop

Fill in all values gathered above, including the generated API key.

### Phase 12 — Deploy code to server

```bash
ssh -i ~/.ssh/qwopus-key.pem ubuntu@<elastic-ip>
git clone https://github.com/pky00/QwopusUncensored.git
cd QwopusUncensored
bash server/setup.sh
```
`setup.sh` installs Docker, certbot, vLLM, CloudWatch agent, downloads the model (~15-20 min), launches SearXNG, installs the systemd service, sets the auto-shutdown cron, generates the TLS cert, and reboots.

### Phase 13 — Laptop tooling (WSL)

```bash
# AWS CLI v2
sudo dnf install -y unzip curl
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
unzip awscliv2.zip && sudo ./aws/install && rm -rf aws awscliv2.zip
aws configure  # region=eu-west-1

# Node + OpenCode
sudo dnf install -y nodejs npm
sudo npm install -g @opencode/cli

# Make client scripts executable
chmod +x /mnt/c/Projects/QwopusUncensored/client/qwopus{,-stop,-status}
```

### Phase 14 — First run

```bash
cd /mnt/c/Projects/QwopusUncensored
./client/qwopus-status     # should show instance running + model loaded
./client/qwopus            # starts everything and launches opencode
```

## Daily use

- `./client/qwopus ~/some/project` — start instance, wait for vLLM, launch OpenCode in that dir
- `./client/qwopus-status` — quick health check
- `./client/qwopus-stop` — stop instance (or walk away, auto-shutdown handles it after 30 min)

## Sharing access

Give someone the URL + API key:
- Endpoint: `https://qwopus.peteryamout.com:8000/v1`
- API key: the value from `.env`
- They can use it from any OpenAI-compatible client (OpenCode, Continue, Cursor, etc.)
- No VPN, no client install, no IP whitelisting

## Updates

```bash
# laptop
git add <files> && git commit -m "..." && git push

# server
ssh -i ~/.ssh/qwopus-key.pem ubuntu@<elastic-ip>
cd QwopusUncensored && git pull
sudo systemctl restart qwopus.service
```

## Teardown

Manual in the console:
1. Terminate the instance (cancel the Spot request first)
2. Release the Elastic IP (bills while unattached)
3. Delete the security group
4. Delete the key pair (optional)
5. Remove the DNS A record from Namecheap

## Cost estimate

| Component | Monthly |
|---|---|
| g6.2xlarge **Spot** (~3 hrs/day, eu-west-1) | ~$15–25 |
| 100 GB gp3 EBS | ~$8 |
| Elastic IP while attached to running instance | $0 |
| Elastic IP while instance stopped | ~$3.65 |
| CloudWatch (logs + custom metrics) | ~$1–3 |
| Domain (peteryamout.com, annual) | ~$1/month |
| **Total** | **~$28–40/month** |

Spot pricing is ~60-70% cheaper than on-demand.

## Known issues / decisions

1. ~~Model quantization mismatch~~ **Resolved**. Switched to GPTQ variant, `--quantization gptq_marlin`.

2. ~~Model architecture not supported by vLLM~~ **Resolved**. Qwen3.5 is an official model family (released Feb 2026) with day-0 vLLM support.

3. **AMI ID not yet selected**. Must be looked up manually in Phase 7 for `eu-west-1`.

4. **OpenCode config paths**. `client/opencode-config.json` and `client/mcp-config.json` need to be copied into wherever OpenCode actually reads its config from — not verified.

5. **certbot on Spot interruption**. If AWS reclaims the instance and it stops, the cert and renewal cron survive on the EBS volume. On restart, certbot picks up where it left off. No action needed, but worth verifying on first reclaim.

## Troubleshooting

| Issue | Fix |
|---|---|
| vLLM OOM | Lower `MAX_MODEL_LEN` to 8192 in `server/startup.sh` |
| Slow first response | Normal — KV cache warmup |
| Tool calls failing | Try higher quant or add `--chat-template` |
| SearXNG no results | Check `formats: - json` in settings.yml, `docker restart searxng` |
| Can't connect | Check SG rules, verify `qwopus.peteryamout.com` resolves to EIP via `nslookup` |
| TLS cert expired | SSH in, run `sudo certbot renew --force-renewal` |
| Rate limited yourself | Wait 1 min, or SSH in and restart the rate limiter |
| Auto-shutdown too aggressive | Raise `IDLE_LIMIT` in `auto-shutdown.sh` |
| Model download failed | SSH in, re-run `bash server/download-model.sh` |
| Spot reclaim mid-session | Instance stops, disk preserved. Run `./client/qwopus` to restart. |
| CloudWatch not receiving logs | Check IAM role is attached, run `sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a status` |

## Decisions log

| Date | Decision | Reason |
|---|---|---|
| 2026-04-11 | Switched from BF16 to GPTQ 4-bit (`groxaxo/...`) | Original model is 60 GB BF16, won't fit in 24 GB VRAM without on-the-fly quant |
| 2026-04-11 | Changed `--quantization awq_marlin` → `gptq_marlin` | No AWQ variant exists for this model |
| 2026-04-13 | Dropped Tailscale | HTTPS + API key solves IP rotation and access sharing more simply |
| 2026-04-13 | Added HTTPS via Let's Encrypt + vLLM native SSL | Encrypts API key in transit, proper trusted cert via `qwopus.peteryamout.com` |
| 2026-04-13 | Added rate limiting (50 req/min, 3-strike ban for 1hr) | Prevents brute-force and abuse on public endpoint |
| 2026-04-13 | Added SearXNG proxy with API key auth | SearXNG has no built-in auth; proxy enforces same API key |
| 2026-04-13 | Added CloudWatch monitoring | Centralized logging for vLLM, GPU, system metrics, rate limiter |
| 2026-04-13 | Switched from on-demand to Spot (persistent, Stop) | ~60-70% cost reduction, acceptable interruption risk for personal use |
| 2026-04-13 | Domain: `qwopus.peteryamout.com` | Already owned on Namecheap |
