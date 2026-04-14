#!/bin/bash
set -e

MODEL_REPO="groxaxo/Huihui-Qwen3.5-27B-Claude-4.6-Opus-abliterated-gptq-w4g128"
MODEL_PATH="${MODEL_PATH:-/workspace/models/qwopus-27b}"

mkdir -p "$MODEL_PATH"

echo "Downloading $MODEL_REPO..."
echo "This will take 10-20 minutes depending on bandwidth."

python3 -m huggingface_hub.commands.huggingface_cli download "$MODEL_REPO" \
  --local-dir "$MODEL_PATH" \
  --exclude "*.bak"

echo "Model downloaded to $MODEL_PATH"
ls -lh "$MODEL_PATH"
