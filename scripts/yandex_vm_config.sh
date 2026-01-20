#!/usr/bin/env bash
# Единые настройки доступа к ВМ Yandex Cloud.
# Использование: source "$(dirname "$0")/yandex_vm_config.sh"
#
# Актуальный публичный IP смотри в Yandex Cloud Console:
#   Compute Cloud → ВМ → Публичный IPv4

VM_USER="ubuntu"
# IP из Yandex Cloud Console (Подключиться с помощью SSH-клиента). Переопределение: YANDEX_VM_IP.
VM_HOST="${YANDEX_VM_IP:-84.252.137.116}"

# Ключ: папка при скачивании из Yandex — ssh-key-1767684261599, внутри файл ssh-key-1767684261599
SSH_KEY="${SSH_KEY_PATH:-$HOME/.ssh/ssh-key-1767684261599/ssh-key-1767684261599}"

REMOTE_DIR="/home/ubuntu/marketingbot"
