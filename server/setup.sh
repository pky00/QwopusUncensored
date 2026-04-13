#!/bin/bash
# Run once after instance creation
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

if [ -z "$QWOPUS_API_KEY" ]; then
  echo "ERROR: QWOPUS_API_KEY env var not set."
  echo "  export QWOPUS_API_KEY=your-secret-key"
  exit 1
fi

if [ -z "$QWOPUS_DOMAIN" ]; then
  echo "ERROR: QWOPUS_DOMAIN env var not set."
  echo "  export QWOPUS_DOMAIN=qwopus.peteryamout.com"
  exit 1
fi

echo "========================================="
echo " Qwopus 27B — Server Setup"
echo "========================================="

echo "[1/9] Installing Docker..."
sudo apt-get update
if ! command -v docker &> /dev/null; then
  sudo apt-get install -y docker.io docker-compose
fi
sudo usermod -aG docker ubuntu

echo "[2/9] Installing vLLM + dependencies..."
pip3 install vllm huggingface-hub httpx fastapi uvicorn --break-system-packages

echo "[3/9] Installing Node.js..."
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

echo "[4/9] Downloading model (this takes 10-20 min)..."
bash "$SCRIPT_DIR/download-model.sh"

echo "[5/9] Setting up SearXNG..."
docker run -d \
  --name searxng \
  --restart unless-stopped \
  -p 127.0.0.1:8888:8888 \
  -v "$SCRIPT_DIR/searxng/settings.yml:/etc/searxng/settings.yml" \
  searxng/searxng

echo "[6/9] Installing certbot and generating TLS cert..."
echo "  NOTE: Port 80 must be open in the security group for cert generation."
echo "  You can close it after setup if desired (only needed for renewals)."
sudo apt-get install -y certbot
sudo certbot certonly --standalone \
  -d "$QWOPUS_DOMAIN" \
  --non-interactive \
  --agree-tos \
  --register-unsafely-without-email

sudo chmod 755 /etc/letsencrypt/live /etc/letsencrypt/archive
(crontab -l 2>/dev/null; echo "0 3 1 */2 * certbot renew --quiet --standalone --post-hook 'systemctl restart qwopus.service'") | crontab -

echo "[7/9] Installing CloudWatch agent..."
wget -q https://amazoncloudwatch-agent.s3.amazonaws.com/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i -E amazon-cloudwatch-agent.deb
rm -f amazon-cloudwatch-agent.deb

sudo cp "$SCRIPT_DIR/cloudwatch-agent-config.json" /opt/aws/amazon-cloudwatch-agent/etc/
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config \
  -m ec2 \
  -s \
  -c file:/opt/aws/amazon-cloudwatch-agent/etc/cloudwatch-agent-config.json

echo "[8/9] Writing env config..."
sudo tee /etc/qwopus.env > /dev/null <<EOF
QWOPUS_API_KEY=$QWOPUS_API_KEY
QWOPUS_DOMAIN=$QWOPUS_DOMAIN
SEARXNG_URL=http://127.0.0.1:8888
SEARXNG_PROXY_PORT=8889
SSL_CERTFILE=/etc/letsencrypt/live/$QWOPUS_DOMAIN/fullchain.pem
SSL_KEYFILE=/etc/letsencrypt/live/$QWOPUS_DOMAIN/privkey.pem
EOF
sudo chmod 600 /etc/qwopus.env

echo "[9/9] Installing startup service..."
sudo cp "$SCRIPT_DIR/qwopus.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable qwopus.service

chmod +x "$SCRIPT_DIR/auto-shutdown.sh"
chmod +x "$SCRIPT_DIR/request-tracker.sh"
chmod +x "$SCRIPT_DIR/startup.sh"
chmod +x "$SCRIPT_DIR/gpu_metrics.sh"
(crontab -l 2>/dev/null; echo "*/5 * * * * $SCRIPT_DIR/auto-shutdown.sh >> /var/log/auto-shutdown.log 2>&1") | crontab -

echo ""
echo "========================================="
echo " Setup complete!"
echo " Rebooting to start services..."
echo "========================================="

sudo reboot
