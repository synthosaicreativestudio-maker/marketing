# Инструкция по обновлению Google Apps Script для мгновенных уведомлений

## Важно

Для работы мгновенных уведомлений о публикации акций необходимо обновить код в Google Apps Script.

## Пошаговая инструкция

### 1. Откройте файл с кодом

Откройте файл `GOOGLE_APPS_SCRIPT_FULL.js` из репозитория:
- Локально: `/Users/verakoroleva/Desktop/marketingbot/GOOGLE_APPS_SCRIPT_FULL.js`
- На GitHub: `https://github.com/synthosaicreativestudio-maker/marketing/blob/main/GOOGLE_APPS_SCRIPT_FULL.js`

### 2. Скопируйте весь код

Скопируйте **весь** код из файла `GOOGLE_APPS_SCRIPT_FULL.js` (Ctrl+A / Cmd+A, затем Ctrl+C / Cmd+C).

### 3. Откройте Google Apps Script

1. Откройте Google Sheets с акциями
2. Перейдите в **Расширения → Apps Script** (Extensions → Apps Script)

### 4. Вставьте обновленный код

1. Выделите весь существующий код в редакторе (Ctrl+A / Cmd+A)
2. Удалите его (Delete)
3. Вставьте обновленный код (Ctrl+V / Cmd+V)

### 5. Проверьте конфигурацию

Убедитесь, что в начале файла есть правильные константы:

```javascript
// Webhook настройки для мгновенных уведомлений
const WEBHOOK_URL = 'http://158.160.0.127:8080/webhook/promotions';
const WEBHOOK_SECRET = 'default_secret'; // Должен совпадать с WEBHOOK_SECRET на сервере
```

**Важно:** `WEBHOOK_SECRET` должен совпадать со значением `WEBHOOK_SECRET` в файле `.env` на сервере.

### 6. Сохраните проект

Нажмите **Ctrl+S** (Windows/Linux) или **Cmd+S** (Mac) или кнопку сохранения (дискета).

### 7. Проверьте, что код сохранен

В верхней части редактора должно появиться сообщение "Сохранено" (Saved) или время последнего сохранения.

## Проверка работы

### 1. Проверка webhook endpoint

Откройте в браузере:
```
http://158.160.0.127:8080/webhook/promotions
```

Должно показаться JSON сообщение:
```json
{
  "status": "webhook_active",
  "message": "Webhook endpoint для уведомлений о публикации акций",
  "method": "POST",
  "url": "/webhook/promotions",
  "note": "Этот endpoint работает только с POST запросами..."
}
```

### 2. Тестовая публикация акции

1. Создайте новую акцию в Google Sheets
2. Заполните все обязательные поля:
   - **Название**
   - **Описание**
   - **Дата начала**
   - **Дата окончания**
3. В столбце **"Действие"** выберите **"Опубликовать"**
4. Уведомление должно прийти **мгновенно** в Telegram чат

### 3. Проверка логов

**В Google Apps Script:**
1. Перейдите в **Вид → Логи выполнения** (View → Execution log)
2. Выполните публикацию акции
3. Должны появиться записи:
   ```
   Webhook response code: 200
   Webhook response: {"status":"success"}
   ✅ Webhook успешно отправлен для акции: [название акции]
   ```

**На сервере:**
```bash
ssh ubuntu@158.160.0.127
journalctl -u marketingbot-web.service -f
```

Должны появиться записи:
```
Получен webhook от Google Sheets: {...}
```

## Возможные проблемы

### Уведомления все еще не приходят

1. **Проверьте код в Google Apps Script:**
   - Убедитесь, что функция `sendWebhookNotification()` присутствует
   - Проверьте, что функция `handlePublish()` вызывает `sendWebhookNotification(promotionData)`
   - Убедитесь, что константы `WEBHOOK_URL` и `WEBHOOK_SECRET` правильные

2. **Проверьте логи Google Apps Script:**
   - Откройте **Вид → Логи выполнения**
   - Выполните публикацию акции
   - Если есть ошибки, они будут отображены в логах

3. **Проверьте WEBHOOK_SECRET:**
   - На сервере: `grep WEBHOOK_SECRET /home/ubuntu/marketingbot/.env`
   - В Google Apps Script: должен быть `'default_secret'`
   - Значения должны **совпадать**

### Ошибка "Could not fetch" в Google Apps Script

Google Apps Script может иметь ограничения на доступ к внутренним IP адресам.

**Решение:**
- Убедитесь, что сервер доступен из интернета
- Или используйте Cloudflare Tunnel для доступа к серверу

### Webhook возвращает ошибку 401 (Unauthorized)

**Причина:** Неверный `WEBHOOK_SECRET`.

**Решение:**
1. Проверьте `WEBHOOK_SECRET` на сервере:
   ```bash
   grep WEBHOOK_SECRET /home/ubuntu/marketingbot/.env
   ```
2. Убедитесь, что в Google Apps Script используется то же значение
3. Перезапустите сервис webhook:
   ```bash
   sudo systemctl restart marketingbot-web.service
   ```

### Webhook возвращает ошибку 500 (Internal Server Error)

**Причина:** Ошибка в обработке webhook на сервере.

**Решение:**
1. Проверьте логи сервиса:
   ```bash
   journalctl -u marketingbot-web.service -n 50
   ```
2. Убедитесь, что сервис запущен:
   ```bash
   sudo systemctl status marketingbot-web.service
   ```
3. Проверьте, что бот работает:
   ```bash
   sudo systemctl status marketingbot.service
   ```

## Дополнительная информация

После обновления кода в Google Apps Script, уведомления будут приходить **мгновенно** при публикации акции, без задержки в 15 минут.

**Примечание:** Если вы изменили `WEBHOOK_SECRET` на сервере, обязательно обновите его и в Google Apps Script.
