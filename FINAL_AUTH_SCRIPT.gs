function authorizeUser(code, phone, telegramId) {
  try {
    const sheet = SpreadsheetApp.getActiveSpreadsheet();
    const worksheet = sheet.getSheetByName('список сотрудников для авторизации');
    
    if (!worksheet) {
      return { success: false, error: 'Лист не найден' };
    }
    
    const data = worksheet.getDataRange().getValues();
    const headers = data[0];
    
    const codeCol = headers.indexOf('Код партнера');
    const phoneCol = headers.indexOf('Телефон партнера');
    const statusCol = headers.indexOf('Статус авторизации');
    const telegramCol = headers.indexOf('Telegram ID');
    
    if (codeCol === -1 || phoneCol === -1 || statusCol === -1 || telegramCol === -1) {
      return { success: false, error: 'Колонки не найдены' };
    }
    
    let userRow = -1;
    for (let i = 1; i < data.length; i++) {
      if (data[i][codeCol] == code && data[i][phoneCol] == phone) {
        userRow = i + 1;
        break;
      }
    }
    
    if (userRow === -1) {
      return { success: false, error: 'Пользователь не найден' };
    }
    
    worksheet.getRange(userRow, statusCol + 1).setValue('авторизован');
    worksheet.getRange(userRow, telegramCol + 1).setValue(telegramId);
    
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

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    const { code, phone, telegramId } = data;
    
    if (!code || !phone || !telegramId) {
      return ContentService
        .createTextOutput(JSON.stringify({
          success: false,
          error: 'Не все поля заполнены'
        }))
        .setMimeType(ContentService.MimeType.JSON);
    }
    
    const result = authorizeUser(code, phone, telegramId);
    
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

function testAuth() {
  const result = authorizeUser('111098', '89827701055', '284355186');
  console.log(result);
}

function testMultipleUsers() {
  const testUsers = [
    { code: '111098', phone: '89827701055', telegramId: '284355186' },
    { code: '222099', phone: '89827701056', telegramId: '284355187' },
    { code: '333100', phone: '89827701057', telegramId: '284355188' }
  ];
  
  testUsers.forEach(user => {
    const result = authorizeUser(user.code, user.phone, user.telegramId);
    console.log(`Тест для ${user.code}:`, result);
  });
}
