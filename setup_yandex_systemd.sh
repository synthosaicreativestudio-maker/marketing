#!/usr/bin/env bash

# Настройка systemd-сервисов для MarketingBot на ВМ Yandex Cloud.
# Скрипт создаёт два сервиса:
#  - marketingbot-bot.service      — Telegram-бот (polling), запускает bot.py
#  - marketingbot-web.service      — Flask-приложение webhook_handler.py (API + статика для мини-аппа)
#
# Требования:
#  - проект уже развернут в /home/ubuntu/marketingbot (deploy_yandex.sh)
#  - создан файл /home/ubuntu/marketingbot/.env с нужными переменными

set -e

VM_USER="ubuntu"
VM_HOST="158.160.0.127"
SSH_KEY="${SSH_KEY_PATH:-$HOME/.ssh/ssh-key-1767684261599/ssh-key-1767684261599}"
REMOTE_DIR="/home/ubuntu/marketingbot"

echo "==> Настраиваю systemd-сервисы на ${VM_USER}@${VM_HOST}"

ssh -i "$SSH_KEY" "${VM_USER}@${VM_HOST}" bash <<'EOF'
set -e

REMOTE_DIR="/home/ubuntu/marketingbot"
VENV_DIR="${REMOTE_DIR}/.venv"
PYTHON="${VENV_DIR}/bin/python"

if [ ! -d "${REMOTE_DIR}" ]; then
  echo "❌ Каталог ${REMOTE_DIR} не найден. Сначала выполните deploy_yandex.sh"
  exit 1
fi

if [ ! -d "${VENV_DIR}" ]; then
  echo "❌ Виртуальное окружение ${VENV_DIR} не найдено. Сначала выполните deploy_yandex.sh"
  exit 1
fi

if [ ! -f "${REMOTE_DIR}/.env" ]; then
  echo "⚠️  Файл ${REMOTE_DIR}/.env не найден."
  echo "    Я создам пустой шаблон .env — обязательно заполните его перед запуском сервисов."
  cat > "${REMOTE_DIR}/.env" <<EENV
# Пример .env для MarketingBot
TELEGRAM_TOKEN=ВАШ_TELEGRAM_TOKEN
OPENAI_API_KEY=ВАШ_OPENAI_API_KEY
OPENAI_ASSISTANT_ID=ВАШ_ASSISTANT_ID
GOOGLE_SERVICE_ACCOUNT_JSON=credentials.json
SPREADSHEET_ID=ВАШ_SPREADSHEET_ID
APPEALS_SHEET_NAME=обращения
PROMOTIONS_SHEET_ID=ID_ТАБЛИЦЫ_АКЦИЙ
WEB_APP_URL=http://158.160.0.127/
ADMIN_TELEGRAM_ID=0
WEBHOOK_SECRET=замените_на_случайный_секрет
EENV
fi

echo "==> Создаю systemd unit для бота: /etc/systemd/system/marketingbot-bot.service"
sudo tee /etc/systemd/system/marketingbot-bot.service >/dev/null <<ESVC
[Unit]
Description=MarketingBot Telegram bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=${REMOTE_DIR}
EnvironmentFile=${REMOTE_DIR}/.env
ExecStart=${PYTHON} bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
ESVC

echo "==> Создаю systemd unit для Flask веб-приложения: /etc/systemd/system/marketingbot-web.service"
sudo tee /etc/systemd/system/marketingbot-web.service >/dev/null <<ESVC2
[Unit]
Description=MarketingBot Flask web app (webhook_handler.py)
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=${REMOTE_DIR}
EnvironmentFile=${REMOTE_DIR}/.env
ExecStart=${PYTHON} webhook_handler.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
ESVC2

echo "==> Перечитываю конфигурацию systemd и включаю сервисы в автозапуск (без старта)"
sudo systemctl daemon-reload
sudo systemctl enable marketingbot-bot.service
sudo systemctl enable marketingbot-web.service

echo "==> Готово."
echo "Проверьте и отредактируйте файл ${REMOTE_DIR}/.env, затем запустите сервисы:"
echo "  sudo systemctl start marketingbot-bot.service"
echo "  sudo systemctl start marketingbot-web.service"
echo "И посмотрите статус:"
echo "  sudo systemctl status marketingbot-bot.service"
echo "  sudo systemctl status marketingbot-web.service"
EOF

echo "==> Настройка systemd на ВМ завершена."

