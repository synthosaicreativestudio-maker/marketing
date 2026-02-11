# Простая настройка Google Apps Script URL

## Один шаг

1. Откройте `menu.html` в редакторе
2. Найдите строку 773 (или найдите `GOOGLE_APPS_SCRIPT_URL`)
3. Вставьте ваш URL между кавычками:

```javascript
const GOOGLE_APPS_SCRIPT_URL = 'https://script.google.com/macros/s/ВАШ_ID/exec';
```

Где взять URL:
- Откройте Google Apps Script
- Нажмите "Развернуть" → "Управление развертываниями"
- Нажмите на иконку копирования рядом с URL
- Вставьте в menu.html

## Готово!

После этого акции будут загружаться через Google Apps Script.

Если URL не указан, система автоматически использует Cloudflare Tunnel как fallback.
