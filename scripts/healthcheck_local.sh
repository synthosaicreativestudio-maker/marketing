#!/usr/bin/env bash
set -euo pipefail

SERVICE="marketingbot-bot.service"

STATUS=$(systemctl is-active "$SERVICE" || true)
if [ "$STATUS" != "active" ]; then
  echo "CRITICAL: $SERVICE not active: $STATUS"
  exit 1
fi

ERRORS=$(journalctl -u "$SERVICE" --since "10 minutes ago" --no-pager | grep -E "(CRITICAL|ERROR|401 Unauthorized|409 Conflict)" | wc -l)
if [ "$ERRORS" -gt 0 ]; then
  echo "WARN: recent errors: $ERRORS"
  exit 1
fi

echo "OK: $SERVICE healthy"
