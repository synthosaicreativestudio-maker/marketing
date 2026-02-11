// === КОНФИГУРАЦИЯ (НОВАЯ ЛОГИКА) ===

// Название листа
const SHEET_NAME = "Акции";

// Номера столбцов
const RELEASE_DATE_COL = 1;
const TITLE_COL = 2;
const DESCRIPTION_COL = 3;
const STATUS_COL = 4;
const START_DATE_COL = 5;
const END_DATE_COL = 6;
const CONTENT_COL = 7;
const LINK_COL = 8;
const ACTION_COL = 9;

// Заголовки столбцов
const HEADERS = [
  "Дата релиза", "Название", "Описание", "Статус", 
  "Дата начала", "Дата окончания", "Контент", "Ссылка", "Действие"
];

// Новые статусы
const STATUS_PENDING = "Ожидает";
const STATUS_ACTIVE = "Активна";
const STATUS_FINISHED = "Закончена";

// Новые команды
const ACTION_PUBLISH = "Опубликовать";
const ACTION_FINISH = "Завершить";

// Новые цвета для заливки
const COLOR_PENDING = "#fff2cc";   // Светло-желтый
const COLOR_ACTIVE = "#d9ead3";    // Светло-зеленый
const COLOR_FINISHED = "#f4cccc";  // Светло-красный

// Webhook настройки для мгновенных уведомлений
const WEBHOOK_URL = 'http://158.160.0.127:8080/webhook/promotions';
const WEBHOOK_SECRET = 'default_secret'; // Должен совпадать с WEBHOOK_SECRET на сервере

// === КОНЕЦ КОНФИГУРАЦИИ ===


/**
 * Создает кастомное меню при открытии таблицы.
 */
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('⚠️ Управление Акциями')
    .addItem('✅ 1. Полная настройка/перезагрузка правил', 'setupSheet')
    .addToUi();
}

/**
 * Основная функция полной настройки листа.
 */
function setupSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME, 0);
  const ui = SpreadsheetApp.getUi();

  sheet.getRange(1, 1, 1, sheet.getMaxColumns()).clearDataValidations();
  sheet.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]).setFontWeight("bold");
  sheet.setFrozenRows(1);

  const dateColumns = [RELEASE_DATE_COL, START_DATE_COL, END_DATE_COL];
  dateColumns.forEach(col => {
    sheet.getRange(2, col, sheet.getMaxRows() - 1, 1).setNumberFormat("dd.MM.yyyy");
  });

  const statusRange = sheet.getRange(2, STATUS_COL, sheet.getMaxRows() - 1, 1);
  const protection = statusRange.protect().setDescription('Статус изменяется автоматически');
  const me = Session.getEffectiveUser();
  protection.addEditor(me);
  protection.removeEditors(protection.getEditors());
  if (protection.canDomainEdit()) {
    protection.setDomainEdit(false);
  }

  sheet.getRange(2, ACTION_COL, sheet.getMaxRows() - 1, 1)
    .setDataValidation(SpreadsheetApp.newDataValidation().requireValueInList([ACTION_PUBLISH, ACTION_FINISH], true).build());
  sheet.getRange(2, START_DATE_COL, sheet.getMaxRows() - 1, 2)
    .setDataValidation(SpreadsheetApp.newDataValidation().requireDate().setAllowInvalid(false).build());

  sheet.clearConditionalFormatRules();
  const fullRange = `A2:I${sheet.getMaxRows()}`;
  const rules = [
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied(`=$D2="${STATUS_PENDING}"`).setBackground(COLOR_PENDING).setRanges([sheet.getRange(fullRange)]).build(),
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied(`=$D2="${STATUS_ACTIVE}"`).setBackground(COLOR_ACTIVE).setRanges([sheet.getRange(fullRange)]).build(),
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied(`=$D2="${STATUS_FINISHED}"`).setBackground(COLOR_FINISHED).setRanges([sheet.getRange(fullRange)]).build()
  ];
  sheet.setConditionalFormatRules(rules);
  
  createTriggers();

  ui.alert('✅ Настройка по новой логике завершена!', 'Лист "Акции" готов к работе.', ui.ButtonSet.OK);
}

/**
 * Создает программные триггеры (на редактирование и по времени).
 */
