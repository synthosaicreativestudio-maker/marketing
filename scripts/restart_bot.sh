#!/usr/bin/env bash
# Stops all running bot.py processes and starts a single new one, logging to logs/bot.log
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/.."
LOG_DIR="${PROJECT_ROOT}/logs"
LOG_FILE="${LOG_DIR}/bot.log"
# Prefer project virtualenv python if present (try .venv312 then .venv), fall back to system python3
if [ -x "${PROJECT_ROOT}/.venv312/bin/python" ]; then
  PYTHON="${PROJECT_ROOT}/.venv312/bin/python"
elif [ -x "${PROJECT_ROOT}/.venv/bin/python" ]; then
  PYTHON="${PROJECT_ROOT}/.venv/bin/python"
else
  PYTHON=python3
fi

mkdir -p "${LOG_DIR}"

# Find processes running bot.py (exclude this script)
PIDS=$(pgrep -f "bot.py" || true)
if [ -n "${PIDS}" ]; then
  echo "Found running bot processes: ${PIDS}" | tee -a "${LOG_FILE}"
  echo "Stopping..." | tee -a "${LOG_FILE}"
  # Kill gracefully
  kill ${PIDS} || true
  sleep 2
  # Force kill if still running
  PIDS_REMAIN=$(pgrep -f "bot.py" || true)
  if [ -n "${PIDS_REMAIN}" ]; then
    echo "Force killing: ${PIDS_REMAIN}" | tee -a "${LOG_FILE}"
    kill -9 ${PIDS_REMAIN} || true
  fi
else
  echo "No running bot processes found." | tee -a "${LOG_FILE}"
fi

# Load environment from .env if present (safe export)
if [ -f "${PROJECT_ROOT}/.env" ]; then
  echo "Loading environment from .env" | tee -a "${LOG_FILE}"
  # Export all variables defined in .env (ignore lines starting with #)
  set -a
  # shellcheck disable=SC1090
  source "${PROJECT_ROOT}/.env" || echo "Warning: failed to source .env" | tee -a "${LOG_FILE}"
  set +a
else
  echo ".env not found, relying on current environment" | tee -a "${LOG_FILE}"
fi

# Optionally validate required vars
if [ -z "${TELEGRAM_TOKEN}" ]; then
  echo "ERROR: TELEGRAM_TOKEN is not set in environment" | tee -a "${LOG_FILE}"
  # Continue starting anyway so logs capture the bot's own error if any
fi

# Start new bot in background
cd "${PROJECT_ROOT}"
nohup ${PYTHON} bot.py >> "${LOG_FILE}" 2>&1 &
NEW_PID=$!
sleep 1
echo "Started new bot pid=${NEW_PID}" | tee -a "${LOG_FILE}"

exit 0
