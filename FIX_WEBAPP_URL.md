# Инструкция по исправлению WEB_APP_URL на сервере

## Проблема
Мини-приложение не загружается из-за неправильного формата URL в переменной окружения `WEB_APP_URL`.

## Что нужно сделать на сервере

### 1. Проверить текущее значение WEB_APP_URL

```bash
ssh ubuntu@158.160.0.127
cd /home/ubuntu/marketingbot
grep WEB_APP_URL .env
```

### 2. Убедиться, что значение правильное

`WEB_APP_URL` должен быть простой строкой URL, заканчивающейся на `/`:

```
WEB_APP_URL=https://synthosaicreativestudio-maker.github.io/marketing/
```

**НЕ должно быть:**
- JSON объекта
- URL-encoded данных
- Других параметров после URL

### 3. Обновить .env файл (если нужно)

```bash
# Отредактировать .env
nano .env

# Или использовать sed для замены
sed -i 's|WEB_APP_URL=.*|WEB_APP_URL=https://synthosaicreativestudio-maker.github.io/marketing/|' .env
```

### 4. Проверить, что значение корректное

```bash
python3 -c "import os; from dotenv import load_dotenv; load_dotenv('.env'); print('WEB_APP_URL:', repr(os.getenv('WEB_APP_URL')))"
```

Должно вывести:
```
WEB_APP_URL: 'https://synthosaicreativestudio-maker.github.io/marketing/'
```

### 5. Перезапустить бота

```bash
sudo systemctl restart marketingbot-bot.service
sudo systemctl restart marketingbot-web.service
```

### 6. Проверить логи

```bash
sudo journalctl -u marketingbot-bot.service -f
```

В логах не должно быть ошибок типа "WEB_APP_URL содержит невалидный URL".

## Изменения в коде

Все изменения уже внесены в код:

1. ✅ `webhook_handler.py` - исправлено использование `WebAppInfo` вместо словаря
2. ✅ `promotions_notifier.py` - исправлено использование `WebAppInfo` вместо словаря  
3. ✅ `handlers/utils.py` - добавлена валидация URL

После обновления кода на сервере и перезапуска бота проблема должна быть решена.
