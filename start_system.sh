#!/bin/bash

echo "🚀 Starting MarketingBot System..."

# Get local IP
LOCAL_IP=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | head -1 | awk '{print $2}')
echo "📡 Local IP: $LOCAL_IP"

# Load environment variables
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Set TELEGRAM_BOT_TOKEN from TELEGRAM_TOKEN if needed
if [ ! -z "$TELEGRAM_TOKEN" ]; then
    export TELEGRAM_BOT_TOKEN="$TELEGRAM_TOKEN"
fi

# Set WEBAPP_URL
export WEBAPP_URL="https://$LOCAL_IP:8000/webapp/index.html"
echo "🌐 WebApp URL: $WEBAPP_URL"

# Check if certificates exist
if [ ! -f "cert.pem" ] || [ ! -f "key.pem" ]; then
    echo "🔐 Creating SSL certificates..."
    openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/C=RU/ST=Moscow/L=Moscow/O=MarketingBot/CN=$LOCAL_IP"
fi

# Start web server in background
echo "🌐 Starting HTTPS web server..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --ssl-keyfile key.pem --ssl-certfile cert.pem &
WEB_PID=$!

# Wait for web server to start
sleep 3

# Start bot
echo "🤖 Starting Telegram bot..."
python3 bot.py &
BOT_PID=$!

echo "✅ System started!"
echo "📱 Bot PID: $BOT_PID"
echo "🌐 Web Server PID: $WEB_PID"
echo ""
echo "📋 Instructions:"
echo "1. Send /start to your bot in Telegram"
echo "2. Click 'Авторизоваться' button"
echo "3. Web app will open at: $WEBAPP_URL"
echo ""
echo "⚠️  Note: You may need to accept the self-signed certificate in your browser"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for interrupt
trap 'echo "🛑 Stopping services..."; kill $BOT_PID $WEB_PID 2>/dev/null; exit' INT
wait
