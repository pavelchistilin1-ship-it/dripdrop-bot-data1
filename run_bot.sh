#!/bin/bash
while true; do
    echo "Syncing database to GitHub at $(date)" >> /home/ubuntu/dripdrop_bot/bot.log
    /home/ubuntu/dripdrop_bot/sync_db.sh >> /home/ubuntu/dripdrop_bot/bot.log 2>&1
    
    echo "Starting bot at $(date)" >> /home/ubuntu/dripdrop_bot/bot.log
    /home/ubuntu/dripdrop_bot/rotate_logs.sh && /usr/bin/python3.11 /home/ubuntu/dripdrop_bot/bot.py >> /home/ubuntu/dripdrop_bot/bot.log 2>&1
    
    echo "Bot crashed at $(date). Syncing and restarting in 5 seconds..." >> /home/ubuntu/dripdrop_bot/bot.log
    /home/ubuntu/dripdrop_bot/sync_db.sh >> /home/ubuntu/dripdrop_bot/bot.log 2>&1
    sleep 5
done
