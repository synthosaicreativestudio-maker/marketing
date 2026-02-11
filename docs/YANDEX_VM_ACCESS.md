# Доступ к ВМ Yandex Cloud — сводка по проекту

## Общие параметры

| Параметр | Значение | Примечание |
|----------|----------|------------|
| **Пользователь** | `marketing` | Везде одинаково |
| **Каталог на ВМ** | `/home/marketing/marketingbot` | |
| **Сервисы systemd** | `marketingbot-bot.service`, `marketingbot-web.service` | |
| **Виртуальное окружение** | `/home/marketing/marketingbot/.venv` | |

---

## IP-адрес ВМ

**89.169.176.108** — актуальный IP из Yandex Cloud Console (Подключиться с помощью SSH-клиента). Все скрипты и документация приведены к нему. Задаётся в `scripts/yandex_vm_config.sh` (переменная `YANDEX_VM_IP` для переопределения).

---

## SSH-ключ

Путь: `$HOME/.ssh/ssh-key-1770366966512/ssh-key-1770366966512` (папка + файл при скачивании из Yandex Cloud). Задаётся в `yandex_vm_config.sh`. Переопределение: `SSH_KEY_PATH`.

---

## Скрипты с доступом к ВМ (локальный SSH)

Все используют `scripts/yandex_vm_config.sh` (89.169.176.108, marketing, SSH_KEY).

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
| `scripts/update_yandex_server.sh` | **На ВМ** (после `ssh` в `marketing@...`) | `cd /home/marketing/marketingbot`, git pull, проверка WEB_APP_URL, restart bot+web |

Не использует VM_HOST/SSH_KEY — рассчитан на запуск уже на сервере.

---

## Документация и примеры

- **README.md** — `ssh marketing@89.169.176.108 "journalctl -u marketingbot-bot.service -f"` (при необходимости добавьте `-i` и путь к ключу).
- **docs/DEVELOPMENT_RULES.md** — примеры с `-i ~/.ssh/ssh-key-1770366966512/ssh-key-1770366966512` и `89.169.176.108`.
- **GOOGLE_APPS_SCRIPT_FULL.js**, **docs/archive/guides/UPDATE_GOOGLE_APPS_SCRIPT_WEBHOOK.md** — webhook `http://89.169.176.108:8080/webhook/promotions`.
- **setup_yandex_systemd.sh** — в шаблоне `.env` на ВМ: `WEB_APP_URL=http://89.169.176.108/`.

---

## Обход блокировок Gemini (Вариант Б)

Чтобы ИИ работал с Yandex VM (Россия), запросы к Gemini идут через американский сервер. Настройка — **только для Gemini**, без глобального прокси: [GEMINI_PROXY_AMERICAN_SERVER.md](GEMINI_PROXY_AMERICAN_SERVER.md).

---

## Единый источник настроек

**`scripts/yandex_vm_config.sh`** задаёт: `VM_USER`, `VM_HOST`, `SSH_KEY`, `REMOTE_DIR`. Его подключают все скрипты из таблицы выше.

Подключение: `source "$(dirname "$0")/yandex_vm_config.sh"`

Переопределение без правки файла:
- **YANDEX_VM_IP** — IP ВМ (по умолчанию: 89.169.176.108)
- **SSH_KEY_PATH** — путь к приватному ключу

