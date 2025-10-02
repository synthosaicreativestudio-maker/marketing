# API Reference - MarketingBot v3.0

## Обзор API

MarketingBot v3.0 предоставляет набор сервисов для управления авторизацией, обращениями и интеграции с OpenAI Assistant.

## AuthService

### Методы

#### `get_user_auth_status(telegram_id: int) -> bool`
Проверяет статус авторизации пользователя.

**Параметры**:
- `telegram_id` (int): ID пользователя в Telegram

**Возвращает**:
- `bool`: True если пользователь авторизован, False иначе

**Пример**:
```python
auth_service = AuthService()
is_authorized = auth_service.get_user_auth_status(123456789)
```

#### `find_and_update_user(partner_code: str, partner_phone: str, telegram_id: int) -> bool`
Ищет пользователя по коду и телефону, обновляет Telegram ID.

**Параметры**:
- `partner_code` (str): Код партнера
- `partner_phone` (str): Телефон партнера
- `telegram_id` (int): ID пользователя в Telegram

**Возвращает**:
- `bool`: True если пользователь найден и обновлен

**Пример**:
```python
success = auth_service.find_and_update_user("12345", "89123456789", 123456789)
```

#### `force_check_auth_status(telegram_id: int) -> bool`
Принудительно проверяет статус авторизации, игнорируя кэш.

**Параметры**:
- `telegram_id` (int): ID пользователя в Telegram

**Возвращает**:
- `bool`: True если пользователь авторизован

## OpenAIService

### Методы

#### `is_enabled() -> bool`
Проверяет, включен ли сервис OpenAI.

**Возвращает**:
- `bool`: True если сервис доступен

#### `ask(user_id: int, message: str) -> str`
Отправляет сообщение ассистенту и получает ответ.

**Параметры**:
- `user_id` (int): ID пользователя
- `message` (str): Текст сообщения

**Возвращает**:
- `str`: Ответ ассистента

**Пример**:
```python
openai_service = OpenAIService()
response = openai_service.ask(123456789, "Привет, как дела?")
```

#### `get_or_create_thread(user_id: int) -> str`
Получает или создает Thread для пользователя.

**Параметры**:
- `user_id` (int): ID пользователя

**Возвращает**:
- `str`: ID Thread

## AppealsService

### Методы

#### `is_available() -> bool`
Проверяет доступность сервиса обращений.

**Возвращает**:
- `bool`: True если сервис доступен

#### `create_appeal(code: str, phone: str, fio: str, telegram_id: int, text: str) -> bool`
Создает или обновляет обращение.

**Параметры**:
- `code` (str): Код партнера
- `phone` (str): Телефон партнера
- `fio` (str): ФИО партнера
- `telegram_id` (int): ID пользователя в Telegram
- `text` (str): Текст обращения

**Возвращает**:
- `bool`: True если обращение создано/обновлено

**Пример**:
```python
appeals_service = AppealsService()
success = appeals_service.create_appeal(
    code="12345",
    phone="89123456789",
    fio="Иванов Иван Иванович",
    telegram_id=123456789,
    text="У меня проблема с загрузкой объекта"
)
```

#### `set_status_in_work(telegram_id: int) -> bool`
Устанавливает статус обращения "в работе".

**Параметры**:
- `telegram_id` (int): ID пользователя в Telegram

**Возвращает**:
- `bool`: True если статус установлен

#### `get_appeal_status(telegram_id: int) -> str`
Получает статус обращения пользователя.

**Параметры**:
- `telegram_id` (int): ID пользователя в Telegram

**Возвращает**:
- `str`: Статус обращения (новое/в работе/решено)

#### `check_for_responses() -> List[Dict]`
Проверяет наличие новых ответов специалистов.

**Возвращает**:
- `List[Dict]`: Список ответов с данными

**Структура ответа**:
```python
{
    'row': int,           # Номер строки в таблице
    'telegram_id': str,   # ID пользователя
    'response': str,      # Текст ответа
    'code': str,          # Код партнера
    'fio': str            # ФИО партнера
}
```

#### `clear_response(row: int) -> bool`
Очищает ячейку с ответом специалиста.

**Параметры**:
- `row` (int): Номер строки для очистки

**Возвращает**:
- `bool`: True если ячейка очищена

#### `add_specialist_response(telegram_id: int, response_text: str) -> bool`
Добавляет ответ специалиста к обращениям пользователя.

**Параметры**:
- `telegram_id` (int): ID пользователя в Telegram
- `response_text` (str): Текст ответа специалиста

**Возвращает**:
- `bool`: True если ответ добавлен

#### `has_records() -> bool`
Проверяет наличие записей в таблице.

**Возвращает**:
- `bool`: True если есть записи

#### `get_user_appeals(telegram_id: int) -> List[Dict]`
Получает обращения пользователя.

**Параметры**:
- `telegram_id` (int): ID пользователя в Telegram

**Возвращает**:
- `List[Dict]`: Список обращений пользователя

## ResponseMonitor

### Методы

#### `start()`
Запускает мониторинг ответов.

#### `stop()`
Останавливает мониторинг ответов.

#### `send_test_response(telegram_id: int, test_message: str)`
Отправляет тестовое сообщение пользователю.

