#!/usr/bin/env bash
# Stops all running bot.py processes and starts a single new one, logging to logs/bot.log
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/.."
LOG_DIR="${PROJECT_ROOT}/logs"
LOG_FILE="${LOG_DIR}/bot.log"
PYTHON=python3

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

# Start new bot in background
cd "${PROJECT_ROOT}"
nohup ${PYTHON} bot.py >> "${LOG_FILE}" 2>&1 &
NEW_PID=$!
sleep 1
echo "Started new bot pid=${NEW_PID}" | tee -a "${LOG_FILE}"

exit 0