function createTriggers() {
  ScriptApp.getProjectTriggers().forEach(trigger => ScriptApp.deleteTrigger(trigger));

  ScriptApp.newTrigger('onEditTrigger')
    .forSpreadsheet(SpreadsheetApp.getActive())
    .onEdit()
    .create();

  ScriptApp.newTrigger('updateStatusesDaily')
    .timeBased()
    .everyDays(1)
    .atHour(1)
    .create();
}

/**
 * Обработчик события редактирования ячеек.
 * @param {Object} e - Объект события.
 */
function onEditTrigger(e) {
  // Проверяем, что объект события e существует, иначе выходим.
  if (!e || !e.range) {
    return;
  }

  const range = e.range;
  const sheet = range.getSheet();
  if (sheet.getName() !== SHEET_NAME || range.getRow() <= 1) return;

  const col = range.getColumn();
  const row = range.getRow();
  
  // Логика для столбца "Название"
  if (col === TITLE_COL) {
    const titleValue = range.getValue();
    const releaseDateCell = sheet.getRange(row, RELEASE_DATE_COL);

    // Если в ячейке появилось значение и дата еще не стоит - ставим дату
    if (titleValue !== "" && releaseDateCell.isBlank()) {
      releaseDateCell.setValue(new Date());
    } 
    // Если значение из ячейки удалили - стираем дату
    else if (titleValue === "") {
      releaseDateCell.clearContent();
    }
  }

  // Логика для столбца "Действие"
  if (col === ACTION_COL) {
    const actionValue = range.getValue();
    if (actionValue === ACTION_PUBLISH) {
      handlePublish(sheet, row);
    } else if (actionValue === ACTION_FINISH) {
      handleFinish(sheet, row);
    }
  }
}

/**
 * Отправляет данные акции на webhook для мгновенной отправки уведомлений.
 * @param {Object} promotionData - Данные акции в формате, совместимом с webhook_handler.py
 * @returns {boolean} - true если запрос успешен, false в противном случае
 */
function sendWebhookNotification(promotionData) {
  try {
    var payload = {
      action: 'publish',
      promotion: promotionData
    };
    
    var options = {
      method: 'post',
      contentType: 'application/json',
      headers: {
        'X-Webhook-Secret': WEBHOOK_SECRET
      },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    };
    
    var response = UrlFetchApp.fetch(WEBHOOK_URL, options);
    var responseCode = response.getResponseCode();
    var responseText = response.getContentText();
    
    Logger.log('Webhook response code: ' + responseCode);
    Logger.log('Webhook response: ' + responseText);
    
    if (responseCode === 200) {
      Logger.log('✅ Webhook успешно отправлен для акции: ' + promotionData.title);
      return true;
    } else {
      Logger.log('⚠️ Webhook вернул код ошибки: ' + responseCode);
      return false;
    }
  } catch (error) {
    Logger.log('❌ Ошибка отправки webhook: ' + error.toString());
    return false;
  }
}

/**
 * Логика для действия "Опубликовать".
 */
