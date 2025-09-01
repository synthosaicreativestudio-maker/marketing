#!/bin/bash

# Unified script for managing the Marketing Bot
#
# Commands:
#   start   - Safely start the bot
#   stop    - Stop the bot
#   restart - Restart the bot
#   status  - Check the status
#   logs    - Show the latest logs

# --- Settings ---
BOT_NAME="marketing_bot"
# Use project directory for lock and log files for simplicity
LOCK_FILE="bot.lock"
LOG_FILE="bot.log"
PYTHON_CMD="python3"
BOT_SCRIPT="bot.py"

# --- Functions ---

# Function to stop all bot processes
stop_bot() {
    echo "Stopping all bot processes..."
    
    # 1. By PID from lock file (safest method)
    if [ -f "$LOCK_FILE" ]; then
        BOT_PID=$(cat "$LOCK_FILE")
        if [ -n "$BOT_PID" ] && ps -p $BOT_PID > /dev/null 2>&1; then
            echo "   - Stopping process with PID $BOT_PID..."
            kill $BOT_PID
            sleep 1
        fi
        rm -f "$LOCK_FILE"
        echo "   - Lock file removed."
    fi

    # 2. By process name (fallback)
    PIDS=$(ps aux | grep -E "($PYTHON_CMD.*$BOT_SCRIPT)" | grep -v grep | awk '{print $2}')
    if [ -n "$PIDS" ]; then
        echo "   - Found and stopped processes by name: $PIDS"
        pkill -f "$PYTHON_CMD.*$BOT_SCRIPT" 2>/dev/null
        sleep 1
    fi
    
    # 3. Force stop (last resort)
    PIDS=$(ps aux | grep -E "($PYTHON_CMD.*$BOT_SCRIPT)" | grep -v grep | awk '{print $2}')
    if [ -n "$PIDS" ]; then
        echo "   - Forcibly stopping remaining processes: $PIDS"
        kill -9 $PIDS 2>/dev/null
    fi

    echo "Bot processes stopped."
}

# --- Script Logic ---

# Get command from user
COMMAND=$1

case "$COMMAND" in
    start)
        echo "Starting bot..."
        
        # Check if bot is already running
        if [ -f "$LOCK_FILE" ]; then
            BOT_PID=$(cat "$LOCK_FILE")
            if [ -n "$BOT_PID" ] && ps -p $BOT_PID > /dev/null 2>&1; then
                echo "Warning: Bot is already running with PID $BOT_PID. To restart, use: ./manage.sh restart"
                exit 1
            else
                # If process is dead but lock file remains
                echo "   - Found stale lock file. Removing..."
                rm -f "$LOCK_FILE"
            fi
        fi

        # Start the bot in the background
        nohup $PYTHON_CMD $BOT_SCRIPT >> "$LOG_FILE" 2>&1 & 
        
        # Get the PID of the started process
        BOT_PID=$!
        echo "$BOT_PID" > "$LOCK_FILE"
        
        echo "Bot started successfully with PID: $BOT_PID"
        echo "   - Logs are written to: $LOG_FILE"
        echo "   - Lock file created: $LOCK_FILE"
        ;;

    stop)
        stop_bot
        ;;

    restart)
        echo "Restarting bot..."
        stop_bot
        sleep 1
        # Call start in this same script
        bash "$0" start
        ;;

    status)
        echo "Checking bot status..."
        if [ -f "$LOCK_FILE" ]; then
            BOT_PID=$(cat "$LOCK_FILE")
            if [ -n "$BOT_PID" ] && ps -p $BOT_PID > /dev/null 2>&1; then
                echo "Bot is running. PID: $BOT_PID"
                echo "Process details:"
                ps -p $BOT_PID -o pid,ppid,cmd,etime,pcpu,pmem
            else
                echo "Error: Bot is not running (but lock file exists)."
                echo "   - Recommendation: Run ./manage.sh stop and then ./manage.sh start"
            fi
        else
            echo "Error: Bot is not running (lock file not found)."
        fi
        ;;

    logs)
        echo "Last 15 lines of log ($LOG_FILE):"
        tail -n 15 "$LOG_FILE"
        ;;

    *)
        echo "Unknown command: '$COMMAND'"
        echo ""
        echo "Available commands:"
        echo "  start   - Safely start the bot"
        echo "  stop    - Stop the bot"
        echo "  restart - Restart the bot"
        echo "  status  - Check the status"
        echo "  logs    - Show the latest logs"
        exit 1
        ;;
esac