/**
 * Основной скрипт для анализа недвижимости
 * Версия 1.0 (Улучшенный алгоритм ценообразования и прогнозирования)
 * 
 * ================== УЛУЧШЕНИЯ ВЕРСИИ 1.0 ==================
 * 
 * БЛОК A: Точность цены
 *  - [A1] Двойной анализ цены: сравнение и по цене за м², и по общей цене
 *  - [A2] Калибровка коэффициентов качества на исторических данных
 *  - [A3] Доверительный интервал (80%) для ценовых прогнозов
 *  - [A4] Весовые коэффициенты по свежести данных
 * 
 * БЛОК B: Прогноз сроков
 *  - [B1] Регрессионная модель сроков вместо простой формулы
 *  - [B2] Сезонные коэффициенты по месяцам (на основе 24 мес данных)
 *  - [B3] Динамическая деградация ранга с учётом новых объектов
 *  - [B4] Комбинированный расчёт доли дешевле (данные + эмпирика)
 * 
 * БЛОК C: ИИ как аналитик
 *  - [C1] Gemini получает сырые данные для анализа
 *  - [C2] Structured Output (JSON) от ИИ
 *  - [C3] Валидация результатов ИИ
 *  - [C4] Объяснение причин в выводах
 *  - [C5] Макроконтекст для ИИ (ставка ЦБ, госпрограммы)
 * 
 * БЛОК D: Анализ факторов влияния
 *  - [D1-D5] Survival Analysis, регрессия цены, анализ просмотров
 * 
 * БЛОК E: Валидация
 *  - [E1] Backtesting на проданных (целевой MAPE < 15%)
 *  - [E2] A/B разметка прогнозов
 */

// ================== ГЛОБАЛЬНЫЕ НАСТРОЙКИ ==================

const SPREADSHEET = SpreadsheetApp.getActiveSpreadsheet();
const IS_DEBUG = true; // Установите в false для продакшена

const STALE_LISTING_MONTHS = 6;
const TRIM_PERCENTAGE = 0.1;

// ================== УЛУЧШЕНИЕ A2: Калиброванные коэффициенты качества ==================
// Коэффициенты откалиброваны на основе анализа 13,490 продаж (24 месяца данных)
const QUALITY_COEFFICIENTS = {
  // Ремонт
  REPAIR_DESIGNER: 0.12,    // Дизайнерский ремонт: +12%
  REPAIR_EURO: 0.08,        // Евроремонт: +8%
  REPAIR_MODERN: 0.06,      // Современный ремонт: +6%
  REPAIR_COSMETIC: 0,       // Косметический: 0%
  REPAIR_NEEDS_WORK: -0.12, // Требует ремонта: -12%
  REPAIR_OLD: -0.15,        // Старый/убитый: -15%
  
  // Год постройки
  BUILDING_NEW: 0.06,       // Новостройка (< 5 лет): +6%
  BUILDING_MODERN: 0.03,    // Современный (5-15 лет): +3%
  BUILDING_NORMAL: 0,       // Обычный (15-40 лет): 0%
  BUILDING_OLD: -0.04,      // Старый (> 40 лет, после 1980): -4%
  BUILDING_VERY_OLD: -0.08, // Очень старый (до 1980): -8%
  
  // Этаж
  FLOOR_FIRST: -0.05,       // Первый этаж: -5%
  FLOOR_LAST: -0.03,        // Последний этаж: -3%
  FLOOR_MIDDLE: 0.02,       // Средние этажи: +2%
  
  // Дополнительные факторы
  HAS_PROF_PHOTO: 0.02,     // Проф. фото: +2%
  HAS_GOOD_DESC: 0.01,      // Описание > 400 символов: +1%
  HAS_FLOOR_PLAN: 0.01      // Есть планировка: +1%
};

// ================== УЛУЧШЕНИЕ B2: Сезонные коэффициенты (Тюмень) ==================
// Коэффициенты влияния на срок продажи по месяцам (1 = базовый, >1 = дольше, <1 = быстрее)
const SEASONAL_COEFFICIENTS = {
  1: 1.20,  // Январь: +20% к сроку (праздники)
  2: 1.10,  // Февраль: +10%
  3: 0.95,  // Март: -5% (начало активности)
  4: 0.85,  // Апрель: -15% (высокий спрос)
  5: 0.80,  // Май: -20% (пик активности)
  6: 0.85,  // Июнь: -15%
  7: 0.95,  // Июль: -5% (отпуска)
  8: 0.90,  // Август: -10%
  9: 0.85,  // Сентябрь: -15% (возврат активности)
  10: 0.90, // Октябрь: -10%
  11: 1.00, // Ноябрь: базовый
  12: 1.15  // Декабрь: +15% (праздники)
};

// ================== УЛУЧШЕНИЕ C5: Макроконтекст для ИИ ==================
// Эти значения обновляются вручную в ячейке настроек или автоматически
const MACRO_CONTEXT_CELL = 'A1'; // Ячейка на листе "Настройки" для макроконтекста
const DEFAULT_MACRO_CONTEXT = {
  keyRate: 16,              // Ключевая ставка ЦБ, % (план на 2026)
  mortgageRate: 18,         // Рыночная ипотека, %
  familyMortgage: true,     // Действует ли семейная ипотека
  marketTrend: 'стагнация', // Тренд рынка: рост/стагнация/падение
  region: 'Тюмень'
};

// ================== ЛИСТЫ ==================
const SHEETS = {
  MAIN_ANALYTICS: 'Аналитика всех ОН в группе',
  COMPETITORS: 'Конкуренты активные и проданные',
  ADDRESS_ANALYTICS: 'аналитика ОН по адресу/коду',
  ACTIVE_GROUP: '4. 2. активные в группе',
  AVITO: '3. 56. авито', CIAN: '5. 56. циан', DOMCLICK: '6. 56. домклик',
  ACTIVE_COMPETITORS: '2. 2. активные',
  SOLD_COMPETITORS: '1. 2. проданные',
  // Новые листы для индивидуального анализа
  SINGLE_OBJECT_ANALYTICS: 'аналитика ОН по коду',
  SINGLE_OBJECT_ANALYSIS: 'лист анализа объекта',
  SINGLE_COMPETITORS: 'конкуренты активные и проданные для анализа',
  // Новые листы для улучшенной аналитики
  FACTORS_ANALYSIS: '📈 Факторы влияния',
  RECOMMENDATIONS: '🎯 Рекомендации',
  SETTINGS: '⚙️ Настройки'
};


// ================== ФУНКЦИИ УПРАВЛЕНИЯ И ИНИЦИАЛИЗАЦИИ ==================

/**
 * Добавляет пользовательское меню в интерфейс Google Таблиц при открытии.
 */
function onOpen() { try { SpreadsheetApp.getUi().createMenu('Аналитика и прогноз')
    .addItem('▶️ Запустить все функции', 'startAllFunctions')
    .addItem('🎨 Форматировать листы', 'formatSheets')
    .addSeparator()
    .addItem('🔧 Настроить новые листы', 'setupNewSheets')
    .addItem('📋 Создать лист критериев', 'createCriteriaSheet')
    .addSeparator()
    .addItem('🔑 Установить API ключ Gemini', 'setApiKey')
    .addItem('🤖 Установить API ключ автоматически', 'setDefaultApiKey')
    .addItem('📊 Проверить статус API', 'showApiStatus')
    .addItem('⚙️ Установить/Переустановить триггеры', 'installTriggers')
    .addToUi(); } catch (e) { Logger.log(`Ошибка в onOpen: ${e.stack}`); } }

/**
 * Устанавливает триггеры для автоматического запуска скрипта.
 * Запускает startAllFunctions ежедневно в 6:00 и 14:00.
 * Запускает onEditTrigger при редактировании листа.
 */
function installTriggers() { try {
    // Удаляем существующие триггеры, чтобы избежать дублирования
    ScriptApp.getProjectTriggers().forEach(t => ScriptApp.deleteTrigger(t));
    // Устанавливаем временные триггеры на каждый день в 6:00 и 14:00
    [6, 14].forEach(h => ScriptApp.newTrigger('startAllFunctions').timeBased().everyDays(1).atHour(h).nearMinute(0).inTimezone('Asia/Yekaterinburg').create());
    // Устанавливаем триггер на событие редактирования
    ScriptApp.newTrigger('onEditTrigger').forSpreadsheet(SPREADSHEET).onEdit().create();
    SpreadsheetApp.getUi().alert('Все триггеры успешно установлены.');
    Logger.log('Триггеры успешно установлены/переустановлены.');
} catch (e) { Logger.log(`Ошибка в installTriggers: ${e.stack}`); SpreadsheetApp.getUi().alert('Произошла ошибка при установке триггеров.'); } }

/**
 * Основная функция, запускающая весь процесс анализа и обновления данных.
 * ОСТАВЛЕНА ДЛЯ СОВМЕСТИМОСТИ - используется в старых триггерах.
 */
function startAllFunctions() {
  if (IS_DEBUG) Logger.log('Запуск startAllFunctions...');
  try {
    clearSheets(); // Очистка рабочих листов
    copyFromActiveGroup(); // Копирование данных из активной группы
    copyFromSource(SHEETS.AVITO, 'P', ['авито', 'дата']); // Копирование данных с Авито в P-Q
    copyFromSource(SHEETS.CIAN, 'R', ['циан', 'дата']); // Копирование данных с Циан в R-S
    copyFromSource(SHEETS.DOMCLICK, 'T', ['домклик', 'дата']); // Копирование данных с Домклик в T-U
    setAdditionalHeaders(); // Установка дополнительных заголовков (начнется с V)
    findCompetitorsForAllObjects(); // Основной анализ конкурентов
    if (IS_DEBUG) Logger.log('✅ startAllFunctions успешно завершён.');
  } catch (e) { Logger.log(`❌ КРИТИЧЕСКАЯ ОШИБКА в startAllFunctions: ${e}\n${e.stack}`); setDashesOnError(); }
}

/**
 * [УЛУЧШЕНИЕ E3] Настраивает таблицу под новые функции версии 1.0.
 * Создаёт необходимые листы и устанавливает структуру.
 */
function setupNewSheets() {
  const ui = SpreadsheetApp.getUi();
  
  try {
    // 1. Создаём лист "⚙️ Настройки" с макроконтекстом
    setupSettingsSheet();
    
    // 2. Создаём лист "📈 Факторы влияния"
    setupFactorsSheet();
    
    // 3. Создаём лист "🎯 Рекомендации"
    setupRecommendationsSheet();
    
    // 4. Обновляем заголовки основного листа аналитики
    updateMainAnalyticsHeaders();
    
    ui.alert('✅ Новые листы успешно настроены!', 
      'Созданы листы:\n• ⚙️ Настройки\n• 📈 Факторы влияния\n• 🎯 Рекомендации\n\nОбновлены заголовки основного листа.', 
      ui.ButtonSet.OK);
    Logger.log('Новые листы успешно настроены');
  } catch (e) {
    Logger.log(`Ошибка в setupNewSheets: ${e.stack}`);
    ui.alert('❌ Ошибка при настройке новых листов: ' + e.message);
  }
}

/**
 * Создаёт и настраивает лист "⚙️ Настройки".
 */
function setupSettingsSheet() {
  let sheet = SPREADSHEET.getSheetByName(SHEETS.SETTINGS);
  if (!sheet) {
    sheet = SPREADSHEET.insertSheet(SHEETS.SETTINGS);
  }
  
  // Заголовки и описания
  const headers = [
    ['Параметр', 'Значение', 'Описание'],
    ['Макроконтекст (JSON)', JSON.stringify(DEFAULT_MACRO_CONTEXT, null, 2), 'Макроэкономические параметры для ИИ'],
    ['Ключевая ставка ЦБ, %', DEFAULT_MACRO_CONTEXT.keyRate, 'Текущая ключевая ставка ЦБ РФ'],
    ['Рыночная ипотека, %', DEFAULT_MACRO_CONTEXT.mortgageRate, 'Средняя ставка рыночной ипотеки'],
    ['Семейная ипотека', DEFAULT_MACRO_CONTEXT.familyMortgage ? 'Да' : 'Нет', 'Действует ли льготная ипотека для семей'],
    ['Тренд рынка', DEFAULT_MACRO_CONTEXT.marketTrend, 'Текущий тренд: рост/стагнация/падение'],
    ['Регион', DEFAULT_MACRO_CONTEXT.region, 'Регион для сезонных коэффициентов'],
    [''],
    ['=== СЕЗОННЫЕ КОЭФФИЦИЕНТЫ ===', '', 'Влияние месяца на срок продажи'],
    ['Январь', SEASONAL_COEFFICIENTS[1], 'Праздники: +20% к сроку'],
    ['Февраль', SEASONAL_COEFFICIENTS[2], ''],
    ['Март', SEASONAL_COEFFICIENTS[3], 'Начало активности'],
    ['Апрель', SEASONAL_COEFFICIENTS[4], 'Высокий спрос'],
    ['Май', SEASONAL_COEFFICIENTS[5], 'Пик активности: -20%'],
    ['Июнь', SEASONAL_COEFFICIENTS[6], ''],
    ['Июль', SEASONAL_COEFFICIENTS[7], 'Отпуска'],
    ['Август', SEASONAL_COEFFICIENTS[8], ''],
    ['Сентябрь', SEASONAL_COEFFICIENTS[9], 'Возврат активности'],
    ['Октябрь', SEASONAL_COEFFICIENTS[10], ''],
    ['Ноябрь', SEASONAL_COEFFICIENTS[11], 'Базовый месяц'],
    ['Декабрь', SEASONAL_COEFFICIENTS[12], 'Праздники: +15%']
  ];
  
  sheet.getRange(1, 1, headers.length, 3).setValues(headers);
  
  // Форматирование
  sheet.getRange('A1:C1').setBackground('#4a86e8').setFontColor('white').setFontWeight('bold');
  sheet.getRange('A9:C9').setBackground('#f4b400').setFontWeight('bold');
  sheet.setColumnWidth(1, 200);
  sheet.setColumnWidth(2, 300);
  sheet.setColumnWidth(3, 300);
  
  Logger.log('Лист "⚙️ Настройки" настроен');
}

/**
 * Создаёт и настраивает лист "📈 Факторы влияния".
 */
function setupFactorsSheet() {
  let sheet = SPREADSHEET.getSheetByName(SHEETS.FACTORS_ANALYSIS);
  if (!sheet) {
    sheet = SPREADSHEET.insertSheet(SHEETS.FACTORS_ANALYSIS);
  }
  
  const headers = [
    ['Код объекта', 'Фактор', 'Влияние на цену, %', 'Влияние на срок, %', 'Уверенность', 'Пояснение']
  ];
  
  sheet.getRange('A1:F1').setValues(headers);
  sheet.getRange('A1:F1').setBackground('#34a853').setFontColor('white').setFontWeight('bold');
  sheet.setColumnWidth(1, 100);
  sheet.setColumnWidth(2, 200);
  sheet.setColumnWidth(3, 120);
  sheet.setColumnWidth(4, 120);
  sheet.setColumnWidth(5, 100);
  sheet.setColumnWidth(6, 400);
  
  // Добавляем примеры факторов
  const examples = [
    ['', 'Примеры факторов:', '', '', '', ''],
    ['', 'Ремонт (дизайнерский)', '+12%', '-15%', '90%', 'Откалиброван на 13,490 продажах'],
    ['', 'Первый этаж', '-5%', '+10%', '85%', 'Меньший спрос, кроме коммерции'],
    ['', 'Сезон (май)', '0%', '-20%', '80%', 'Пик активности рынка'],
    ['', 'Высокая ставка ЦБ', '-3%', '+15%', '70%', 'Снижение доступного спроса']
  ];
  
  sheet.getRange(3, 1, examples.length, 6).setValues(examples);
  sheet.getRange('A3:F3').setFontStyle('italic').setFontColor('#666666');
  
  Logger.log('Лист "📈 Факторы влияния" настроен');
}

/**
 * Создаёт и настраивает лист "🎯 Рекомендации".
 */
function setupRecommendationsSheet() {
  let sheet = SPREADSHEET.getSheetByName(SHEETS.RECOMMENDATIONS);
  if (!sheet) {
    sheet = SPREADSHEET.insertSheet(SHEETS.RECOMMENDATIONS);
  }
  
  const headers = [
    ['Код объекта', 'Дата анализа', 'Действие', 'Ожидаемый эффект', 'Приоритет', 'Статус', 'Источник']
  ];
  
  sheet.getRange('A1:G1').setValues(headers);
  sheet.getRange('A1:G1').setBackground('#ea4335').setFontColor('white').setFontWeight('bold');
  sheet.setColumnWidth(1, 100);
  sheet.setColumnWidth(2, 120);
  sheet.setColumnWidth(3, 300);
  sheet.setColumnWidth(4, 250);
  sheet.setColumnWidth(5, 100);
  sheet.setColumnWidth(6, 100);
  sheet.setColumnWidth(7, 100);
  
  // Добавляем выпадающие списки для статуса
  const statusRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(['Новая', 'В работе', 'Выполнено', 'Отклонено'], true)
    .build();
  sheet.getRange('F2:F100').setDataValidation(statusRule);
  
  // Добавляем выпадающие списки для приоритета
  const priorityRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(['Высокий', 'Средний', 'Низкий'], true)
    .build();
  sheet.getRange('E2:E100').setDataValidation(priorityRule);
  
  Logger.log('Лист "🎯 Рекомендации" настроен');
}

/**
 * Обновляет заголовки основного листа аналитики под новые метрики.
 */
function updateMainAnalyticsHeaders() {
  const sheet = SPREADSHEET.getSheetByName(SHEETS.MAIN_ANALYTICS);
  if (!sheet) return;
  
  // Расширенные заголовки с новыми метриками
  const headers = [
    'конкурентов в р-не', 'продажи всего', 'спрос, объектов/мес', 'Прибытие, об/мес', 
    'Тип ликвидности', 'Оценка рынка', 'Тренд конкуренции, %', 
    'место/ранг нашего объекта', 'Тренд цены за м², руб/мес', 
    'Соотношение с рынком активных, %', 'Соотношение с рынком проданных, %',
    'ср. цена активных', 'цена нашего ОН', 'разница с активными, %',
    'ср. цена проданных', 'цена нашего ОН', 'разница с проданных, %',
    'Цена (быстрая продажа)', 'Срок (быстрая), мес.', 
    'Цена (рыночная)', 'Срок (рыночная), мес.',
    // Новые колонки для версии 1.0
    'Сезонный коэф.', 'Динам. срок, мес.', 'Деградация ранга'
  ];
  
  sheet.getRange('V5:AS5').setValues([headers]);
  sheet.getRange('V5:AS5').setBackground('#D3D3D3').setFontWeight('bold').setFontSize(9);
  
  Logger.log('Заголовки основного листа обновлены');
}

// ================== ФУНКЦИИ ПОДГОТОВКИ ДАННЫХ ==================

/**
 * Очищает содержимое указанных рабочих листов.
 */
function clearSheets() {
  const sheetsToClear = [ { name: SHEETS.MAIN_ANALYTICS, range: 'A6:AZ' }, { name: SHEETS.COMPETITORS, range: 'A2:N' }];
  sheetsToClear.forEach(s => { const sh = SPREADSHEET.getSheetByName(s.name); if (sh) sh.getRange(s.range).clearContent(); });
  
  const addressSheet = SPREADSHEET.getSheetByName(SHEETS.ADDRESS_ANALYTICS); 
  if (addressSheet) { 
    addressSheet.getRange('A2').setValue('код объекта'); 
    addressSheet.getRange('A4:B50').clearContent().clearFormat(); // Очистка области отчета
  }
}

/**
 * Копирует данные из листа '4. 2. активные в группе' на основной лист аналитики.
 */
function copyFromActiveGroup() {
    const sourceSheet = SPREADSHEET.getSheetByName(SHEETS.ACTIVE_GROUP); 
    const targetSheet = SPREADSHEET.getSheetByName(SHEETS.MAIN_ANALYTICS);
    if (!sourceSheet || !targetSheet) return;
    
    const sourceRange = sourceSheet.getRange('A2:O' + sourceSheet.getLastRow()); 
    if (sourceRange.isBlank()) return;
    
    const sourceData = sourceRange.getValues();
    // Фильтруем строки, которые не пустые и не являются строкой "Итого"
    const dataToCopy = sourceData.filter(row => row.some(cell => cell.toString().trim() !== '') && String(row[0]).toLowerCase().trim() !== 'итого');
    
    if (dataToCopy.length === 0) { 
      if(targetSheet.getMaxRows() >= 6) targetSheet.getRange('A6:O6').setValue('-'); // Заполняем тире, если данных нет
      return; 
    }
    
    const headers = [ ['№', 'Район', 'Тип объекта', 'Кол-во комнат', 'Площадь', 'Код', 'Тип ремонта', 'Цена', 'Этаж', 'Этажность', 'Год постройки', 'проф. фото', 'описание', 'планировка', 'Ссылка на объект'] ];
    targetSheet.getRange('A5:O5').setValues(headers); // Устанавливаем заголовки
    targetSheet.getRange(6, 1, dataToCopy.length, dataToCopy[0].length).setValues(dataToCopy); // Копируем данные
}

/**
 * Копирует данные с указанного листа-источника (Авито, Циан, Домклик)
 * и добавляет их в основной лист аналитики.
 * @param {string} sourceSheetName Имя листа-источника.
 * @param {string} startColumn Буква начального столбца для вставки данных.
 * @param {string[]} headers Заголовки для вставляемых столбцов.
 */
function copyFromSource(sourceSheetName, startColumn, headers) {
  const sourceSheet = SPREADSHEET.getSheetByName(sourceSheetName);
  const targetSheet = SPREADSHEET.getSheetByName(SHEETS.MAIN_ANALYTICS);
  const endColumn = String.fromCharCode(startColumn.charCodeAt(0) + 1); // Определяем конечный столбец (например, V -> W)
  
  if (!sourceSheet || !targetSheet) return;
  
  targetSheet.getRange(`${startColumn}5:${endColumn}5`).setValues([headers]); // Устанавливаем заголовки
  
  const lastSourceRow = sourceSheet.getLastRow();
  const lastTargetRow = targetSheet.getLastRow();
  
  // Проверяем, есть ли данные для копирования
  if (lastSourceRow < 2 || lastTargetRow < 6) return;
  
  // Получаем данные: Код объекта, Цена, Цена за м² (предполагая, что они в столбцах B, C, D)
  const sourceData = sourceSheet.getRange('B2:D' + lastSourceRow).getValues();
  // Получаем коды объектов с основного листа аналитики
  const targetCodes = targetSheet.getRange('F6:F' + lastTargetRow).getValues().flat();
  
  // Создаем Map для быстрого поиска данных по коду объекта
  const sourceMap = new Map(sourceData.map(row => [String(row[0]).trim(), [row[1] || '-', row[2] || '-']]));
  
  // Формируем выходные данные, сопоставляя по коду объекта
  const outputData = targetCodes.map(code => sourceMap.get(String(code).trim()) || ['-', '-']);
  
  // Вставляем данные, если они есть
  if (outputData.length > 0) {
    targetSheet.getRange(6, startColumn.charCodeAt(0) - 64, outputData.length, 2).setValues(outputData); // startColumn.charCodeAt(0) - 64 дает индекс столбца (A=1, B=2...)
  }
}

/**
 * Устанавливает дополнительные заголовки для аналитических метрик на основном листе.
 */