function handlePublish(sheet, row) {
  const ui = SpreadsheetApp.getUi();
  const rowValues = sheet.getRange(row, 1, 1, HEADERS.length).getValues()[0];

  const missingFields = [];
  if (!rowValues[TITLE_COL - 1]) missingFields.push(HEADERS[TITLE_COL - 1]);
  if (!rowValues[DESCRIPTION_COL - 1]) missingFields.push(HEADERS[DESCRIPTION_COL - 1]);
  if (!rowValues[START_DATE_COL - 1]) missingFields.push(HEADERS[START_DATE_COL - 1]);
  if (!rowValues[END_DATE_COL - 1]) missingFields.push(HEADERS[END_DATE_COL - 1]);

  if (missingFields.length > 0) {
    ui.alert('Ошибка публикации', `Не заполнены обязательные поля:\n- ${missingFields.join('\n- ')}`, ui.ButtonSet.OK);
    sheet.getRange(row, ACTION_COL).clearContent();
    return;
  }

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const startDate = new Date(rowValues[START_DATE_COL - 1]);
  startDate.setHours(0,0,0,0);

  const statusCell = sheet.getRange(row, STATUS_COL);
  
  // Определяем финальный статус
  var finalStatus;
  if (startDate > today) {
    finalStatus = STATUS_PENDING;
  } else {
    finalStatus = STATUS_ACTIVE;
  }
  statusCell.setValue(finalStatus);
  
  // Отправляем webhook ТОЛЬКО если статус "Активна"
  if (finalStatus === STATUS_ACTIVE) {
    // Собираем данные акции для отправки на webhook
    var releaseDate = rowValues[RELEASE_DATE_COL - 1];
    var title = rowValues[TITLE_COL - 1];
    var description = rowValues[DESCRIPTION_COL - 1];
    var content = rowValues[CONTENT_COL - 1];
    var link = rowValues[LINK_COL - 1];
    
    // Форматируем даты
    var formattedReleaseDate = '';
    var formattedStartDate = '';
    var formattedEndDate = '';
    
    if (releaseDate instanceof Date) {
      formattedReleaseDate = Utilities.formatDate(releaseDate, Session.getScriptTimeZone(), 'dd.MM.yyyy HH:mm:ss');
    } else if (releaseDate) {
      formattedReleaseDate = String(releaseDate).trim();
    } else {
      // Если дата релиза не установлена, используем текущее время
      formattedReleaseDate = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'dd.MM.yyyy HH:mm:ss');
    }
    
    if (startDate instanceof Date) {
      formattedStartDate = Utilities.formatDate(startDate, Session.getScriptTimeZone(), 'dd.MM.yyyy');
    } else if (startDate) {
      formattedStartDate = String(startDate).trim();
    }
    
    var endDate = rowValues[END_DATE_COL - 1];
    if (endDate instanceof Date) {
      formattedEndDate = Utilities.formatDate(endDate, Session.getScriptTimeZone(), 'dd.MM.yyyy');
    } else if (endDate) {
      formattedEndDate = String(endDate).trim();
    }
    
    // Конвертируем контент (если это Google Drive ссылка)
    var convertedContent = content && content !== 'None' && content !== '' 
      ? convertImageUrl(content) 
      : null;
    
    // Формируем объект данных акции для webhook
    var promotionData = {
      title: String(title).trim(),
      description: description ? String(description).trim() : 'Описание отсутствует',
      start_date: formattedStartDate,
      end_date: formattedEndDate,
      release_date: formattedReleaseDate,
      status: finalStatus  // Добавляем статус в данные акции
    };
    
    // Добавляем контент, если есть
    if (convertedContent) {
      promotionData.content = convertedContent;
    } else if (content && content !== 'None' && content !== '') {
      promotionData.content = String(content).trim();
    }
    
    // Добавляем ссылку, если есть
    if (link && link !== 'None' && link !== '') {
      promotionData.link = String(link).trim();
    }
    
    // Отправляем данные на webhook для мгновенной отправки уведомлений (только для статуса "Активна")
    sendWebhookNotification(promotionData);
  }
  
  sheet.getRange(row, ACTION_COL).clearContent();
}

/**
 * Логика для действия "Завершить".
 */
function handleFinish(sheet, row) {
  sheet.getRange(row, STATUS_COL).setValue(STATUS_FINISHED);
  sheet.getRange(row, ACTION_COL).clearContent();
}

/**
 * Ежедневная автоматическая проверка и обновление статусов.
 */
function updateStatusesDaily() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME);
  if (!sheet || sheet.getLastRow() < 2) return;

  const dataRange = sheet.getRange(2, 1, sheet.getLastRow() - 1, HEADERS.length);
  const values = dataRange.getValues();
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  let changesMade = false;
  for (let i = 0; i < values.length; i++) {
    const status = values[i][STATUS_COL - 1];
    const startDate = values[i][START_DATE_COL - 1] ? new Date(values[i][START_DATE_COL - 1]) : null;
    const endDate = values[i][END_DATE_COL - 1] ? new Date(values[i][END_DATE_COL - 1]) : null;
    
    if (status === STATUS_ACTIVE && endDate && endDate < today) {
      values[i][STATUS_COL - 1] = STATUS_FINISHED;
      values[i][ACTION_COL - 1] = "";
      changesMade = true;
    } 
    else if (status === STATUS_PENDING && startDate && startDate <= today) {
      values[i][STATUS_COL - 1] = STATUS_ACTIVE;
      changesMade = true;
    }
  }

  if (changesMade) {
    dataRange.setValues(values);
  }
}

// ============================================================================
// ФУНКЦИЯ КОНВЕРТАЦИИ ССЫЛОК НА КАРТИНКИ
// ============================================================================

