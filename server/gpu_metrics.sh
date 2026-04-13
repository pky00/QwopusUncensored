#!/bin/bash
# Publishes GPU metrics to CloudWatch every 60 seconds
# Runs as a background process started by startup.sh

NAMESPACE="Qwopus"
REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region)
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)

while true; do
  METRICS=$(nvidia-smi --query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total,temperature.gpu,power.draw --format=csv,noheader,nounits 2>/dev/null)

  if [ -n "$METRICS" ]; then
    IFS=',' read -r GPU_UTIL MEM_UTIL MEM_USED MEM_TOTAL GPU_TEMP POWER <<< "$METRICS"

    GPU_UTIL=$(echo "$GPU_UTIL" | tr -d ' ')
    MEM_UTIL=$(echo "$MEM_UTIL" | tr -d ' ')
    MEM_USED=$(echo "$MEM_USED" | tr -d ' ')
    MEM_TOTAL=$(echo "$MEM_TOTAL" | tr -d ' ')
    GPU_TEMP=$(echo "$GPU_TEMP" | tr -d ' ')
    POWER=$(echo "$POWER" | tr -d ' ')

    aws cloudwatch put-metric-data \
      --namespace "$NAMESPACE" \
      --region "$REGION" \
      --metric-data \
        "MetricName=GPUUtilization,Value=$GPU_UTIL,Unit=Percent,Dimensions=[{Name=InstanceId,Value=$INSTANCE_ID}]" \
        "MetricName=GPUMemoryUtilization,Value=$MEM_UTIL,Unit=Percent,Dimensions=[{Name=InstanceId,Value=$INSTANCE_ID}]" \
        "MetricName=GPUMemoryUsed,Value=$MEM_USED,Unit=Megabytes,Dimensions=[{Name=InstanceId,Value=$INSTANCE_ID}]" \
        "MetricName=GPUTemperature,Value=$GPU_TEMP,Unit=None,Dimensions=[{Name=InstanceId,Value=$INSTANCE_ID}]" \
        "MetricName=GPUPowerDraw,Value=$POWER,Unit=None,Dimensions=[{Name=InstanceId,Value=$INSTANCE_ID}]" \
      2>/dev/null
  fi

  sleep 60
done