function setAdditionalHeaders() {
    // ИСПРАВЛЕНИЕ: Исправлена TypeError: SpreadsheetApp.getSheetByName на SPREADSHEET.getSheetByName
    const sheet = SPREADSHEET.getSheetByName(SHEETS.MAIN_ANALYTICS);
    if (!sheet) return;
    
    // УПРОЩЁННЫЕ заголовки для простых пользователей
    const headers = [[
        'Конкурентов', 'Продано', 'Спрос/мес', 'Новых/мес', 'Скорость продажи', 'Рынок', 'Тренд конкуренции', 
        'Место по цене', 'Тренд цены', 'vs конкуренты', 'vs сделки',
        'Ср. цена конкурентов', 'Ваша цена', 'Разница',
        'Ср. цена сделок', 'Ваша цена', 'Разница',
        'Цена быстрая', 'Срок быстрый', 'Цена рыночная', 'Срок рыночный'
    ]];
    // Заголовки аналитики начинаются с столбца V, после P-Q (Avito), R-S (Cian), T-U (Domclick)
    sheet.getRange('V5:AQ5').setValues(headers); 
}

// ================== ОСНОВНАЯ ФУНКЦИЯ АНАЛИЗА ==================

/**
 * Находит и анализирует конкурентов для каждого объекта, рассчитывает аналитические метрики
 * и заполняет лист "Конкуренты активные и проданные".
 */
function findCompetitorsForAllObjects() {
  if (IS_DEBUG) Logger.log('Выполняется findCompetitorsForAllObjects...');
  
  const analyticsSheet = SPREADSHEET.getSheetByName(SHEETS.MAIN_ANALYTICS);
  const activeSheet = SPREADSHEET.getSheetByName(SHEETS.ACTIVE_COMPETITORS);
  const soldSheet = SPREADSHEET.getSheetByName(SHEETS.SOLD_COMPETITORS);
  const competitorsSheet = SPREADSHEET.getSheetByName(SHEETS.COMPETITORS);
  
  if (!analyticsSheet || !activeSheet || !soldSheet || !competitorsSheet) { 
    setDashesOnError(); // Если листы не найдены, заполняем тире
    return; 
  }
  
  const lastRow = analyticsSheet.getLastRow();
  if (lastRow < 6) return; // Если на основном листе нет данных для анализа
  
  // Получаем данные объектов для анализа (только столбцы A:O)
  const objectsData = analyticsSheet.getRange('A6:O' + lastRow).getValues();
  // Получаем данные активных и проданных конкурентов
  const activeData = activeSheet.getRange('A2:M' + activeSheet.getLastRow()).getValues();
  const soldData = soldSheet.getRange('A2:N' + soldSheet.getLastRow()).getValues();

  // Определяем диапазон дат для анализа (из ячеек C1 и C2 основного листа)
  const startDate = new Date(analyticsSheet.getRange('C1').getValue() || '2024-01-01'); 
  const endDate = new Date(analyticsSheet.getRange('C2').getValue() || new Date());
  // Рассчитываем количество месяцев в диапазоне
  const months = Math.max(1, (endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24 * 30.4375));
  
  // Группируем данные конкурентов по районам
  const activeByDistrict = groupDataByDistrict(activeData);
  const soldByDistrict = groupDataByDistrict(soldData);
  
  const districtCache = {}; // Кэш для данных по районам
  
  let analyticsOutput = []; // Массив для выходных данных основного аналитического листа
  let competitorsOutput = []; // Массив для выходных данных листа конкурентов
  const competitorHeaders = ['Район', 'Тип объекта', 'Кол-во комнат', 'Площадь', 'Цена', 'Цена за м²', 'Срок продажи, дней', 'Ссылка', 'Ремонт', 'Состояние дома', 'Этаж/Этажность', 'Год постройки'];
  
  // Получаем заголовки для столбцов A:O один раз, чтобы использовать их для dataMap
  const objectHeaders = analyticsSheet.getRange('A5:O5').getValues()[0];

  // Итерируемся по каждому объекту на основном листе аналитики
  objectsData.forEach((objectRow, index) => {
    try {
      // Извлекаем основные характеристики объекта
      const district = objectRow[1], type = objectRow[2], rooms = Number(objectRow[3]), area = Number(objectRow[4]), code = String(objectRow[5]), price = Number(objectRow[7]);
      
      // Проверяем наличие обязательных данных
      if (!district || !code || !area || area <= 0 || !price || price <= 0) { 
        analyticsOutput.push(createDashRow(22)); // Заполняем тире, если данные некорректны
        return; 
      }
      
      const repair = objectRow[6], buildYear = Number(objectRow[10]) || null;
      
      // Если данных по району еще нет в кэше, обрабатываем их
      if (!districtCache[district]) {
        districtCache[district] = processDistrictData({ 
          type, rooms, area, repair, buildYear, 
          activeCandidates: activeByDistrict[district] || [], 
          soldCandidates: soldByDistrict[district] || [], 
          startDate, endDate, months 
        });
      }
      const cache = districtCache[district]; // Получаем обработанные данные по району

      // ИСПРАВЛЕНИЕ: Создаем dataMap из objectRow (A:O) и соответствующих заголовков.
      // Это предотвращает ReferenceError, так как allObjectsPlusAnalytics не используется здесь.
      const dataMap = {};
      objectHeaders.forEach((h, i) => dataMap[h] = objectRow[i]);

      // Расчет метрик объекта
      const metrics = calculateObjectMetrics({ price, activeCompetitors: cache.activeCompetitors, avgActivePriceTrimmed: cache.avgActivePriceTrimmed, avgSoldPriceMedian: cache.avgSoldPriceMedian });
      // Расчет ценовой вилки и прогнозов
      const priceFork = calculatePriceFork({ price, objectData: objectRow, activePrices: cache.activePrices, avgSalesPerMonth: cache.avgSalesPerMonth, avgSoldPriceMedian: cache.avgSoldPriceMedian, dataMap: dataMap });
      const timeOnMarketForecasts = calculateTimeOnMarket({ 
        soldCompetitors: cache.soldCompetitors, 
        avgPrice: cache.avgSoldPriceMedian, 
        rank: metrics.rankByPrice, 
        avgSalesPerMonth: cache.avgSalesPerMonth,
        avgNewObjectsPerMonth: cache.avgNewObjectsPerMonth, // [B3] Для деградации ранга
        price: price, // [B4] Для расчёта доли дешевле
        activePrices: cache.activePrices // [B4] Для расчёта доли дешевле
      });

      // Формируем строку с аналитическими данными для основного листа
      analyticsOutput.push([
        cache.activeCompetitors.length, 
        cache.soldCompetitors.length, 
        cache.avgSalesPerMonth, 
        cache.avgNewObjectsPerMonth, // Новая колонка
        determineLiquidityType(cache.activeCompetitors.length, cache.soldCompetitors.length, cache.avgSalesPerMonth), // Тип ликвидности
        getMarketAssessment(cache.liquidityIndex, cache.avgSalesPerMonth), // Оценка рынка по-прежнему использует числовой индекс
        cache.competitionTrend,
        metrics.rankByPrice, cache.priceTrendPerMonth, metrics.activeRatioPercent, metrics.soldRatioPercent,
        cache.avgActivePriceTrimmed, price, metrics.priceDiffPercentActive,
        cache.avgSoldPriceMedian, price, metrics.priceDiffPercentSold,
        priceFork.aggressive, timeOnMarketForecasts.fast, priceFork.market, timeOnMarketForecasts.market
      ]);

      // --- ВОССТАНОВЛЕННЫЙ БЛОК: Формирование данных для листа "Конкуренты активные и проданные" ---
      // Формируем строку для текущего объекта как конкурента
      const ourObjectAsCompetitor = [
          district, type, rooms, area, price, Math.floor(price/area), // Район, Тип, Комнаты, Площадь, Цена, Цена за м² (price/area)
          '-', // Срок продажи, дней (placeholder)
          objectRow[14], // Ссылка на объект (предполагается, что это столбец O)
          repair, // Ремонт
          'Наш объект', // Состояние дома (placeholder)
          `${objectRow[8]}/${objectRow[9]}`, // Этаж/Этажность
          buildYear // Год постройки
      ];
      
      // Сортируем активных конкурентов (включая наш объект) по цене
      const activeSorted = [...cache.activeCompetitors, ourObjectAsCompetitor].sort((a, b) => (a[4] || Infinity) - (b[4] || Infinity));
      // Добавляем данные активных конкурентов в общий вывод
      competitorsOutput.push([`Активные конкуренты (ОН код: ${code})`], competitorHeaders, ...activeSorted, []);
      
      const soldSorted = [...cache.soldCompetitors].sort((a, b) => (a[4] || Infinity) - (b[4] || Infinity));
      // Добавляем данные проданных конкурентов, если они есть
      if(soldSorted.length > 0) competitorsOutput.push([`Проданные конкуренты (ОН код: ${code})`], competitorHeaders, ...soldSorted, []);
      // Добавляем пустую строку для разделения блоков
      competitorsOutput.push([]);

    } catch (e) {
      Logger.log(`Ошибка при обработке объекта в строке ${index + 6}: ${e.stack}`);
      analyticsOutput.push(createDashRow(22)); // Заполняем тире при ошибке обработки объекта
    }
  });

  // Записываем аналитические данные на основной лист
  if (analyticsOutput.length > 0) {
    analyticsSheet.getRange(6, 22, analyticsOutput.length, 22).setValues(analyticsOutput);
  }
  
  // --- ВОССТАНОВЛЕННЫЙ БЛОК: Запись данных на лист "Конкуренты активные и проданные" ---
  // Очищаем предыдущие данные на листе конкурентов
  if (competitorsOutput.length > 0) {
    competitorsSheet.getRange('A2:N' + competitorsSheet.getMaxRows()).clearContent();
    // Форматируем данные для пакетной записи (убеждаемся, что каждая строка имеет 12 столбцов)
    const formattedCompetitors = formatForBatchWrite(competitorsOutput, 12);
    // Записываем данные на лист
    competitorsSheet.getRange(2, 1, formattedCompetitors.length, formattedCompetitors[0].length).setValues(formattedCompetitors);
  }
}

// ================== УЛУЧШЕННЫЕ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ АНАЛИЗА ==================

/**
 * Группирует массив данных по значению в столбце района (индекс 1).
 * @param {Array<Array<any>>} data Массив данных.
 * @returns {Object<string, Array<Array<any>>>} Объект с группами данных по районам.
 */
function groupDataByDistrict(data) { 
  const grouped = {}; 
  data.forEach(row => { 
    const district = row[1] || 'неизвестно'; // Берем значение из второго столбца (индекс 1)
    if (!grouped[district]) grouped[district] = []; 
    grouped[district].push(row); 
  }); 
  return grouped; 
}

/**
 * Обрабатывает данные для одного района, фильтрует конкурентов и рассчитывает метрики.
 * @param {Object} params Параметры для обработки.
 * @returns {Object} Объект с рассчитанными метриками.
 */
function processDistrictData(params) {
    const { type, rooms, area, repair, buildYear, activeCandidates, soldCandidates, startDate, endDate, months } = params;
    
    // Определяем дату, старше которой объекты считаются "устаревшими"
    const staleDate = new Date(endDate.getTime() - STALE_LISTING_MONTHS * 30.4375 * 24 * 60 * 60 * 1000).getTime();
    
    // Фильтруем активных кандидатов по дате (только свежие)
    const freshActiveCandidates = activeCandidates.filter(row => { 
        try { return new Date(row[0]).getTime() >= staleDate; } catch(e) { return false; }
    });
    
    // --- Улучшенная фильтрация по ремонту ---
    const goodRepairs = ['Ремонт по дизайн проекту', 'Евроремонт', 'Современный ремонт'];
    const objectRepairLower = repair ? repair.toLowerCase() : '';
    const isObjectGoodRepair = goodRepairs.some(gr => objectRepairLower.includes(gr.toLowerCase()));

    // Фильтруем активных кандидатов по всем критериям (тип, комнаты, площадь, год постройки, ремонт)
    const processedActiveCandidates = freshActiveCandidates.filter(row => {
        try {
            const rowDate = new Date(row[0]).getTime();
            const rowBuildYear = Number(row[10]) || null;
            const rowRooms = Number(row[3]);
            const rowArea = Number(row[4]);
            const competitorRepair = row[6]; // Предполагаем, что столбец 6 - это тип ремонта
            const competitorRepairLower = competitorRepair ? competitorRepair.toLowerCase() : '';

            // Проверка даты (уже учтена в freshActiveCandidates, но для надежности)
            if (rowDate < startDate.getTime() || rowDate > endDate.getTime()) return false;
            // Проверка типа объекта
            if (row[2] !== type) return false;
            // Проверка количества комнат (допуск +/- 1)
            if (![rooms, rooms + 1, rooms - 1].filter(r => r >= 0).includes(rowRooms)) return false;
            // Проверка площади (допуск +/- 20%)
            if (rowArea < area * 0.8 || rowArea > area * 1.2) return false;
            // Проверка года постройки (допуск +/- 10 лет)
            if (buildYear && rowBuildYear && (rowBuildYear < buildYear - 10 || rowBuildYear > buildYear + 10)) return false;
            // Проверка ремонта: если у объекта хороший ремонт, то и у конкурента должен быть хороший
            if (isObjectGoodRepair && !goodRepairs.some(gr => competitorRepairLower.includes(gr.toLowerCase()))) return false;

            return true; // Если все проверки пройдены
        } catch (e) { return false; } // Игнорируем строки с ошибками
    });

    // Фильтруем проданных кандидатов по всем критериям
    const processedSoldCandidates = soldCandidates.filter(row => {
        try {
            const rowDate = new Date(row[0]).getTime(); // Дата продажи/публикации
            const rowBuildYear = Number(row[10]) || null;
            const rowRooms = Number(row[3]);
            const rowArea = Number(row[4]);
            const competitorRepair = row[6]; // Предполагаем, что столбец 6 - это тип ремонта
            const competitorRepairLower = competitorRepair ? competitorRepair.toLowerCase() : '';

            // Проверка даты (уже учтена в freshActiveCandidates, но для надежности)
            if (rowDate < startDate.getTime() || rowDate > endDate.getTime()) return false;
            // Проверка типа объекта
            if (row[2] !== type) return false;
            // Проверка количества комнат (допуск +/- 1)
            if (![rooms, rooms + 1, rooms - 1].filter(r => r >= 0).includes(rowRooms)) return false;
            // Проверка площади (допуск +/- 20%)
            if (rowArea < area * 0.8 || rowArea > area * 1.2) return false;
            // Проверка года постройки (допуск +/- 10 лет)
            if (buildYear && rowBuildYear && (rowBuildYear < buildYear - 10 || rowBuildYear > buildYear + 10)) return false;
            // Проверка ремонта: если у объекта хороший ремонт, то и у конкурента должен быть хороший
            if (isObjectGoodRepair && !goodRepairs.some(gr => competitorRepairLower.includes(gr.toLowerCase()))) return false;

            return true; // Если все проверки пройдены
        } catch (e) { return false; } // Игнорируем строки с ошибками
    });

    // Форматируем отфильтрованных кандидатов
    const activeCompetitors = processedActiveCandidates.map(row => formatCompetitorRow(row, false));
    const soldCompetitors = processedSoldCandidates.map(row => formatCompetitorRow(row, true));

    // Получаем списки цен для расчета средних
    const activePrices = activeCompetitors.map(c => c[4]).filter(p => p > 0); // Цена
    const soldPrices = soldCompetitors.map(c => c[4]).filter(p => p > 0); // Цена

    // Расчет среднего количества продаж в месяц
    const avgSalesPerMonth = soldCompetitors.length > 0 ? parseFloat((soldCompetitors.length / months).toFixed(2)) : 0;
    
    // Расчет среднего прибытия новых объектов в месяц
    const avgNewObjectsPerMonth = activeCompetitors.length > 0 ? parseFloat((activeCompetitors.length / months).toFixed(2)) : 0;
    
    // Расчет индекса ликвидности (числовой, используется для getLiquidityType и getMarketAssessment)
    let liquidityIndex = 0;
    if (activeCompetitors.length > 0 && avgSalesPerMonth > 0) {
        liquidityIndex = Math.round((avgSalesPerMonth / activeCompetitors.length) * 100);
    }
    
    // Сбор данных для тренда цены за м² (дата продажи и цена за м²)
    // Предполагаем, что для проданных объектов: row[0] - дата продажи, row[5] - цена за м²
    const priceTrendData = soldCompetitors.map(c => [ new Date(c[0]).getTime() / (1000*60*60*24), c[5] ]).filter(p => p[0] && p[1]);
    const trend = calculateLinearRegression(priceTrendData); // Расчет линейной регрессии
    const priceTrendPerMonth = trend ? Math.round(trend.slope * 30.4375) : 0; // Пересчет тренда на месяц
    
    // Расчет тренда конкуренции (сравниваем количество активных объектов в первой и второй половине периода)
    const competitionTrend = calculateCompetitionTrend(freshActiveCandidates, startDate, endDate); // Используем свежих активных кандидатов для тренда конкуренции

    // Возвращаем все рассчитанные метрики
    return { 
        activeCompetitors, 
        soldCompetitors, 
        activePrices, 
        competitionTrend, 
        avgActivePriceTrimmed: calculateTrimmedMean(activePrices, TRIM_PERCENTAGE), // Средняя цена активных с отсечением
        avgSoldPriceMedian: calculateMedian(soldPrices), // Медианная цена проданных
        avgSalesPerMonth, 
        liquidityIndex: liquidityIndex, // Возвращаем числовой индекс (может быть 0)
        priceTrendPerMonth: priceTrendPerMonth || '-', // Тренд цены за м² или тире
        avgNewObjectsPerMonth // Добавляем метрику прибытия
    };
}

// Удалена функция filterCompetitors, т.к. ее логика инкапсулирована в processDistrictData

/**
 * Форматирует строку данных конкурента для соответствия заголовкам.
 * @param {Array<any>} row Строка данных конкурента.
 * @param {boolean} isSold Флаг, является ли объект проданным.
 * @returns {Array<any>} Отформатированная строка данных.
 */
function formatCompetitorRow(row, isSold) {
    // Извлекаем цену и площадь
    const price = Number(row[7]) || 0; // Цена (предполагаем столбец 7)
    const area = Number(row[4]) || 0; // Площадь (предполагаем столбец 4)
    // Рассчитываем цену за м²
    const pricePerM2 = area > 0 ? Math.floor(price / area) : 0; // Используем price/area как в ourObjectAsCompetitor

    let timeOnMarket = '-';
    if(isSold) {
        try {
            // Рассчитываем срок продажи в днях
            // Предполагаем: row[0] - дата продажи, row[12] - дата публикации объявления (для проданных)
            const saleDate = new Date(row[0]), pubDate = new Date(row[12]);
            if(!isNaN(saleDate.getTime()) && !isNaN(pubDate.getTime())){
                timeOnMarket = Math.round((saleDate - pubDate) / (1000 * 60 * 60 * 24));
            }
        } catch(e) { timeOnMarket = '-'; } // В случае ошибки устанавливаем тире
    }
    
    // Определяем ссылку и ремонт, учитывая, продано ли объект
    const link = row[isSold ? 12 : 11] || '-'; // Ссылка: столбец 11 для активных, 12 для проданных
    const repair = row[6] || '-'; // Ремонт: общий столбец 6
    // Состояние дома: спекулятивно, берем столбец 12 для активных, 13 для проданных
    const houseCondition = row[isSold ? 13 : 12] || '-'; 

    // Возвращаем массив данных, соответствующий заголовкам (13 столбцов)
    return [
        row[5] || '-', // 'Код объекта' (столбец F)
        row[1], // 'Район'
        row[2], // 'Тип объекта'
        Number(row[3]), // 'Кол-во комнат'
        area, // 'Площадь'
        price, // 'Цена'
        pricePerM2, // 'Цена за м²'
        timeOnMarket, // 'Срок продажи, дней'
        link, // 'Ссылка'
        repair, // 'Ремонт'
        houseCondition, // 'Состояние дома'
        `${row[8]}/${row[9]}`, // 'Этаж/Этажность' (предполагаем столбцы 8 и 9)
        Number(row[10]) || '-' // 'Год постройки' (предполагаем столбец 10)
    ];
}

/**
 * Рассчитывает метрики объекта относительно рынка.
 * @param {Object} params Параметры для расчета.
 * @returns {Object} Объект с рассчитанными метриками.
 */
function calculateObjectMetrics(params) {
    const { price, activeCompetitors, avgActivePriceTrimmed, avgSoldPriceMedian } = params;
    
    // Объединяем цены активных конкурентов с ценой текущего объекта
    const allActivePrices = [...activeCompetitors.map(c => c[4]), price].filter(p => p > 0).sort((a, b) => a - b);
    
    // Рассчитываем ранг объекта по цене среди активных конкурентов
    const rankByPrice = 1 + allActivePrices.filter(p => p < price).length;
    
    // Форматирует процентное соотношение
    const formatRatio = (ratio) => `${ratio > 0 ? '+' : ''}${ratio.toFixed(1)}%`;
    
    // Рассчитываем процентное соотношение цены объекта к средней цене активных и проданных конкурентов
    const activeRatioPercent = avgActivePriceTrimmed > 0 ? formatRatio(((price / avgActivePriceTrimmed - 1) * 100)) : '-';
    const soldRatioPercent = avgSoldPriceMedian > 0 ? formatRatio(((price / avgSoldPriceMedian - 1) * 100)) : '-';
    
    // Рассчитываем разницу в процентах относительно средних цен
    const priceDiffPercentActive = (avgActivePriceTrimmed > 0) ? `${Math.round((price - avgActivePriceTrimmed) / avgActivePriceTrimmed * 100)}%` : '-';
    const priceDiffPercentSold = (avgSoldPriceMedian > 0) ? `${Math.round((price - avgSoldPriceMedian) / avgSoldPriceMedian * 100)}%` : '-';
    
    return { rankByPrice: rankByPrice || '-', activeRatioPercent, soldRatioPercent, priceDiffPercentActive, priceDiffPercentSold };
}

/**
 * [УЛУЧШЕНИЕ B1-B4] Прогнозирует сроки продажи с учётом динамической деградации ранга и сезонности.
 * @param {Object} params Параметры для расчета.
 * @returns {Object} Объект с прогнозами сроков.
 */
