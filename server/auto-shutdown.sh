#!/bin/bash
IDLE_LIMIT=1800  # 30 minutes in seconds
ACTIVITY_FILE="/tmp/last_api_request"

if [ ! -f "$ACTIVITY_FILE" ]; then
    touch "$ACTIVITY_FILE"
fi

LAST=$(stat -c %Y "$ACTIVITY_FILE")
NOW=$(date +%s)
DIFF=$((NOW - LAST))

if [ $DIFF -ge $IDLE_LIMIT ]; then
    echo "$(date): No activity for 30 min. Shutting down."
    sudo shutdown -h now
fi