**Параметры**:
- `telegram_id` (int): ID пользователя в Telegram
- `test_message` (str): Тестовое сообщение

## Handlers

### Функции

#### `create_main_menu_keyboard() -> ReplyKeyboardMarkup`
Создает клавиатурное меню с опциями.

**Возвращает**:
- `ReplyKeyboardMarkup`: Клавиатура с кнопками

**Кнопки**:
- "👨‍💼 Обратиться к специалисту"
- "🤖 Продолжить с ассистентом"

#### `_should_show_specialist_button(text: str) -> bool`
Проверяет, нужно ли показать кнопку обращения к специалисту.

**Параметры**:
- `text` (str): Текст сообщения

**Возвращает**:
- `bool`: True если нужно показать кнопку

### Обработчики

#### `start_command_handler(auth_service: AuthService)`
Обработчик команды /start.

#### `web_app_data_handler(auth_service: AuthService)`
Обработчик данных из WebApp.

#### `chat_handler(auth_service: AuthService, openai_service: OpenAIService, appeals_service: AppealsService)`
Обработчик текстовых сообщений.

#### `appeals_command_handler(auth_service: AuthService, appeals_service: AppealsService)`
Обработчик команды /appeals.

#### `callback_query_handler(auth_service: AuthService, appeals_service: AppealsService)`
Обработчик callback queries (инлайн кнопки).

## Конфигурация

### Переменные окружения

#### Telegram
- `TELEGRAM_TOKEN`: Токен бота
- `ADMIN_TELEGRAM_ID`: ID администратора

#### OpenAI
- `OPENAI_API_KEY`: API ключ OpenAI
- `OPENAI_ASSISTANT_ID`: ID ассистента

#### Google Sheets
- `SHEET_ID`: ID таблицы авторизации
- `APPEALS_SHEET_ID`: ID таблицы обращений
- `SHEET_NAME`: Название листа авторизации
- `APPEALS_SHEET_NAME`: Название листа обращений
- `GCP_SA_FILE`: Путь к файлу Service Account

#### WebApp
- `WEB_APP_URL`: URL WebApp для авторизации

### Структура таблиц

#### Таблица авторизации
| Колонка | Описание | Тип |
|---------|----------|-----|
| A | Код партнера | String |
| B | Телефон партнера | String |
| C | ФИО партнера | String |
| D | Telegram ID | String |
| E | Статус авторизации | String |
| F | Дата авторизации | DateTime |

#### Таблица обращений
| Колонка | Описание | Тип |
|---------|----------|-----|
| A | Код партнера | String |
| B | Телефон партнера | String |
| C | ФИО партнера | String |
| D | Telegram ID | String |
| E | Текст обращений | Multi-line String |
| F | Статус | Enum |
| G | Ответ специалиста | String |
| H | Время обновления | DateTime |

## Обработка ошибок

### Типы исключений

#### `SheetsNotConfiguredError`
Вызывается при неправильной конфигурации Google Sheets.

#### `telegram.error.Conflict`
Вызывается при конфликте с другими экземплярами бота.

#### `openai.OpenAIError`
Вызывается при ошибках OpenAI API.

### Обработка ошибок

```python
try:
    result = service.method()
except SpecificError as e:
    logger.error(f"Error: {e}")
    return fallback_value
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    return None
```

## Логирование

### Уровни логирования

- `DEBUG`: Детальная информация для отладки
- `INFO`: Общая информация о работе
- `WARNING`: Предупреждения
- `ERROR`: Ошибки
- `CRITICAL`: Критические ошибки

### Примеры логов

```python
logger.info(f"CHAT_HANDLER: Текстовое сообщение от {user.id}: {text}")
logger.error(f"Ошибка создания обращения: {e}", exc_info=True)
logger.warning(f"AppealsService недоступен: {e}")
```

## Примеры использования

### Базовое использование

```python
from auth_service import AuthService
from openai_service import OpenAIService
from appeals_service import AppealsService

# Инициализация сервисов
auth_service = AuthService()
openai_service = OpenAIService()
appeals_service = AppealsService()

# Проверка авторизации
if auth_service.get_user_auth_status(123456789):
    # Создание обращения
    appeals_service.create_appeal(
        code="12345",
        phone="89123456789",
        fio="Иванов И.И.",
        telegram_id=123456789,
        text="Вопрос по маркетингу"
    )
    
    # Обращение к ассистенту
    response = openai_service.ask(123456789, "Привет!")
    print(response)
```

### Обработка ответов специалистов

```python
from response_monitor import ResponseMonitor

# Создание монитора
monitor = ResponseMonitor(bot, appeals_service)

# Запуск мониторинга
await monitor.start()

# Остановка мониторинга
await monitor.stop()
```

### Работа с клавиатурным меню

```python
from handlers import create_main_menu_keyboard

# Создание меню
keyboard = create_main_menu_keyboard()

# Отправка с клавиатурой
await update.message.reply_text(
    "Выберите действие:",
    reply_markup=keyboard
)
```

## Заключение

API MarketingBot v3.0 предоставляет полный набор инструментов для создания маркетингового бота с интеграцией ИИ-ассистента и системой управления обращениями. Все методы имеют подробную документацию и примеры использования.
