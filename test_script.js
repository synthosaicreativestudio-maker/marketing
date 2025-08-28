// Простой тест синтаксиса Google Apps Script
function testSyntax() {
  console.log("Синтаксис корректен!");
  return true;
}

// Тест функции авторизации
function testAuthFunction() {
  const testData = {
    code: "111098",
    phone: "89827701055",
    telegramId: "284355186"
  };
  
  console.log("Тестовые данные:", testData);
  return testData;
}
