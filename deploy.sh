#!/bin/bash
set -euo pipefail

# ============================================================
# Blue-Green Deploy Script for MarketingBot
# Usage: ./deploy.sh [branch]
# Default branch: main
# ============================================================

BRANCH="${1:-main}"
BASE_DIR="/home/marketing"
RELEASES_DIR="$BASE_DIR/releases"
SHARED_DIR="$BASE_DIR/shared"
CURRENT_LINK="$BASE_DIR/current"
REPO_URL="https://github.com/synthosaicreativestudio-maker/marketing.git"
SERVICE_NAME="marketingbot-bot.service"
MAX_RELEASES=3

# Shared files that will be symlinked into each release
SHARED_FILES=(".env" "credentials.json")
SHARED_DIRS=("logs")
SHARED_RUNTIME=("chat_memory.db" "rag_cache.db" "rag_index.json")

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[DEPLOY]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ============================================================
# Step 0: Pre-flight checks
# ============================================================
log "Pre-flight checks..."
[ -d "$SHARED_DIR" ] || error "Shared directory $SHARED_DIR not found. Run migration first."
[ -f "$SHARED_DIR/.env" ] || error "Shared .env not found. Run migration first."

# ============================================================
# Step 1: Clone repository into new release directory
# ============================================================
SHORT_HASH=$(git ls-remote "$REPO_URL" "refs/heads/$BRANCH" | cut -c1-7)
RELEASE_NAME="$(date +%Y%m%d_%H%M%S)_${SHORT_HASH}"
RELEASE_DIR="$RELEASES_DIR/$RELEASE_NAME"

log "Cloning branch '$BRANCH' into $RELEASE_DIR..."
mkdir -p "$RELEASES_DIR"
git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$RELEASE_DIR"

# ============================================================
# Step 2: Create virtualenv and install dependencies
# ============================================================
log "Creating virtualenv..."
python3 -m venv "$RELEASE_DIR/.venv"

log "Installing dependencies..."
"$RELEASE_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$RELEASE_DIR/.venv/bin/pip" install --quiet -r "$RELEASE_DIR/requirements.txt"

# ============================================================
# Step 3: Symlink shared files
# ============================================================
log "Creating symlinks to shared files..."

for f in "${SHARED_FILES[@]}"; do
    if [ -f "$SHARED_DIR/$f" ]; then
        ln -sf "$SHARED_DIR/$f" "$RELEASE_DIR/$f"
        log "  Linked: $f"
    else
        warn "  Shared file not found: $f (skipping)"
    fi
done

for d in "${SHARED_DIRS[@]}"; do
    mkdir -p "$SHARED_DIR/$d"
    if [ -d "$RELEASE_DIR/$d" ]; then
        rm -rf "$RELEASE_DIR/$d"
    fi
    ln -sf "$SHARED_DIR/$d" "$RELEASE_DIR/$d"
    log "  Linked dir: $d"
done

for f in "${SHARED_RUNTIME[@]}"; do
    if [ -f "$SHARED_DIR/$f" ]; then
        ln -sf "$SHARED_DIR/$f" "$RELEASE_DIR/$f"
        log "  Linked runtime: $f"
    else
        warn "  Runtime file not found: $f (will be created on first run)"
    fi
done

# ============================================================
# Step 4: Smoke test
# ============================================================
log "Running smoke test..."
cd "$RELEASE_DIR"
"$RELEASE_DIR/.venv/bin/python" -c "
import sys
sys.path.insert(0, '.')
# Test critical imports
import importlib
for mod in ['bot', 'gemini_service', 'auth_service', 'knowledge_base']:
    try:
        importlib.import_module(mod)
        print(f'  ✓ {mod}')
    except Exception as e:
        print(f'  ✗ {mod}: {e}')
        sys.exit(1)
print('Smoke test passed!')
" || error "Smoke test failed! Aborting deploy."

# ============================================================
# Step 5: Atomic switch
# ============================================================
log "Switching current -> $RELEASE_NAME..."
ln -sfn "$RELEASE_DIR" "$CURRENT_LINK"

# ============================================================
# Step 6: Restart service
# ============================================================
log "Restarting $SERVICE_NAME..."
sudo systemctl restart "$SERVICE_NAME"
sleep 3

# ============================================================
# Step 7: Verify
# ============================================================
if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
    log "✅ Bot is running!"
    sudo systemctl status "$SERVICE_NAME" --no-pager -l | tail -5
else
    error "❌ Bot failed to start! Rolling back..."
    # Auto-rollback
    PREVIOUS=$(ls -t "$RELEASES_DIR" | sed -n '2p')
    if [ -n "$PREVIOUS" ]; then
        ln -sfn "$RELEASES_DIR/$PREVIOUS" "$CURRENT_LINK"
        sudo systemctl restart "$SERVICE_NAME"
        warn "Rolled back to $PREVIOUS"
    fi
    exit 1
fi

# ============================================================
# Step 8: Cleanup old releases
# ============================================================
log "Cleaning up old releases (keeping last $MAX_RELEASES)..."
cd "$RELEASES_DIR"
ls -dt */ | tail -n +$((MAX_RELEASES + 1)) | while read -r old; do
    log "  Removing: $old"
    rm -rf "$old"
done

log "🎉 Deploy complete: $RELEASE_NAME"
