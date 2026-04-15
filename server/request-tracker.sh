#!/bin/bash
# Watches vLLM log for requests and updates activity timestamp

LOGFILE="/workspace/logs/vllm.log"

while true; do
    if [ -f "$LOGFILE" ]; then
        tail -n 0 -f "$LOGFILE" 2>/dev/null | while read line; do
            if echo "$line" | grep -q "POST\|chat/completions\|200 OK"; then
                touch /tmp/last_api_request
            fi
        done
    fi
    sleep 5
done
