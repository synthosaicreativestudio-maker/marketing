#!/usr/bin/env bash

# Установка systemd timer для healthcheck каждые 6 часов
# Хост и ключ: scripts/yandex_vm_config.sh

set -e
source "$(dirname "$0")/yandex_vm_config.sh"

ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i "$SSH_KEY" "${VM_USER}@${VM_HOST}" bash <<EOF
set -e
REMOTE_DIR="${REMOTE_DIR}"

sudo tee /etc/systemd/system/marketingbot-healthcheck.service >/dev/null <<SVC
[Unit]
Description=MarketingBot healthcheck

[Service]
Type=oneshot
User=${VM_USER}
WorkingDirectory=${REMOTE_DIR}
ExecStart=${REMOTE_DIR}/scripts/healthcheck_local.sh
SVC

sudo tee /etc/systemd/system/marketingbot-healthcheck.timer >/dev/null <<TMR
[Unit]
Description=Run MarketingBot healthcheck every 6 hours

[Timer]
OnCalendar=*-*-* 00,06,12,18:00:00
Persistent=true

[Install]
WantedBy=timers.target
TMR

sudo systemctl daemon-reload
sudo systemctl enable --now marketingbot-healthcheck.timer
sudo systemctl status marketingbot-healthcheck.timer --no-pager
EOF
