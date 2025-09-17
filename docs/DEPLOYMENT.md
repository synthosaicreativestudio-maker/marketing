# 🚀 Развертывание MarketingBot

## 🐳 Docker развертывание (рекомендуемый способ)

### Быстрый запуск с Docker Compose:
```bash
# 1. Настройка переменных окружения
cp .env.example .env
nano .env  # Заполните TELEGRAM_BOT_TOKEN и другие переменные

# 2. Запуск бота
docker-compose up -d

# 3. Просмотр логов
docker-compose logs -f marketingbot

# 4. Остановка
docker-compose down
# Сборка образа
> NOTE: Containerized deployment is optional for this project. The preferred simple workflow is documented in `README.md` under "Run without Docker". If you still need container instructions (legacy), keep a local copy or consult the Docker section in the repository history.

For cloud deployments (Cloud Run, etc.) you can package the app as a container; see `README.md` for guidance and examples.
  marketingbot

# Просмотр логов
docker logs -f marketingbot
```

## 🖥️ Локальное развертывание

### Прямой запуск:
```bash
# 1. Установка зависимостей
pip install requests python-dotenv gspread google-auth

# 2. Настройка окружения
cp .env.example .env
nano .env

# 3. Запуск бота
python3 bot.py
```

### С виртуальным окружением:
```bash
# 1. Создание окружения
python3 -m venv .venv
source .venv/bin/activate

# 2. Установка зависимостей
pip install -e .

# 3. Запуск
python3 bot.py
```

## ☁️ Cloud развертывание

### Google Cloud Run:
```bash
# 1. Сборка и отправка образа
gcloud builds submit --tag gcr.io/PROJECT_ID/marketingbot

# 2. Развертывание сервиса
gcloud run deploy marketingbot \
  --image gcr.io/PROJECT_ID/marketingbot \
  --platform managed \
  --region us-central1 \
  --set-env-vars TELEGRAM_BOT_TOKEN=your-token \
  --set-env-vars WEBAPP_URL=https://your-service-url/webapp \
  --no-allow-unauthenticated
```

### Переменные окружения для Cloud Run:
- `TELEGRAM_BOT_TOKEN` — токен бота от @BotFather
- `WEBAPP_URL` — URL веб-приложения
- `SHEET_ID` — ID Google Sheets документа (опционально)
- `GCP_SA_JSON` — JSON service account (опционально)

## 🔧 Настройка production окружения

### Обязательные переменные:
```env
TELEGRAM_BOT_TOKEN=your-bot-token
WEBAPP_URL=https://your-domain.com/webapp
```

### Опциональные переменные:
```env
# Google Sheets интеграция
SHEET_ID=your-sheets-id
SHEET_NAME=Sheet1
GCP_SA_JSON='{"type":"service_account",...}'

# Логирование
LOG_LEVEL=INFO
```

### Безопасность:
1. **Никогда не коммитьте** `.env` файлы
2. **Используйте секреты** в cloud провайдерах
3. **Ограничьте доступ** к service account
4. **Регулярно ротируйте** токены и ключи

## 🔍 Проверка развертывания

### Проверка работы бота:
1. Отправьте `/start` боту в Telegram
2. Проверьте появление кнопки "Авторизоваться"
3. Протестируйте веб-приложение
4. Проверьте логи на ошибки

### Мониторинг:
```bash
# Docker логи
docker logs -f marketingbot

# Системные ресурсы
docker stats marketingbot

# Проверка процесса
pgrep -f "python.*bot.py"
```

## 🚨 Устранение проблем

### Частые проблемы:
1. **Бот не отвечает** - проверьте токен и сетевое подключение
2. **Ошибки WebApp** - проверьте WEBAPP_URL
3. **Проблемы с Google Sheets** - проверьте GCP_SA_JSON и права доступа
4. **Контейнер не запускается** - проверьте переменные окружения

### Отладка:
```bash
# Проверка конфигурации
python3 -c "from dotenv import load_dotenv; import os; load_dotenv(); print('Token:', 'OK' if os.getenv('TELEGRAM_BOT_TOKEN') else 'MISSING')"

# Тест импортов
python3 -c "import bot, sheets; print('Imports OK')"

# Проверка Docker
docker run --rm --env-file .env marketingbot python3 -c "print('Docker OK')"
```

## 📋 Чек-лист развертывания

**Перед развертыванием:**
- [ ] Токен бота получен от @BotFather
- [ ] `.env` файл настроен
- [ ] WebApp URL корректный
- [ ] Google Sheets настроены (если используются)
- [ ] Docker образ собирается без ошибок

**После развертывания:**
- [ ] Бот отвечает на `/start`
- [ ] WebApp открывается и работает
- [ ] Авторизация проходит успешно
- [ ] Логи не содержат ошибок
- [ ] Мониторинг настроен
