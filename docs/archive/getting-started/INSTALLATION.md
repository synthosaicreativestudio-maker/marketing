# Установка и настройка MarketingBot

Полная инструкция по установке и настройке MarketingBot на вашей системе.

## Требования

- Python 3.10 или выше
- Git
- Аккаунт Telegram (для создания бота)
- Google Cloud аккаунт (для работы с Google Sheets)
- (Опционально) OpenAI API ключ (для ИИ-ассистента)

## Быстрая установка

### 1. Клонирование репозитория

```bash
git clone https://github.com/synthosaicreativestudio-maker/marketing.git
cd marketing
```

### 2. Создание виртуального окружения

```bash
# Создание окружения
python3 -m venv .venv

# Активация (Linux/Mac)
source .venv/bin/activate

# Активация (Windows)
.venv\Scripts\activate
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Настройка переменных окружения

```bash
# Копирование примера конфигурации
cp .env.example .env

# Редактирование .env файла
nano .env  # или используйте любой текстовый редактор
```

### 5. Обязательные переменные

Минимальный набор переменных для работы бота:

```bash
# Telegram
TELEGRAM_TOKEN=your_bot_token
ADMIN_TELEGRAM_ID=your_admin_id

# WebApp URL (GitHub Pages или другой HTTPS URL)
WEB_APP_URL=https://your-username.github.io/marketing/

# Google Sheets
SHEET_ID=your_google_sheet_id
GCP_SA_JSON='{"type": "service_account", ...}'  # или GCP_SA_FILE=/path/to/file.json

# OpenAI (опционально, для ИИ-ассистента)
OPENAI_API_KEY=your_openai_key
```

### 6. Запуск бота

```bash
python bot.py
```

## Подробная настройка

### Настройка Telegram бота

1. Создайте бота через [@BotFather](https://t.me/BotFather)
2. Получите токен бота
3. Добавьте токен в `.env` как `TELEGRAM_TOKEN`
4. Получите ваш Telegram ID (через [@userinfobot](https://t.me/userinfobot))
5. Добавьте ID в `.env` как `ADMIN_TELEGRAM_ID`

### Настройка Google Sheets

1. Создайте проект в [Google Cloud Console](https://console.cloud.google.com)
2. Включите Google Sheets API
3. Создайте Service Account
4. Скачайте JSON ключ
5. Добавьте ключ в `.env` как `GCP_SA_JSON` или укажите путь в `GCP_SA_FILE`
6. Поделитесь Google Sheet с email из Service Account

См. [Настройка Google Sheets](../guides/GOOGLE_SHEETS.md) для подробностей.

### Настройка WebApp

1. Разместите `index.html` и `menu.html` на HTTPS сервере (например, GitHub Pages)
2. Укажите URL в `.env` как `WEB_APP_URL`
3. Убедитесь, что URL заканчивается на `/`

### Настройка ИИ-ассистента (опционально)

1. Получите API ключ на [OpenAI](https://platform.openai.com)
2. Добавьте ключ в `.env` как `OPENAI_API_KEY`

## Проверка установки

После настройки проверьте:

1. **Бот запускается:**
   ```bash
   python bot.py
   ```
   Должны увидеть сообщение "Бот запущен"

2. **WebApp доступен:**
   Откройте `WEB_APP_URL` в браузере

3. **Google Sheets подключен:**
   Бот должен успешно читать данные из таблицы

## Следующие шаги

- [Быстрая настройка Google Apps Script для акций](QUICK_START_GOOGLE_APPS_SCRIPT.md)
- [Быстрая настройка Cloudflare Tunnel](QUICK_START_CLOUDFLARE.md)
- [Развертывание на сервере](../deployment/DEPLOYMENT_YANDEX.md)

## Решение проблем

Если возникли проблемы при установке, см.:
- [Общее руководство по устранению неполадок](../troubleshooting/TROUBLESHOOTING.md)
- [Проблемы при развертывании](../troubleshooting/DEPLOYMENT_ISSUES.md)
