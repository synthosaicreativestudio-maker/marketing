#!/bin/bash

# Load environment variables from .env file
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Load environment variables directly
export TELEGRAM_BOT_TOKEN="8232668997:AAHCvWtcjtqw5b5tuYrYwg1lCz0oItjhUEg"
export ADMIN_TELEGRAM_ID=284355186

# Create logs directory
mkdir -p logs

# Start the bot with proper logging
echo "Starting MarketingBot..."
echo "Bot starting at $(date)" > logs/bot.log
python3 bot.py 2>&1 | tee -a logs/bot.log
