# 🚀 MarketingBot — Профессиональный Telegram-бот
# MarketingBot

> **Stable & Resilient Telegram Bot for Marketing Automation**

This repository contains the source code for the MarketingBot, designed for high availability and integration with Google Sheets and **Google Gemini 3 Pro API**.

## 📚 Documentation

## 📚 Documentation / Документация

**The Single Source of Truth for this project is [TECHNICAL_DOCUMENTATION.md](docs/TECHNICAL_DOCUMENTATION.md).**
**(Русская версия: [TECHNICAL_DOCUMENTATION_RU.md](docs/TECHNICAL_DOCUMENTATION_RU.md))**

Please refer to it for:
- **Gemini 3 Pro** (вместо OpenAI)
- **Дедупликация уведомлений** (SENT-флаг)
- **Гибридный Медиа-Хэндлер** (Base64, Google Drive, URL)

### Additional Resources
- **TODO / Тех. Долг:** [docs/TODO.md](docs/TODO.md) ([RU](docs/TODO_RU.md))
- **IDEAS / Идеи:** [docs/IDEAS.md](docs/IDEAS.md) ([RU](docs/IDEAS_RU.md))
- **Обход блокировок Gemini (Вариант Б):** [docs/GEMINI_PROXY_AMERICAN_SERVER.md](docs/GEMINI_PROXY_AMERICAN_SERVER.md) — только Gemini через американский сервер; Telegram и Google Sheets — напрямую.

## 📂 Project Structure

- **`docs/TECHNICAL_DOCUMENTATION.md`** - Main technical reference (EN).
- **`docs/TECHNICAL_DOCUMENTATION_RU.md`** - Main technical reference (RU).
- **`bot.py`** - Application entry point.
- **`handlers.py`** - Telegram update handlers.
- **`docs/CHANGELOG.md`** - Version history.
- **`docs/archive/`** - Archived documentation.

## 🚀 Quick Start

> **⚠️ ВАЖНО: ЗАПРЕЩЕН ЛОКАЛЬНЫЙ ЗАПУСК БОТА!**
> 
> Telegram API не позволяет двум ботам с одним токеном работать одновременно.
> **Бот должен работать ТОЛЬКО на сервере!**
> 
> **Для разработки и тестирования читайте:** [DEVELOPMENT_RULES.md](docs/DEVELOPMENT_RULES.md)

```bash
# ❌ ЗАПРЕЩЕНО запускать локально:
# python bot.py

# ✅ ПРАВИЛЬНО - Deploy на сервер:
./scripts/deploy_and_test.sh
```
├── 🎯 handlers.py             # Обработчики команд и сообщений
├── 🔐 auth_service.py         # Сервис авторизации
├── 📊 sheets_gateway.py       # Async Google Sheets Gateway (Retry + Circuit Breaker)
├── 🤖 ai_service.py           # Унифицированный сервис ИИ
├── 🤖 gemini_service.py       # Интеграция с Google Gemini 3 Pro
├── 🤖 appeals_service.py       # Сервис обращений
├── 📊 response_monitor.py     # Мониторинг ответов специалистов
├── 📊 promotions_notifier.py  # Рассылка акций с дедупликацией
├── 📊 promotions_api.py        # API для работы с таблицей акций
├── 🌐 index.html              # WebApp авторизации
├── 🌐 menu.html               # WebApp личного кабинета
├── 🌐 app.js                  # JavaScript для WebApp
├── 📚 docs/                   # Документация (структурированная)
│   ├── getting-started/       # Быстрый старт
│   ├── deployment/            # Развертывание
│   ├── guides/                # Руководства
│   ├── troubleshooting/       # Решение проблем
│   └── reference/             # Справочники
├── 🔧 scripts/                # Вспомогательные скрипты
├── 🔄 .github/workflows/      # GitHub Actions
├── requirements.txt            # Зависимости Python
├── .env.example               # Пример переменных окружения
└── README.md                  # Этот файл
```

## 🚀 Быстрый старт

> **⚠️ КРИТИЧЕСКОЕ ПРАВИЛО:** Бот запускается **ТОЛЬКО на сервере Yandex Cloud**!
> 
> Локальный запуск `python bot.py` **ЗАПРЕЩЕН** - это вызовет конфликт с серверной версией!

### Для разработчиков:

1.  **Установите зависимости:**
    ```bash
    pip install -r requirements.txt
    ```

2. **Настройте `.env`:**
    ```bash
    cp .env.example .env
    # Укажите ваш TELEGRAM_TOKEN
    nano .env
    ```

3.  **Деплой на сервер:**
    ```bash
    ./scripts/deploy_and_test.sh
    ```
    
    Этот скрипт:
    - Проверит отсутствие локальных процессов бота
    - Запушит изменения в GitHub
    - Задеплоит на сервер Yandex Cloud
    - Перезапустит бота
    - Покажет статус

4.  **Тестирование:**
    - Отправьте сообщение боту в Telegram
    - Проверьте логи: `ssh marketing@89.169.176.108 "journalctl -u marketingbot-bot.service -f"`

**📚 Подробные правила:** [docs/DEVELOPMENT_RULES.md](docs/DEVELOPMENT_RULES.md)

## 📚 Документация

Вся подробная документация находится в папке [`docs`](./docs/). Начните с [README документации](./docs/README.md) для навигации.

### Быстрый доступ

- **[⚠️ Правила разработки](./docs/DEVELOPMENT_RULES.md)** - КРИТИЧЕСКИ ВАЖНО: запрет локального запуска
- **[🚀 Быстрый старт](./docs/getting-started/INSTALLATION.md)** - Установка и настройка
- **[🏗️ Архитектура](./docs/ARCHITECTURE.md)** - Описание компонентов и потоков данных
- **[🚢 Развертывание](./docs/deployment/DEPLOYMENT_YANDEX.md)** - Инструкции по развертыванию
- **[🐛 Решение проблем](./docs/troubleshooting/TROUBLESHOOTING.md)** - Устранение неполадок
- **[📡 API Справочник](./docs/reference/API_REFERENCE.md)** - Документация REST API
- **[📝 История изменений](./docs/CHANGELOG.md)** - Лог всех версий и изменений

### 🧰 Dev-tools

В каталоге `docs/tools/` находятся вспомогательные утилиты и скрипты для отладки:

- `debug_telegram_auth.js` — симуляция отправки данных WebApp
- `telegram_webapp_debug.py` — пошаговая диагностика потока Mini App → бот
- `fetch_sheets.py` — безопасное чтение и сводка Google Sheets (read-only)

Эти файлы не участвуют в работе продакшен-бота, а используются только локально при разработке.

### 🛠️ Изменения для авторизации через Mini App

- **Исправлена логика авторизации**: Теперь Mini App запускается через `KeyboardButton` для корректной работы метода `Telegram.WebApp.sendData()`.
- **Добавлена обработка данных**: Бот обрабатывает данные, отправленные Mini App, и обновляет статус сотрудника в Google Sheets.
- **Улучшена безопасность**: Реализована валидация `initData` для проверки подлинности данных.

### 🚀 Инструкции по обновлению

1. **Обновите бота**:
    - Убедитесь, что в коде используется `KeyboardButton` для запуска Mini App.
    - Проверьте, что обработчик `web_app_data` настроен корректно.

2. **Проверьте WebApp**:
    - Убедитесь, что Mini App размещен на HTTPS (например, GitHub Pages).
    - Проверьте работу Mini App на мобильных устройствах.

3. **Обновите Google Sheets**:
    - Убедитесь, что таблица содержит актуальные данные сотрудников.
    - Проверьте, что бот корректно обновляет статус авторизации.
