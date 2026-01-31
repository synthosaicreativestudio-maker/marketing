# Скрипты MarketingBot

Эта директория содержит вспомогательные скрипты для развертывания и управления проектом.

## Развертывание на Yandex Cloud

- `deploy_yandex.sh` - Полный деплой проекта на Yandex VM
- `setup_yandex_systemd.sh` - Настройка systemd сервисов
- `start_yandex_services.sh` - Запуск/проверка сервисов
- `update_yandex_server.sh` - Обновление кода на сервере
- `ssh_yandex.sh` - Удобное подключение к серверу

## Развертывание на PythonAnywhere

- `start_bot_pythonanywhere.sh` - Запуск бота
- `update_bot_pythonanywhere.sh` - Обновление бота
- `update_pythonanywhere.sh` - Полное обновление

## Настройка Cloudflare Tunnel

- `install_cloudflare_tunnel.sh` - Установка туннеля
- `setup_cloudflare_tunnel.sh` - Полная настройка
- `setup_cloudflare_tunnel_simple.sh` - Упрощенная настройка

## Утилиты

- `update_gas_url.py` - Обновление URL Google Apps Script в menu.html
- `update_google_apps_script_url.sh` - Обновление URL через shell
- `update_sheet_id.py` - Обновление ID Google Sheet
- `update_env.py` - Обновление переменных окружения

## Использование

Все скрипты должны быть исполняемыми:

```bash
chmod +x scripts/*.sh
```

Запуск:

```bash
./scripts/deploy_yandex.sh
```
