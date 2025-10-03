# 🚀 Установка и развертывание MarketingBot

В этом документе описаны все шаги — от локальной установки для разработки до развертывания на сервере.

## 🖥️ Локальная установка

Этот способ подходит для быстрой проверки и разработки.

### 1. Клонирование репозитория
```bash
git clone <repository-url>
cd marketingbot
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
# Установка через pip
pip install -r requirements.txt
```

### 4. Настройка переменных окружения
```bash
# Копирование примера конфигурации
cp .env.example .env

# Редактирование .env файла
# Укажите как минимум TELEGRAM_TOKEN
nano .env
```

**Обязательные переменные для v3.1:**
```bash
# Telegram
TELEGRAM_TOKEN=your_bot_token
ADMIN_TELEGRAM_ID=your_admin_id

# OpenAI (для ИИ-ассистента)
OPENAI_API_KEY=your_openai_key
OPENAI_ASSISTANT_ID=your_assistant_id

# Google Sheets (для авторизации и обращений)
SHEET_ID=authorization_sheet_id
APPEALS_SHEET_ID=appeals_sheet_id
SHEET_NAME=authorization_sheet_name
APPEALS_SHEET_NAME=обращения
GCP_SA_FILE=path_to_credentials.json

# WebApp (для авторизации и меню)
WEB_APP_URL=https://your-domain.com/
```

### 5. Настройка Google Sheets

**Создание таблицы авторизации:**
1. Создайте Google Sheet с колонками: A (Код партнера), B (Телефон), C (ФИО), D (Telegram ID), E (Статус авторизации), F (Дата авторизации)
2. Скопируйте ID таблицы в `SHEET_ID`

**Создание таблицы обращений:**
1. Создайте Google Sheet с колонками: A (Код партнера), B (Телефон), C (ФИО), D (Telegram ID), E (Текст обращений), F (Статус), G (Ответ специалиста), H (Время обновления)
2. Скопируйте ID таблицы в `APPEALS_SHEET_ID`

**Настройка Service Account:**
1. Создайте Service Account в Google Cloud Console
2. Скачайте JSON ключ и укажите путь в `GCP_SA_FILE`
3. Предоставьте доступ к таблицам для email из JSON ключа

### 6. Настройка OpenAI Assistant

**Создание ассистента:**
1. Перейдите в OpenAI Playground
2. Создайте нового ассистента с инструкциями для маркетингового бота
3. Скопируйте ID ассистента в `OPENAI_ASSISTANT_ID`

### 7. Настройка WebApp

**Создание файлов WebApp:**
```bash
# Проверьте наличие файлов
ls -la index.html menu.html app.js

# Настройте URL в .env
WEB_APP_URL=https://your-domain.com/
```

### 8. Запуск бота
```bash
# Простой запуск
python3 bot.py

# Запуск с логированием
python3 bot.py 2>&1 | tee bot.log

# Запуск в фоне
nohup python3 bot.py > bot.log 2>&1 &
```

## 🐳 Docker развертывание (для Production)

Docker — рекомендуемый способ для стабильной работы на сервере.

### 1. Настройка
```bash
# Убедитесь, что у вас настроен .env файл
cp .env.example .env
nano .env
```

### 2. Запуск с Docker Compose
```bash
# Запуск в фоновом режиме
docker-compose up -d

# Просмотр логов
docker-compose logs -f

# Остановка
docker-compose down
```

## ☁️ Развертывание в облаке (Пример для Google Cloud Run)

### 1. Сборка и отправка образа
```bash
gcloud builds submit --tag gcr.io/PROJECT_ID/marketingbot
```

### 2. Развертывание сервиса
```bash
gcloud run deploy marketingbot \
  --image gcr.io/PROJECT_ID/marketingbot \
  --platform managed \
  --region us-central1 \
  --set-env-vars TELEGRAM_TOKEN=your-token \
  --no-allow-unauthenticated
```

## 🚨 Устранение проблем

### Ошибка импорта `gspread` или `dotenv`:
Убедитесь, что вы активировали виртуальное окружение и выполнили `pip install -r requirements.txt`.

### Бот не отвечает:
1.  Проверьте правильность `TELEGRAM_TOKEN` в `.env`.
2.  Проверьте логи на наличие ошибок.
3.  Убедитесь, что сервер имеет доступ в интернет.

### Ошибки WebApp:
1.  Проверьте, что `WEB_APP_URL` в `.env` указан корректно и доступен.
2.  Убедитесь, что файлы `index.html` и `menu.html` доступны по URL.

### Проблемы с системой обращений:
1. **Статус не обновляется**: Проверьте права доступа Service Account к таблице обращений
2. **Эскалация не работает**: Убедитесь, что функция `_is_user_escalation_request()` работает корректно
3. **Ответы не отправляются**: Проверьте работу ResponseMonitor в логах

### Проблемы с OpenAI:
1. **Ошибки API**: Проверьте правильность `OPENAI_API_KEY` и `OPENAI_ASSISTANT_ID`
2. **Превышение лимитов**: Проверьте баланс аккаунта OpenAI
3. **Медленные ответы**: Это нормально для OpenAI API (2-10 секунд)

### Проблемы с авторизацией:
1. **Кнопка авторизации вместо меню**: Проверьте правильность `WEB_APP_URL` и работу функции `get_spa_menu_url()`
2. **Партнер не найден**: Проверьте данные в таблице авторизации
3. **Ошибки кэширования**: Удалите файл `auth_cache.json` для сброса кэша

## 🔧 Диагностика v3.1

### Проверка всех сервисов:
```bash
# Проверка конфигурации
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()

print('=== Конфигурация MarketingBot v3.1 ===')
print(f'Telegram Token: {\"✓\" if os.getenv(\"TELEGRAM_TOKEN\") else \"✗\"}')
print(f'OpenAI API Key: {\"✓\" if os.getenv(\"OPENAI_API_KEY\") else \"✗\"}')
print(f'OpenAI Assistant ID: {\"✓\" if os.getenv(\"OPENAI_ASSISTANT_ID\") else \"✗\"}')
print(f'Sheets ID: {\"✓\" if os.getenv(\"SHEET_ID\") else \"✗\"}')
print(f'Appeals Sheets ID: {\"✓\" if os.getenv(\"APPEALS_SHEET_ID\") else \"✗\"}')
print(f'WebApp URL: {os.getenv(\"WEB_APP_URL\", \"✗\")}')
print(f'GCP SA File: {\"✓\" if os.getenv(\"GCP_SA_FILE\") else \"✗\"}')
"
```

### Тест новых функций:
```bash
# Тест автоматической эскалации
python3 -c "
from handlers import _is_user_escalation_request
test_phrases = ['а вы мне помочь не можете?', 'нужен специалист', 'привет']
for phrase in test_phrases:
    result = _is_user_escalation_request(phrase)
    print(f'{phrase}: {\"Эскалация\" if result else \"Обычное сообщение\"}')
"

# Тест генерации URL
python3 -c "
from handlers import get_web_app_url, get_spa_menu_url
print(f'Auth URL: {get_web_app_url()}')
print(f'Menu URL: {get_spa_menu_url()}')
"
```

### Мониторинг работы:
```bash
# Просмотр логов в реальном времени
tail -f bot.log | grep -E "(эскалация|статус|заливка|WebApp)"

# Проверка работы ResponseMonitor
grep -i "response_monitor" bot.log | tail -10

# Проверка обновлений статусов
grep -i "статус.*установлен\|статус.*обновлен" bot.log | tail -10
```
