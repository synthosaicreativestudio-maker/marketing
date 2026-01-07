# Исправление ошибки в Google Apps Script

## Проблема

Ошибка: `TypeError: ContentService.createTextOutput(...).setMimeType(...).setHeader is not a function`

## Причина

Метод `setHeader()` не существует в Google Apps Script API. CORS заголовки устанавливаются автоматически при настройке доступа "Anyone" в веб-приложении.

## Решение

Удалите все вызовы `.setHeader('Access-Control-Allow-Origin', '*')` из функции `doGet`.

### Что нужно сделать:

1. Откройте ваш Google Apps Script
2. Найдите функцию `doGet`
3. Удалите все строки с `.setHeader('Access-Control-Allow-Origin', '*')`
4. Сохраните (Ctrl+S)
5. Обновите развертывание:
   - Нажмите "Развернуть" → "Управление развертываниями"
   - Нажмите на иконку редактирования ✏️
   - Выберите "Новая версия"
   - Нажмите "Развернуть"

### Исправленный код:

**Было:**
```javascript
return ContentService
  .createTextOutput(JSON.stringify(result))
  .setMimeType(ContentService.MimeType.JSON)
  .setHeader('Access-Control-Allow-Origin', '*');
```

**Стало:**
```javascript
return ContentService
  .createTextOutput(JSON.stringify(result))
  .setMimeType(ContentService.MimeType.JSON);
```

## Проверка

После исправления откройте URL веб-приложения в браузере. Вы должны увидеть JSON с акциями без ошибок.

---

**Важно:** Файлы `google_apps_script_complete.js` и `google_apps_script_promotions.js` уже исправлены. Просто скопируйте исправленную функцию `doGet` из `google_apps_script_complete.js` в ваш Google Apps Script.
