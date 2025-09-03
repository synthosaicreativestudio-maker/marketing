# 🔌 API ДОКУМЕНТАЦИЯ MARKETING BOT

## 📅 Последнее обновление: 2025-09-03 10:40

---

## 🎯 ОБЗОР API

Marketing Bot предоставляет RESTful API для взаимодействия с Telegram WebApp и внешними системами. API построен на основе Telegram Bot API с дополнительными endpoints для управления акциями и пользователями.

---

## 🔧 БАЗОВАЯ ИНФОРМАЦИЯ

### 📋 Общие параметры
- **Base URL**: `https://api.telegram.org/bot<TOKEN>/`
- **Content-Type**: `application/json`
- **Authentication**: Bearer Token (Telegram Bot Token)

### 🚀 Основные endpoints
- **Telegram Bot API**: Стандартные методы Telegram
- **WebApp Data**: Обработка данных от WebApp
- **Promotions API**: Управление акциями
- **Auth API**: Авторизация пользователей

---

## 📱 TELEGRAM BOT API

### 🔧 Основные методы

#### 1. **sendMessage** - Отправка сообщения
```http
POST https://api.telegram.org/bot<TOKEN>/sendMessage
```

**Параметры:**
```json
{
  "chat_id": "integer|string",
  "text": "string",
  "parse_mode": "HTML|Markdown",
  "reply_markup": {
    "inline_keyboard": [
      [
        {
          "text": "string",
          "callback_data": "string",
          "web_app": {
            "url": "string"
          }
        }
      ]
    ]
  }
}
```

**Пример:**
```json
{
  "chat_id": 123456789,
  "text": "🎉 Новая акция опубликована!\n\n📢 Скидка 20% на все товары",
  "parse_mode": "HTML",
  "reply_markup": {
    "inline_keyboard": [
      [
        {
          "text": "👀 Ознакомиться подробнее",
          "web_app": {
            "url": "https://your-domain.com/spa_menu.html?section=promotions"
          }
        }
      ]
    ]
  }
}
```

#### 2. **answerCallbackQuery** - Ответ на callback
```http
POST https://api.telegram.org/bot<TOKEN>/answerCallbackQuery
```

**Параметры:**
```json
{
  "callback_query_id": "string",
  "text": "string",
  "show_alert": "boolean"
}
```

#### 3. **sendDocument** - Отправка документа
```http
POST https://api.telegram.org/bot<TOKEN>/sendDocument
```

**Параметры:**
```json
{
  "chat_id": "integer|string",
  "document": "string|InputFile",
  "caption": "string",
  "parse_mode": "HTML|Markdown"
}
```

---

## 🎉 PROMOTIONS API

### 📋 Управление акциями

#### 1. **get_promotions** - Получение акций
**Endpoint:** WebApp Data Handler
**Method:** POST (через Telegram WebApp)

**Запрос:**
```json
{
  "type": "get_promotions",
  "timestamp": "2025-09-03T10:40:00.000Z"
}
```

**Ответ:**
```json
{
  "type": "promotions_response",
  "promotions": [
    {
      "row": 2,
      "release_date": "2025-09-03",
      "name": "Скидка 20% на все товары",
      "description": "Специальное предложение для всех клиентов",
      "status": "Активна",
      "start_date": "2025-09-03",
      "end_date": "2025-09-30",
      "content": "Подробное описание акции...",
      "ui_status": "active",
      "media": [
        {
          "type": "image",
          "url": "https://example.com/image.jpg"
        }
      ]
    }
  ],
  "timestamp": "2025-09-03T10:40:00.000Z",
  "count": 1
}
```

#### 2. **view_promotion** - Просмотр конкретной акции
**Endpoint:** Callback Query Handler
**Method:** POST (через Telegram Callback)

**Запрос:**
```
callback_data: "view_promotion:2"
```

