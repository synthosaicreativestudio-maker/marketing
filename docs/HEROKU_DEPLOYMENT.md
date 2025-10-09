# Деплой Telegram бота на Heroku

## 🚀 Быстрый старт

### 1. Подготовка проекта

Убедитесь, что у вас есть все необходимые файлы:
- `Procfile` - указывает Heroku как запускать приложение
- `runtime.txt` - версия Python
- `requirements.txt` - зависимости
- `bot_webhook.py` - версия бота для webhook
- `.env` - переменные окружения (НЕ загружается в Git)

### 2. Создание приложения на Heroku

```bash
# Войдите в Heroku
heroku login

# Создайте приложение
heroku create your-bot-name

# Добавьте переменные окружения
heroku config:set TELEGRAM_TOKEN=your_bot_token
heroku config:set ADMIN_TELEGRAM_ID=your_telegram_id
heroku config:set WEB_APP_URL=https://your-app.herokuapp.com/
heroku config:set WEBHOOK_URL=https://your-app.herokuapp.com/webhook
heroku config:set PROMOTIONS_WEBHOOK_SECRET=your_secret_key
heroku config:set OPENAI_API_KEY=your_openai_key
heroku config:set GOOGLE_SHEETS_CREDENTIALS='{"type": "service_account", ...}'
heroku config:set APPEALS_SHEET_ID=your_appeals_sheet_id
heroku config:set PROMOTIONS_SHEET_ID=your_promotions_sheet_id
heroku config:set AUTH_SHEET_ID=your_auth_sheet_id
```

### 3. Деплой

```bash
# Добавьте Heroku как remote
git remote add heroku https://git.heroku.com/your-bot-name.git

# Деплой
git push heroku main
```

### 4. Настройка webhook

```bash
# Установите webhook
python setup_webhook.py set

# Проверьте статус
python setup_webhook.py info
```

## 📋 Переменные окружения

Обязательные переменные:
- `TELEGRAM_TOKEN` - токен бота от @BotFather
- `ADMIN_TELEGRAM_ID` - ваш Telegram ID
- `WEB_APP_URL` - URL вашего приложения (https://your-app.herokuapp.com/)
- `WEBHOOK_URL` - URL для webhook (https://your-app.herokuapp.com/webhook)
- `PROMOTIONS_WEBHOOK_SECRET` - секретный ключ для webhook акций
- `OPENAI_API_KEY` - ключ OpenAI API
- `GOOGLE_SHEETS_CREDENTIALS` - JSON с учетными данными Google Service Account
- `APPEALS_SHEET_ID` - ID таблицы обращений
- `PROMOTIONS_SHEET_ID` - ID таблицы акций
- `AUTH_SHEET_ID` - ID таблицы авторизации

## 🔧 Управление приложением

```bash
# Просмотр логов
heroku logs --tail

# Перезапуск приложения
heroku restart

# Масштабирование (для платных планов)
heroku ps:scale web=1

# Просмотр переменных окружения
heroku config

# Изменение переменной
heroku config:set VARIABLE_NAME=new_value
```

## 🐛 Отладка

### Просмотр логов
```bash
heroku logs --tail --app your-bot-name
```

### Проверка статуса webhook
```bash
python setup_webhook.py info
```

### Удаление webhook (возврат к polling)
```bash
python setup_webhook.py delete
```

## 📊 Мониторинг

### Health Check
Приложение предоставляет endpoint для проверки здоровья:
```
GET https://your-app.herokuapp.com/health
```

### Webhook для акций
```
POST https://your-app.herokuapp.com/promotions_webhook
```

## 💰 Стоимость

- **Eco** (бесплатно): 550-1000 часов в месяц
- **Basic** ($7/месяц): 24/7 работа
- **Standard** ($25/месяц): больше ресурсов

## ⚠️ Ограничения бесплатного плана

- Приложение "засыпает" после 30 минут неактивности
- Просыпается при первом запросе (задержка ~10 секунд)
- Ограниченное количество часов в месяц

## 🔄 Автоматический деплой

Настройте GitHub integration в панели Heroku:
1. Подключите GitHub репозиторий
2. Включите "Wait for CI to pass before deploy"
3. Включите "Enable automatic deploys"

## 📱 Настройка Mini App

Обновите `WEB_APP_URL` в переменных окружения:
```bash
heroku config:set WEB_APP_URL=https://your-app.herokuapp.com/
```

Загрузите статические файлы (`index.html`, `menu.html`, `app.js`) в корень приложения.

## 🚨 Решение проблем

### Webhook не работает
1. Проверьте URL: `https://your-app.herokuapp.com/webhook`
2. Убедитесь, что приложение запущено: `heroku ps`
3. Проверьте логи: `heroku logs --tail`

### Бот не отвечает
1. Проверьте webhook: `python setup_webhook.py info`
2. Проверьте логи: `heroku logs --tail`
3. Перезапустите: `heroku restart`

### Ошибки Google Sheets
1. Проверьте `GOOGLE_SHEETS_CREDENTIALS`
2. Убедитесь, что Service Account имеет доступ к таблицам
3. Проверьте ID таблиц

## 📞 Поддержка

При возникновении проблем:
1. Проверьте логи: `heroku logs --tail`
2. Проверьте статус webhook: `python setup_webhook.py info`
3. Проверьте переменные окружения: `heroku config`
