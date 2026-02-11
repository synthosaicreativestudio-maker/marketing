#!/bin/bash
cd /home/marketing/marketingbot
pkill -9 -f "python bot.py" || true
sleep 2
nohup /home/marketing/marketingbot/.venv/bin/python -u /home/marketing/marketingbot/bot.py > /home/marketing/marketingbot/bot_rag_v4.log 2>&1 &
echo "Bot started PID: $!"
