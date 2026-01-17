/**
 * Google Apps Script для получения активных акций из Google Sheets
 * 
 * Инструкция по развертыванию:
 * 1. Откройте Google Таблицу с акциями
 * 2. Расширения → Apps Script
 * 3. Вставьте этот код
 * 4. Сохраните проект (Ctrl+S)
 * 5. Нажмите "Развернуть" → "Новое развертывание"
 * 6. Выберите тип: "Веб-приложение"
 * 7. У кого есть доступ: "Все"
 * 8. Нажмите "Развернуть"
 * 9. Скопируйте URL веб-приложения
 */

function doGet(e) {
  try {
    // Получаем активную таблицу
    var spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
    
    // Получаем лист "Акции" (если лист называется по-другому, измените здесь)
    var sheet = spreadsheet.getSheetByName("Акции");
    
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
    
    // Первая строка - это заголовки
    var headers = data[0];
    
    // Находим индексы колонок по заголовкам
    var headerMap = {};
    headers.forEach(function(header, index) {
      // Нормализуем заголовок (убираем пробелы, приводим к нижнему регистру)
      var normalizedHeader = String(header).trim().toLowerCase();
      headerMap[normalizedHeader] = index;
    });
    
    // Определяем индексы колонок (поддерживаем разные варианты названий)
    var statusIndex = headerMap['статус'] !== undefined ? headerMap['статус'] : 
                      headerMap['status'] !== undefined ? headerMap['status'] : 3; // По умолчанию колонка D (индекс 3)
    
    var titleIndex = headerMap['название'] !== undefined ? headerMap['название'] : 
                     headerMap['title'] !== undefined ? headerMap['title'] : 1; // По умолчанию колонка B (индекс 1)
    
    var descriptionIndex = headerMap['описание'] !== undefined ? headerMap['описание'] : 
                           headerMap['description'] !== undefined ? headerMap['description'] : 2; // По умолчанию колонка C (индекс 2)
    
    var startDateIndex = headerMap['дата начала'] !== undefined ? headerMap['дата начала'] : 
                         headerMap['start date'] !== undefined ? headerMap['start date'] : 4; // По умолчанию колонка E (индекс 4)
    
    var endDateIndex = headerMap['дата окончания'] !== undefined ? headerMap['дата окончания'] : 
                       headerMap['end date'] !== undefined ? headerMap['end date'] : 5; // По умолчанию колонка F (индекс 5)
    
    var contentIndex = headerMap['контент'] !== undefined ? headerMap['контент'] : 
                       headerMap['content'] !== undefined ? headerMap['content'] : 6; // По умолчанию колонка G (индекс 6)
    
    // Обрабатываем строки данных (начиная со второй строки)
    var rows = data.slice(1);
    var result = [];
    
    rows.forEach(function(row, rowIndex) {
      // Получаем статус акции
      var status = row[statusIndex];
      
      // Проверяем, что статус равен "Активна" (без учета регистра)
      if (status && String(status).trim().toLowerCase() === 'активна') {
        // Получаем данные акции
        var title = row[titleIndex] || '';
        var description = row[descriptionIndex] || '';
        var startDate = row[startDateIndex] || '';
        var endDate = row[endDateIndex] || '';
        var content = row[contentIndex] || '';
        
        // Если название пустое, используем описание
        if (!title || title === 'None' || title === '') {
          title = description ? 'Акция ' + description : 'Акция без названия';
        }
        
        // Создаем уникальный ID
        var uniqueId = (title + '_' + description + '_' + startDate + '_' + endDate)
          .replace(/\s+/g, '_')
          .replace(/:/g, '')
          .replace(/-/g, '');
        
        // Формируем объект акции в формате, совместимом с promotions_api.py
        var promotion = {
          'id': uniqueId,
          'title': String(title).trim(),
          'description': description ? String(description).trim() : 'Описание отсутствует',
          'status': 'Активна',
          'start_date': startDate ? String(startDate).trim() : '',
          'end_date': endDate ? String(endDate).trim() : ''
        };
        
        // Добавляем контент, если он есть
        if (content && content !== 'None' && content !== '') {
          promotion['content'] = String(content).trim();
        }
        
        // Добавляем акцию в результат, если есть название
        if (promotion['title'] && promotion['title'] !== 'None') {
          result.push(promotion);
        }
      }
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
 * Тестовая функция для проверки работы скрипта
 * Запустите эту функцию в редакторе Apps Script для проверки
 */
function testGetPromotions() {
  var result = doGet({});
  Logger.log(result.getContent());
}
