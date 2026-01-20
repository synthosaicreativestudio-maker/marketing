# Доступ к ВМ Yandex Cloud — сводка по проекту

## Общие параметры

| Параметр | Значение | Примечание |
|----------|----------|------------|
| **Пользователь** | `ubuntu` | Везде одинаково |
| **Каталог на ВМ** | `/home/ubuntu/marketingbot` | |
| **Сервисы systemd** | `marketingbot-bot.service`, `marketingbot-web.service` | |
| **Виртуальное окружение** | `/home/ubuntu/marketingbot/.venv` | |

---

## IP-адрес ВМ

**84.252.137.116** — актуальный IP из Yandex Cloud Console (Подключиться с помощью SSH-клиента). Все скрипты и документация приведены к нему. Задаётся в `scripts/yandex_vm_config.sh` (переменная `YANDEX_VM_IP` для переопределения).

---

## SSH-ключ

Путь: `$HOME/.ssh/ssh-key-1767684261599/ssh-key-1767684261599` (папка + файл при скачивании из Yandex Cloud). Задаётся в `yandex_vm_config.sh`. Переопределение: `SSH_KEY_PATH`.

---

## Скрипты с доступом к ВМ (локальный SSH)

Все используют `scripts/yandex_vm_config.sh` (84.252.137.116, ubuntu, SSH_KEY).

| Скрипт | Назначение |
|--------|------------|
| `update_server_from_local.sh` | git reset --hard origin/main на ВМ + перезапуск bot + web |
| `ssh_yandex.sh` | Интерактивный SSH |
| `deploy_yandex.sh` | Первый деплой: clone/pull, venv, pip install |
| `deploy_and_test.sh` | Пуш в git + pull на ВМ + restart bot |
| `check_server_version.sh` | Сравнение коммитов локально/на ВМ, статус |
| `check_bot_status.sh` | Статус бота на ВМ |
| `check_vm_sleep_policy.sh` | Крон, таймеры, uptime, питание |
| `long_term_stability_test.sh` | Долгий тест, память, рестарты |
| `monitor_bot_health.sh` | Мониторинг статуса, логов, процессов |
| `setup_yandex_systemd.sh` | Создание systemd-units (bot + web) |
| `start_yandex_services.sh` | start + status + journalctl |
| `install_cloudflare_tunnel.sh` | Установка cloudflared |
| `setup_cloudflare_tunnel.sh` | Настройка туннеля |
| `setup_cloudflare_tunnel_simple.sh` | Упрощённая настройка туннеля |

---

## Скрипт, который выполняется на самой ВМ

| Скрипт | Где запускать | Назначение |
|--------|----------------|------------|
| `scripts/update_yandex_server.sh` | **На ВМ** (после `ssh` в `ubuntu@...`) | `cd /home/ubuntu/marketingbot`, git pull, проверка WEB_APP_URL, restart bot+web |

Не использует VM_HOST/SSH_KEY — рассчитан на запуск уже на сервере.

---

## Документация и примеры

- **README.md** — `ssh ubuntu@84.252.137.116 "journalctl -u marketingbot-bot.service -f"` (при необходимости добавьте `-i` и путь к ключу).
- **docs/DEVELOPMENT_RULES.md** — примеры с `-i ~/.ssh/ssh-key-1767684261599/ssh-key-1767684261599` и `84.252.137.116`.
- **GOOGLE_APPS_SCRIPT_FULL.js**, **docs/archive/guides/UPDATE_GOOGLE_APPS_SCRIPT_WEBHOOK.md** — webhook `http://84.252.137.116:8080/webhook/promotions`.
- **setup_yandex_systemd.sh** — в шаблоне `.env` на ВМ: `WEB_APP_URL=http://84.252.137.116/`.

---

## Единый источник настроек

**`scripts/yandex_vm_config.sh`** задаёт: `VM_USER`, `VM_HOST`, `SSH_KEY`, `REMOTE_DIR`. Его подключают все скрипты из таблицы выше.

Подключение: `source "$(dirname "$0")/yandex_vm_config.sh"`

Переопределение без правки файла:
- **YANDEX_VM_IP** — IP ВМ (по умолчанию: 84.252.137.116)
- **SSH_KEY_PATH** — путь к приватному ключу
