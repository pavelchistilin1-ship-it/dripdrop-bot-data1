#!/bin/bash
cd /home/ubuntu/dripdrop_bot
git add dripdrop.db
git commit -m "Auto-sync database: $(date)"
git push origin main
