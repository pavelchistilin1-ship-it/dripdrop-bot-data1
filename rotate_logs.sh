#!/bin/bash
LOG_FILE="/home/ubuntu/dripdrop_bot/bot.log"
MAX_SIZE=10485760 # 10MB
if [ -f "$LOG_FILE" ]; then
    SIZE=$(stat -c%s "$LOG_FILE")
    if [ $SIZE -gt $MAX_SIZE ]; then
        mv "$LOG_FILE" "${LOG_FILE}.old"
        touch "$LOG_FILE"
        echo "Log rotated at $(date)" > "$LOG_FILE"
    fi
fi
