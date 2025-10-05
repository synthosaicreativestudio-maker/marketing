/**
 * Google Apps Script для автоматической отправки уведомлений в Telegram бот
 * при публикации или обновлении акций
 */

// Конфигурация
const CONFIG = {
  // URL вашего webhook сервера (замените на ваш домен)
  WEBHOOK_URL: 'https://your-domain.com/webhook/promotions',
  
  // Секретный ключ для безопасности (должен совпадать с WEBHOOK_SECRET в боте)
  WEBHOOK_SECRET: 'your_secret_key_here',
  
  // ID листа с акциями
  SHEET_NAME: 'Акции',
  
  // Номера колонок (A=1, B=2, C=3, D=4, E=5, F=6, G=7, H=8)
  COLUMNS: {
    RELEASE_DATE: 1,    // A - Дата релиза
    TITLE: 2,           // B - Название
    DESCRIPTION: 3,     // C - Описание
    STATUS: 4,          // D - Статус
    START_DATE: 5,      // E - Дата начала
    END_DATE: 6,        // F - Дата окончания
    CONTENT: 7,         // G - Контент
    ACTION: 8           // H - Действие
  }
};

/**
 * Функция, которая вызывается при изменении в таблице
 */
function onEdit(e) {
  try {
    const range = e.range;
    const sheet = range.getSheet();
    
    // Проверяем, что изменение в нужном листе
    if (sheet.getName() !== CONFIG.SHEET_NAME) {
      return;
    }
    
    // Проверяем, что изменение в колонке H (Действие)
    if (range.getColumn() !== CONFIG.COLUMNS.ACTION) {
      return;
    }
    
    const row = range.getRow();
    const actionValue = range.getValue();
    
    // Проверяем, что нажата кнопка "Опубликовать"
    if (actionValue === 'Опубликовать') {
      publishPromotion(row);
    }
    
  } catch (error) {
    console.error('Ошибка в onEdit:', error);
  }
}

/**
 * Публикует акцию и отправляет уведомление в бот
 */
function publishPromotion(row) {
  try {
    const sheet = SpreadsheetApp.getActiveSheet();
    
    // Получаем данные акции
    const promotionData = getPromotionData(sheet, row);
    
    if (!promotionData) {
      console.error('Не удалось получить данные акции для строки', row);
      return;
    }
    
    // Обновляем статус на "Активна"
    sheet.getRange(row, CONFIG.COLUMNS.STATUS).setValue('Активна');
    
    // Устанавливаем дату релиза на сегодня
    const today = new Date();
    const todayString = Utilities.formatDate(today, Session.getScriptTimeZone(), 'dd.MM.yyyy');
    sheet.getRange(row, CONFIG.COLUMNS.RELEASE_DATE).setValue(todayString);
    
    // Очищаем кнопку действия
    sheet.getRange(row, CONFIG.COLUMNS.ACTION).setValue('');
    
    // Отправляем уведомление в бот
    sendWebhookNotification('publish', promotionData);
    
    console.log('Акция успешно опубликована:', promotionData.title);
    
  } catch (error) {
    console.error('Ошибка при публикации акции:', error);
  }
}

/**
 * Получает данные акции из указанной строки
 */
function getPromotionData(sheet, row) {
  try {
    const data = {
      title: sheet.getRange(row, CONFIG.COLUMNS.TITLE).getValue(),
      description: sheet.getRange(row, CONFIG.COLUMNS.DESCRIPTION).getValue(),
      status: sheet.getRange(row, CONFIG.COLUMNS.STATUS).getValue(),
      start_date: sheet.getRange(row, CONFIG.COLUMNS.START_DATE).getValue(),
      end_date: sheet.getRange(row, CONFIG.COLUMNS.END_DATE).getValue(),
      content: sheet.getRange(row, CONFIG.COLUMNS.CONTENT).getValue(),
      row: row
    };
    
    // Форматируем даты
    if (data.start_date instanceof Date) {
      data.start_date = Utilities.formatDate(data.start_date, Session.getScriptTimeZone(), 'dd.MM.yyyy');
    }
    if (data.end_date instanceof Date) {
      data.end_date = Utilities.formatDate(data.end_date, Session.getScriptTimeZone(), 'dd.MM.yyyy');
    }
    
    return data;
    
  } catch (error) {
    console.error('Ошибка получения данных акции:', error);
    return null;
  }
}

/**
 * Отправляет webhook уведомление в бот
 */
function sendWebhookNotification(action, promotionData) {
  try {
    const payload = {
      action: action,
      promotion: promotionData,
      timestamp: new Date().toISOString()
    };
    
    const options = {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Webhook-Secret': CONFIG.WEBHOOK_SECRET
      },
      payload: JSON.stringify(payload)
    };
    
    const response = UrlFetchApp.fetch(CONFIG.WEBHOOK_URL, options);
    
    if (response.getResponseCode() === 200) {
      console.log('Webhook уведомление успешно отправлено');
    } else {
      console.error('Ошибка отправки webhook:', response.getResponseCode(), response.getContentText());
    }
    
  } catch (error) {
    console.error('Ошибка отправки webhook уведомления:', error);
  }
}

/**
 * Функция для ручного тестирования
 */
function testPublishPromotion() {
  // Замените 2 на номер строки для тестирования
  publishPromotion(2);
}

/**
 * Функция для настройки триггера
 */
function setupTrigger() {
  // Удаляем существующие триггеры
  const triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(trigger => {
    if (trigger.getHandlerFunction() === 'onEdit') {
      ScriptApp.deleteTrigger(trigger);
    }
  });
  
  // Создаем новый триггер
  ScriptApp.newTrigger('onEdit')
    .timeBased()
    .everyMinutes(1) // Проверяем каждую минуту
    .create();
    
  console.log('Триггер настроен успешно');
}

/**
 * Функция для создания кнопок "Опубликовать" в колонке H
 */
function createPublishButtons() {
  const sheet = SpreadsheetApp.getActiveSheet();
  const lastRow = sheet.getLastRow();
  
  // Создаем кнопки для всех строк с данными (начиная со строки 2)
  for (let row = 2; row <= lastRow; row++) {
    const title = sheet.getRange(row, CONFIG.COLUMNS.TITLE).getValue();
    const status = sheet.getRange(row, CONFIG.COLUMNS.STATUS).getValue();
    
    // Создаем кнопку только если есть название и статус не "Активна"
    if (title && status !== 'Активна') {
      sheet.getRange(row, CONFIG.COLUMNS.ACTION).setValue('Опубликовать');
    }
  }
  
  console.log('Кнопки "Опубликовать" созданы');
}
