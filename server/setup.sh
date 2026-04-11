#!/bin/bash
# Run once after instance creation
set -e

echo "========================================="
echo " Qwopus 27B — Server Setup"
echo "========================================="

echo "[1/6] Installing Docker..."
sudo apt-get update
sudo apt-get install -y docker.io docker-compose
sudo usermod -aG docker ubuntu

echo "[2/6] Installing vLLM..."
pip install vllm huggingface-hub --break-system-packages

echo "[3/6] Installing Node.js..."
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

echo "[4/6] Downloading model (this takes 10-20 min)..."
bash /home/ubuntu/QwopusUncensored/server/download-model.sh

echo "[5/6] Setting up SearXNG..."
docker run -d \
  --name searxng \
  --restart unless-stopped \
  -p 8888:8888 \
  -v /home/ubuntu/QwopusUncensored/server/searxng/settings.yml:/etc/searxng/settings.yml \
  searxng/searxng

echo "[6/6] Installing startup service..."
sudo cp /home/ubuntu/QwopusUncensored/server/qwopus.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable qwopus.service

chmod +x /home/ubuntu/QwopusUncensored/server/auto-shutdown.sh
chmod +x /home/ubuntu/QwopusUncensored/server/request-tracker.sh
chmod +x /home/ubuntu/QwopusUncensored/server/startup.sh
(crontab -l 2>/dev/null; echo "*/5 * * * * /home/ubuntu/QwopusUncensored/server/auto-shutdown.sh >> /var/log/auto-shutdown.log 2>&1") | crontab -

echo ""
echo "========================================="
echo " Setup complete!"
echo " Rebooting to start services..."
echo "========================================="

sudo reboot
