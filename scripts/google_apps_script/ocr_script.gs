/**
 * Google Apps Script для автоматического OCR изображений в папке Knowledge Base.
 * 
 * Инструкция по установке:
 * 1. Перейдите в папку с базой знаний в Google Drive.
 * 2. Нажмите "+ Создать" -> "Еще" -> "Google Apps Script".
 * 3. Вставьте этот код в редактор.
 * 4. Задайте имя проекту (например, "RAG OCR Service").
 * 5. Нажмите на иконку часов (Триггеры) слева.
 * 6. Нажмите "+ Добавление триггера" -> Выберите функцию "processFolderBatch" -> 
 *    Тип источника: "По времени" -> Выберите интервал (например, "Раз в час").
 * 7. Выполните функцию `processFolderBatch` вручную один раз, чтобы дать разрешения.
 */

// ПРОВЕРЬТЕ: Скрипт будет работать с папкой, в которой он запущен, 
// или вы можете вставить ID папки ниже:
const FOLDER_ID = ""; // Оставьте пустым, чтобы использовать текущую папку

function processFolderBatch() {
  const folder = FOLDER_ID ? DriveApp.getFolderById(FOLDER_ID) : getParentFolder();
  if (!folder) {
    Logger.log("Ошибка: Не удалось найти папку.");
    return;
  }
  
  const files = folder.getFiles();
  const imageTypes = ['image/png', 'image/jpeg', 'image/jpg'];
  const docTypes = ['application/vnd.google-apps.document', 'application/vnd.google-apps.spreadsheet', 'application/pdf'];
  const processedTag = '.ocr.txt';
  
  while (files.hasNext()) {
    const file = files.next();
    const mimeType = file.getMimeType();
    const fileName = file.getName();
    
    // Пропускаем сами результаты OCR
    if (fileName.endsWith(processedTag)) continue;

    if (imageTypes.includes(mimeType) || docTypes.includes(mimeType)) {
      const txtName = fileName + processedTag;
      
      // Проверяем, есть ли уже .ocr.txt для этого файла
      const existingTxt = folder.getFilesByName(txtName);
      if (existingTxt.hasNext()) continue;
      
      Logger.log("Обработка: " + fileName + " (" + mimeType + ")");
      try {
        let text = "";
        if (mimeType === 'application/vnd.google-apps.spreadsheet') {
          text = processSpreadsheet(file);
        } else if (mimeType === 'application/vnd.google-apps.document') {
          text = DocumentApp.openById(file.getId()).getBody().getText();
        } else {
          // Для картинок и PDF используем OCR метод
          text = performOcr(file);
        }

        if (text && text.trim().length > 0) {
          folder.createFile(txtName, text);
          Logger.log("Успех: Создан " + txtName);
        }
      } catch (e) {
        Logger.log("Ошибка при обработке " + fileName + ": " + e);
      }
    }
  }
}

function processSpreadsheet(file) {
  const ss = SpreadsheetApp.openById(file.getId());
  const sheets = ss.getSheets();
  let fullText = "";
  
  sheets.forEach(sheet => {
    const data = sheet.getDataRange().getValues();
    fullText += "\nЛист: " + sheet.getName() + "\n";
    data.forEach(row => {
      fullText += row.join(" | ") + "\n";
    });
  });
  return fullText;
}

function performOcr(file) {
  // Используем Google Drive API для создания временного документа с OCR
  const resource = {
    title: file.getName(),
    mimeType: file.getMimeType()
  };
  
  // Параметр ocr=true включает распознавание
  const doc = Drive.Files.copy(resource, file.getId(), {ocr: true, ocrLanguage: 'ru'});
  
  // Берем текст из созданного Google Doc
  const gDoc = DocumentApp.openById(doc.id);
  const text = gDoc.getBody().getText();
  
  // Удаляем временный документ
  Drive.Files.remove(doc.id);
  
  return text;
}

function getParentFolder() {
  const ss = SpreadsheetApp.getActive(); // Если это внутри таблицы
  if (ss) {
    const file = DriveApp.getFileById(ss.getId());
    return file.getParents().next();
  }
  
  // Если запущен как независимый скрипт из папки - берем папку скрипта
  try {
    const scriptId = ScriptApp.getScriptId();
    const parents = DriveApp.getFileById(scriptId).getParents();
    if (parents.hasNext()) return parents.next();
  } catch (e) {}
  
  return null;
}
