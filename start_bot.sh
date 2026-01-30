#!/bin/bash
cd /home/ubuntu/marketingbot
pkill -9 -f "python bot.py" || true
sleep 2
nohup /home/ubuntu/marketingbot/.venv/bin/python -u /home/ubuntu/marketingbot/bot.py > /home/ubuntu/marketingbot/bot_rag_v4.log 2>&1 &
echo "Bot started PID: $!"
