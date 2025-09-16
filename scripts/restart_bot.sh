#!/usr/bin/env bash
# Enhanced restart bot script with better error handling and monitoring

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Configuration
readonly MAX_RETRIES=3
readonly HEALTH_CHECK_TIMEOUT=30
readonly GRACEFUL_SHUTDOWN_TIMEOUT=10

log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1"
}

log_debug() {
    if [[ "${DEBUG:-}" == "true" ]]; then
        echo -e "${BLUE}[DEBUG]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1"
    fi
}

# Cleanup function for trap
cleanup() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        log_error "Script failed with exit code $exit_code"
    fi
    exit $exit_code
}

trap cleanup EXIT

# Change to project root
cd "$(dirname "$0")/.."
readonly PROJECT_ROOT=$(pwd)

log_info "Project root: $PROJECT_ROOT"

# Load environment variables from .env if it exists
if [[ -f ".env" ]]; then
    log_info "Loading environment from .env"
    set -a  # automatically export all variables
    # shellcheck source=/dev/null
    source .env
    set +a
else
    log_warn ".env file not found, using system environment"
fi

# Find Python executable - prefer project venv
find_python() {
    local python_cmd="python3"
    
    if [[ -f ".venv312/bin/python" ]]; then
        python_cmd=".venv312/bin/python"
        log_info "Using project Python: $python_cmd"
    elif [[ -f ".venv/bin/python" ]]; then
        python_cmd=".venv/bin/python"
        log_info "Using project Python: $python_cmd"
    else
        log_warn "Using system Python: $python_cmd"
    fi
    
    # Verify Python works
    if ! "$python_cmd" --version >/dev/null 2>&1; then
        log_error "Python executable not working: $python_cmd"
        exit 1
    fi
    
    echo "$python_cmd"
}

readonly PYTHON_CMD=$(find_python)

# Check if bot.py exists
if [[ ! -f "bot.py" ]]; then
    log_error "bot.py not found in project root"
    exit 1
fi

# Stop existing bot processes gracefully
stop_existing_bots() {
    log_info "Stopping existing bot processes..."
    local pids
    pids=$(pgrep -f "python.*bot\.py" 2>/dev/null || true)
    
    if [[ -n "$pids" ]]; then
        log_info "Found running bot processes: $pids"
        
        # Send TERM signal
        echo "$pids" | xargs kill -TERM 2>/dev/null || true
        
        # Wait for graceful shutdown
        local count=0
        while [[ $count -lt $GRACEFUL_SHUTDOWN_TIMEOUT ]]; do
            pids=$(pgrep -f "python.*bot\.py" 2>/dev/null || true)
            if [[ -z "$pids" ]]; then
                log_info "All bot processes stopped gracefully"
                return 0
            fi
            sleep 1
            ((count++))
        done
        
        # Force kill if still running
        pids=$(pgrep -f "python.*bot\.py" 2>/dev/null || true)
        if [[ -n "$pids" ]]; then
            log_warn "Force killing processes: $pids"
            echo "$pids" | xargs kill -KILL 2>/dev/null || true
            sleep 1
        fi
    else
        log_info "No existing bot processes found"
    fi
}

# Health check function
health_check() {
    local pid=$1
    local count=0
    
    log_info "Performing health check for PID $pid..."
    
    while [[ $count -lt $HEALTH_CHECK_TIMEOUT ]]; do
        if ! kill -0 "$pid" 2>/dev/null; then
            log_error "Bot process died during startup"
            return 1
        fi
        
        # Check if bot is responding (you can add more sophisticated checks here)
        if [[ -f "logs/bot.log" ]]; then
            if grep -q "Starting bot polling" "logs/bot.log" 2>/dev/null; then
                log_info "Bot health check passed"
                return 0
            fi
        fi
        
        sleep 1
        ((count++))
    done
    
    log_warn "Health check timeout, but process is still running"
    return 0
}

# Main execution
main() {
    log_info "Starting bot restart process..."
    
    # Stop existing processes
    stop_existing_bots
    
    # Create logs directory
    mkdir -p logs
    
    # Backup previous log
    if [[ -f "logs/bot.log" ]]; then
        mv "logs/bot.log" "logs/bot.log.$(date +%Y%m%d_%H%M%S).bak" 2>/dev/null || true
    fi
    
    # Start new bot process with retry logic
    local retry_count=0
    while [[ $retry_count -lt $MAX_RETRIES ]]; do
        log_info "Starting bot (attempt $((retry_count + 1))/$MAX_RETRIES)..."
        
        # Start bot in background
        nohup "$PYTHON_CMD" bot.py > logs/bot.log 2>&1 &
        local bot_pid=$!
        
        log_info "Bot started with PID: $bot_pid"
        
        # Perform health check
        if health_check "$bot_pid"; then
            log_info "Bot is running successfully"
            log_info "Logs: tail -f logs/bot.log"
            log_info "Stop bot: kill $bot_pid"
            return 0
        else
            log_error "Bot failed health check on attempt $((retry_count + 1))"
            kill "$bot_pid" 2>/dev/null || true
            ((retry_count++))
            
            if [[ $retry_count -lt $MAX_RETRIES ]]; then
                log_info "Retrying in 5 seconds..."
                sleep 5
            fi
        fi
    done
    
    log_error "Failed to start bot after $MAX_RETRIES attempts"
    log_error "Check logs/bot.log for details"
    exit 1
}

# Run main function
main "$@"
