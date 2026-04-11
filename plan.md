# Qwopus 27B — Self-Hosted AI Stack

A private, uncensored, Claude Opus 4.6-distilled 27B model on AWS with coding agent, web search, and auto-shutdown. Target cost: ~$40–50/month.

> **Status**: scaffolding complete, not yet deployed. Infrastructure is created manually in the AWS console (no CloudFormation). Code is deployed to the server via `git clone` from the public GitHub repo.

## Environment

- **Laptop OS**: Windows 11 with WSL2 running Fedora Linux 42
- **Project path (Windows)**: `c:\Projects\QwopusUncensored`
- **Project path (WSL)**: `/mnt/c/Projects/QwopusUncensored`
- **GitHub repo**: https://github.com/pky00/QwopusUncensored (public)
- **AWS region**: `eu-west-1` (Ireland)
- **Why `/mnt/c`**: user wants to stay on Windows filesystem. The only thing that must live on the Linux side is the SSH private key (permissions). Line endings are handled via `.gitattributes` (`*.sh text eol=lf`).

## Architecture

```
Windows laptop / WSL2                AWS eu-west-1, g6.2xlarge (L4 24 GB VRAM)
┌──────────────────────┐             ┌──────────────────────────┐
│  OpenCode (agent)    │────────────▶│  vLLM (model serving)    │
│  ├── local files     │   prompt    │  └── Qwopus 27B (AWQ)    │
│  ├── terminal/bash   │◀────────────│                          │
│  ├── git             │   response  │  SearXNG (web search)    │
│  └── MCP: SearXNG ───│────────────▶│  └── Google/Bing/DDG     │
│                      │   search    │                          │
│  qwopus CLI          │             │  Auto-shutdown (30m idle) │
│  └── start/stop AWS  │             │                          │
└──────────────────────┘             └──────────────────────────┘
```

## Repository layout

```
QwopusUncensored/
├── .gitattributes          # *.sh text eol=lf (CRLF protection)
├── .gitignore              # .env, *.pem, test.sh
├── .env.example            # copy to .env, fill in AWS values
├── plan.md                 # this file
├── README.md
├── server/                 # runs on EC2
│   ├── setup.sh            # one-time install (docker, vllm, model, searxng, systemd)
│   ├── startup.sh          # launched by systemd on every boot
│   ├── download-model.sh   # HF model pull
│   ├── auto-shutdown.sh    # 30-min idle shutdown (cron */5)
│   ├── request-tracker.sh  # tails vllm.log, touches activity file
│   ├── qwopus.service      # systemd unit
│   └── searxng/settings.yml
└── client/                 # runs on laptop (WSL)
    ├── qwopus              # start instance + wait for health + launch opencode
    ├── qwopus-stop         # stop instance
    ├── qwopus-status       # quick health check
    ├── opencode-config.json
    └── mcp-config.json
```