/**
 * Конвертирует ссылки Google Drive в прямые ссылки на изображения.
 * Обычные ссылки и base64 возвращает без изменений.
 * 
 * Поддерживаемые форматы Google Drive:
 * - https://drive.google.com/file/d/ID/view?usp=sharing
 * - https://drive.google.com/file/d/ID/view
 * - https://drive.google.com/open?id=ID
 * - https://drive.google.com/uc?id=ID
 * - https://drive.google.com/uc?export=view&id=ID
 * 
 * @param {string} url - URL картинки (Google Drive, обычная ссылка или base64)
 * @returns {string|null} - Прямая ссылка на картинку или null
 */
function convertImageUrl(url) {
  // Если URL пустой или null
  if (!url || url === 'None' || url === '') {
    return null;
  }
  
  var urlStr = String(url).trim();
  
  // Если это base64 — возвращаем как есть
  if (urlStr.indexOf('data:image') === 0) {
    return urlStr;
  }
  
  // Паттерны для Google Drive ссылок
  var drivePatterns = [
    /drive\.google\.com\/file\/d\/([a-zA-Z0-9_-]+)/,      // /file/d/ID/
    /drive\.google\.com\/open\?id=([a-zA-Z0-9_-]+)/,     // /open?id=ID
    /drive\.google\.com\/uc\?.*id=([a-zA-Z0-9_-]+)/,     // /uc?id=ID или /uc?export=view&id=ID
    /drive\.google\.com\/uc\?id=([a-zA-Z0-9_-]+)/        // /uc?id=ID
  ];
  
  // Проверяем каждый паттерн
  for (var i = 0; i < drivePatterns.length; i++) {
    var match = urlStr.match(drivePatterns[i]);
    if (match && match[1]) {
      // Возвращаем прямую ссылку через googleusercontent
      // Это более надежный способ, чем drive.google.com/uc?export=view
      return 'https://lh3.googleusercontent.com/d/' + match[1];
    }
  }
  
  // Если это не Google Drive — возвращаем как есть (обычная ссылка из интернета)
  return urlStr;
}

// ============================================================================
// API ФУНКЦИЯ ДЛЯ ПОЛУЧЕНИЯ АКТИВНЫХ АКЦИЙ (ИСПРАВЛЕННАЯ ВЕРСИЯ)
// ============================================================================

/**
 * Google Apps Script веб-приложение для получения активных акций из Google Sheets.
 * 
 * Эта функция используется для получения акций через API в Telegram Mini App.
 * 
 * @param {Object} e - Объект события запроса (не используется, но требуется для doGet)
 * @returns {TextOutput} JSON с активными акциями
 */