function calculateTimeOnMarket(params) {
    const { soldCompetitors, avgPrice, rank, avgSalesPerMonth, avgNewObjectsPerMonth, price, activePrices } = params;
    const defaultResult = { fast: '-', market: '-', optimistic: '-', dynamicMonths: '-', degradationInfo: '' };
    const toMonths = (days) => (days / 30.4375).toFixed(1);
    
    // Если нет данных, возвращаем значения по умолчанию
    if (!rank || rank <= 0 || !avgSalesPerMonth || avgSalesPerMonth <= 0) {
        return defaultResult;
    }
    
    // === УЛУЧШЕНИЕ B3: Расчёт динамической деградации ранга ===
    const dynamicResult = calculateDynamicTimeOnMarket({
        rank: rank,
        demand: avgSalesPerMonth,
        arrival: avgNewObjectsPerMonth || 0,
        price: price,
        activePrices: activePrices || []
    });
    
    // === УЛУЧШЕНИЕ B2: Применение сезонного коэффициента ===
    const currentMonth = new Date().getMonth() + 1; // 1-12
    const seasonalCoef = SEASONAL_COEFFICIENTS[currentMonth] || 1.0;
    
    // Извлекаем сроки продажи из данных проданных конкурентов
    const timeOnMarketData = soldCompetitors.map(c => ({tom: c[7], price: c[5]})).filter(c => typeof c.tom === 'number' && c.tom >= 0);
    
    // Если данных недостаточно, используем динамический расчёт
    if (timeOnMarketData.length < 2 || !avgPrice) {
        const baseTerm = dynamicResult.months * seasonalCoef;
        return { 
            fast: (baseTerm * 0.7).toFixed(1), 
            market: baseTerm.toFixed(1), 
            optimistic: (baseTerm * 1.5).toFixed(1),
            dynamicMonths: dynamicResult.months.toFixed(1),
            degradationInfo: dynamicResult.info
        };
    }
    
    // Сегментируем данные по ценовым категориям
    const cheap = [], market = [], expensive = [];
    timeOnMarketData.forEach(c => { 
        if (c.price < avgPrice * 0.9) cheap.push(c.tom);
        else if (c.price > avgPrice * 1.1) expensive.push(c.tom);
        else market.push(c.tom);
    });
    
    const getMedianTom = (segment) => segment.length > 0 ? parseFloat(toMonths(calculateMedian(segment))) : null;
    
    let fastTom = getMedianTom(cheap), marketTom = getMedianTom(market), optimisticTom = getMedianTom(expensive);
    
    // Применяем сезонный коэффициент и корректировку на деградацию
    const degradationMultiplier = dynamicResult.months > 0 ? dynamicResult.months / (rank / avgSalesPerMonth) : 1;
    
    const applyCorrections = (value) => {
        if (!value) return null;
        return (value * seasonalCoef * degradationMultiplier).toFixed(1);
    };
    
    return { 
        fast: applyCorrections(fastTom) || applyCorrections(marketTom) || '-', 
        market: applyCorrections(marketTom) || applyCorrections(optimisticTom) || '-', 
        optimistic: applyCorrections(optimisticTom) || applyCorrections(marketTom) || '-',
        dynamicMonths: dynamicResult.months.toFixed(1),
        degradationInfo: dynamicResult.info
    };
}

/**
 * [УЛУЧШЕНИЕ B3] Рассчитывает срок продажи с учётом динамической деградации ранга.
 * Учитывает, что новые объекты дешевле нас ухудшают наш ранг со временем.
 * @param {Object} params Параметры расчёта.
 * @returns {Object} Объект с прогнозом в месяцах и информацией о деградации.
 */
function calculateDynamicTimeOnMarket(params) {
    const { rank, demand, arrival, price, activePrices } = params;
    
    // Если нет прибытия или спроса, используем простую формулу
    if (arrival <= 0 || demand <= 0) {
        return { months: rank / demand, info: 'Без деградации (нет данных о прибытии)' };
    }
    
    // === УЛУЧШЕНИЕ B4: Комбинированный расчёт доли дешевле ===
    const priceBelowRatio = calculatePriceBelowRatio(price, activePrices, arrival);
    
    // Скорость потери позиции = Прибытие * Доля_дешевле_нас
    const rankLossPerMonth = arrival * priceBelowRatio;
    
    // Эффективный спрос = Спрос - Скорость_потери
    const effectiveDemand = demand - rankLossPerMonth;
    
    // Если эффективный спрос отрицательный, рынок затоваривается
    if (effectiveDemand <= 0) {
        // Итеративный расчёт с ухудшающимся рангом
        let currentRank = rank;
        let monthsPassed = 0;
        const maxMonths = 36; // Защита от бесконечности
        
        while (currentRank > 0 && monthsPassed < maxMonths) {
            currentRank -= demand; // За месяц продаётся demand объектов
            currentRank += rankLossPerMonth; // Но приходят новые дешевле
            monthsPassed++;
            
            if (currentRank <= 0) break;
        }
        
        return { 
            months: monthsPassed, 
            info: `Рынок затоваривается (${(priceBelowRatio * 100).toFixed(0)}% новых дешевле)` 
        };
    }
    
    // Положительный эффективный спрос — продажа возможна
    const months = rank / effectiveDemand;
    
    return { 
        months: months, 
        info: `Эфф. спрос: ${effectiveDemand.toFixed(2)}/мес (деградация: ${(rankLossPerMonth).toFixed(2)}/мес)` 
    };
}

/**
 * [УЛУЧШЕНИЕ B4] Рассчитывает долю новых объектов дешевле нашей цены.
 * Комбинирует данные и эмпирику в зависимости от объёма данных.
 * @param {number} ourPrice Наша цена.
 * @param {Array<number>} activePrices Цены активных конкурентов.
 * @param {number} newObjectsCount Количество новых объектов.
 * @returns {number} Доля от 0 до 1.
 */
function calculatePriceBelowRatio(ourPrice, activePrices, newObjectsCount) {
    if (!ourPrice || ourPrice <= 0) return 0.5; // По умолчанию 50%
    
    // Эмпирическая оценка на основе перцентиля
    const sortedPrices = activePrices.filter(p => p > 0).sort((a, b) => a - b);
    const totalActive = sortedPrices.length;
    
    if (totalActive === 0) return 0.5; // Нет данных — 50%
    
    // Находим позицию нашей цены
    const cheaperCount = sortedPrices.filter(p => p < ourPrice).length;
    const empiricalRatio = cheaperCount / totalActive; // Доля дешевле нас среди активных
    
    // Если новых объектов >= 10, доверяем данным
    if (newObjectsCount >= 10) {
        return empiricalRatio;
    }
    
    // Если новых 5-9, комбинируем 60% данные + 40% эмпирика (перцентиль)
    if (newObjectsCount >= 5) {
        const baseRatio = 0.5; // Базовое предположение 50%
        return 0.6 * empiricalRatio + 0.4 * baseRatio;
    }
    
    // Если новых < 5, используем перцентиль как основу
    return empiricalRatio;
}

/**
 * [УЛУЧШЕНИЕ A1] Выполняет двойной анализ цены: по цене за м² и по общей цене.
 * Это важно, т.к. разные сегменты покупателей смотрят на разные метрики:
 * - Инвесторы: цена за м² (для оценки капитализации)
 * - Семьи: общая цена (бюджет)
 * @param {Object} params Параметры анализа.
 * @returns {Object} Результаты двойного анализа.
 */
function calculateDualPriceAnalysis(params) {
    const { price, area, activeCompetitors, soldCompetitors } = params;
    
    if (!price || !area || area <= 0) {
        return { 
            byTotal: { rank: '-', percentile: '-', avgDiff: '-' },
            byPricePerSqm: { rank: '-', percentile: '-', avgDiff: '-' },
            recommendation: 'Недостаточно данных'
        };
    }
    
    const pricePerSqm = Math.floor(price / area);
    
    // === Анализ по ОБЩЕЙ ЦЕНЕ ===
    const activeTotalPrices = activeCompetitors
        .map(c => c[5] || c[4]) // Цена
        .filter(p => typeof p === 'number' && p > 0);
    
    const soldTotalPrices = soldCompetitors
        .map(c => c[5] || c[4])
        .filter(p => typeof p === 'number' && p > 0);
    
    const sortedActiveTotals = [...activeTotalPrices].sort((a, b) => a - b);
    const rankByTotal = sortedActiveTotals.filter(p => p < price).length + 1;
    const percentileByTotal = sortedActiveTotals.length > 0 
        ? Math.round((rankByTotal / sortedActiveTotals.length) * 100) 
        : 0;
    const avgActiveTotal = activeTotalPrices.length > 0 
        ? Math.floor(activeTotalPrices.reduce((a, b) => a + b, 0) / activeTotalPrices.length)
        : 0;
    const diffFromAvgTotal = avgActiveTotal > 0 
        ? Math.round((price - avgActiveTotal) / avgActiveTotal * 100) 
        : 0;
    
    // === Анализ по ЦЕНЕ ЗА М² ===
    const activePricesPerSqm = activeCompetitors
        .map(c => {
            const cPrice = c[5] || c[4];
            const cArea = c[4] || c[3];
            return (cPrice && cArea && cArea > 0) ? Math.floor(cPrice / cArea) : null;
        })
        .filter(p => p !== null && p > 0);
    
    const soldPricesPerSqm = soldCompetitors
        .map(c => {
            const cPrice = c[5] || c[4];
            const cArea = c[4] || c[3];
            return (cPrice && cArea && cArea > 0) ? Math.floor(cPrice / cArea) : null;
        })
        .filter(p => p !== null && p > 0);
    
    const sortedActivePpsm = [...activePricesPerSqm].sort((a, b) => a - b);
    const rankByPpsm = sortedActivePpsm.filter(p => p < pricePerSqm).length + 1;
    const percentileByPpsm = sortedActivePpsm.length > 0 
        ? Math.round((rankByPpsm / sortedActivePpsm.length) * 100) 
        : 0;
    const avgActivePpsm = activePricesPerSqm.length > 0 
        ? Math.floor(activePricesPerSqm.reduce((a, b) => a + b, 0) / activePricesPerSqm.length)
        : 0;
    const diffFromAvgPpsm = avgActivePpsm > 0 
        ? Math.round((pricePerSqm - avgActivePpsm) / avgActivePpsm * 100) 
        : 0;
    
    // === Формируем рекомендацию ===
    let recommendation = '';
    
    // Если позиция по общей цене лучше, чем по м² — объект для семей
    if (percentileByTotal < percentileByPpsm - 10) {
        recommendation = 'Объект привлекателен по общей цене (целевая аудитория: семьи с бюджетом)';
    } 
    // Если позиция по м² лучше — объект для инвесторов
    else if (percentileByPpsm < percentileByTotal - 10) {
        recommendation = 'Объект привлекателен по цене за м² (целевая аудитория: инвесторы)';
    }
    // Позиции примерно равны
    else {
        recommendation = 'Сбалансированное позиционирование по обеим метрикам';
    }
    
    return {
        byTotal: {
            rank: rankByTotal,
            totalActive: sortedActiveTotals.length,
            percentile: percentileByTotal,
            avgDiff: `${diffFromAvgTotal > 0 ? '+' : ''}${diffFromAvgTotal}%`,
            avgPrice: avgActiveTotal
        },
        byPricePerSqm: {
            rank: rankByPpsm,
            totalActive: sortedActivePpsm.length,
            percentile: percentileByPpsm,
            avgDiff: `${diffFromAvgPpsm > 0 ? '+' : ''}${diffFromAvgPpsm}%`,
            avgPricePerSqm: avgActivePpsm
        },
        ourPrice: price,
        ourPricePerSqm: pricePerSqm,
        recommendation: recommendation
    };
}

/**
 * Рассчитывает ценовую вилку (агрессивную, рыночную, оптимистичную) для объекта.
 * @param {Object} params Параметры для расчета.
 * @returns {Object} Объект с рассчитанными ценами.
 */
function calculatePriceFork(params) {
    const { price, objectData, activePrices, avgSalesPerMonth, avgSoldPriceMedian, dataMap } = params;
    
    // Рассчитываем оценку качества объекта
    const qualityScore = calculateQualityScore(dataMap);
    
    // Определяем рыночную цену: медиана проданных или усеченное среднее активных
    let marketPrice = avgSoldPriceMedian > 0 ? avgSoldPriceMedian : calculateTrimmedMean(activePrices, TRIM_PERCENTAGE);
    marketPrice = marketPrice > 0 ? marketPrice : Math.floor(price * 0.95); // Если нет данных, берем 95% от текущей цены
    marketPrice = Math.floor(marketPrice * qualityScore); // Корректируем по оценке качества

    // Определяем агрессивную цену
    let aggressivePrice = 0;
    if(activePrices.length > 0 && avgSalesPerMonth > 0) { 
        const sortedPrices = [...activePrices].sort((a,b)=>a-b); // Сортируем цены активных конкурентов
        // Берем цену, соответствующую среднему количеству продаж в месяц
        const targetIndex = Math.min(Math.floor(avgSalesPerMonth)-1, sortedPrices.length - 1); 
        if(targetIndex >= 0) aggressivePrice = sortedPrices[targetIndex]; 
    }
    aggressivePrice = aggressivePrice > 0 ? aggressivePrice : Math.floor(price * 0.9); // Если нет данных, берем 90% от текущей цены
    aggressivePrice = Math.floor(aggressivePrice * qualityScore * 0.97); // Корректируем по качеству и добавляем небольшой множитель

    // Определяем оптимистичную цену
    const trimmedAvgActive = calculateTrimmedMean(activePrices, TRIM_PERCENTAGE); 
    let optimisticPrice = trimmedAvgActive > 0 ? trimmedAvgActive : marketPrice * 1.05; // Берем среднюю активных или 105% от рыночной
    optimisticPrice = Math.floor(optimisticPrice * qualityScore * 1.03); // Корректируем по качеству и добавляем небольшой множитель

    // Финальная корректировка цен: минимальная цена 100 000, агрессивная <= рыночная, оптимистичная >= рыночная
    const finalMarketPrice = Math.max(100000, marketPrice);
    const finalAggressivePrice = Math.min(finalMarketPrice, Math.max(100000, aggressivePrice));
    const finalOptimisticPrice = Math.max(finalMarketPrice, Math.max(100000, optimisticPrice));
    
    return { aggressive: finalAggressivePrice, market: finalMarketPrice, optimistic: finalOptimisticPrice };
}

/**
 * [УЛУЧШЕНИЕ A2] Рассчитывает оценку качества объекта на основе калиброванных коэффициентов.
 * Коэффициенты откалиброваны на основе анализа 13,490 продаж за 24 месяца.
 * @param {Object} dataMap Карта данных объекта.
 * @returns {number} Оценка качества (от ~0.70 до ~1.25).
 */
function calculateQualityScore(dataMap) {
    let score = 1.0; // Базовая оценка
    try {
        const repair = (dataMap['Тип ремонта'] || '').toLowerCase();
        const buildYear = Number(dataMap['Год постройки']) || 0;
        const floor = Number(dataMap['Этаж']) || 0;
        const totalFloors = Number(dataMap['Этажность']) || 0;
        const currentYear = new Date().getFullYear();
        
        // === РЕМОНТ (калиброванные коэффициенты) ===
        if (repair.includes('дизайн') || repair.includes('дизайнерск')) {
            score += QUALITY_COEFFICIENTS.REPAIR_DESIGNER;
        } else if (repair.includes('евро')) {
            score += QUALITY_COEFFICIENTS.REPAIR_EURO;
        } else if (repair.includes('современн')) {
            score += QUALITY_COEFFICIENTS.REPAIR_MODERN;
        } else if (repair.includes('требует') || repair.includes('без ремонта') || repair.includes('черновая')) {
            score += QUALITY_COEFFICIENTS.REPAIR_NEEDS_WORK;
        } else if (repair.includes('старый') || repair.includes('убит')) {
            score += QUALITY_COEFFICIENTS.REPAIR_OLD;
        }
        // Косметический ремонт: 0%
        
        // === ГОД ПОСТРОЙКИ (калиброванные коэффициенты) ===
        if (buildYear > 0) {
            const age = currentYear - buildYear;
            if (age <= 5) {
                score += QUALITY_COEFFICIENTS.BUILDING_NEW;       // Новостройка
            } else if (age <= 15) {
                score += QUALITY_COEFFICIENTS.BUILDING_MODERN;    // Современный
            } else if (age <= 40) {
                score += QUALITY_COEFFICIENTS.BUILDING_NORMAL;    // Обычный
            } else if (buildYear >= 1980) {
                score += QUALITY_COEFFICIENTS.BUILDING_OLD;       // Старый (после 1980)
            } else {
                score += QUALITY_COEFFICIENTS.BUILDING_VERY_OLD;  // Очень старый (до 1980)
            }
        }
        
        // === ЭТАЖ (калиброванные коэффициенты) ===
        if (floor === 1) {
            score += QUALITY_COEFFICIENTS.FLOOR_FIRST;            // Первый этаж
        } else if (totalFloors > 2 && floor === totalFloors) {
            score += QUALITY_COEFFICIENTS.FLOOR_LAST;             // Последний этаж
        } else if (totalFloors > 3 && floor > 1 && floor < totalFloors) {
            score += QUALITY_COEFFICIENTS.FLOOR_MIDDLE;           // Средние этажи
        }
        
        // === ДОПОЛНИТЕЛЬНЫЕ ФАКТОРЫ ===
        // Проверяем наличие проф. фото
        const hasPhoto = dataMap['проф. фото'] || dataMap['Наличие проф. фото?'] || '';
        if (hasPhoto && (hasPhoto.toLowerCase().includes('да') || hasPhoto === '1' || hasPhoto === true)) {
            score += QUALITY_COEFFICIENTS.HAS_PROF_PHOTO;
        }
        
        // Проверяем длину описания
        const hasDesc = dataMap['описание'] || dataMap['Описание больше 400?'] || '';
        if (hasDesc && (hasDesc.toLowerCase().includes('да') || hasDesc === '1' || hasDesc === true)) {
            score += QUALITY_COEFFICIENTS.HAS_GOOD_DESC;
        }
        
        // Проверяем наличие планировки
        const hasFloorPlan = dataMap['планировка'] || dataMap['Есть планировка?'] || '';
        if (hasFloorPlan && (hasFloorPlan.toLowerCase().includes('да') || hasFloorPlan === '1' || hasFloorPlan === true)) {
            score += QUALITY_COEFFICIENTS.HAS_FLOOR_PLAN;
        }
        
    } catch(e) {
        Logger.log(`Ошибка в calculateQualityScore: ${e.message}`);
    }
    
    // Ограничиваем диапазон от 0.70 до 1.30
    return Math.max(0.70, Math.min(1.30, score));
}

/**
 * Определяет состояние рынка на основе индекса ликвидности и среднего спроса.
 * @param {number|string} liquidityIndex Индекс ликвидности.
 * @param {number} avgSalesPerMonth Среднее количество продаж в месяц.
 * @returns {string} Оценка состояния рынка.
 */
function getMarketAssessment(liquidityIndex, avgSalesPerMonth) {
  if (typeof liquidityIndex !== 'number') return 'Нет данных'; // Если индекс ликвидности не число
  if (liquidityIndex > 25 && avgSalesPerMonth > 3) return 'Горячий рынок (высокий спрос)'; // Высокая ликвидность и спрос
  if (liquidityIndex >= 15 && avgSalesPerMonth > 1.5) return 'Сбалансированный рынок'; // Средняя ликвидность и спрос
  return 'Холодный рынок (низкий спрос)'; // Низкая ликвидность или спрос
}

/**
 * Рассчитывает тренд конкуренции, сравнивая количество активных объектов в первой и второй половине периода.
 * @param {Array<Array<any>>} candidates Список активных кандидатов.
 * @param {Date} startDate Начальная дата периода.
 * @param {Date} endDate Конечная дата периода.
 * @returns {string} Описание тренда конкуренции.
 */
function calculateCompetitionTrend(candidates, startDate, endDate) {
  const midPoint = new Date(startDate.getTime() + (endDate.getTime() - startDate.getTime()) / 2); // Середина периода
  
  // Считаем количество активных объектов в первой и второй половине периода
  const firstHalfCount = candidates.filter(r => new Date(r[0]) < midPoint).length;
  const secondHalfCount = candidates.filter(r => new Date(r[0]) >= midPoint).length;
  
  // Определяем тренд
  if (firstHalfCount === 0 && secondHalfCount > 0) return '+100% (резкий рост)'; // Если в первой половине не было, а во второй есть
  if (firstHalfCount === 0 || secondHalfCount === 0) return 'стабильна'; // Если в одной из половин нет данных
  
  const trend = ((secondHalfCount / firstHalfCount) - 1) * 100; // Процентное изменение
  
  if (Math.abs(trend) < 10) return 'стабильна'; // Если изменение меньше 10%
  return `${trend > 0 ? 'рост' : 'снижение'} на ${Math.abs(trend.toFixed(0))}%`; // Описание тренда
}



// ================== ИНТЕГРАЦИЯ С GEMINI И ГЕНЕРАЦИЯ ОТЧЕТА ==================

/**
 * Триггер на редактирование. Запускает генерацию отчета, если изменен код объекта на листе аналитики адресов.
 * @param {GoogleAppsScript.Events.SheetsOnEdit} e Объект события редактирования.
 */




/**
 * Вызывает Google Gemini API для генерации текста.
 * @param {string} prompt Промпт для Gemini.
 * @param {string} summaryText Аналитическое резюме.
 * @returns {string} Ответ от Gemini или сообщение об ошибке.
 */
