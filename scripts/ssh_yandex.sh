#!/usr/bin/env bash

# Удобное подключение к ВМ Yandex Cloud
# Хост и ключ: scripts/yandex_vm_config.sh (YANDEX_VM_IP, SSH_KEY_PATH)

source "$(dirname "$0")/yandex_vm_config.sh"
ssh -i "$SSH_KEY" "${VM_USER}@${VM_HOST}"

