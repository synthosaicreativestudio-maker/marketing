#!/bin/bash
set -euo pipefail

# ============================================================
# Rollback Script for MarketingBot Blue-Green Deploy
# Usage: ./rollback.sh
# ============================================================

BASE_DIR="/home/marketing"
RELEASES_DIR="$BASE_DIR/releases"
CURRENT_LINK="$BASE_DIR/current"
SERVICE_NAME="marketingbot-bot.service"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[ROLLBACK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Get current release name
CURRENT_RELEASE=$(basename "$(readlink -f "$CURRENT_LINK")")
log "Current release: $CURRENT_RELEASE"

# Find previous release
PREVIOUS=$(ls -dt "$RELEASES_DIR"/*/ | awk -F/ '{print $(NF-1)}' | grep -A1 "^$CURRENT_RELEASE$" | tail -1)

if [ "$PREVIOUS" = "$CURRENT_RELEASE" ] || [ -z "$PREVIOUS" ]; then
    # Fallback: just get the second newest release
    PREVIOUS=$(ls -dt "$RELEASES_DIR"/*/ | awk -F/ '{print $(NF-1)}' | sed -n '2p')
fi

[ -z "$PREVIOUS" ] && error "No previous release found to roll back to."

log "Rolling back to: $PREVIOUS"

# Switch symlink
ln -sfn "$RELEASES_DIR/$PREVIOUS" "$CURRENT_LINK"

# Restart service
sudo systemctl restart "$SERVICE_NAME"
sleep 3

# Verify
if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
    log "✅ Rollback successful! Bot is running on $PREVIOUS"
    sudo systemctl status "$SERVICE_NAME" --no-pager -l | tail -3
else
    error "❌ Bot failed to start after rollback!"
fi