**No `infra/` folder** — CloudFormation was removed in favor of manual console setup.

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
VLLM_PORT=8000
SEARXNG_PORT=8888
MODEL_REPO=huihui-ai/Huihui-Qwen3.5-27B-Claude-4.6-Opus-abliterated
MODEL_PATH=/home/ubuntu/models/qwopus-27b
MAX_MODEL_LEN=16384
GPU_MEMORY_UTILIZATION=0.90
```

The SSH key lives on the Linux filesystem (`~/.ssh/`) because `chmod 600` is required and that doesn't stick on `/mnt/c`.

## Deployment flow

### Phase 1 — G-family quota (blocking)

AWS console → **Service Quotas** → EC2 → `Running On-Demand G and VT instances` → need **≥ 8 vCPUs** in `eu-west-1`. Request increase if 0. Takes hours to 2 days.

### Phase 2 — SSH key pair

AWS console → EC2 → Key Pairs → Create `qwopus-key` (RSA, .pem). Download, then in WSL:
```bash
mkdir -p ~/.ssh
mv /mnt/c/Users/<win-user>/Downloads/qwopus-key.pem ~/.ssh/
chmod 600 ~/.ssh/qwopus-key.pem
```

### Phase 3 — Security group

EC2 → Security Groups → Create `qwopus-sg`. Inbound rules, all `Source = My IP`:
- SSH (22)
- Custom TCP 8000 (vLLM)
- Custom TCP 8888 (SearXNG)

### Phase 4 — Elastic IP

EC2 → Elastic IPs → Allocate. Save the IPv4 address for `.env`.

### Phase 5 — AMI lookup

EC2 → AMIs → Public images, owner `amazon`. Search: `Deep Learning OSS Nvidia Driver AMI GPU PyTorch Ubuntu 22.04`. Pick newest. AMI IDs are region-specific — must be an `eu-west-1` AMI.

### Phase 6 — Launch instance

EC2 → Launch instances:
- Name: `qwopus-27b`
- AMI: from Phase 5
- Type: **g6.2xlarge**
- Key pair: `qwopus-key`
- Security group: existing `qwopus-sg`
- Storage: **100 GiB gp3**
- Leave user-data empty (setup is run manually)

### Phase 7 — Associate Elastic IP

EC2 → Elastic IPs → Actions → Associate → pick the instance.

### Phase 8 — Verify SSH

```bash
ssh -i ~/.ssh/qwopus-key.pem ubuntu@<elastic-ip>
```

### Phase 9 — Populate `.env` on laptop

Fill in the values gathered above.

### Phase 10 — Deploy code to server

Server pulls directly from the public GitHub repo:
```bash
ssh -i ~/.ssh/qwopus-key.pem ubuntu@<elastic-ip>
git clone https://github.com/pky00/QwopusUncensored.git
cd QwopusUncensored
bash server/setup.sh
```
`setup.sh` installs Docker, vLLM, Node, downloads the model (~15–20 min), launches SearXNG, installs the systemd service, sets the auto-shutdown cron, and reboots.

### Phase 11 — Laptop tooling (WSL)

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

### Phase 12 — First run

```bash
cd /mnt/c/Projects/QwopusUncensored
./client/qwopus-status     # should show instance running + model loaded
./client/qwopus            # starts everything and launches opencode
```

## Daily use

- `./client/qwopus ~/some/project` — start instance, wait for vLLM, launch OpenCode in that dir
- `./client/qwopus-status` — quick health check
- `./client/qwopus-stop` — stop instance (or just walk away, auto-shutdown handles it after 30 min)

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
1. Terminate the instance
2. Release the Elastic IP (otherwise it bills while unattached)
3. Delete the security group
4. Delete the key pair (optional)

## Cost estimate

| Component | Monthly |
|---|---|
| g6.2xlarge on-demand (~3 hrs/day, eu-west-1) | ~$35–45 |
| 100 GB gp3 EBS | ~$8 |
| Elastic IP while attached to running instance | $0 |
| Elastic IP while instance stopped | ~$3.65 |
| **Total** | **~$45–55/month** |

eu-west-1 is ~10–15% more expensive than us-east-1.

## Known issues / decisions pending

These must be resolved before first successful deploy:

1. **Model quantization mismatch**. [server/startup.sh](server/startup.sh) passes `--quantization awq_marlin`, but it's not verified that the HF repo `huihui-ai/Huihui-Qwen3.5-27B-Claude-4.6-Opus-abliterated` is actually an AWQ build. vLLM will refuse to load a non-AWQ model with that flag. **Action**: inspect the HF repo. If fp16/bf16, find an AWQ variant or switch quantization strategy (GPTQ, bitsandbytes, or a pre-quantized mirror).

2. **AMI ID not yet selected**. Must be looked up manually in Phase 5 for `eu-west-1`.

3. **`opencode-config.json` and `mcp-config.json`** contain `YOUR_ELASTIC_IP` placeholders — replace after Phase 4.

4. **OpenCode config paths**. `client/opencode-config.json` and `client/mcp-config.json` need to be copied into wherever OpenCode actually reads its config from — not verified.

## Troubleshooting

| Issue | Fix |
|---|---|
| vLLM OOM | Lower `MAX_MODEL_LEN` to 8192 in `server/startup.sh` |
| Slow first response | Normal — KV cache warmup |
| Tool calls failing | Try higher quant or add `--chat-template` |
| SearXNG no results | Check `formats: - json` in settings.yml, `docker restart searxng` |
| Can't connect | Security group IP may be stale — update to current IP |
| Auto-shutdown too aggressive | Raise `IDLE_LIMIT` in `auto-shutdown.sh` |
| Model download failed | SSH in, re-run `bash server/download-model.sh` |
| vLLM refuses to load model | Almost certainly the quantization mismatch (issue 1 above) |
