# Google Apps Script для прямой мобильной авторизации

## 📱 **Проблема:**
- `tg.sendData` не работает на мобильных устройствах
- HTTP fallback сложный и ненадежный
- Нужна прямая авторизация из WebApp

## 🚀 **Решение:**
Создать Google Apps Script, который будет принимать данные авторизации напрямую из WebApp и обновлять таблицу.

## 📝 **Код Google Apps Script:**

```javascript
// Google Apps Script для прямой мобильной авторизации
// Разместить в Google Таблице: Расширения -> Apps Script

// Функция для авторизации пользователя
function authorizeUser(code, phone, telegramId) {
  try {
    // Получаем активную таблицу
    const sheet = SpreadsheetApp.getActiveSpreadsheet();
    const worksheet = sheet.getSheetByName('список сотрудников для авторизации');
    
    if (!worksheet) {
      return { success: false, error: 'Лист не найден' };
    }
    
    // Получаем все данные
    const data = worksheet.getDataRange().getValues();
    const headers = data[0];
    
    // Находим индексы колонок
    const codeCol = headers.indexOf('Код партнера');
    const phoneCol = headers.indexOf('Телефон партнера');
    const statusCol = headers.indexOf('Статус авторизации');
    const telegramCol = headers.indexOf('Telegram ID');
    
    if (codeCol === -1 || phoneCol === -1 || statusCol === -1 || telegramCol === -1) {
      return { success: false, error: 'Колонки не найдены' };
    }
    
    // Ищем пользователя по коду и телефону
    let userRow = -1;
    for (let i = 1; i < data.length; i++) {
      if (data[i][codeCol] == code && data[i][phoneCol] == phone) {
        userRow = i + 1; // +1 потому что индексы начинаются с 0
        break;
      }
    }
    
    if (userRow === -1) {
      return { success: false, error: 'Пользователь не найден' };
    }
    
    // Обновляем статус и Telegram ID
    worksheet.getRange(userRow, statusCol + 1).setValue('авторизован');
    worksheet.getRange(userRow, telegramCol + 1).setValue(telegramId);
    
    // Получаем ФИО пользователя
    const fioCol = headers.indexOf('ФИО партнера');
    const userName = fioCol !== -1 ? data[userRow - 1][fioCol] : 'Неизвестно';
    
    return { 
      success: true, 
      message: `Пользователь ${userName} успешно авторизован`,
      user: {
        code: code,
        phone: phone,
        telegramId: telegramId,
        name: userName
      }
    };
    
  } catch (error) {
    return { success: false, error: error.toString() };
  }
}

// Функция для веб-приложения (вызывается из WebApp)
function doPost(e) {
  try {
    // Получаем данные из POST запроса
    const data = JSON.parse(e.postData.contents);
    const { code, phone, telegramId } = data;
    
    // Проверяем обязательные поля
    if (!code || !phone || !telegramId) {
      return ContentService
        .createTextOutput(JSON.stringify({
          success: false,
          error: 'Не все поля заполнены'
        }))
        .setMimeType(ContentService.MimeType.JSON);
    }
    
    // Выполняем авторизацию
    const result = authorizeUser(code, phone, telegramId);
    
    // Возвращаем результат
    return ContentService
      .createTextOutput(JSON.stringify(result))
      .setMimeType(ContentService.MimeType.JSON);
      
  } catch (error) {
    return ContentService
      .createTextOutput(JSON.stringify({
        success: false,
        error: 'Ошибка обработки запроса: ' + error.toString()
      }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

// Функция для тестирования
function testAuth() {
  const result = authorizeUser('111098', '89827701055', '284355186');
  console.log(result);
}
```

## 🔧 **Как настроить:**

1. **Откройте Google Таблицу** с авторизацией
2. **Перейдите в:** Расширения → Apps Script
3. **Вставьте код** выше
4. **Сохраните** и **опубликуйте** как веб-приложение
5. **Скопируйте URL** веб-приложения

## 📱 **Использование в WebApp:**
WebApp будет отправлять POST запрос напрямую в Google Apps Script, который обновит таблицу.

## ✅ **Преимущества:**
- ✅ Работает на всех устройствах
- ✅ Прямое обновление таблицы
- ✅ Простая и надежная логика
- ✅ Не зависит от Telegram API
- ✅ Мгновенная авторизация