function doGet(e) {
  try {
    // Получаем активную таблицу
    var spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
    
    // Получаем лист "Акции"
    var sheet = spreadsheet.getSheetByName(SHEET_NAME);
    
    // Если лист "Акции" не найден, пробуем первый лист
    if (!sheet) {
      sheet = spreadsheet.getActiveSheet();
    }
    
    // Получаем все данные из таблицы
    var data = sheet.getDataRange().getValues();
    
    // Если таблица пустая, возвращаем пустой массив
    if (data.length < 2) {
      return ContentService
        .createTextOutput(JSON.stringify([]))
        .setMimeType(ContentService.MimeType.JSON);
    }
    
    // Первая строка - это заголовки (пропускаем)
    // Обрабатываем строки данных (начиная со второй строки)
    var rows = data.slice(1);
    var result = [];
    
    rows.forEach(function(row, rowIndex) {
      // Получаем данные акции по индексам колонок (индекс начинается с 0)
      var releaseDate = row[RELEASE_DATE_COL - 1]; // Колонка A (индекс 0)
      var status = row[STATUS_COL - 1]; // Колонка D (индекс 3)
      var title = row[TITLE_COL - 1]; // Колонка B (индекс 1)
      var description = row[DESCRIPTION_COL - 1]; // Колонка C (индекс 2)
      var startDate = row[START_DATE_COL - 1]; // Колонка E (индекс 4)
      var endDate = row[END_DATE_COL - 1]; // Колонка F (индекс 5)
      var content = row[CONTENT_COL - 1]; // Колонка G (индекс 6)
      var link = row[LINK_COL - 1]; // Колонка H (индекс 7)
      
      // Проверяем, что статус равен "Активна"
      if (status && String(status).trim() === STATUS_ACTIVE) {
        // Если название пустое, используем описание
        if (!title || title === 'None' || title === '') {
          title = description ? 'Акция ' + description : 'Акция без названия';
        }
        
        // Форматируем даты, если они есть
        var formattedReleaseDate = '';
        var formattedStartDate = '';
        var formattedEndDate = '';
        
        if (releaseDate instanceof Date) {
          formattedReleaseDate = Utilities.formatDate(releaseDate, Session.getScriptTimeZone(), 'dd.MM.yyyy');
        } else if (releaseDate) {
          formattedReleaseDate = String(releaseDate).trim();
        }
        
        if (startDate instanceof Date) {
          formattedStartDate = Utilities.formatDate(startDate, Session.getScriptTimeZone(), 'dd.MM.yyyy');
        } else if (startDate) {
          formattedStartDate = String(startDate).trim();
        }
        
        if (endDate instanceof Date) {
          formattedEndDate = Utilities.formatDate(endDate, Session.getScriptTimeZone(), 'dd.MM.yyyy');
        } else if (endDate) {
          formattedEndDate = String(endDate).trim();
        }
        
        // Создаем уникальный ID
        var uniqueId = (title + '_' + description + '_' + formattedStartDate + '_' + formattedEndDate)
          .replace(/\s+/g, '_')
          .replace(/:/g, '')
          .replace(/-/g, '');
        
        // Формируем объект акции в формате, совместимом с promotions_api.py
        var promotion = {
          'id': uniqueId,
          'title': String(title).trim(),
          'description': description ? String(description).trim() : 'Описание отсутствует',
          'status': STATUS_ACTIVE,
          'release_date': formattedReleaseDate,
          'start_date': formattedStartDate,
          'end_date': formattedEndDate
        };
        
        // Добавляем контент (картинку), если он есть
        // Автоматически конвертируем Google Drive ссылки в прямые ссылки
        if (content && content !== 'None' && content !== '') {
          var convertedContent = convertImageUrl(content);
          if (convertedContent) {
            promotion['content'] = convertedContent;
          }
        }
        
        // Добавляем ссылку, если она есть
        if (link && link !== 'None' && link !== '') {
          promotion['link'] = String(link).trim();
        }
        
        // Добавляем акцию в результат, если есть название
        if (promotion['title'] && promotion['title'] !== 'None') {
          result.push(promotion);
        }
      }
    });
    
    // Сортировка по release_date (от новых к старым)
    result.sort(function(a, b) {
      var dateA = a.release_date ? new Date(a.release_date.split('.').reverse().join('-')) : new Date(0);
      var dateB = b.release_date ? new Date(b.release_date.split('.').reverse().join('-')) : new Date(0);
      return dateB - dateA; // От новых к старым
    });
    
    // Возвращаем результат в формате JSON
    // В Google Apps Script CORS заголовки устанавливаются автоматически при настройке "Anyone" доступа
    return ContentService
      .createTextOutput(JSON.stringify(result, null, 2))
      .setMimeType(ContentService.MimeType.JSON);
      
  } catch (error) {
    // В случае ошибки возвращаем пустой массив с информацией об ошибке
    Logger.log('Ошибка в doGet: ' + error.toString());
    return ContentService
      .createTextOutput(JSON.stringify({ 
        error: 'Ошибка при получении данных: ' + error.toString(),
        promotions: []
      }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * Тестовая функция для проверки работы API.
 * Запустите эту функцию в редакторе Apps Script для проверки.
 */
function testGetPromotions() {
  var result = doGet({});
  Logger.log(result.getContent());
}

/**
 * Тестовая функция для проверки конвертации ссылок на картинки.
 * Запустите эту функцию в редакторе Apps Script для проверки.
 */
function testConvertImageUrl() {
  var testUrls = [
    'https://drive.google.com/file/d/1Mw89IfV3FlK0TGPJbFyPAdMFhqpp0Csl/view?usp=sharing',
    'https://drive.google.com/file/d/ABC123XYZ/view',
    'https://drive.google.com/open?id=ABC123XYZ',
    'https://drive.google.com/uc?id=ABC123XYZ',
    'https://drive.google.com/uc?export=view&id=ABC123XYZ',
    'https://example.com/image.jpg',
    'data:image/jpeg;base64,/9j/4AAQSkZJRg...',
    '',
    null
  ];
  
  testUrls.forEach(function(url) {
    var result = convertImageUrl(url);
    Logger.log('Input:  ' + url);
    Logger.log('Output: ' + result);
    Logger.log('---');
  });
}
