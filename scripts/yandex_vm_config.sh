#!/usr/bin/env bash
# Единые настройки доступа к ВМ Yandex Cloud.
# Использование: source "$(dirname "$0")/yandex_vm_config.sh"
#
# Актуальный публичный IP смотри в Yandex Cloud Console:
#   Compute Cloud → ВМ → Публичный IPv4

# Подхватываем .env из корня репозитория, если он есть.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -f "${ROOT_DIR}/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "${ROOT_DIR}/.env"
  set +a
fi

VM_USER="${YANDEX_VM_USER:-marketing}"
# IP из Yandex Cloud Console (Подключиться с помощью SSH-клиента). Переопределение: YANDEX_VM_IP.
VM_HOST="${YANDEX_VM_IP:-89.169.191.124}"

# Ключ: папка при скачивании из Yandex — ssh-key-1767684261599, внутри файл ssh-key-1767684261599
SSH_KEY="${SSH_KEY_PATH:-$HOME/.ssh/yc_marketing_new}"

REMOTE_DIR="/home/marketing/marketingbot"