**Ответ:**
```json
{
  "type": "promotions_response",
  "promotions": [
    {
      "row": 2,
      "name": "Скидка 20% на все товары",
      "description": "Специальное предложение для всех клиентов",
      "status": "Активна",
      "start_date": "2025-09-03",
      "end_date": "2025-09-30",
      "content": "Подробное описание акции...",
      "ui_status": "active"
    }
  ],
  "count": 1
}
```

---

## 🔐 AUTH API

### 📋 Авторизация пользователей

#### 1. **check_auth** - Проверка авторизации
**Endpoint:** WebApp Data Handler
**Method:** POST (через Telegram WebApp)

**Запрос:**
```json
{
  "type": "check_auth",
  "user_id": 123456789,
  "timestamp": "2025-09-03T10:40:00.000Z"
}
```

**Ответ:**
```json
{
  "type": "auth_response",
  "authorized": true,
  "user_data": {
    "telegram_id": 123456789,
    "fio": "Иванов Иван Иванович",
    "phone": "+79001234567",
    "code": "123456"
  },
  "timestamp": "2025-09-03T10:40:00.000Z"
}
```

#### 2. **auth_request** - Запрос авторизации
**Endpoint:** WebApp Data Handler
**Method:** POST (через Telegram WebApp)

**Запрос:**
```json
{
  "type": "auth_request",
  "phone": "+79001234567",
  "timestamp": "2025-09-03T10:40:00.000Z"
}
```

**Ответ:**
```json
{
  "type": "auth_response",
  "status": "pending",
  "message": "Запрос на авторизацию отправлен",
  "timestamp": "2025-09-03T10:40:00.000Z"
}
```

---

## 🎫 TICKETS API

### 📋 Управление тикетами

#### 1. **create_ticket** - Создание тикета
**Endpoint:** WebApp Data Handler
**Method:** POST (через Telegram WebApp)

**Запрос:**
```json
{
  "type": "create_ticket",
  "subject": "Проблема с заказом",
  "description": "Не могу найти свой заказ",
  "priority": "medium",
  "timestamp": "2025-09-03T10:40:00.000Z"
}
```

**Ответ:**
```json
{
  "type": "ticket_response",
  "ticket_id": 123,
  "status": "created",
  "message": "Тикет создан успешно",
  "timestamp": "2025-09-03T10:40:00.000Z"
}
```

#### 2. **get_tickets** - Получение тикетов
**Endpoint:** WebApp Data Handler
**Method:** POST (через Telegram WebApp)

**Запрос:**
```json
{
  "type": "get_tickets",
  "status": "open",
  "timestamp": "2025-09-03T10:40:00.000Z"
}
```

**Ответ:**
```json
{
  "type": "tickets_response",
  "tickets": [
    {
      "id": 123,
      "subject": "Проблема с заказом",
      "status": "open",
      "priority": "medium",
      "created_at": "2025-09-03T10:40:00.000Z",
      "updated_at": "2025-09-03T10:40:00.000Z"
    }
  ],
  "count": 1,
  "timestamp": "2025-09-03T10:40:00.000Z"
}
```

---

## 🔄 WEBAPP DATA HANDLER

### 📋 Обработка данных от WebApp

#### Общий формат запроса:
```json
{
  "type": "string",
  "data": "object",
  "timestamp": "ISO 8601 string"
}
```

#### Поддерживаемые типы:
- `get_promotions` - Получение акций
- `check_auth` - Проверка авторизации
- `auth_request` - Запрос авторизации
- `create_ticket` - Создание тикета
- `get_tickets` - Получение тикетов
- `subsection_selection` - Выбор подраздела

---

## 📊 КОДЫ ОТВЕТОВ

### ✅ Успешные ответы
- **200 OK** - Запрос выполнен успешно
- **201 Created** - Ресурс создан успешно

### ❌ Ошибки клиента (4xx)
- **400 Bad Request** - Неверный запрос
- **401 Unauthorized** - Не авторизован
- **403 Forbidden** - Доступ запрещен
- **404 Not Found** - Ресурс не найден
- **429 Too Many Requests** - Слишком много запросов

