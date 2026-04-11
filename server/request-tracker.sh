#!/bin/bash
# Watches vLLM log for requests and updates activity timestamp

while true; do
    if [ -f /tmp/vllm.log ]; then
        tail -n 0 -f /tmp/vllm.log 2>/dev/null | while read line; do
            if echo "$line" | grep -q "POST\|chat/completions"; then
                touch /tmp/last_api_request
            fi
        done
    fi
    sleep 5
done