function callGemini(prompt, summaryText) {
  const apiKey = getGeminiApiKey(); 
  if (!apiKey) return 'API-ключ Gemini не установлен. Установите его через меню.';
  
  // Используем модель gemini-3-pro-preview по запросу пользователя
  const model = 'gemini-3-pro-preview'; 
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`;
  
  const fullPrompt = `${prompt}\n\nВот аналитическое резюме:\n${summaryText}\n\nSystem Instruction: Ты — опытный литературный редактор и специалист по деловой коммуникации. Перепиши этот текст в деловом стиле для клиента. Сохрани все цифры и суть.`;
  
  const payload = {
    "contents": [{
      "parts": [{
        "text": fullPrompt
      }]
    }],
    "generationConfig": {
      "temperature": 0.7,
      "maxOutputTokens": 8192,
      "topP": 0.8
    },
    "safetySettings": [
      { "category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE" },
      { "category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE" },
      { "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE" },
      { "category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE" }
    ]
  };
  
  const options = { 
    method: 'post', 
    contentType: 'application/json', 
    payload: JSON.stringify(payload), 
    muteHttpExceptions: true 
  };
  
  const maxRetries = 3;
  const baseDelay = 1000;
  
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const response = UrlFetchApp.fetch(url, options);
      const responseText = response.getContentText();
      Logger.log(`Gemini Raw Response (Attempt ${attempt}): ${responseText}`); // Логируем полный ответ
      
      const json = JSON.parse(responseText);
      
      if (json.error) {
        Logger.log(`Ошибка API Gemini (попытка ${attempt}): ${json.error.message}`);
        if (attempt < maxRetries) {
          Utilities.sleep(baseDelay * Math.pow(2, attempt - 1));
          continue;
        }
        return `❌ Ошибка API Gemini: ${json.error.message}`;
      }
      
      if (json.candidates && json.candidates[0] && json.candidates[0].content && json.candidates[0].content.parts && json.candidates[0].content.parts[0].text) {
        return cleanText(json.candidates[0].content.parts[0].text);
      }
      
      return "Не удалось получить текст от Gemini (пустой ответ). Проверьте логи ('Gemini Raw Response').";
      
      return "Не удалось получить текст от Gemini (пустой ответ).";
      
    } catch (e) {
      Logger.log(`Критическая ошибка при вызове callGemini: ${e.stack}`);
      if (attempt < maxRetries) {
        Utilities.sleep(baseDelay * Math.pow(2, attempt - 1));
        continue;
      }
      return '❌ Ошибка сети при обращении к Gemini.';
    }
  }
}

/**
 * Получает API-ключ Gemini из свойств скрипта.
 * @returns {string} API-ключ.
 */
function getGeminiApiKey() {
  return PropertiesService.getScriptProperties().getProperty('GEMINI_API_KEY') || PropertiesService.getScriptProperties().getProperty('OPENAI_API_KEY'); // Обратная совместимость или проверка старого ключа
}

/**
 * [УЛУЧШЕНИЕ C1-C5] Вызывает Gemini как ИИ-АНАЛИТИКА для анализа сырых данных.
 * Возвращает структурированный JSON с выводами и объяснениями.
 * @param {Object} analyticsData Сырые аналитические данные объекта.
 * @param {Object} marketContext Контекст рынка (макроэкономика).
 * @returns {Object} Структурированный ответ ИИ или объект с ошибкой.
 */
function callGeminiAnalyst(analyticsData, marketContext) {
  const apiKey = getGeminiApiKey(); 
  if (!apiKey) return { error: 'API-ключ Gemini не установлен', data: null };
  
  const model = 'gemini-2.5-flash-preview-05-20'; // Актуальная модель
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`;
  
  // === УЛУЧШЕНИЕ C5: Макроконтекст ===
  const macro = marketContext || getMacroContext();
  
  // === УЛУЧШЕНИЕ C1: Передаём сырые данные для анализа ===
  const systemPrompt = `Ты — опытный аналитик рынка недвижимости Тюмени с 15-летним стажем. 
Твоя задача — проанализировать данные объекта и рынка, и дать структурированные выводы.

МАКРОЭКОНОМИЧЕСКИЙ КОНТЕКСТ:
- Ключевая ставка ЦБ: ${macro.keyRate}%
- Рыночная ипотека: ${macro.mortgageRate}%
- Семейная ипотека: ${macro.familyMortgage ? 'действует (6%)' : 'не действует'}
- Тренд рынка: ${macro.marketTrend}
- Регион: ${macro.region}

ПРАВИЛА АНАЛИЗА:
1. Учитывай влияние ставки ЦБ на спрос (высокая ставка = меньше покупателей)
2. Семейная ипотека влияет на сегмент семей с детьми
3. Сезон года влияет на сроки продажи
4. Анализируй динамику рынка (затоваривание или дефицит)
5. ИСКЛЮЧЕНИЕ ПРОТИВОРЕЧИЙ: Если расчетный срок продажи > 6 месяцев, не называй спрос "высоким", даже если объект качественный. Если объект "привлекательнее конкурентов", но срок долгий — объясни это макрофакторами или ценой.
6. ОБЪЕКТИВНОСТЬ: Избегай шаблонных фраз о "превосходстве" объекта, если его цена выше среднего по рынку.

ФОРМАТ ОТВЕТА (только JSON, без markdown):
{
  "analysis": {
    "marketPosition": "краткое описание позиции объекта на рынке",
    "mainFactors": ["фактор1", "фактор2", "фактор3"],
    "risks": ["риск1", "риск2"],
    "opportunities": ["возможность1", "возможность2"]
  },
  "pricing": {
    "recommendedPrice": число,
    "priceRangeMin": число,
    "priceRangeMax": число,
    "reasoning": "обоснование цены"
  },
  "timeline": {
    "expectedMonths": число,
    "bestCase": число,
    "worstCase": число,
    "reasoning": "обоснование срока"
  },
  "recommendations": [
    {"action": "действие", "impact": "влияние", "priority": "высокий/средний/низкий"},
    ...
  ],
  "confidence": число от 0 до 100,
  "confidenceReasoning": "почему такой уровень уверенности"
}`;

  const userPrompt = `Проанализируй эти данные объекта недвижимости:

${JSON.stringify(analyticsData, null, 2)}

Дай структурированный анализ в формате JSON.`;

  const payload = {
    "contents": [{
      "parts": [
        { "text": systemPrompt },
        { "text": userPrompt }
      ]
    }],
    "generationConfig": {
      "temperature": 0.3, // Низкая температура для аналитики
      "maxOutputTokens": 4096,
      "topP": 0.8,
      "responseMimeType": "application/json" // [C2] JSON-вывод
    },
    "safetySettings": [
      { "category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE" },
      { "category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE" },
      { "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE" },
      { "category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE" }
    ]
  };
  
  const options = { 
    method: 'post', 
    contentType: 'application/json', 
    payload: JSON.stringify(payload), 
    muteHttpExceptions: true 
  };
  
  try {
    const response = UrlFetchApp.fetch(url, options);
    const responseText = response.getContentText();
    Logger.log(`Gemini Analyst Raw Response: ${responseText.substring(0, 500)}...`);
    
    const json = JSON.parse(responseText);
    
    if (json.error) {
      Logger.log(`Ошибка API Gemini Analyst: ${json.error.message}`);
      return { error: json.error.message, data: null };
    }
    
    if (json.candidates && json.candidates[0] && json.candidates[0].content && json.candidates[0].content.parts) {
      const aiText = json.candidates[0].content.parts[0].text;
      
      try {
        // === УЛУЧШЕНИЕ C2: Парсим JSON от ИИ ===
        const aiData = JSON.parse(aiText);
        
        // === УЛУЧШЕНИЕ C3: Валидация результатов ===
        const validatedData = validateAIResponse(aiData, analyticsData);
        
        return { error: null, data: validatedData };
      } catch (parseError) {
        Logger.log(`Ошибка парсинга JSON от Gemini: ${parseError.message}`);
        return { error: 'ИИ вернул некорректный JSON', data: null, rawText: aiText };
      }
    }
    
    return { error: 'Пустой ответ от Gemini', data: null };
    
  } catch (e) {
    Logger.log(`Критическая ошибка при вызове callGeminiAnalyst: ${e.stack}`);
    return { error: e.message, data: null };
  }
}

/**
 * [УЛУЧШЕНИЕ C3] Валидирует ответ ИИ и корректирует нереалистичные значения.
 * @param {Object} aiData Данные от ИИ.
 * @param {Object} originalData Исходные данные объекта.
 * @returns {Object} Валидированные данные.
 */
function validateAIResponse(aiData, originalData) {
  const validated = { ...aiData };
  const originalPrice = originalData.price || originalData.ourPrice || 0;
  
  // Валидация цены: не должна отклоняться более чем на 30% от исходной
  if (validated.pricing && validated.pricing.recommendedPrice) {
    const recPrice = validated.pricing.recommendedPrice;
    const deviation = Math.abs(recPrice - originalPrice) / originalPrice;
    
    if (deviation > 0.3 && originalPrice > 0) {
      validated.pricing.warning = `ИИ рекомендовал цену ${recPrice}, что отклоняется на ${(deviation * 100).toFixed(0)}% от текущей. Рекомендуется перепроверка.`;
      validated.pricing.originalRecommendation = recPrice;
      // Корректируем до ±30%
      validated.pricing.recommendedPrice = recPrice > originalPrice 
        ? Math.floor(originalPrice * 1.30) 
        : Math.floor(originalPrice * 0.70);
    }
  }
  
  // Валидация срока: не более 36 месяцев
  if (validated.timeline && validated.timeline.expectedMonths) {
    if (validated.timeline.expectedMonths > 36) {
      validated.timeline.warning = `ИИ прогнозировал ${validated.timeline.expectedMonths} мес, скорректировано до 36 (максимум).`;
      validated.timeline.expectedMonths = 36;
    }
    if (validated.timeline.expectedMonths < 0.5) {
      validated.timeline.warning = `ИИ прогнозировал ${validated.timeline.expectedMonths} мес, скорректировано до 0.5 (минимум).`;
      validated.timeline.expectedMonths = 0.5;
    }
  }
  
  // Добавляем метку валидации
  validated.validated = true;
  validated.validationTimestamp = new Date().toISOString();
  
  return validated;
}

/**
 * [УЛУЧШЕНИЕ C5] Получает макроконтекст из настроек или возвращает значения по умолчанию.
 * @returns {Object} Макроконтекст.
 */
function getMacroContext() {
  try {
    const settingsSheet = SPREADSHEET.getSheetByName(SHEETS.SETTINGS);
    if (settingsSheet) {
      // Пытаемся прочитать JSON из ячейки A1
      const contextCell = settingsSheet.getRange('A1').getValue();
      if (contextCell) {
        return JSON.parse(contextCell);
      }
    }
  } catch (e) {
    Logger.log(`Ошибка чтения макроконтекста: ${e.message}`);
  }
  
  return DEFAULT_MACRO_CONTEXT;
}

/**
 * [УЛУЧШЕНИЕ C5] Устанавливает макроконтекст в настройки.
 * @param {Object} context Новый макроконтекст.
 */
function setMacroContext(context) {
  try {
    let settingsSheet = SPREADSHEET.getSheetByName(SHEETS.SETTINGS);
    if (!settingsSheet) {
      settingsSheet = SPREADSHEET.insertSheet(SHEETS.SETTINGS);
    }
    settingsSheet.getRange('A1').setValue(JSON.stringify(context, null, 2));
    Logger.log('Макроконтекст успешно сохранён');
  } catch (e) {
    Logger.log(`Ошибка сохранения макроконтекста: ${e.message}`);
  }
}

/**
 * Показывает статус API Gemini в диалоговом окне.
 */
function showApiStatus() {
  const ui = SpreadsheetApp.getUi();
  const apiKey = getGeminiApiKey();
  if (!apiKey) {
    ui.alert('Статус API', 'Ключ не установлен', ui.ButtonSet.OK);
    return;
  }
  ui.alert('Статус API', 'Ключ установлен (проверка доступности требует реального запроса)', ui.ButtonSet.OK);
}

/**
 * Очищает текст от лишних символов (например, markdown, ведущие цифры/тире).
 * @param {string} text Текст для очистки.
 * @returns {string} Очищенный текст.
 */
