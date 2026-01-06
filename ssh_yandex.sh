#!/usr/bin/env bash

# Удобное подключение к ВМ Yandex Cloud
# Перед запуском убедитесь, что приватный ключ лежит по пути ~/.ssh/ssh-key-1767684261599

VM_USER="ubuntu"
VM_HOST="158.160.0.127"
SSH_KEY="${SSH_KEY_PATH:-$HOME/.ssh/ssh-key-1767684261599}"

ssh -i "$SSH_KEY" "${VM_USER}@${VM_HOST}"

