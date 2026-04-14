#!/bin/bash
# Auto-shutdown: stops the RunPod pod after 30 minutes of no API activity

IDLE_LIMIT=1800
ACTIVITY_FILE=/tmp/last_api_request

if [ ! -f "$ACTIVITY_FILE" ]; then
  touch "$ACTIVITY_FILE"
fi

LAST=$(stat -c %Y "$ACTIVITY_FILE")
NOW=$(date +%s)
DIFF=$((NOW - LAST))

if [ $DIFF -ge $IDLE_LIMIT ]; then
  echo "$(date): No activity for 30 min. Stopping pod..."

  if [ -z "$RUNPOD_API_KEY" ] || [ -z "$RUNPOD_POD_ID" ]; then
    echo "$(date): RUNPOD_API_KEY or RUNPOD_POD_ID not set. Cannot stop pod."
    exit 1
  fi

  curl -s -X POST "https://api.runpod.io/graphql?api_key=$RUNPOD_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"query\": \"mutation { podTerminate(input: { podId: \\\"$RUNPOD_POD_ID\\\" }) }\"}" \
    > /dev/null 2>&1

  echo "$(date): Pod terminate request sent."
fi