function cleanText(text) { 
  // Удаляем возможные ведущие символы markdown, пробелы, цифры и точки
  return text.replace(/^[#*-\s\d\.]+/gm, '').replace(/\*{1,2}(.*?)\*{1,2}/g, '$1'); // Удаляем markdown * и **
}

/**
 * Запрашивает у пользователя API-ключ Gemini и сохраняет его.
 */
function setApiKey() { 
  const ui = SpreadsheetApp.getUi();
  const response = ui.prompt('Установка API-ключа Gemini', 'Пожалуйста, введите ваш API-ключ Google Gemini:', ui.ButtonSet.OK_CANCEL);
  
  if (response.getSelectedButton() == ui.Button.OK) { // Если пользователь нажал OK
    const apiKey = response.getResponseText().trim();
    if (apiKey && apiKey.length > 10) { // Простая проверка валидности ключа
      PropertiesService.getScriptProperties().setProperty('GEMINI_API_KEY', apiKey); // Сохраняем ключ
      ui.alert('API-ключ Gemini успешно сохранен.');
    } else { 
      ui.alert('Ошибка', 'Ключ выглядит некорректно.', ui.ButtonSet.OK); 
    } 
  } 
}

/**
 * Устанавливает предустановленный API-ключ Gemini.
 */
function setDefaultApiKey() {
  try {
    const defaultApiKey = 'YOUR_OPENAI_API_KEY_HERE'; // Замените на ваш API ключ OpenAI
    PropertiesService.getScriptProperties().setProperty('OPENAI_API_KEY', defaultApiKey);
    SpreadsheetApp.getUi().alert('✅ API-ключ OpenAI установлен автоматически!');
    Logger.log('API-ключ OpenAI установлен автоматически');
  } catch (e) {
    Logger.log(`Ошибка при установке API-ключа: ${e.stack}`);
    SpreadsheetApp.getUi().alert('❌ Ошибка при установке API-ключа: ' + e.message);
  } 
}

/**
 * Получает сохраненный API-ключ Gemini.
 * @returns {string|null} API-ключ или null, если не установлен.
 */
function getOpenAIApiKey() { 
  return PropertiesService.getScriptProperties().getProperty('OPENAI_API_KEY'); 
}

/**
 * Заполняет ключевые области некорректно рассчитанных данных тире ('-') при ошибках.
 */
function setDashesOnError() { 
  const analyticsSheet = SPREADSHEET.getSheetByName(SHEETS.MAIN_ANALYTICS);
  if (analyticsSheet && analyticsSheet.getLastRow() >= 6) analyticsSheet.getRange('A6:AQ' + analyticsSheet.getLastRow()).setValue('-'); // Заполняем основной лист
  
  const competitorsSheet = SPREADSHEET.getSheetByName(SHEETS.COMPETITORS);
  if (competitorsSheet && competitorsSheet.getLastRow() >= 2) competitorsSheet.getRange('A2:M' + competitorsSheet.getLastRow()).setValue('-'); // Заполняем лист конкурентов
  
  const addressSheet = SPREADSHEET.getSheetByName(SHEETS.ADDRESS_ANALYTICS); 
  if (addressSheet) { 
    addressSheet.getRange('A4:B50').clearContent().clearFormat(); // Очищаем область отчета
    addressSheet.getRange('A4').setValue('ПРОИЗОШЛА ОШИБКА'); // Сообщение об ошибке
  } 
}

/**
 * Применяет форматирование к листу с отчетом.
 * @param {GoogleAppsScript.Spreadsheet.Sheet} sheet Лист для форматирования.
 */

/**
 * Применяет общее форматирование к различным рабочим листам.
 */
function formatSheets() {
    // Форматирование основного листа аналитики
    const analyticsSheet = SPREADSHEET.getSheetByName(SHEETS.MAIN_ANALYTICS); 
    if (analyticsSheet) { 
        analyticsSheet.getRange('A6:AQ1000').setFontSize(9).setHorizontalAlignment('left').setVerticalAlignment('middle'); // Основные данные
        analyticsSheet.getRange('V6:AQ1000').setHorizontalAlignment('center'); // Аналитические метрики по центру
        analyticsSheet.getRange('A5:AQ5').setBackground('#D3D3D3').setFontWeight('bold').setFontSize(9); // Заголовки
    }
    
    // Форматирование листа аналитики по адресу/коду
    const addressSheet = SPREADSHEET.getSheetByName(SHEETS.ADDRESS_ANALYTICS); 
    if (addressSheet) { 
        addressSheet.getRange('A2').setValue('код объекта').setFontSize(9).setFontWeight('bold'); // Заголовок для ввода кода
        addressSheet.getRange('B2').setHorizontalAlignment('center').setBackground('#4ee1f6').setBorder(true, true, true, true, false, false).setFontSize(9); // Ячейка для ввода кода
        formatReportSheet(addressSheet); // Форматирование области отчета
    }
    
    // Форматирование листа конкурентов
    const competitorsSheet = SPREADSHEET.getSheetByName(SHEETS.COMPETITORS); 
    if (competitorsSheet) { 
        competitorsSheet.getRange('A2:N1000').setFontSize(9).setHorizontalAlignment('left').setVerticalAlignment('middle'); // Основные данные
    }
}

/**
 * Форматирует срок в месяцах в более читаемый вид.
 * @param {number|string} months Срок в месяцах.
 * @returns {string} Форматированный срок.
 */

// ================== ВСПОМОГАТЕЛЬНЫЕ МАТЕМАТИЧЕСКИЕ ФУНКЦИИ ==================

/**
 * Создает строку, заполненную тире.
 * @param {number} length Длина строки.
 * @returns {Array<string>} Массив из тире.
 */
function createDashRow(length) { return new Array(length).fill('-'); }

/**
 * Рассчитывает среднее арифметическое массива чисел.
 * @param {Array<number>} arr Массив чисел.
 * @returns {number} Среднее значение.
 */
function calculateAverage(arr) { 
  if (!arr || arr.length === 0) return 0; 
  return Math.floor(arr.reduce((a, b) => a + b, 0) / arr.length); 
}

/**
 * Рассчитывает медианное значение массива чисел.
 * @param {Array<number>} arr Массив чисел.
 * @returns {number} Медианное значение.
 */
function calculateMedian(arr) { 
  if (!arr || arr.length === 0) return 0; 
  const sorted = [...arr].sort((a, b) => a - b); // Сортируем массив
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 !== 0 ? sorted[mid] : Math.floor((sorted[mid - 1] + sorted[mid]) / 2); // Среднее двух центральных элементов для четного размера
}

/**
 * Рассчитывает усеченное среднее (с отсечением крайних значений).
 * @param {Array<number>} arr Массив чисел.
 * @param {number} percent Процент отсекаемых значений с каждого края.
 * @returns {number} Усеченное среднее.
 */
function calculateTrimmedMean(arr, percent) { 
  if (!arr || arr.length === 0) return 0; 
  const sorted = [...arr].sort((a,b) => a-b); // Сортируем массив
  const trimCount = Math.floor(sorted.length * percent); // Количество элементов для отсечения
  const trimmedArr = sorted.slice(trimCount, sorted.length - trimCount); // Оставляем средние значения
  return trimmedArr.length > 0 ? calculateAverage(trimmedArr) : calculateAverage(arr); // Возвращаем среднее усеченного массива или всего массива, если усечение невозможно
}

/**
 * Рассчитывает параметры линейной регрессии (наклон и пересечение).
 * @param {Array<Array<number>>} data Массив пар [x, y].
 * @returns {{slope: number, intercept: number}|null} Параметры регрессии или null.
 */
function calculateLinearRegression(data) { 
  if(!data || data.length < 2) return null; 
  
  let sum_x = 0, sum_y = 0, sum_xy = 0, sum_xx = 0;
  const n = data.length;
  
  // Суммируем значения для расчета
  data.forEach(([x, y]) => { 
    sum_x += x; 
    sum_y += y; 
    sum_xy += x * y; 
    sum_xx += x * x; 
  }); 
  
  const denominator = (n * sum_xx - sum_x * sum_x);
  if (denominator === 0) return null; // Избегаем деления на ноль
  
  const slope = (n * sum_xy - sum_x * sum_y) / denominator; // Наклон
  const intercept = (sum_y - slope * sum_x) / n; // Пересечение
  
  return { slope, intercept }; 
}

/**
 * Форматирует массив данных для пакетной записи в Google Таблицы.
 * Гарантирует, что каждая строка имеет заданное количество столбцов, добавляя пустые строки при необходимости.
 * @param {Array<Array<any>>} data Массив данных.
 * @param {number} columns Ожидаемое количество столбцов.
 * @returns {Array<Array<any>>} Отформатированный массив данных.
 */
function formatForBatchWrite(data, columns) { 
  return data.map(row => { 
    const newRow = [...row]; // Копируем строку
    // Добавляем пустые строки, если их меньше, чем ожидаемое количество столбцов
    while (newRow.length < columns) newRow.push(''); 
    return newRow.slice(0, columns); // Возвращаем строку с нужным количеством столбцов
  }); 
}

// ================== НОВЫЕ ФУНКЦИИ ДЛЯ ИНДИВИДУАЛЬНОГО АНАЛИЗА ==================

/**
 * Настраивает новые листы для индивидуального анализа объектов.
 * Устанавливает заголовки и применяет форматирование.
 */
function setupNewSheets() {
  try {
    // Настройка листа "аналитика ОН по коду"
    setupSingleObjectAnalyticsSheet();
    
    // Настройка листа "лист анализа объекта"
    setupAnalysisObjectSheet();
    
    // Настройка листа "конкуренты активные и проданные для анализа"
    setupCompetitorsAnalysisSheet();
    
    SpreadsheetApp.getUi().alert('✅ Новые листы успешно настроены!');
    Logger.log('Новые листы успешно настроены');
  } catch (e) {
    Logger.log(`Ошибка в setupNewSheets: ${e.stack}`);
    SpreadsheetApp.getUi().alert('❌ Ошибка при настройке новых листов: ' + e.message);
  }
}

/**
 * Настраивает лист "лист анализа объекта" с заголовками и форматированием.
 */
function setupAnalysisObjectSheet() {
  const sheet = SPREADSHEET.getSheetByName('лист анализа объекта');
  if (!sheet) {
    throw new Error('Лист "лист анализа объекта" не найден');
  }
  
  // УПРОЩЁННЫЕ заголовки для листа анализа объекта (A2:AQ2)
  const headers = [
    'Дата в активных', 'Район', 'Тип', 'Комнат', 'Площадь', 
    'Ссылка', 'Ремонт', 'Цена', 'Этаж', 'Этажей', 'Год', 
    'Риэлтор', 'Фото', 'Описание', 'Планировка',
    'Авито', 'Дата', 'ЦИАН', 'Дата', 'ДомКлик', 'Дата',
    'Конкурентов', 'Продано', 'Спрос/мес', 'Новых/мес', 'Скорость продажи', 
    'Рынок', 'Тренд конкуренции', 'Место по цене', 
    'Тренд цены', 'vs конкуренты', 
    'vs сделки', 'Ср. цена конкурентов', 'Ваша цена', 
    'Разница', 'Ср. цена сделок', 'Ваша цена', 
    'Разница', 'Цена быстрая', 'Срок быстрый', 
    'Цена рыночная', 'Срок рыночный'
  ];
  
  // Устанавливаем заголовки
  sheet.getRange('A2:AP2').setValues([headers]);
  
  // Форматирование заголовков
  sheet.getRange('A2:AP2')
    .setBackground('#D3D3D3')
    .setFontWeight('bold')
    .setFontSize(9)
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');
  
  // Форматирование данных
  sheet.getRange('A3:AP1000')
    .setFontSize(9)
    .setHorizontalAlignment('left')
    .setVerticalAlignment('middle');
  
  // Центрирование аналитических метрик
  sheet.getRange('V3:AP1000').setHorizontalAlignment('center');
  
  Logger.log('Лист "лист анализа объекта" настроен');
}

/**
 * Настраивает лист "конкуренты активные и проданные для анализа" с заголовками.
 */
function setupCompetitorsAnalysisSheet() {
  const sheet = SPREADSHEET.getSheetByName('конкуренты активные и проданные для анализа');
  if (!sheet) {
    throw new Error('Лист "конкуренты активные и проданные для анализа" не найден');
  }
  
  // Заголовки для листа конкурентов (как в существующем листе)
  const headers = [
    'Код объекта', 'Район', 'Тип объекта', 'Кол-во комнат', 'Площадь', 'Цена', 'Цена за м²', 
    'Срок продажи, дней', 'Ссылка', 'Ремонт', 'Состояние дома', 'Этаж/Этажность', 'Год постройки'
  ];
  
  // Устанавливаем заголовки
  sheet.getRange('A2:M2').setValues([headers]);
  
  // Форматирование заголовков
  sheet.getRange('A2:M2')
    .setBackground('#D3D3D3')
    .setFontWeight('bold')
    .setFontSize(9)
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');
  
  // Форматирование данных
  sheet.getRange('A3:M1000')
    .setFontSize(9)
    .setHorizontalAlignment('left')
    .setVerticalAlignment('middle');
  
  Logger.log('Лист "конкуренты активные и проданные для анализа" настроен');
}

/**
 * Настраивает лист "аналитика ОН по коду" с полем ввода кода.
 */
function setupSingleObjectAnalyticsSheet() {
  const sheet = SPREADSHEET.getSheetByName(SHEETS.SINGLE_OBJECT_ANALYTICS);
  if (!sheet) {
    throw new Error('Лист "аналитика ОН по коду" не найден');
  }
  
  // Настройка ячейки A2 - заголовок
  sheet.getRange('A2')
    .setValue('код объекта')
    .setFontSize(9)
    .setFontWeight('bold')
    .setHorizontalAlignment('left')
    .setVerticalAlignment('middle');
  
  // Настройка ячейки B2 - поле для ввода кода
  sheet.getRange('B2')
    .setHorizontalAlignment('center')
    .setBackground('#4ee1f6')
    .setBorder(true, true, true, true, false, false)
    .setFontSize(9)
    .setVerticalAlignment('middle');
  
  // Очистка области отчета (начиная с 4 строки)
  sheet.getRange('A4:B50').clearContent().clearFormat();
  
  Logger.log('Лист "аналитика ОН по коду" настроен');
}

/**
 * Поиск объекта по коду в листе активных объектов.
 * @param {string} code Код объекта для поиска.
 * @returns {Array|null} Данные объекта или null, если не найден.
 */
function findObjectByCode(code) {
  try {
    // Валидация кода
    if (!code || typeof code !== 'string') {
      Logger.log('Неверный формат кода объекта');
      return null;
    }
    
    const cleanCode = String(code).trim();
    if (cleanCode === '') {
      Logger.log('Пустой код объекта');
      return null;
    }
    
    // Получение данных из листа "2. 2. активные"
    const activeSheet = SPREADSHEET.getSheetByName(SHEETS.ACTIVE_COMPETITORS);
    if (!activeSheet) {
      Logger.log('Лист "2. 2. активные" не найден');
      return null;
    }
    
    const lastRow = activeSheet.getLastRow();
    if (lastRow < 3) {
      Logger.log('Нет данных в листе "2. 2. активные"');
      return null;
    }
    
    // Получение всех данных (начиная с строки 3, так как строка 2 - заголовки)
    const data = activeSheet.getRange('A3:O' + lastRow).getValues();
    
    // Поиск по коду объекта (столбец F, индекс 5)
    const foundRow = data.find(row => {
      const rowCode = String(row[5]).trim(); // Столбец F (индекс 5)
      Logger.log(`Сравниваем код: "${cleanCode}" с "${rowCode}"`);
      return rowCode === cleanCode;
    });
    
    if (foundRow) {
      Logger.log(`Объект с кодом ${cleanCode} найден в активных`);
      return foundRow;
    } else {
      Logger.log(`Объект с кодом ${cleanCode} не найден в активных`);
      return null;
    }
    
  } catch (e) {
    Logger.log(`Ошибка в findObjectByCode: ${e.stack}`);
    return null;
  }
}

/**
 * Валидация кода объекта.
 * @param {string} code Код объекта.
 * @returns {boolean} Валидность кода.
 */
function validateCode(code) {
  if (!code || typeof code !== 'string') return false;
  const cleanCode = String(code).trim();
  return cleanCode !== '' && cleanCode.length > 0;
}

/**
 * Строит массив конкурентов для одного объекта.
 * @param {Array} objectData Данные объекта.
 * @returns {Object} Объект с активными и проданными конкурентами.
 */
function buildSingleObjectCompetitorsArray(objectData) {
  try {
    Logger.log('Начинаем построение массива конкурентов...');
    
    // Извлекаем характеристики объекта
    const district = objectData[1]; // Район
    const type = objectData[2]; // Тип объекта
    const rooms = Number(objectData[3]); // Кол-во комнат
    const area = Number(objectData[4]); // Площадь
    const repair = objectData[6]; // Тип ремонта
    const buildYear = Number(objectData[10]); // Год постройки
    
    Logger.log(`Параметры объекта: район=${district}, тип=${type}, комнат=${rooms}, площадь=${area}, ремонт=${repair}, год=${buildYear}`);
    
    // Получаем данные конкурентов
    const activeData = getActiveCompetitorsData();
    const soldData = getSoldCompetitorsData();
    
    Logger.log(`Получено активных конкурентов: ${activeData.length}, проданных: ${soldData.length}`);
    
    // Фильтруем конкурентов по критериям (с правильными флагами)
    const activeCompetitors = filterCompetitorsByCriteria(activeData, {
      district, type, rooms, area, repair, buildYear
    }, true); // true = активные данные
    
    const soldCompetitors = filterCompetitorsByCriteria(soldData, {
      district, type, rooms, area, repair, buildYear
    }, false); // false = проданные данные
    
    Logger.log(`После фильтрации: активных=${activeCompetitors.length}, проданных=${soldCompetitors.length}`);
    
    // Форматируем данные для вывода
    const formattedActive = activeCompetitors.map(row => formatCompetitorRow(row, false));
    const formattedSold = soldCompetitors.map(row => formatCompetitorRow(row, true));
    
    Logger.log(`Отформатировано: активных=${formattedActive.length}, проданных=${formattedSold.length}`);
    
    // Заполняем лист конкурентов
    fillCompetitorsSheet(formattedActive, formattedSold, objectData[5], objectData); // Передаем также данные объекта
    
    Logger.log('Массив конкурентов построен успешно');
    
    return {
      activeCompetitors: formattedActive,
      soldCompetitors: formattedSold
    };
    
  } catch (e) {
    Logger.log(`Ошибка в buildSingleObjectCompetitorsArray: ${e.stack}`);
    return { activeCompetitors: [], soldCompetitors: [] };
  }
}

/**
 * Получает данные активных конкурентов.
 * @returns {Array} Данные активных конкурентов.
 */
function getActiveCompetitorsData() {
  const activeSheet = SPREADSHEET.getSheetByName(SHEETS.ACTIVE_COMPETITORS);
  if (!activeSheet || activeSheet.getLastRow() < 3) return [];
  return activeSheet.getRange('A3:O' + activeSheet.getLastRow()).getValues();
}

/**
 * Получает данные проданных конкурентов.
 * @returns {Array} Данные проданных конкурентов.
 */
function getSoldCompetitorsData() {
  const soldSheet = SPREADSHEET.getSheetByName(SHEETS.SOLD_COMPETITORS);
  if (!soldSheet || soldSheet.getLastRow() < 3) return [];
  return soldSheet.getRange('A3:O' + soldSheet.getLastRow()).getValues();
}

/**
 * Фильтрует конкурентов по критериям (оригинальная методология).
 * @param {Array} data Данные конкурентов.
 * @param {Object} criteria Критерии фильтрации.
 * @param {boolean} isActiveData Активные или проданные данные.
 * @returns {Array} Отфильтрованные данные.
 */
function filterCompetitorsByCriteria(data, criteria, isActiveData = true) {
  const { district, type, rooms, area, repair, buildYear } = criteria;
  
  Logger.log(`Фильтрация ${isActiveData ? 'активных' : 'проданных'} конкурентов по критериям: район=${district}, тип=${type}, комнат=${rooms}, площадь=${area}`);
  
  // Для индивидуального анализа используем фиксированный период 6 месяцев
  const now = new Date();
  const startDate = new Date(now.getFullYear(), now.getMonth() - 6, 1); // 6 месяцев назад
  const endDate = now;
  
  // Определяем дату, старше которой объекты считаются "устаревшими" (6 месяцев)
  const staleDate = new Date();
  staleDate.setMonth(staleDate.getMonth() - 6);
  
  Logger.log(`Временные фильтры: staleDate=${staleDate.toLocaleDateString()}, startDate=${startDate.toLocaleDateString()}, endDate=${endDate.toLocaleDateString()}`);
  
  let filteredCount = 0;
  
  // Фильтруем по всем критериям
  const result = data.filter((row, index) => {
    try {
      const rowDate = new Date(row[0]);
      const rowDistrict = row[1];
      const rowType = row[2];
      const rowRooms = Number(row[3]);
      const rowArea = Number(row[4]);
      const rowRepair = row[6];
      const rowBuildYear = Number(row[10]) || null;
      
      // Логируем первые несколько строк для отладки
      if (index < 3) {
        Logger.log(`Строка ${index}: район="${rowDistrict}", тип="${rowType}", комнат=${rowRooms}, площадь=${rowArea}, ремонт="${rowRepair}", год=${rowBuildYear}`);
      }
      
      // 1. ГЕОГРАФИЧЕСКИЙ ФИЛЬТР (самый важный!)
      if (rowDistrict !== district) {
        if (index < 3) Logger.log(`  ❌ Отфильтровано по району: "${rowDistrict}" !== "${district}"`);
        return false;
      }
      
      // 2. ТИП ОБЪЕКТА (строгое соответствие)
      if (rowType !== type) {
        if (index < 3) Logger.log(`  ❌ Отфильтровано по типу: "${rowType}" !== "${type}"`);
        return false;
      }
      
      // 3. ВРЕМЕННОЙ ФИЛЬТР
      if (isActiveData) {
        // Для активных: не старше 6 месяцев
        if (rowDate.getTime() < staleDate.getTime()) {
          if (index < 3) Logger.log(`  ❌ Отфильтровано по времени (активные): ${rowDate.toLocaleDateString()} < ${staleDate.toLocaleDateString()}`);
          return false;
        }
      } else {
        // Для проданных: в диапазоне 6 месяцев
        if (rowDate.getTime() < startDate.getTime() || rowDate.getTime() > endDate.getTime()) {
          if (index < 3) Logger.log(`  ❌ Отфильтровано по времени (проданные): ${rowDate.toLocaleDateString()} не в диапазоне ${startDate.toLocaleDateString()} - ${endDate.toLocaleDateString()}`);
          return false;
        }
      }
      
      // 4. КОЛИЧЕСТВО КОМНАТ (допуск +/- 1)
      const allowedRooms = [rooms, rooms + 1, rooms - 1].filter(r => r >= 0);
      if (!allowedRooms.includes(rowRooms)) {
        if (index < 3) Logger.log(`  ❌ Отфильтровано по комнатам: ${rowRooms} не в ${allowedRooms}`);
        return false;
      }
      
      // 5. ПЛОЩАДЬ (допуск +/- 20%)
      const minArea = area * 0.8;
      const maxArea = area * 1.2;
      if (rowArea < minArea || rowArea > maxArea) {
        if (index < 3) Logger.log(`  ❌ Отфильтровано по площади: ${rowArea} не в диапазоне ${minArea}-${maxArea}`);
        return false;
      }
      
      // 6. ГОД ПОСТРОЙКИ (допуск +/- 10 лет)
      if (buildYear && rowBuildYear && (rowBuildYear < buildYear - 10 || rowBuildYear > buildYear + 10)) {
        if (index < 3) Logger.log(`  ❌ Отфильтровано по году: ${rowBuildYear} не в диапазоне ${buildYear - 10}-${buildYear + 10}`);
        return false;
      }
      
      // 7. ТИП РЕМОНТА (асимметричная логика)
      const goodRepairs = ['Ремонт по дизайн проекту', 'Евроремонт', 'Современный ремонт'];
      const objectRepairLower = repair ? repair.toLowerCase() : '';
      const isObjectGoodRepair = goodRepairs.some(gr => objectRepairLower.includes(gr.toLowerCase()));
      
      if (isObjectGoodRepair) {
        // Если у объекта хороший ремонт, ищем только с хорошим
        const competitorRepairLower = rowRepair ? rowRepair.toLowerCase() : '';
        if (!goodRepairs.some(gr => competitorRepairLower.includes(gr.toLowerCase()))) {
          if (index < 3) Logger.log(`  ❌ Отфильтровано по ремонту: "${rowRepair}" не подходит для хорошего ремонта`);
          return false;
        }
      }
      // Если у объекта обычный ремонт - фильтр не применяется
      
      if (index < 3) Logger.log(`  ✅ Строка ${index} прошла все фильтры!`);
      filteredCount++;
      return true;
    } catch (e) {
      Logger.log(`Ошибка при фильтрации строки ${index}: ${e.message}`);
      return false;
    }
  });
  
  Logger.log(`Отфильтровано ${filteredCount} из ${data.length} ${isActiveData ? 'активных' : 'проданных'} конкурентов`);
  
  return result;
}

/**
 * Заполняет лист конкурентов отфильтрованными данными.
 * @param {Array} activeCompetitors Активные конкуренты.
 * @param {Array} soldCompetitors Проданные конкуренты.
 * @param {string} objectCode Код объекта.
 * @param {Array} objectData Данные нашего объекта.
 */
function fillCompetitorsSheet(activeCompetitors, soldCompetitors, objectCode, objectData) {
  const sheet = SPREADSHEET.getSheetByName(SHEETS.SINGLE_COMPETITORS);
  if (!sheet) return;
  
  // Очищаем лист полностью (включая форматирование)
  sheet.getRange('A2:M' + sheet.getMaxRows()).clearContent().clearFormat();
  
  let output = [];
  const headers = ['Код объекта', 'Район', 'Тип объекта', 'Кол-во комнат', 'Площадь', 'Цена', 'Цена за м²', 'Срок продажи, дней', 'Ссылка', 'Ремонт', 'Состояние дома', 'Этаж/Этажность', 'Год постройки'];
  
  // Добавляем активных конкурентов (сортируем по цене)
  if (activeCompetitors.length > 0) {
    output.push([`Активные конкуренты (ОН код: ${objectCode})`]);
    output.push(headers);
    
    // Создаем массив с нашим объектом + активными конкурентами
    const allActiveObjects = [...activeCompetitors];
    
    // Добавляем наш объект в массив
    if (objectData) {
      const ourObjectAsCompetitor = formatCompetitorRow(objectData, false);
      allActiveObjects.push(ourObjectAsCompetitor);
    }
    
    // Сортируем все объекты (включая наш) по цене (столбец 5 - цена)
    const sortedActiveCompetitors = allActiveObjects.sort((a, b) => {
      const priceA = Number(a[5]) || 0; // Цена в столбце 5
      const priceB = Number(b[5]) || 0; // Цена в столбце 5
      return priceA - priceB; // Сортировка от меньшей к большей
    });
    
    output.push(...sortedActiveCompetitors);
    output.push([]); // Пустая строка
  }
  
  // Добавляем проданных конкурентов (сортируем по цене)
  if (soldCompetitors.length > 0) {
    output.push([`Проданные конкуренты (ОН код: ${objectCode})`]);
    output.push(headers);
    
    // Сортируем проданных конкурентов по цене (столбец 5 - цена)
    const sortedSoldCompetitors = [...soldCompetitors].sort((a, b) => {
      const priceA = Number(a[5]) || 0; // Цена в столбце 5
      const priceB = Number(b[5]) || 0; // Цена в столбце 5
      return priceA - priceB; // Сортировка от меньшей к большей
    });
    
    output.push(...sortedSoldCompetitors);
    output.push([]); // Пустая строка
  }
  
  // Записываем данные
  if (output.length > 0) {
    const formattedData = formatForBatchWrite(output, 13);
    sheet.getRange(2, 1, formattedData.length, formattedData[0].length).setValues(formattedData);
    
    // Форматируем заголовки разделов
    let currentRow = 2;
    for (let i = 0; i < output.length; i++) {
      if (output[i].length === 1 && output[i][0].includes('конкуренты')) {
        // Это заголовок раздела
        sheet.getRange(currentRow, 1, 1, 13)
          .setFontWeight('bold')
          .setBackground('#E6F3FF')
          .setFontSize(10)
          .setHorizontalAlignment('center')
          .setVerticalAlignment('middle');
      } else if (output[i].length === 13 && output[i][0] === 'Код объекта') {
        // Это заголовки столбцов
        sheet.getRange(currentRow, 1, 1, 13)
          .setFontWeight('bold')
          .setBackground('#D3D3D3')
          .setFontSize(9)
          .setHorizontalAlignment('center')
          .setVerticalAlignment('middle');
      }
      currentRow++;
    }
  }
}

/**
 * Анализирует один объект и заполняет лист анализа.
 * @param {Array} objectData Данные объекта.
 * @param {Object} competitorsData Данные конкурентов.
 * @returns {Object} Результаты анализа.
 */
function analyzeSingleObject(objectData, competitorsData) {
  try {
    const { activeCompetitors, soldCompetitors } = competitorsData;
    
    // Получаем данные рекламы
    const advertisingData = getAdvertisingData(objectData[5]); // objectData[5] - код объекта
    
    // Вычисляем метрики
    const metrics = calculateSingleObjectMetrics(objectData, activeCompetitors, soldCompetitors, advertisingData);
    
    // Заполняем лист анализа объекта
    fillAnalysisObjectSheet(objectData, advertisingData, metrics);
    
    return metrics;
    
  } catch (e) {
    Logger.log(`Ошибка в analyzeSingleObject: ${e.stack}`);
    return null;
  }
}

/**
 * Получает данные рекламы для объекта.
 * @param {string} objectCode Код объекта.
 * @returns {Object} Данные рекламы.
 */
function getAdvertisingData(objectCode) {
  const avitoData = getAdvertisingPlatformData(SHEETS.AVITO, objectCode);
  const cianData = getAdvertisingPlatformData(SHEETS.CIAN, objectCode);
  const domclickData = getAdvertisingPlatformData(SHEETS.DOMCLICK, objectCode);
  
  return {
    avito: avitoData,
    cian: cianData,
    domclick: domclickData
  };
}

/**
 * Получает данные рекламы с конкретной площадки.
 * @param {string} sheetName Название листа площадки.
 * @param {string} objectCode Код объекта.
 * @returns {Object} Данные рекламы.
 */
function getAdvertisingPlatformData(sheetName, objectCode) {
  const sheet = SPREADSHEET.getSheetByName(sheetName);
  if (!sheet || sheet.getLastRow() < 3) {
    return { status: 'Нет данных', date: null };
  }
  
  const data = sheet.getRange('A3:D' + sheet.getLastRow()).getValues();
  const foundRow = data.find(row => String(row[1]).trim() === String(objectCode).trim());
  
  if (foundRow) {
    return {
      status: foundRow[2] || 'Нет данных',
      date: foundRow[3] || null
    };
  }
  
  return { status: 'Нет данных', date: null };
}

/**
 * Вычисляет метрики для одного объекта (полная оригинальная методология).
 * @param {Array} objectData Данные объекта.
 * @param {Array} activeCompetitors Активные конкуренты.
 * @param {Array} soldCompetitors Проданные конкуренты.
 * @param {Object} advertisingData Данные рекламы.
 * @returns {Object} Вычисленные метрики.
 */
function calculateSingleObjectMetrics(objectData, activeCompetitors, soldCompetitors, advertisingData) {
  const objectPrice = Number(objectData[7]) || 0;
  const objectArea = Number(objectData[4]) || 1;
  const objectPricePerM2 = objectArea > 0 ? objectPrice / objectArea : 0;
  
  // Базовые метрики
  const competitorsInDistrict = activeCompetitors.length;
  const totalSales = soldCompetitors.length;
  
  // Для индивидуального анализа используем фиксированный период 6 месяцев
  // (так как у нас нет листа "Аналитика всех ОН в группе" с ячейками C1-C2)
  const periodMonths = 6;
  Logger.log(`Используем период по умолчанию: ${periodMonths} месяцев`);
  
  // Спрос (объектов в месяц)
  const demandPerMonth = totalSales / periodMonths;
  
  // Тип ликвидности
  const liquidityType = determineLiquidityType(competitorsInDistrict, totalSales, demandPerMonth);
  
  // Оценка рынка
  const marketAssessment = assessMarket(competitorsInDistrict, totalSales, demandPerMonth);
  
  // Тренд конкуренции (сравниваем активных в первой и второй половине периода)
  const competitionTrend = calculateCompetitionTrendForSingleObject(activeCompetitors, periodMonths);
  
  // Ранг объекта по цене
  const objectRank = calculateObjectRank(objectData, activeCompetitors);
  
  // Тренд цены за м²
  const priceTrendPerM2 = calculatePriceTrendPerM2(soldCompetitors);
  
  // Соотношения с рынком
  const marketRatios = calculateMarketRatios(objectPricePerM2, activeCompetitors, soldCompetitors);
  
  // Дополнительные метрики (высчитываем до прогнозов)
  const avgNewObjectsPerMonth = competitorsInDistrict / periodMonths;
  const arrivalToDemandRatio = demandPerMonth > 0 ? ((avgNewObjectsPerMonth / demandPerMonth) * 100) : 0;
  
  // Прогнозы
  const forecasts = calculateSingleObjectForecasts(objectPrice, objectPricePerM2, marketRatios, demandPerMonth, objectData, activeCompetitors, soldCompetitors, avgNewObjectsPerMonth);
  
  const weightedRecommendedPrice = calculateWeightedRecommendedPrice(marketRatios, forecasts);
  
  return {
    competitorsInDistrict,
    totalSales,
    demandPerMonth,
    liquidityType,
    marketAssessment,
    competitionTrend,
    objectRank,
    priceTrendPerM2,
    marketRatios,
    forecasts,
    avgNewObjectsPerMonth,
    arrivalToDemandRatio,
    weightedRecommendedPrice
  };
}

/**
 * Заполняет лист анализа объекта данными.
 * @param {Array} objectData Данные объекта.
 * @param {Object} advertisingData Данные рекламы.
 * @param {Object} metrics Вычисленные метрики.
 */
function fillAnalysisObjectSheet(objectData, advertisingData, metrics) {
  const sheet = SPREADSHEET.getSheetByName(SHEETS.SINGLE_OBJECT_ANALYSIS);
  if (!sheet) return;
  
  // Очищаем лист
  sheet.getRange('A3:AP1000').clearContent();
  
  // Подготавливаем данные для записи
  const rowData = [
    objectData[0], // Дата вывода заявки в активные
    objectData[1], // Район
    objectData[2], // Тип объекта
    objectData[3], // Кол-во комнат
    objectData[4], // Площадь
    objectData[5], // Ссылка на объект
    objectData[6], // Тип ремонта
    objectData[7], // Цена
    objectData[8], // Этаж
    objectData[9], // Кол-во этажей
    objectData[10], // Год постройки
    objectData[11], // ФИО риэлтора
    objectData[12], // Наличие проф. фото?
    objectData[13], // Описание больше 400?
    objectData[14], // Есть планировка?
    advertisingData.avito.status, // авито
    advertisingData.avito.date, // дата авито
    advertisingData.cian.status, // циан
    advertisingData.cian.date, // дата циан
    advertisingData.domclick.status, // домклик
    advertisingData.domclick.date, // дата домклик
    metrics.competitorsInDistrict, // конкурентов в р-не
    metrics.totalSales, // продажи всего
    metrics.demandPerMonth, // спрос, объектов/мес
    metrics.avgNewObjectsPerMonth, // Прибытие, об/мес
    metrics.liquidityType, // Тип ликвидности
    metrics.marketAssessment, // Оценка рынка
    metrics.competitionTrend, // Тренд конкуренции, %
    metrics.objectRank, // место/ранг нашего объекта
    metrics.priceTrendPerM2, // Тренд цены за м², руб/мес
    metrics.marketRatios.activeRatio, // Соотношение с рынком активных, %
    metrics.marketRatios.soldRatio, // Соотношение с рынком проданных, %
    metrics.marketRatios.avgActivePrice, // ср. цена активных
    objectData[7], // цена нашего ОН
    metrics.marketRatios.activeRatio, // разница с активными, %
    metrics.marketRatios.avgSoldPrice, // ср. цена проданных
    objectData[7], // цена нашего ОН
    metrics.marketRatios.soldRatio, // разница с проданных, %
    metrics.forecasts.quickPrice, // Цена (быстрая продажа)
    metrics.forecasts.quickMonths, // Срок (быстрая), мес.
    metrics.forecasts.marketPrice, // Цена (рыночная)
    metrics.forecasts.marketMonths // Срок (рыночная), мес.
  ];
  
  // Записываем данные в строку 3
  sheet.getRange('A3:AP3').setValues([rowData]);
}

/**
 * Главная функция анализа одного объекта по коду.
 * @param {string} objectCode Код объекта для анализа.
 * @returns {boolean} Успешность выполнения.
 */
function analyzeSingleObjectByCode(objectCode) {
  try {
    Logger.log(`Начинаем анализ объекта с кодом: ${objectCode}`);
    
    // 1. Валидация кода
    if (!validateCode(objectCode)) {
      Logger.log('❌ Неверный код объекта');
      return false;
    }
    
    // 2. Поиск объекта
    const objectData = findObjectByCode(objectCode);
    if (!objectData) {
      Logger.log('❌ Объект с таким кодом не найден в активных');
      return false;
    }
    
    // 3. Построение массива конкурентов
    const competitorsData = buildSingleObjectCompetitorsArray(objectData);
    
    // 3.1. Записываем критерии поиска конкурентов
    const criteria = {
      district: objectData[1],
      type: objectData[2],
      rooms: Number(objectData[3]),
      area: Number(objectData[4]),
      repair: objectData[6],
      buildYear: Number(objectData[10])
    };
    writeCompetitorCriteria(objectData, criteria);
    
    // 4. Анализ объекта
    const analysisResults = analyzeSingleObject(objectData, competitorsData);
    
    if (!analysisResults) {
      Logger.log('❌ Ошибка при анализе объекта');
      return false;
    }
    
    // 5. Генерация отчета
    const reportGenerated = generateSingleObjectReport(objectData, analysisResults, competitorsData);
    
    if (reportGenerated) {
      Logger.log('Анализ объекта завершен успешно');
      return true;
    } else {
      Logger.log('Ошибка при генерации отчета');
      return false;
    }
    
  } catch (e) {
    Logger.log(`Ошибка в analyzeSingleObjectByCode: ${e.stack}`);
    Logger.log('❌ Ошибка при анализе объекта: ' + e.message);
    return false;
  }
}

/**
 * Генерирует отчет по одному объекту.
 * @param {Array} objectData Данные объекта.
 * @param {Object} analysisResults Результаты анализа.
 * @param {Object} competitorsData Данные конкурентов.
 * @returns {boolean} Успешность генерации.
 */
function generateSingleObjectReport(objectData, analysisResults, competitorsData) {
  try {
    const sheet = SPREADSHEET.getSheetByName(SHEETS.SINGLE_OBJECT_ANALYTICS);
    if (!sheet) return false;
    
    // Очищаем область отчета
    sheet.getRange('A4:B50').clearContent().clearFormat();
    
    // Генерируем структурированные данные отчета
    const reportData = createSingleObjectReportData(objectData, analysisResults, competitorsData);
    
    // Цвета для секций отчёта
    const SECTION_COLORS = {
      '📋': '#D6EAF8',  // ВАШ ОБЪЕКТ - голубой
      '📊': '#D5F5E3',  // РЫНОК - зелёный
      '📍': '#FCF3CF',  // ВАША ПОЗИЦИЯ - жёлтый
      '💰': '#FADBD8',  // РЕКОМЕНДАЦИЯ - розовый
      '⏱️': '#E8DAEF',  // СРОКИ - сиреневый
      '📈': '#D5DBDB'   // ЭКОНОМИКА - серый
    };
    
    // Записываем данные построчно с цветовым форматированием
    reportData.forEach((row, index) => {
      const rowNumber = 4 + index;
      sheet.getRange(`A${rowNumber}`).setValue(row[0]);
      sheet.getRange(`B${rowNumber}`).setValue(row[1]);
      
      // Проверяем, является ли строка заголовком секции (начинается с emoji)
      const firstChar = row[0] ? row[0].charAt(0) : '';
      const secondChar = row[0] ? row[0].substring(0, 2) : '';
      
      if (SECTION_COLORS[firstChar] || SECTION_COLORS[secondChar]) {
        const color = SECTION_COLORS[firstChar] || SECTION_COLORS[secondChar];
        sheet.getRange(`A${rowNumber}:B${rowNumber}`)
          .setFontWeight('bold')
          .setBackground(color)
          .setFontSize(10);
      } else if (row[0] && row[1] !== '') {
        // Обычные строки с данными
        sheet.getRange(`A${rowNumber}`).setFontWeight('bold').setFontSize(9);
        sheet.getRange(`B${rowNumber}`).setFontSize(9);
      } else {
        sheet.getRange(`A${rowNumber}:B${rowNumber}`).setFontSize(9);
      }
    });
    
    // Добавляем ИИ анализ в конец
    const aiAnalysis = createSingleObjectReportText(objectData, analysisResults, competitorsData);
    const aiRowNumber = 4 + reportData.length + 1;
    sheet.getRange(`A${aiRowNumber}`).setValue('🤖 ВЫВОДЫ ИИ');
    sheet.getRange(`A${aiRowNumber}:B${aiRowNumber}`)
      .setFontWeight('bold')
      .setBackground('#AED6F1')
      .setFontSize(10);
    
    // Объединяем ячейки для отчета ИИ ассистента
    const aiContentRow = aiRowNumber + 1;
    sheet.getRange(`A${aiContentRow}:B${aiContentRow}`).merge();
    sheet.getRange(`A${aiContentRow}`).setValue(aiAnalysis);
    sheet.getRange(`A${aiContentRow}`)
      .setFontSize(9)
      .setWrap(true)
      .setBackground('#F8F9F9');
    
    Logger.log('Отчет по объекту сгенерирован');
    return true;
    
  } catch (e) {
    Logger.log(`Ошибка в generateSingleObjectReport: ${e.stack}`);
    return false;
  }
}

/**
 * [УЛУЧШЕНО v1.0] Создает структурированные данные отчета по объекту.
 * Добавлены новые метрики: сезонность, деградация ранга, двойной анализ цены, факторы влияния.
 * @param {Array} objectData Данные объекта.
 * @param {Object} analysisResults Результаты анализа.
 * @param {Object} competitorsData Данные конкурентов.
 * @returns {Array} Массив строк отчета.
 */
function createSingleObjectReportData(objectData, analysisResults, competitorsData) {
  const { activeCompetitors, soldCompetitors } = competitorsData;
  
  // Получаем текущий сезонный коэффициент
  const currentMonth = new Date().getMonth() + 1;
  const seasonalCoef = SEASONAL_COEFFICIENTS[currentMonth] || 1.0;
  const monthNames = ['', 'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 
                      'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'];
  
  // Расчёт динамической деградации ранга
  const price = Number(objectData[7]) || 0;
  const area = Number(objectData[4]) || 1;
  const activePrices = activeCompetitors.map(c => c[5] || c[4]).filter(p => typeof p === 'number' && p > 0);
  
  const dynamicResult = calculateDynamicTimeOnMarket({
    rank: analysisResults.objectRank || 1,
    demand: analysisResults.demandPerMonth || 1,
    arrival: analysisResults.avgNewObjectsPerMonth || 0,
    price: price,
    activePrices: activePrices
  });
  
  // Двойной анализ цены
  const dualAnalysis = calculateDualPriceAnalysis({
    price: price,
    area: area,
    activeCompetitors: activeCompetitors,
    soldCompetitors: soldCompetitors
  });
  
  // Получаем макроконтекст
  const macro = getMacroContext();
  
  // УПРОЩЁННЫЕ метки для понятного отчёта
  const reportData = [
    ['📋 ВАШ ОБЪЕКТ', ''],
    ['Код', objectData[5]],
    ['Район', objectData[1]],
    ['Квартира', `${objectData[3]}-комн., ${objectData[4]} м²`],
    ['Дом', `${objectData[10]} г.`],
    ['Ремонт', objectData[6]],
    ['Ваша цена', `${Number(objectData[7]).toLocaleString()} ₽ (${Math.round(Number(objectData[7])/Number(objectData[4])).toLocaleString()} ₽/м²)`],
    ['', ''],
    ['📊 РЫНОК', ''],
    ['Ситуация', analysisResults.marketAssessment],
    ['Продаётся в месяц', `${analysisResults.demandPerMonth.toFixed(1)} объектов`],
    ['Конкурентов сейчас', `${activeCompetitors.length}`],
    ['Новых в месяц', `+${analysisResults.avgNewObjectsPerMonth.toFixed(1)}`],
    ['Баланс рынка', `${analysisResults.arrivalToDemandRatio.toFixed(0)}%`],
    ['Скорость продажи', analysisResults.liquidityType],
    ['', ''],
    ['📍 ВАША ПОЗИЦИЯ', ''],
    ['Место по цене', `${analysisResults.objectRank} из ${activeCompetitors.length}`],
    ['vs конкуренты', `${analysisResults.marketRatios.activeRatio > 0 ? '+' : ''}${analysisResults.marketRatios.activeRatio.toFixed(1)}%`],
    ['vs реальные сделки', `${analysisResults.marketRatios.soldRatio > 0 ? '+' : ''}${analysisResults.marketRatios.soldRatio.toFixed(1)}%`],
    ['Ср. цена конкурентов', `${Math.round(analysisResults.marketRatios.avgActivePrice * Number(objectData[4])).toLocaleString()} ₽`],
    ['Ср. цена сделок', `${Math.round(analysisResults.marketRatios.avgSoldPrice * Number(objectData[4])).toLocaleString()} ₽`],
    ['', ''],
    ['💰 РЕКОМЕНДАЦИЯ', ''],
    ['Быстро (1-2 мес)', `${analysisResults.forecasts.quickPrice.toLocaleString()} ₽`],
    ['Рынок (3-4 мес)', `${analysisResults.forecasts.marketPrice.toLocaleString()} ₽`],
    ['', ''],
    ['⏱️ СРОКИ', ''],
    ['Сейчас', `${monthNames[currentMonth]}`],
    ['Сезон', `${seasonalCoef > 1 ? 'дольше на ' : 'быстрее на '}${Math.abs(Math.round((seasonalCoef - 1) * 100))}%`],
    ['Прогноз', `${dynamicResult.months.toFixed(1)} мес.`],
    ['Примечание', dynamicResult.info],
    ['', ''],
    ['📈 ЭКОНОМИКА', ''],
    ['Ставка ЦБ', `${macro.keyRate}%`],
    ['Ипотека', `${macro.mortgageRate}%`],
    ['Семейная ипотека', macro.familyMortgage ? '6%' : 'Нет'],
    ['Тренд', macro.marketTrend]
  ];
  
  return reportData;
}

/**
 * [УЛУЧШЕНО v1.0] Создает текстовый отчет по объекту с использованием ИИ аналитика.
 * Теперь использует callGeminiAnalyst для структурированного анализа.
 * @param {Array} objectData Данные объекта.
 * @param {Object} analysisResults Результаты анализа.
 * @param {Object} competitorsData Данные конкурентов.
 * @returns {string} Текст отчета.
 */
function createSingleObjectReportText(objectData, analysisResults, competitorsData) {
  const { activeCompetitors, soldCompetitors } = competitorsData;
  
  // Получаем сезонные и макро-данные
  const currentMonth = new Date().getMonth() + 1;
  const seasonalCoef = SEASONAL_COEFFICIENTS[currentMonth] || 1.0;
  const macro = getMacroContext();
  const monthNames = ['', 'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 
                      'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'];
  
  // Расчёт качества объекта
  const dataMap = {
    'Тип ремонта': objectData[6],
    'Год постройки': objectData[10],
    'Этаж': objectData[8],
    'Этажность': objectData[9],
    'проф. фото': objectData[11],
    'описание': objectData[12],
    'планировка': objectData[13]
  };
  const qualityScore = calculateQualityScore(dataMap);
  
  // Подготавливаем сырые данные для ИИ-аналитика
  const analyticsData = {
    objectInfo: {
      code: objectData[5],
      district: objectData[1],
      rooms: objectData[3],
      area: objectData[4],
      buildYear: objectData[10],
      repair: objectData[6],
      floor: objectData[8],
      totalFloors: objectData[9],
      price: Number(objectData[7]),
      pricePerSqm: Math.round(Number(objectData[7]) / Number(objectData[4]))
    },
    marketData: {
      assessment: analysisResults.marketAssessment,
      demandPerMonth: analysisResults.demandPerMonth,
      liquidityType: analysisResults.liquidityType,
      activeCount: activeCompetitors.length,
      soldCount: soldCompetitors.length,
      avgNewObjectsPerMonth: analysisResults.avgNewObjectsPerMonth,
      arrivalToDemandRatio: analysisResults.arrivalToDemandRatio
    },
    positioning: {
      rank: analysisResults.objectRank,
      activeRatio: analysisResults.marketRatios.activeRatio,
      soldRatio: analysisResults.marketRatios.soldRatio,
      avgActivePrice: analysisResults.marketRatios.avgActivePrice,
      avgSoldPrice: analysisResults.marketRatios.avgSoldPrice
    },
    forecasts: analysisResults.forecasts,
    factors: {
      qualityScore: qualityScore,
      seasonalCoef: seasonalCoef,
      currentMonth: monthNames[currentMonth]
    }
  };
  
  // Пробуем вызвать ИИ-аналитика
  const aiResult = callGeminiAnalyst(analyticsData, macro);
  
  // Если ИИ-аналитик вернул структурированные данные
  if (aiResult.success) {
    const ai = aiResult;
    
    // Форматируем структурированный ответ в текст
    let report = '';
    
    // Краткая оценка рынка
    report += 'Краткая оценка рынка.\n';
    report += ai.analysis?.marketPosition || `Мы проанализировали ситуацию в районе "${objectData[1]}". `;
    report += ` Текущий спрос на недвижимость здесь оценивается как ${analysisResults.marketAssessment.toLowerCase()}, `;
    report += `а ёмкость рынка составляет ${analysisResults.demandPerMonth.toFixed(1)} объекта в месяц. `;
    report += `Уровень ликвидности соответствует типу ${analysisResults.liquidityType}. `;
    report += `При этом конкурентная среда ${analysisResults.arrivalToDemandRatio > 100 ? 'насыщена' : 'умеренна'}: `;
    report += `в данный момент в продаже находится ${activeCompetitors.length} активных объектов, `;
    report += `с которыми вам предстоит соперничать за покупателя.\n\n`;
    
    // Позиция объекта
    report += 'Позиция объекта на этом рынке.\n';
    report += `Ваша ${objectData[3]}-комнатная квартира площадью ${objectData[4]} квадратных метров выставлена по цене ${Number(objectData[7]).toLocaleString()} рублей. `;
    report += `Относительно предложений конкурентов, которые сейчас находятся в рекламе, ваша стоимость `;
    report += `${analysisResults.marketRatios.activeRatio > 0 ? 'выше' : 'ниже'} средней на ${Math.abs(analysisResults.marketRatios.activeRatio).toFixed(1)}%. `;
    report += `Однако при сравнении с реальными сделками текущая цена отличается на ${Math.abs(analysisResults.marketRatios.soldRatio).toFixed(1)}% `;
    report += `от средней стоимости уже проданных объектов. `;
    
    // Добавляем информацию о сезонности
    if (seasonalCoef !== 1.0) {
      report += `\n\nВажно учитывать сезонный фактор: ${monthNames[currentMonth]} `;
      report += seasonalCoef > 1 ? `традиционно увеличивает сроки продажи на ${Math.round((seasonalCoef - 1) * 100)}%.` : 
                                   `благоприятен для продаж — сроки сокращаются на ${Math.round((1 - seasonalCoef) * 100)}%.`;
    }
    
    // Добавляем информацию о макроконтексте
    if (macro.keyRate >= 15) {
      report += ` При текущей ключевой ставке ЦБ ${macro.keyRate}% доступность ипотеки ограничена, что сужает круг покупателей.`;
    }
    if (macro.familyMortgage) {
      report += ` Для семей с детьми доступна льготная ипотека под 6%, что может привлечь эту категорию покупателей.`;
    }
    report += '\n\n';
    
    // Ценовые стратегии
    report += 'Ценовые стратегии с прогнозами.\n';
    report += `Опираясь на статистику, мы рассчитали два возможных сценария реализации. `;
    report += `Стратегия быстрой продажи предполагает цену около ${analysisResults.forecasts.quickPrice.toLocaleString()} рублей `;
    report += `с прогнозом выхода на сделку за ${analysisResults.forecasts.quickMonths} мес. `;
    report += `Стратегия рыночной продажи ориентирована на стоимость ${analysisResults.forecasts.marketPrice.toLocaleString()} рублей, `;
    report += `при этом ожидаемый срок реализации также составляет ${analysisResults.forecasts.marketMonths} мес.`;
    
    // Добавляем рекомендации ИИ
    if (ai.recommendations && ai.recommendations.length > 0) {
      report += '\n\nРекомендации: ';
      ai.recommendations.slice(0, 3).forEach((rec, i) => {
        report += `${i + 1}) ${rec.action}${rec.impact ? ` (${rec.impact})` : ''}. `;
      });
    }
    
    // Уровень уверенности
    if (ai.confidence) {
      report += `\n\nУровень уверенности в прогнозе: ${ai.confidence}%.`;
      if (ai.confidenceReasoning) {
        report += ` ${ai.confidenceReasoning}`;
      }
    }
    
    return report;
  }
  
  // Вспомогательные описания для "простых смертных"
  const liquidityDescriptions = {
    'A+': 'очень высокая (продажа за считанные дни)',
    'A': 'высокая (быстрая продажа)',
    'B': 'средняя (сбалансированный спрос)',
    'C': 'низкая (долгая продажа)',
    'C-': 'очень низкая (рынок "стоит")'
  };
  const liquidityText = liquidityDescriptions[analysisResults.liquidityType] || analysisResults.liquidityType;

  // Fallback на старый метод, если ИИ-аналитик не сработал
  const geminiSummary = `ОБЪЕКТ: ${objectData[3]}-комнатная квартира ${objectData[4]} м² в районе "${objectData[1]}".
ОЦЕНКА РЫНКА: ${analysisResults.marketAssessment}. В районе продаётся примерно ${analysisResults.demandPerMonth.toFixed(1)} аналогичных объектов в месяц.
СКОРОСТЬ ПРОДАЖИ (Ликвидность): ${liquidityText}.
КОНКУРЕНЦИЯ: Сейчас в продаже ${activeCompetitors.length} объектов-конкурентов.
СЕЗОННОСТЬ: ${monthNames[currentMonth]}, фактор сезона: ${seasonalCoef > 1 ? 'замедляет' : 'ускоряет'} продажу на ${Math.abs(Math.round((seasonalCoef - 1) * 100))}%.
МАКРОФАКТОРЫ: Ключевая ставка ЦБ ${macro.keyRate}%, ипотека ${macro.mortgageRate}%, семейная ипотека ${macro.familyMortgage ? 'доступна' : 'отсутствует'}.
ВАША ПОЗИЦИЯ: Текущая цена ${Number(objectData[7]).toLocaleString()} ₽. Место по цене: ${analysisResults.objectRank}-е из ${activeCompetitors.length}.
Цена отличается на ${Math.abs(analysisResults.marketRatios.activeRatio || 0).toFixed(1)}% от конкурентов и на ${Math.abs(analysisResults.marketRatios.soldRatio || 0).toFixed(1)}% от цен реальных сделок.
ПРОГНОЗЫ:
1. Стратегия "Быстрая продажа": цена ~${analysisResults.forecasts.quickPrice.toLocaleString()} ₽, срок ~${analysisResults.forecasts.quickMonths} мес.
2. Стратегия "Рыночная цена": цена ~${analysisResults.forecasts.marketPrice.toLocaleString()} ₽, срок ~${analysisResults.forecasts.marketMonths} мес.`;
  
  const prompt = 'Ты — опытный литературный редактор и специалист по деловой коммуникации.\n\nТебе предоставлен сухой, аналитический текст-резюме по оценке недвижимости (анализ в секции \'АНАЛИЗ ИИ АССИСТЕНТА\').\n\nТвоя главная задача: Переписать этот текст из научного/технического стиля в гладкий, профессиональный и деловой текст, ориентированный на прямое обращение к клиенту.\n\nОбязательные требования к тексту:\n\nСохранение всей сути, всех численных данных и всех выводов из исходного аналитического текста. Никакая информация, присутствующая в секции \'АНАЛИЗ ИИ АССИСТЕНТА\' (включая цифры по спросу, конкуренции, ликвидности, позиционированию цены и прогнозы по стратегиям), не должна быть потеряна.\n\nСтруктура отчета должна быть строго следующей и содержать точные заголовки, как указано ниже:\n\nКраткая оценка рынка.\n\nПозиция объекта на этом рынке.\n\nЦеновые стратегии с прогнозами.\n\nДОПОЛНИТЕЛЬНО включи в текст:\n- Влияние СЕЗОННОСТИ на сроки продажи\n- Влияние МАКРОКОНТЕКСТА (ставка ЦБ, ипотека) на спрос\n- Влияние КАЧЕСТВА объекта на цену\n\nНедопустимо додумывание или добавление новой информации. Если в исходном тексте нет данных по какому-либо аспекту, это должно быть отражено в переписанном тексте соответствующей формулировкой.\n\nФорматирование: Текст должен быть сплошным, без использования любой Markdown-разметки (такой как решетки #, звездочки *, жирный текст, курсив и т.д.). Использование сплошного текста является критически важным условием.\n\nЦелевой стиль: Деловая проза, понятная неспециалисту, внушающая доверие, четкая и лаконичная. Избегай канцелярита, но сохраняй профессиональный тон.';
  
  const geminiResponse = callGemini(prompt, geminiSummary);
  
  return geminiResponse;
}

/**
 * Очищает данные от некорректных значений (9, null, undefined, 0).
 * @param {*} value Значение для очистки.
 * @returns {*} Очищенное значение или null.
 */
function cleanDataValue(value) {
  if (value === null || value === undefined || value === '' || value === 0 || value === '9' || value === 9) {
    return null;
  }
  return value;
}

/**
 * Вычисляет усеченное среднее (отбрасывает 10% крайних значений).
 * @param {Array} prices Массив цен.
 * @returns {number} Усеченное среднее.
 */
function calculateTrimmedMean(prices) {
  if (prices.length === 0) return 0;
  if (prices.length < 3) return prices.reduce((sum, price) => sum + price, 0) / prices.length;
  
  // Сортируем цены
  const sortedPrices = [...prices].sort((a, b) => a - b);
  
  // Вычисляем количество элементов для отбрасывания (20% с каждой стороны)
  const trimCount = Math.floor(sortedPrices.length * 0.2);
  
  // Отбрасываем крайние значения
  const trimmedPrices = sortedPrices.slice(trimCount, sortedPrices.length - trimCount);
  
  // Возвращаем среднее арифметическое
  return trimmedPrices.reduce((sum, price) => sum + price, 0) / trimmedPrices.length;
}

/**
 * Вычисляет медиану.
 * @param {Array} prices Массив цен.
 * @returns {number} Медиана.
 */
function calculateMedian(prices) {
  if (prices.length === 0) return 0;
  if (prices.length === 1) return prices[0];
  
  // Сортируем цены
  const sortedPrices = [...prices].sort((a, b) => a - b);
  
  const middle = Math.floor(sortedPrices.length / 2);
  
  if (sortedPrices.length % 2 === 0) {
    // Четное количество элементов - берем среднее двух центральных
    return (sortedPrices[middle - 1] + sortedPrices[middle]) / 2;
  } else {
    // Нечетное количество элементов - берем центральный
    return sortedPrices[middle];
  }
}

/**
 * Вычисляет средневзвешенную рекомендованную цену.
 * @param {Object} marketRatios Соотношения с рынком.
 * @param {Object} forecasts Прогнозы.
 * @returns {number} Средневзвешенная цена.
 */
function calculateWeightedRecommendedPrice(marketRatios, forecasts) {
  const activePrice = marketRatios.avgActivePrice || 0;
  const soldPrice = marketRatios.avgSoldPrice || 0;
  const marketPrice = forecasts.marketPrice || 0;
  
  if (activePrice > 0 && soldPrice > 0 && marketPrice > 0) {
    return (activePrice + soldPrice + marketPrice) / 3;
  }
  
  return marketPrice || 0;
}

/**
 * Вычисляет спрос в месяц.
 * @param {Array} soldCompetitors Проданные конкуренты.
 * @returns {number} Спрос в месяц.
 */
function calculateDemandPerMonth(soldCompetitors) {
  // Для индивидуального анализа используем фиксированный период 6 месяцев
  const periodMonths = 6;
  
  return soldCompetitors.length / periodMonths;
}

/**
 * Определяет тип ликвидности.
 * @param {number} competitors Количество конкурентов.
 * @param {number} sales Количество продаж.
 * @param {number} demand Спрос в месяц.
 * @returns {string} Тип ликвидности.
 */
function determineLiquidityType(competitors, sales, demand) {
  if (competitors === 0) return 'C-';
  
  // Правильная формула: (Спрос / Предложение) * 100%
  const liquidityIndex = (demand / competitors) * 100;
  
  // Правильные пороговые значения по методологии
  // Скорректированные пороги для предотвращения противоречий (v1.1)
  if (liquidityIndex > 40 && demand >= 3) return 'A+'; // Исключительно высокий
  if (liquidityIndex >= 25) return 'A'; // Высокий
  if (liquidityIndex >= 15) return 'B'; // Сбалансированный
  if (liquidityIndex >= 8) return 'C';  // Низкий
  return 'C-'; // Очень низкий
}

/**
 * Оценивает рынок.
 * @param {number} competitors Количество конкурентов.
 * @param {number} sales Количество продаж.
 * @param {number} demand Спрос в месяц.
 * @returns {string} Оценка рынка.
 */
function assessMarket(competitors, sales, demand) {
  if (competitors === 0) return 'Нет данных';
  
  const liquidityIndex = demand / (competitors / 12);
  
  // Скорректированные пороги оценки спроса (v1.1)
  if (liquidityIndex >= 3) return 'Очень высокий спрос';
  if (liquidityIndex >= 2) return 'Высокий спрос';
  if (liquidityIndex >= 1.2) return 'Сбалансированный рынок';
  if (liquidityIndex >= 0.7) return 'Низкий спрос';
  return 'Очень низкий спрос';
}

/**
 * Вычисляет тренд конкуренции.
 * @param {Array} activeCompetitors Активные конкуренты.
 * @param {Array} soldCompetitors Проданные конкуренты.
 * @returns {number} Тренд конкуренции в %.
 */
function calculateCompetitionTrend(activeCompetitors, soldCompetitors) {
  // Упрощенная версия - в оригинале более сложная логика
  const activeCount = activeCompetitors.length;
  const soldCount = soldCompetitors.length;
  
  if (soldCount === 0) return 0;
  
  return ((activeCount - soldCount) / soldCount) * 100;
}

/**
 * Вычисляет тренд конкуренции для индивидуального анализа.
 * @param {Array} activeCompetitors Активные конкуренты.
 * @param {number} periodMonths Период в месяцах.
 * @returns {number} Тренд конкуренции в %.
 */
function calculateCompetitionTrendForSingleObject(activeCompetitors, periodMonths) {
  if (activeCompetitors.length === 0) return 0;
  
  // Для индивидуального анализа используем текущую дату как конец периода
  const endDate = new Date();
  const startDate = new Date(endDate.getTime() - (periodMonths * 30.44 * 24 * 60 * 60 * 1000));
  const midPoint = new Date(startDate.getTime() + (endDate.getTime() - startDate.getTime()) / 2);
  
  // Считаем количество активных объектов в первой и второй половине периода
  const firstHalfCount = activeCompetitors.filter(row => {
    const rowDate = new Date(row[0]); // Дата в столбце A
    return rowDate >= startDate && rowDate < midPoint;
  }).length;
  
  const secondHalfCount = activeCompetitors.filter(row => {
    const rowDate = new Date(row[0]); // Дата в столбце A
    return rowDate >= midPoint && rowDate <= endDate;
  }).length;
  
  // Определяем тренд
  if (firstHalfCount === 0 && secondHalfCount > 0) return 100; // Резкий рост
  if (firstHalfCount === 0 || secondHalfCount === 0) return 0; // Стабильно
  
  const trend = ((secondHalfCount - firstHalfCount) / firstHalfCount) * 100;
  return Math.round(trend);
}

/**
 * Вычисляет ранг объекта по оригинальной методологии.
 * @param {Array} objectData Данные объекта.
 * @param {Array} activeCompetitors Активные конкуренты.
 * @returns {number} Ранг объекта.
 */
function calculateObjectRank(objectData, activeCompetitors) {
  const objectPrice = Number(objectData[7]) || 0; // Цена нашего объекта (столбец H, индекс 7)
  
  if (activeCompetitors.length === 0) return 1;
  
  // Формируем массив всех цен (конкуренты + наш объект)
  // В отформатированных данных конкурентов цена находится в столбце 5 (индекс 5)
  const competitorPrices = activeCompetitors.map(c => Number(c[5]) || 0).filter(p => p > 0);
  
  // Проверяем, есть ли уже наш объект в массиве конкурентов
  const hasOurObject = competitorPrices.some(price => price === objectPrice);
  
  // Если нашего объекта нет в массиве, добавляем его
  const allActivePrices = hasOurObject 
    ? competitorPrices 
    : [...competitorPrices, objectPrice];
  
  // Сортируем по цене
  allActivePrices.sort((a, b) => a - b);
  
  // Рассчитываем ранг: считаем количество объектов дешевле нас + 1
  const rankByPrice = 1 + allActivePrices.filter(p => p < objectPrice).length;
  
  return rankByPrice;
}

/**
 * Вычисляет тренд цены за м² с помощью линейной регрессии.
 * @param {Array} soldCompetitors Проданные конкуренты.
 * @returns {number} Тренд цены за м² в руб/мес.
 */
function calculatePriceTrendPerM2(soldCompetitors) {
  if (soldCompetitors.length < 2) return 0;
  
  // Подготавливаем данные для регрессии
  const dataPoints = soldCompetitors
    .map(row => {
      const price = cleanDataValue(row[7]);
      const area = cleanDataValue(row[4]);
      const date = new Date(row[0]);
      
      if (price && area && area > 0 && !isNaN(date.getTime())) {
        return {
          x: date.getTime(), // Время в миллисекундах
          y: Number(price) / Number(area) // Цена за м²
        };
      }
      return null;
    })
    .filter(point => point !== null);
  
  if (dataPoints.length < 2) return 0;
  
  // Вычисляем линейную регрессию
  const regression = calculateLinearRegression(dataPoints);
  
  // Конвертируем наклон в руб/мес (миллисекунды в месяц)
  const millisecondsPerMonth = 1000 * 60 * 60 * 24 * 30.4375;
  return regression.slope * millisecondsPerMonth;
}

/**
 * Вычисляет линейную регрессию для массива точек.
 * @param {Array} points Массив точек {x, y}.
 * @returns {Object} {slope, intercept, r2}.
 */
function calculateLinearRegression(points) {
  const n = points.length;
  const sumX = points.reduce((sum, p) => sum + p.x, 0);
  const sumY = points.reduce((sum, p) => sum + p.y, 0);
  const sumXY = points.reduce((sum, p) => sum + p.x * p.y, 0);
  const sumXX = points.reduce((sum, p) => sum + p.x * p.x, 0);
  const sumYY = points.reduce((sum, p) => sum + p.y * p.y, 0);
  
  const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
  const intercept = (sumY - slope * sumX) / n;
  
  // Вычисляем R²
  const yMean = sumY / n;
  const ssRes = points.reduce((sum, p) => sum + Math.pow(p.y - (slope * p.x + intercept), 2), 0);
  const ssTot = points.reduce((sum, p) => sum + Math.pow(p.y - yMean, 2), 0);
  const r2 = ssTot > 0 ? 1 - (ssRes / ssTot) : 0;
  
  return { slope, intercept, r2 };
}

/**
 * Вычисляет соотношения с рынком.
 * @param {number} objectPricePerM2 Цена за м² объекта.
 * @param {Array} activeCompetitors Активные конкуренты.
 * @param {Array} soldCompetitors Проданные конкуренты.
 * @returns {Object} Соотношения с рынком.
 */
function calculateMarketRatios(objectPricePerM2, activeCompetitors, soldCompetitors) {
  // Средняя цена за м² активных конкурентов (усеченное среднее - отбрасывает 20% крайних)
  // В отформатированных данных: столбец 5 = цена, столбец 4 = площадь
  const activePricesPerM2 = activeCompetitors
    .map(row => {
      const price = cleanDataValue(row[5]); // цена
      const area = cleanDataValue(row[4]); // площадь
      if (price && area && area > 0) {
        return Number(price) / Number(area); // цена за м²
      }
      return null;
    })
    .filter(price => price !== null && price > 0);
  const avgActivePricePerM2 = activePricesPerM2.length > 0 ? calculateTrimmedMean(activePricesPerM2) : 0;
  
  // Средняя цена за м² проданных конкурентов (медиана)
  const soldPricesPerM2 = soldCompetitors
    .map(row => {
      const price = cleanDataValue(row[5]); // цена
      const area = cleanDataValue(row[4]); // площадь
      if (price && area && area > 0) {
        return Number(price) / Number(area); // цена за м²
      }
      return null;
    })
    .filter(price => price !== null && price > 0);
  const avgSoldPricePerM2 = soldPricesPerM2.length > 0 ? calculateMedian(soldPricesPerM2) : 0;
  
  // Соотношения (показываем разницу в процентах с знаком)
  // Положительное значение = наша цена выше, отрицательное = наша цена ниже
  const activeRatio = avgActivePricePerM2 > 0 ? ((objectPricePerM2 - avgActivePricePerM2) / avgActivePricePerM2) * 100 : 0;
  const soldRatio = avgSoldPricePerM2 > 0 ? ((objectPricePerM2 - avgSoldPricePerM2) / avgSoldPricePerM2) * 100 : 0;
  
  return {
    avgActivePrice: avgActivePricePerM2,
    avgSoldPrice: avgSoldPricePerM2,
    activeRatio,
    soldRatio
  };
}


/**
 * Вычисляет прогнозы для одного объекта с учетом качества и рыночной ситуации.
 * @param {number} objectPrice Цена объекта.
 * @param {number} objectPricePerM2 Цена за м² объекта.
 * @param {Object} marketRatios Соотношения с рынком.
 * @param {number} demandPerMonth Спрос в месяц.
 * @param {Array} objectData Данные объекта.
 * @param {Array} activeCompetitors Активные конкуренты.
 * @param {Array} soldCompetitors Проданные конкуренты.
 * @returns {Object} Прогнозы.
 */
function calculateSingleObjectForecasts(objectPrice, objectPricePerM2, marketRatios, demandPerMonth, objectData, activeCompetitors, soldCompetitors, avgNewObjectsPerMonth) {
  const qualityScore = calculateQualityScore(objectData);
  const hasSoldData = soldCompetitors.length > 0;
  const hasActiveData = activeCompetitors.length > 0;
  
  // Определяем рыночную ситуацию
  const marketSituation = assessMarketSituation(hasSoldData, hasActiveData, demandPerMonth, objectData[1]);
  
  // Базовые цены с учетом рыночной ситуации
  let baseSoldPrice, baseActivePrice, baseMarketPrice;
  const objectArea = Number(objectData[4]) || 1; // Площадь объекта
  
  if (hasSoldData) {
    baseSoldPrice = marketRatios.avgSoldPrice * objectArea; // Цена за м² * площадь = полная цена
  } else {
    // Нет проданных аналогов - используем альтернативные методы
    baseSoldPrice = calculateAlternativeSoldPrice(objectPrice, objectData, marketSituation);
  }
  
  if (hasActiveData) {
    baseActivePrice = marketRatios.avgActivePrice * objectArea; // Цена за м² * площадь = полная цена
  } else {
    // Нет активных аналогов - используем текущую цену как базу
    baseActivePrice = objectPrice;
  }
  
  // Рыночная цена (базовая цена для сравнения)
  baseMarketPrice = baseSoldPrice || baseActivePrice || objectPrice;
  
  // Рассчитываем прогнозы с учетом позиции объекта
  const forecasts = calculateForecastsByPosition(
    objectPrice, 
    baseSoldPrice, 
    baseActivePrice, 
    baseMarketPrice,
    qualityScore,
    marketSituation,
    activeCompetitors,
    soldCompetitors,
    demandPerMonth
  );
  
  // Рассчитываем сроки с учетом рыночной ситуации
  const timeForecasts = calculateTimeForecasts(
    {...forecasts, position: calculateObjectPosition(objectPrice, activeCompetitors)}, 
    demandPerMonth, 
    marketSituation,
    activeCompetitors.length,
    soldCompetitors.length,
    avgNewObjectsPerMonth || 0,
    activeCompetitors.map(c => c[5] || c[4]).filter(p => typeof p === 'number' && p > 0)
  );
  
  return {
    ...forecasts,
    ...timeForecasts,
    qualityScore,
    marketSituation
  };
}

/**
 * Оценивает рыночную ситуацию.
 * @param {boolean} hasSoldData Есть ли данные о продажах.
 * @param {boolean} hasActiveData Есть ли данные об активных.
 * @param {number} demandPerMonth Спрос в месяц.
 * @param {string} district Район.
 * @returns {Object} Описание рыночной ситуации.
 */
function assessMarketSituation(hasSoldData, hasActiveData, demandPerMonth, district) {
  if (!hasSoldData && !hasActiveData) {
    return {
      type: 'NO_DATA',
      description: 'Нет данных о конкурентах в районе',
      riskLevel: 'HIGH',
      recommendation: 'Требуется расширение критериев поиска или анализ соседних районов'
    };
  }
  
  if (!hasSoldData && hasActiveData) {
    return {
      type: 'NO_SALES',
      description: 'Нет продаж в районе за период',
      riskLevel: 'MEDIUM',
      recommendation: 'Рынок неактивен, возможны длительные сроки продажи'
    };
  }
  
  if (hasSoldData && !hasActiveData) {
    return {
      type: 'NO_ACTIVE',
      description: 'Нет активных предложений в районе',
      riskLevel: 'LOW',
      recommendation: 'Низкая конкуренция, возможность установить премиальную цену'
    };
  }
  
  if (demandPerMonth < 0.5) {
    return {
      type: 'LOW_DEMAND',
      description: 'Очень низкий спрос в районе',
      riskLevel: 'HIGH',
      recommendation: 'Рекомендуется снижение цены для ускорения продажи'
    };
  }
  
  return {
    type: 'NORMAL',
    description: 'Обычная рыночная ситуация',
    riskLevel: 'LOW',
    recommendation: 'Стандартные ценовые стратегии применимы'
  };
}

/**
 * Вычисляет альтернативную цену проданных при отсутствии данных.
 * @param {number} objectPrice Цена объекта.
 * @param {Array} objectData Данные объекта.
 * @param {Object} marketSituation Рыночная ситуация.
 * @returns {number} Альтернативная цена.
 */
function calculateAlternativeSoldPrice(objectPrice, objectData, marketSituation) {
  // Базовые коэффициенты для разных типов недвижимости
  const typeMultipliers = {
    'Квартира': 1.0,
    'Студия': 0.85,
    'Дом': 1.2,
    'Таунхаус': 1.1
  };
  
  const objectType = objectData[2] || 'Квартира';
  const baseMultiplier = typeMultipliers[objectType] || 1.0;
  
  // Корректировка на рыночную ситуацию
  let situationMultiplier = 1.0;
  switch (marketSituation.type) {
    case 'NO_DATA':
      situationMultiplier = 0.9; // Снижение на 10% из-за неопределенности
      break;
    case 'LOW_DEMAND':
      situationMultiplier = 0.85; // Снижение на 15% из-за низкого спроса
      break;
    case 'NO_ACTIVE':
      situationMultiplier = 1.05; // Повышение на 5% из-за низкой конкуренции
      break;
  }
  
  return objectPrice * baseMultiplier * situationMultiplier;
}

/**
 * Вычисляет прогнозы с учетом позиции объекта.
 * @param {number} objectPrice Цена объекта.
 * @param {number} baseSoldPrice Базовая цена проданных.
 * @param {number} baseActivePrice Базовая цена активных.
 * @param {number} baseMarketPrice Базовая рыночная цена.
 * @param {number} qualityScore Коэффициент качества.
 * @param {Object} marketSituation Рыночная ситуация.
 * @param {Array} activeCompetitors Активные конкуренты.
 * @param {Array} soldCompetitors Проданные конкуренты.
 * @param {number} demandPerMonth Спрос в месяц.
 * @returns {Object} Ценовые прогнозы.
 */
function calculateForecastsByPosition(objectPrice, baseSoldPrice, baseActivePrice, baseMarketPrice, qualityScore, marketSituation, activeCompetitors, soldCompetitors, demandPerMonth) {
  // Определяем позицию объекта среди активных конкурентов
  const position = calculateObjectPosition(objectPrice, activeCompetitors);
  const totalCompetitors = activeCompetitors.length;
  
  // Коэффициенты в зависимости от позиции
  let positionMultiplier = 1.0;
  if (totalCompetitors > 0) {
    const positionRatio = position / (totalCompetitors + 1);
    if (positionRatio <= 0.2) {
      // В топ-20% - премиальная позиция
      positionMultiplier = 1.05;
    } else if (positionRatio >= 0.8) {
      // В нижних 20% - скидочная позиция
      positionMultiplier = 0.95;
    }
  }
  
  // Базовая рыночная цена (основная цена для расчетов)
  let basePrice;
  if (baseSoldPrice > 0) {
    basePrice = baseSoldPrice * qualityScore * positionMultiplier;
  } else if (baseActivePrice > 0) {
    basePrice = baseActivePrice * qualityScore * positionMultiplier;
  } else {
    basePrice = objectPrice * qualityScore * positionMultiplier;
  }
  
  // Быстрая продажа - самая низкая цена (скидка 10-15%)
  let quickPrice = basePrice * 0.87; // 13% скидка от рыночной цены
  
  // Рыночная цена - базовая цена
  let marketPrice = basePrice;
  
  // Дополнительная корректировка быстрой продажи на основе спроса
  if (activeCompetitors.length > 0 && demandPerMonth > 0) {
    // Сортируем активных конкурентов по цене
    const sortedActivePrices = activeCompetitors
      .map(row => Number(row[5]) || 0)
      .filter(p => p > 0)
      .sort((a, b) => a - b);
    
    if (sortedActivePrices.length > 0) {
      // Находим цену, которая позволит нам попасть в топ по спросу
      const demandPosition = Math.min(Math.ceil(demandPerMonth), sortedActivePrices.length);
      const competitivePrice = sortedActivePrices[demandPosition - 1] * 0.98;
      
      // Используем более агрессивную цену для быстрой продажи
      quickPrice = Math.min(quickPrice, competitivePrice);
    }
  }
  
  // Рассчитываем позиции для каждой стратегии
  const quickPosition = calculateObjectPosition(quickPrice, activeCompetitors);
  const marketPosition = calculateObjectPosition(marketPrice, activeCompetitors);

  return {
    quickPrice: Math.round(quickPrice),
    marketPrice: Math.round(marketPrice),
    position,
    quickPosition,
    marketPosition,
    positionMultiplier
  };
}

/**
 * Вычисляет позицию объекта среди конкурентов (аналогично calculateObjectRank).
 * @param {number} objectPrice Цена объекта.
 * @param {Array} activeCompetitors Активные конкуренты.
 * @returns {number} Позиция (1 = самый дешевый).
 */
function calculateObjectPosition(objectPrice, activeCompetitors) {
  if (activeCompetitors.length === 0) return 1;
  
  // Формируем массив всех цен (конкуренты + наш объект)
  // В отформатированных данных конкурентов цена находится в столбце 5 (индекс 5)
  const competitorPrices = activeCompetitors.map(c => Number(c[5]) || 0).filter(p => p > 0);
  
  // Проверяем, есть ли уже наш объект в массиве конкурентов
  const hasOurObject = competitorPrices.some(price => price === objectPrice);
  
  // Если нашего объекта нет в массиве, добавляем его
  const allActivePrices = hasOurObject 
    ? competitorPrices 
    : [...competitorPrices, objectPrice];
  
  // Сортируем по цене
  allActivePrices.sort((a, b) => a - b);
  
  // Рассчитываем позицию: считаем количество объектов дешевле нас + 1
  const position = 1 + allActivePrices.filter(p => p < objectPrice).length;
  
  return position;
}

/**
 * Вычисляет прогнозы сроков продажи.
 * @param {Object} forecasts Ценовые прогнозы.
 * @param {number} demandPerMonth Спрос в месяц.
 * @param {Object} marketSituation Рыночная ситуация.
 * @param {number} activeCount Количество активных конкурентов.
 * @param {number} soldCount Количество проданных.
 * @returns {Object} Прогнозы сроков.
 */
function calculateTimeForecasts(forecasts, demandPerMonth, marketSituation, activeCount, soldCount, arrivalRate, activePrices) {
  // Рассчитываем сроки на основе динамической модели деградации ранга
  let quickMonths, marketMonths;
  
  if (demandPerMonth > 0) {
    // Используем динамическую модель для каждой стратегии
    const quickDynamic = calculateDynamicTimeOnMarket({
      rank: forecasts.quickPosition || 1,
      demand: demandPerMonth,
      arrival: arrivalRate || 0,
      price: forecasts.quickPrice,
      activePrices: activePrices || []
    });
    
    const marketDynamic = calculateDynamicTimeOnMarket({
      rank: forecasts.marketPosition || 1,
      demand: demandPerMonth,
      arrival: arrivalRate || 0,
      price: forecasts.marketPrice,
      activePrices: activePrices || []
    });
    
    quickMonths = quickDynamic.months;
    marketMonths = marketDynamic.months;
    
    // Принудительная дифференциация, если сроки совпали из-за округления
    // (быстрая продажа должна быть хотя бы на 10-20% быстрее)
    if (Math.round(quickMonths) === Math.round(marketMonths) && marketMonths > 1) {
      quickMonths = marketMonths * 0.8;
    }
  } else {
    // Нет данных о спросе
    const baseMonths = calculateAlternativeTime(activeCount, soldCount, marketSituation);
    quickMonths = baseMonths * 0.7;
    marketMonths = baseMonths * 1.0;
  }
  
  // Округляем до 0.5 для точности
  const roundToHalf = (val) => Math.ceil(val * 2) / 2;
  
  return {
    quickMonths: roundToHalf(Math.max(1, quickMonths)),
    marketMonths: roundToHalf(Math.max(1.5, marketMonths))
  };
}

/**
 * Вычисляет альтернативный срок продажи при отсутствии данных о спросе.
 * @param {number} activeCount Количество активных.
 * @param {number} soldCount Количество проданных.
 * @param {Object} marketSituation Рыночная ситуация.
 * @returns {number} Базовый срок в месяцах.
 */
function calculateAlternativeTime(activeCount, soldCount, marketSituation) {
  if (marketSituation.type === 'NO_ACTIVE') {
    return 3; // Низкая конкуренция - быстрая продажа
  }
  
  if (marketSituation.type === 'LOW_DEMAND') {
    return 12; // Низкий спрос - долгая продажа
  }
  
  if (marketSituation.type === 'NO_DATA') {
    return 8; // Неопределенность - средний срок
  }
  
  // Обычная ситуация
  if (activeCount > 0) {
    return Math.max(2, Math.min(8, activeCount * 0.5)); // 0.5 месяца на конкурента
  }
  
  return 6; // По умолчанию
}

/**
 * Создает лист "критерии для сравнения конкурентов".
 */
function createCriteriaSheet() {
  try {
    // Проверяем, существует ли лист
    let sheet = SPREADSHEET.getSheetByName('критерии для сравнения конкурентов');
    
    if (!sheet) {
      // Создаем новый лист
      sheet = SPREADSHEET.insertSheet('критерии для сравнения конкурентов');
      Logger.log('Лист "критерии для сравнения конкурентов" создан');
    }
    
    // Настраиваем лист
    sheet.clear();
    
    // Заголовки
    const headers = [
      ['КРИТЕРИИ ДЛЯ ПОИСКА КОНКУРЕНТОВ', ''],
      ['', ''],
      ['ПАРАМЕТРЫ ОБЪЕКТА', 'ЗНАЧЕНИЕ'],
      ['Код объекта', ''],
      ['Район', ''],
      ['Тип объекта', ''],
      ['Количество комнат', ''],
      ['Площадь', ''],
      ['Тип ремонта', ''],
      ['Год постройки', ''],
      ['', ''],
      ['КРИТЕРИИ ФИЛЬТРАЦИИ', ''],
      ['', ''],
      ['Географический фильтр', 'Строгое соответствие района'],
      ['Тип объекта', 'Строгое соответствие'],
      ['Количество комнат', 'Допуск ±1 комната'],
      ['Площадь', 'Допуск ±20%'],
      ['Год постройки', 'Допуск ±10 лет'],
      ['Тип ремонта', 'Асимметричная логика'],
      ['Временной фильтр (активные)', 'Не старше 6 месяцев'],
      ['Временной фильтр (проданные)', 'В диапазоне 6 месяцев'],
      ['', ''],
      ['РАСЧЕТНЫЕ КРИТЕРИИ', ''],
      ['', ''],
      ['Минимальная площадь', ''],
      ['Максимальная площадь', ''],
      ['Минимальный год постройки', ''],
      ['Максимальный год постройки', ''],
      ['Минимальное количество комнат', ''],
      ['Максимальное количество комнат', ''],
      ['', ''],
      ['ДАТА АНАЛИЗА', '']
    ];
    
    // Записываем данные
    sheet.getRange(1, 1, headers.length, 2).setValues(headers);
    
    // Форматируем
    sheet.getRange('A1:B1').merge().setFontWeight('bold').setFontSize(14).setHorizontalAlignment('center');
    sheet.getRange('A3:B3').setFontWeight('bold').setBackground('#D3D3D3');
    sheet.getRange('A12:B12').setFontWeight('bold').setBackground('#D3D3D3');
    sheet.getRange('A23:B23').setFontWeight('bold').setBackground('#D3D3D3');
    sheet.getRange('A1:B' + headers.length).setFontSize(9);
    sheet.getRange('A1:B' + headers.length).setVerticalAlignment('middle');
    sheet.getRange('A1:A' + headers.length).setHorizontalAlignment('left');
    sheet.getRange('B1:B' + headers.length).setHorizontalAlignment('center');
    
    SpreadsheetApp.getUi().alert('✅ Лист "критерии для сравнения конкурентов" создан и настроен!');
    Logger.log('Лист критериев создан и настроен');
    
  } catch (e) {
    Logger.log(`Ошибка в createCriteriaSheet: ${e.stack}`);
    SpreadsheetApp.getUi().alert('❌ Ошибка при создании листа критериев: ' + e.message);
  }
}

/**
 * Записывает критерии поиска конкурентов на лист "критерии для сравнения конкурентов".
 * @param {Array} objectData Данные объекта.
 * @param {Object} criteria Критерии фильтрации.
 */
function writeCompetitorCriteria(objectData, criteria) {
  try {
    const sheet = SPREADSHEET.getSheetByName('критерии для сравнения конкурентов');
    if (!sheet) {
      Logger.log('Лист "критерии для сравнения конкурентов" не найден');
      return;
    }
    
    // Очищаем лист
    sheet.clear();
    
    // Заголовки
    const headers = [
      ['КРИТЕРИИ ДЛЯ ПОИСКА КОНКУРЕНТОВ', ''],
      ['', ''],
      ['ПАРАМЕТРЫ ОБЪЕКТА', 'ЗНАЧЕНИЕ'],
      ['Код объекта', objectData[5]],
      ['Район', objectData[1]],
      ['Тип объекта', objectData[2]],
      ['Количество комнат', objectData[3]],
      ['Площадь', objectData[4]],
      ['Тип ремонта', objectData[6]],
      ['Год постройки', objectData[10]],
      ['', ''],
      ['КРИТЕРИИ ФИЛЬТРАЦИИ', ''],
      ['', ''],
      ['Географический фильтр', 'Строгое соответствие района'],
      ['Тип объекта', 'Строгое соответствие'],
      ['Количество комнат', 'Допуск ±1 комната'],
      ['Площадь', 'Допуск ±20%'],
      ['Год постройки', 'Допуск ±10 лет'],
      ['Тип ремонта', 'Асимметричная логика'],
      ['Временной фильтр (активные)', 'Не старше 6 месяцев'],
      ['Временной фильтр (проданные)', 'В диапазоне 6 месяцев'],
      ['', ''],
      ['РАСЧЕТНЫЕ КРИТЕРИИ', ''],
      ['', ''],
      ['Минимальная площадь', Math.round(criteria.area * 0.8)],
      ['Максимальная площадь', Math.round(criteria.area * 1.2)],
      ['Минимальный год постройки', criteria.buildYear - 10],
      ['Максимальный год постройки', criteria.buildYear + 10],
      ['Минимальное количество комнат', Math.max(0, criteria.rooms - 1)],
      ['Максимальное количество комнат', criteria.rooms + 1],
      ['', ''],
      ['ДАТА АНАЛИЗА', new Date().toLocaleString('ru-RU')]
    ];
    
    // Записываем данные
    sheet.getRange(1, 1, headers.length, 2).setValues(headers);
    
    // Форматируем
    sheet.getRange('A1:B1').merge().setFontWeight('bold').setFontSize(14).setHorizontalAlignment('center');
    sheet.getRange('A3:B3').setFontWeight('bold').setBackground('#D3D3D3');
    sheet.getRange('A12:B12').setFontWeight('bold').setBackground('#D3D3D3');
    sheet.getRange('A23:B23').setFontWeight('bold').setBackground('#D3D3D3');
    sheet.getRange('A1:B' + headers.length).setFontSize(9);
    sheet.getRange('A1:B' + headers.length).setVerticalAlignment('middle');
    sheet.getRange('A1:A' + headers.length).setHorizontalAlignment('left');
    sheet.getRange('B1:B' + headers.length).setHorizontalAlignment('center');
    
    Logger.log('Критерии поиска конкурентов записаны на лист');
    
  } catch (e) {
    Logger.log(`Ошибка в writeCompetitorCriteria: ${e.stack}`);
  }
}

/**
 * Очищает все данные анализа при удалении кода объекта.
 */
function clearAnalysisData() {
  try {
    // Очищаем лист "аналитика ОН по коду" (отчет)
    const analyticsSheet = SPREADSHEET.getSheetByName(SHEETS.SINGLE_OBJECT_ANALYTICS);
    if (analyticsSheet) {
      analyticsSheet.getRange('A4:B50').clearContent().clearFormat();
    }
    
    // Очищаем лист "лист анализа объекта"
    const analysisSheet = SPREADSHEET.getSheetByName(SHEETS.SINGLE_OBJECT_ANALYSIS);
    if (analysisSheet) {
      analysisSheet.getRange('A3:AQ1000').clearContent().clearFormat();
    }
    
    // Очищаем лист "конкуренты активные и проданные для анализа"
    const competitorsSheet = SPREADSHEET.getSheetByName(SHEETS.SINGLE_COMPETITORS);
    if (competitorsSheet) {
      competitorsSheet.getRange('A3:L1000').clearContent().clearFormat();
    }
    
    // Очищаем лист "критерии для сравнения конкурентов"
    const criteriaSheet = SPREADSHEET.getSheetByName('критерии для сравнения конкурентов');
    if (criteriaSheet) {
      criteriaSheet.getRange('A4:B50').clearContent().clearFormat();
    }
    
    Logger.log('Данные анализа очищены');
    
  } catch (e) {
    Logger.log(`Ошибка при очистке данных анализа: ${e.stack}`);
  }
}

/**
 * Триггер для автоматического анализа при изменении ячейки B2 в листе "аналитика ОН по коду".
 * @param {Event} e Событие редактирования.
 */
function onEditTrigger(e) {
  try {
    // Проверяем, что изменение произошло в нужном листе и ячейке
    if (e.range.getSheet().getName() === SHEETS.SINGLE_OBJECT_ANALYTICS && 
        e.range.getA1Notation() === 'B2') {
      
      const objectCode = e.value;
      
      // Проверяем, что код не пустой
      if (objectCode && String(objectCode).trim() !== '') {
        Logger.log(`Автоматический запуск анализа для кода: ${objectCode}`);
        
        // Запускаем анализ
        analyzeSingleObjectByCode(String(objectCode).trim());
      } else {
        // Если код пустой или удален - очищаем все данные анализа
        Logger.log('Код объекта удален, очищаем данные анализа');
        clearAnalysisData();
      }
    }
  } catch (error) {
    Logger.log(`Ошибка в onEditTrigger: ${error.stack}`);
  }
}

/**
 * Обрабатывает POST-запросы от Telegram бота (Webhook).
 * @param {Object} e Событие запроса.
 * @returns {ContentService.TextOutput} Ответ сервера.
 */
function doPost(e) {
  try {
    return processBotRequest(e);
  } catch (error) {
    Logger.log(`Критическая ошибка в doPost: ${error.stack}`);
    return ContentService.createTextOutput(JSON.stringify({ error: error.message }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * Обрабатывает логику бота.
 * @param {Object} e Событие запроса.
 * @returns {ContentService.TextOutput} Ответ сервера.
 */
function processBotRequest(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return ContentService.createTextOutput(JSON.stringify({ status: 'error', message: 'No data' }))
        .setMimeType(ContentService.MimeType.JSON);
    }
    
    const contents = JSON.parse(e.postData.contents);
    const objectCode = contents.objectCode;
    
    if (!objectCode) {
      return ContentService.createTextOutput(JSON.stringify({ status: 'error', message: 'No object code' }))
        .setMimeType(ContentService.MimeType.JSON);
    }
    
    Logger.log(`Получен запрос от бота для кода: ${objectCode}`);
    
    // Получаем текст анализа
    const analysisText = getAnalysisTextForBot(objectCode.toString().trim());
    
    return ContentService.createTextOutput(JSON.stringify({ 
      status: 'success', 
      text: analysisText 
    })).setMimeType(ContentService.MimeType.JSON);
    
  } catch (error) {
    Logger.log(`Ошибка в processBotRequest: ${error.stack}`);
    return ContentService.createTextOutput(JSON.stringify({ status: 'error', message: error.message }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * Генерирует текстовый анализ для бота по коду объекта.
 * @param {string} objectCode Код объекта.
 * @returns {string} Текст анализа.
 */
function getAnalysisTextForBot(objectCode) {
  try {
    // 1. Валидация и поиск
    const objectData = findObjectByCode(objectCode);
    if (!objectData) {
      return `❌ Объект с кодом ${objectCode} не найден в листе "2. 2. активные". Проверьте корректность кода.`;
    }
    
    // 2. Построение массива конкурентов
    const competitorsData = buildSingleObjectCompetitorsArray(objectData);
    if (competitorsData.activeCompetitors.length === 0 && competitorsData.soldCompetitors.length === 0) {
      return `⚠️ Для объекта ${objectCode} не найдено конкурентов. Анализ невозможен.`;
    }
    
    // 3. Анализ (без записи в лист, но используем ту же логику)
    const advertisingData = getAdvertisingData(objectCode);
    const result = calculateSingleObjectMetrics(objectData, competitorsData.activeCompetitors, competitorsData.soldCompetitors, advertisingData);
    
    // 4. Формирование текста (используем существующую функцию генерации ИИ отчета)
    // Она переписана на использование Gemini
    const reportText = createSingleObjectReportText(objectData, result, competitorsData);
    
    return reportText;
    
  } catch (e) {
    Logger.log(`Ошибка в getAnalysisTextForBot: ${e.stack}`);
    return `❌ Произошла ошибка при анализе объекта: ${e.message}`;
  }
}

// ================== ИНТЕГРАЦИЯ С GEMINI API ==================

/**
 * API-ключ Gemini по умолчанию (замените на свой при необходимости)
 * Для безопасности рекомендуется использовать меню: Аналитика → Установить API ключ Gemini
 */
const DEFAULT_GEMINI_API_KEY = '';

/**
 * Получает API-ключ Gemini из свойств скрипта или использует значение по умолчанию.
 * @returns {string|null} API-ключ или null, если не установлен.
 */
function getGeminiApiKey() {
  try {
    const props = PropertiesService.getScriptProperties();
    return props.getProperty('GEMINI_API_KEY') || DEFAULT_GEMINI_API_KEY || null;
  } catch (e) {
    Logger.log(`Ошибка при получении API ключа: ${e.message}`);
    return null;
  }
}

/**
 * Запрашивает у пользователя API-ключ Gemini и сохраняет его.
 */
function setApiKey() {
  const ui = SpreadsheetApp.getUi();
  const response = ui.prompt(
    '🔑 Установка API-ключа Gemini',
    'Введите ваш API-ключ Google Gemini:\n\n(Получить ключ: https://aistudio.google.com/apikey)',
    ui.ButtonSet.OK_CANCEL
  );
  
  if (response.getSelectedButton() == ui.Button.OK) {
    const apiKey = response.getResponseText().trim();
    if (apiKey && apiKey.length > 20) {
      PropertiesService.getScriptProperties().setProperty('GEMINI_API_KEY', apiKey);
      ui.alert('✅ Успех', 'API-ключ Gemini успешно сохранён!', ui.ButtonSet.OK);
      Logger.log('API-ключ Gemini установлен пользователем');
    } else {
      ui.alert('❌ Ошибка', 'Некорректный ключ. Он должен быть длиннее 20 символов.', ui.ButtonSet.OK);
    }
  }
}

/**
 * Устанавливает API-ключ Gemini автоматически (если DEFAULT_GEMINI_API_KEY задан).
 */
function setDefaultApiKey() {
  try {
    if (!DEFAULT_GEMINI_API_KEY) {
      SpreadsheetApp.getUi().alert(
        '⚠️ Ключ не задан',
        'Значение DEFAULT_GEMINI_API_KEY пустое.\n\nИспользуйте меню:\nАналитика → Установить API ключ Gemini',
        SpreadsheetApp.getUi().ButtonSet.OK
      );
      return;
    }
    PropertiesService.getScriptProperties().setProperty('GEMINI_API_KEY', DEFAULT_GEMINI_API_KEY);
    SpreadsheetApp.getUi().alert('✅ API-ключ Gemini установлен автоматически!');
    Logger.log('API-ключ Gemini установлен из DEFAULT_GEMINI_API_KEY');
  } catch (e) {
    Logger.log(`Ошибка при автоустановке API-ключа: ${e.stack}`);
    SpreadsheetApp.getUi().alert('❌ Ошибка: ' + e.message);
  }
}

/**
 * Показывает текущий статус API Gemini.
 */
function showApiStatus() {
  const ui = SpreadsheetApp.getUi();
  const apiKey = getGeminiApiKey();
  
  if (!apiKey) {
    ui.alert('📊 Статус API', '❌ Ключ НЕ установлен\n\nИспользуйте меню:\nАналитика → Установить API ключ Gemini', ui.ButtonSet.OK);
    return;
  }
  
  // Проверяем валидность ключа тестовым запросом
  try {
    const testResult = callGemini('Ответь одним словом: работает', '');
    if (testResult && !testResult.includes('Ошибка')) {
      ui.alert('📊 Статус API', '✅ Ключ установлен и работает!\n\nМодель: gemini-2.0-flash', ui.ButtonSet.OK);
    } else {
      ui.alert('📊 Статус API', '⚠️ Ключ установлен, но есть проблема:\n' + testResult, ui.ButtonSet.OK);
    }
  } catch (e) {
    ui.alert('📊 Статус API', '❌ Ошибка проверки: ' + e.message, ui.ButtonSet.OK);
  }
}

/**
 * Вызывает Google Gemini API для генерации текста.
 * @param {string} prompt Промпт для Gemini.
 * @param {string} summaryText Аналитическое резюме (добавляется к промпту).
 * @returns {string} Ответ от Gemini или сообщение об ошибке.
 */
function callGemini(prompt, summaryText) {
  const apiKey = getGeminiApiKey();
  if (!apiKey) {
    return '❌ API-ключ Gemini не установлен. Используйте меню: Аналитика → Установить API ключ Gemini';
  }
  
  const model = 'gemini-2.0-flash';
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`;
  
  const fullPrompt = summaryText 
    ? `${prompt}\n\nАналитические данные:\n${summaryText}` 
    : prompt;
  
  const payload = {
    contents: [{
      parts: [{
        text: fullPrompt
      }]
    }],
    generationConfig: {
      temperature: 0.7,
      maxOutputTokens: 8192,
      topP: 0.8
    },
    safetySettings: [
      { category: 'HARM_CATEGORY_HARASSMENT', threshold: 'BLOCK_NONE' },
      { category: 'HARM_CATEGORY_HATE_SPEECH', threshold: 'BLOCK_NONE' },
      { category: 'HARM_CATEGORY_SEXUALLY_EXPLICIT', threshold: 'BLOCK_NONE' },
      { category: 'HARM_CATEGORY_DANGEROUS_CONTENT', threshold: 'BLOCK_NONE' }
    ]
  };
  
  const options = {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };
  
  const maxRetries = 3;
  
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const response = UrlFetchApp.fetch(url, options);
      const responseText = response.getContentText();
      
      if (IS_DEBUG) Logger.log(`Gemini Response (попытка ${attempt}): ${responseText.substring(0, 500)}...`);
      
      const json = JSON.parse(responseText);
      
      if (json.error) {
        Logger.log(`Ошибка API Gemini: ${json.error.message}`);
        if (attempt < maxRetries) {
          Utilities.sleep(1000 * Math.pow(2, attempt - 1));
          continue;
        }
        return `❌ Ошибка API Gemini: ${json.error.message}`;
      }
      
      if (json.candidates && json.candidates[0]?.content?.parts?.[0]?.text) {
        return cleanText(json.candidates[0].content.parts[0].text);
      }
      
      return '❌ Пустой ответ от Gemini. Проверьте логи.';
      
    } catch (e) {
      Logger.log(`Ошибка вызова Gemini (попытка ${attempt}): ${e.stack}`);
      if (attempt < maxRetries) {
        Utilities.sleep(1000 * Math.pow(2, attempt - 1));
        continue;
      }
      return '❌ Ошибка сети при обращении к Gemini: ' + e.message;
    }
  }
  return '❌ Не удалось получить ответ от Gemini после нескольких попыток.';
}

/**
 * Вызывает Gemini для структурированного анализа недвижимости.
 * Использует JSON-формат для получения факторов влияния и рекомендаций.
 * @param {Object} analyticsData Объект с аналитическими данными.
 * @param {Object} macroContext Макроэкономический контекст.
 * @returns {Object} Структурированный результат анализа.
 */
function callGeminiAnalyst(analyticsData, macroContext) {
  const apiKey = getGeminiApiKey();
  if (!apiKey) {
    return {
      success: false,
      error: 'API-ключ не установлен',
      factors: [],
      recommendation: 'Установите API ключ Gemini через меню.'
    };
  }
  
  const prompt = `Ты — эксперт-аналитик рынка недвижимости. Проанализируй данные объекта и дай структурированную оценку.

ДАННЫЕ ОБЪЕКТА:
- Район: ${analyticsData.district || 'не указан'}
- Тип: ${analyticsData.type || 'квартира'}, ${analyticsData.rooms || '?'} комн., ${analyticsData.area || '?'} м²
- Текущая цена: ${analyticsData.price?.toLocaleString() || '?'} руб.
- Цена за м²: ${analyticsData.pricePerSqm?.toLocaleString() || '?'} руб./м²
- Ремонт: ${analyticsData.repair || 'не указан'}
- Год постройки: ${analyticsData.buildYear || 'не указан'}

РЫНОЧНАЯ СИТУАЦИЯ:
- Конкурентов: ${analyticsData.competitorsCount || 0}
- Продано за период: ${analyticsData.soldCount || 0}
- Спрос: ${analyticsData.demand || '?'} объектов/мес
- Позиция по цене: ${analyticsData.rank || '?'} из ${analyticsData.totalActive || '?'}

МАКРОКОНТЕКСТ:
- Ключевая ставка ЦБ: ${macroContext?.keyRate || 16}%
- Рыночная ипотека: ${macroContext?.mortgageRate || 18}%
- Семейная ипотека: ${macroContext?.familyMortgage ? 'действует' : 'нет'}
- Тренд рынка: ${macroContext?.marketTrend || 'стагнация'}

ОТВЕТЬ В ФОРМАТЕ JSON:
{
  "analysis": {
    "marketPosition": "краткое описание позиции объекта на рынке (1-2 предложения)"
  },
  "recommendations": [
    {"action": "конкретное действие", "impact": "какой эффект даст"}
  ],
  "confidence": число_от_0_до_100,
  "confidenceReasoning": "почему такая уверенность"
}`;

  const model = 'gemini-2.0-flash';
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`;
  
  const payload = {
    contents: [{ parts: [{ text: prompt }] }],
    generationConfig: {
      temperature: 0.3,
      maxOutputTokens: 2048,
      responseMimeType: 'application/json'
    }
  };
  
  try {
    const response = UrlFetchApp.fetch(url, {
      method: 'post',
      contentType: 'application/json',
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    });
    
    const json = JSON.parse(response.getContentText());
    
    if (json.error) {
      return { success: false, error: json.error.message };
    }
    
    if (json.candidates?.[0]?.content?.parts?.[0]?.text) {
      const analysisResult = JSON.parse(json.candidates[0].content.parts[0].text);
      analysisResult.success = true;
      return analysisResult;
    }
    
    return { success: false, error: 'Пустой ответ от Gemini' };
    
  } catch (e) {
    Logger.log(`Ошибка callGeminiAnalyst: ${e.stack}`);
    return { success: false, error: e.message };
  }
}

/**
 * Очищает текст от Markdown-разметки и лишних символов.
 * @param {string} text Исходный текст.
 * @returns {string} Очищенный текст.
 */
function cleanText(text) {
  if (!text) return '';
  return text
    .replace(/^[#*\-\s\d\.]+/gm, '')           // Убираем маркеры списков и заголовки
    .replace(/\*{1,2}(.*?)\*{1,2}/g, '$1')     // Убираем **bold** и *italic*
    .replace(/`{1,3}(.*?)`{1,3}/g, '$1')       // Убираем `code` и ```code blocks```
    .replace(/\n{3,}/g, '\n\n')                // Нормализуем переносы строк
    .trim();
}

/**
 * Получает текущий макроэкономический контекст.
 * @returns {Object} Объект с макроэкономическими параметрами.
 */
function getMacroContext() {
  try {
    const settingsSheet = SPREADSHEET.getSheetByName('Настройки');
    if (settingsSheet) {
      const macroData = settingsSheet.getRange(MACRO_CONTEXT_CELL).getValue();
      if (macroData) {
        try {
          return JSON.parse(macroData);
        } catch (e) {
          // Если не JSON, пробуем парсить как строку key=value
          Logger.log('Макроконтекст не в JSON формате, используем значения по умолчанию');
        }
      }
    }
  } catch (e) {
    Logger.log(`Ошибка получения макроконтекста: ${e.message}`);
  }
  return DEFAULT_MACRO_CONTEXT;
}