### 🔥 Ошибки сервера (5xx)
- **500 Internal Server Error** - Внутренняя ошибка сервера
- **502 Bad Gateway** - Ошибка шлюза
- **503 Service Unavailable** - Сервис недоступен
- **504 Gateway Timeout** - Таймаут шлюза

---

## 🐛 ОБРАБОТКА ОШИБОК

### 📋 Формат ошибки
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Описание ошибки",
    "details": "Дополнительные детали",
    "timestamp": "2025-09-03T10:40:00.000Z"
  }
}
```

### 🔧 Коды ошибок
- **INVALID_REQUEST** - Неверный формат запроса
- **AUTH_REQUIRED** - Требуется авторизация
- **PERMISSION_DENIED** - Недостаточно прав
- **RESOURCE_NOT_FOUND** - Ресурс не найден
- **RATE_LIMIT_EXCEEDED** - Превышен лимит запросов
- **INTERNAL_ERROR** - Внутренняя ошибка

---

## 🚀 ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ

### 📱 JavaScript (WebApp)
```javascript
// Отправка запроса акций
function loadPromotions() {
    const requestData = {
        type: 'get_promotions',
        timestamp: new Date().toISOString()
    };
    
    tg.sendData(JSON.stringify(requestData));
}

// Обработка ответа
tg.onEvent('webAppDataReceived', function(data) {
    const response = JSON.parse(data);
    if (response.type === 'promotions_response') {
        renderPromotions(response.promotions);
    }
});
```

### 🐍 Python (Внешний клиент)
```python
import requests
import json

# Отправка сообщения
def send_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        data["reply_markup"] = reply_markup
    
    response = requests.post(url, json=data)
    return response.json()

# Использование
result = send_message(
    chat_id=123456789,
    text="🎉 Новая акция!",
    reply_markup={
        "inline_keyboard": [[
            {
                "text": "Посмотреть",
                "web_app": {"url": "https://example.com/spa_menu.html"}
            }
        ]]
    }
)
```

---

## 🔒 БЕЗОПАСНОСТЬ

### 🛡️ Аутентификация
- **Telegram Bot Token** - для Bot API
- **User ID** - для пользовательских запросов
- **Session validation** - проверка сессий

### 🔐 Авторизация
- **Role-based access** - доступ на основе ролей
- **Permission checks** - проверка разрешений
- **Rate limiting** - ограничение частоты запросов

### 🛡️ Защита данных
- **Input validation** - валидация входных данных
- **SQL injection protection** - защита от SQL инъекций
- **XSS protection** - защита от XSS атак

---

## 📊 МОНИТОРИНГ И ЛОГИРОВАНИЕ

### 📈 Метрики
- **Request count** - количество запросов
- **Response time** - время ответа
- **Error rate** - частота ошибок
- **Active users** - активные пользователи

### 📋 Логирование
```json
{
  "timestamp": "2025-09-03T10:40:00.000Z",
  "level": "INFO",
  "method": "POST",
  "endpoint": "/webapp_data",
  "user_id": 123456789,
  "response_time": 150,
  "status_code": 200
}
```

---

## 🔗 СВЯЗАННЫЕ ДОКУМЕНТЫ

- [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md) - Техническая документация
- [SECURITY_GUIDE.md](SECURITY_GUIDE.md) - Руководство по безопасности
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - Руководство по развертыванию
- [TESTING_GUIDE.md](TESTING_GUIDE.md) - Руководство по тестированию

---

## 📞 ПОДДЕРЖКА

### 🔗 Полезные ссылки
- **Telegram Bot API**: https://core.telegram.org/bots/api
- **Telegram WebApp**: https://core.telegram.org/bots/webapps
- **GitHub репозиторий**: https://github.com/synthosaicreativestudio-maker/marketing

### 📋 Контакты
- **Техническая поддержка**: support@example.com
- **Документация**: docs/ папка в проекте
- **Issues**: GitHub Issues

---

*API документация обновляется автоматически при изменении endpoints.*

