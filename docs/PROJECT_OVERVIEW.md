# 🤖 Marketing Bot

Telegram-бот для маркетинговых задач с системой авторизации сотрудников через Google Sheets и интеграцией с Redis для управления состоянием.

## 🚀 Быстрый старт

### Установка
```bash
git clone https://github.com/your-username/marketing-bot.git
cd marketing-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Настройка
1. Скопируйте `.env.example` в `.env` и заполните переменные
2. Настройте Google Sheets API и сервисный аккаунт
3. Создайте Upstash Redis базу данных
4. Создайте Telegram бота через @BotFather

### Запуск
```bash
python bot.py
```

## 🏗️ Архитектура

Бот построен по модульному принципу с использованием современных технологий:

- **Python 3.8+** - Основной язык программирования
- **python-telegram-bot** - Telegram Bot API
- **Google Sheets API** - База данных сотрудников
- **Upstash Redis** - Управление состоянием
- **Telegram Mini App** - Веб-интерфейс авторизации (размещен в директории `/public`)

## 🌐 Веб-приложение

Веб-приложение для авторизации сотрудников размещено в директории `/public` и автоматически деплоится на GitHub Pages при пуше в ветку main. Настройки деплоя находятся в файле `.github/workflows/deploy.yml`.

## ✅ Текущий статус

**Функционал авторизации полностью реализован:**
- ✅ Обработка команды `/start` и отправка сообщения с кнопкой Mini App
- ✅ Telegram Mini App (`index.html`) для ввода данных сотрудника
- ✅ Логика проверки данных в Google Таблице (`google_sheets_service.py`)
- ✅ Обновление статуса авторизации пользователя в Google Таблице
- ✅ Периодический мониторинг статуса авторизации пользователей (`scheduler_service.py`)
- ✅ Интеграция с Upstash Redis для персистентного хранения
