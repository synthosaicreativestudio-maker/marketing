#!/bin/bash

# Load environment variables from .env file
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Set TELEGRAM_BOT_TOKEN from TELEGRAM_TOKEN if it exists
if [ ! -z "$TELEGRAM_TOKEN" ]; then
    export TELEGRAM_BOT_TOKEN="$TELEGRAM_TOKEN"
fi

# Check if TELEGRAM_BOT_TOKEN is set
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "Error: TELEGRAM_BOT_TOKEN is not set"
    exit 1
fi

echo "Starting MarketingBot..."
echo "Token: ${TELEGRAM_BOT_TOKEN:0:10}..."

# Start the bot
python3 bot.py
