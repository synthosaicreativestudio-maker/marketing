#!/usr/bin/env bash

# Деплой проекта MarketingBot на ВМ Yandex Cloud.
# Скрипт запускается ЛОКАЛЬНО, подключается к серверу по SSH и
# клонирует/обновляет репозиторий в /home/ubuntu/marketingbot.

set -e

VM_USER="ubuntu"
VM_HOST="84.252.137.116"
SSH_KEY="${SSH_KEY_PATH:-$HOME/.ssh/ssh-key-1767684261599}"
REMOTE_DIR="/home/ubuntu/marketingbot"
REPO_URL="https://github.com/synthosaicreativestudio-maker/marketing.git"

echo "==> Подключаюсь к ${VM_USER}@${VM_HOST} и размещаю/обновляю проект в ${REMOTE_DIR}"

ssh -i "$SSH_KEY" "${VM_USER}@${VM_HOST}" bash <<EOF
set -e

echo "==> Проверяю наличие git и Python"
sudo apt-get update -y
sudo apt-get install -y git python3 python3-venv python3-pip

echo "==> Размещаю репозиторий"
if [ ! -d "${REMOTE_DIR}" ]; then
  git clone "${REPO_URL}" "${REMOTE_DIR}"
else
  cd "${REMOTE_DIR}"
  git pull origin main
fi

cd "${REMOTE_DIR}"

echo "==> Создаю/обновляю виртуальное окружение"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
. .venv/bin/activate

echo "==> Устанавливаю зависимости"
pip install --upgrade pip
pip install -r requirements.txt

echo "==> Деплой кода завершен. Не забудьте настроить .env и systemd/nginx для запуска бота и вебхука."
EOF

echo "==> Готово. Проект размещен/обновлен на ВМ."

