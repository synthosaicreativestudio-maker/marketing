# 📚 API Reference - Marketing Bot

## 🔧 Основные модули

### 1. **Bot Core (`bot.py`)**

#### **Класс Bot**
Основной класс бота, инкапсулирующий всю логику.

```python
class Bot:
    def __init__(self, token: str)
    async def run(self)
```

#### **Обработчики команд**

##### **start()**
```python
async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE)
```
- **Назначение**: Обработка команды /start
- **Логика**: Проверка авторизации, показ соответствующего интерфейса
- **Возвращает**: Приветственное сообщение с кнопками

##### **auth_command()**
```python
async def auth_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE)
```
- **Назначение**: Авторизация через команду `/auth <код> <телефон>`
- **Параметры**: 
  - `code` - код партнера
  - `phone` - номер телефона
- **Логика**: Валидация, проверка блокировок, поиск в Google Sheets
- **Возвращает**: Результат авторизации

##### **handle_message()**
```python
async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE)
```
- **Назначение**: Обработка текстовых сообщений
- **Логика**: Авторизация → логирование → AI ответ → кнопки управления
- **Возвращает**: Ответ AI с инлайн-кнопками

##### **web_app_data()**
```python
async def web_app_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE)
```
- **Назначение**: Обработка данных от веб-приложений
- **Типы данных**:
  - `auth_request` - авторизация
  - `menu_selection` - выбор раздела
  - `subsection_selection` - выбор подраздела
  - `get_promotions` - запрос акций
- **Возвращает**: Соответствующий ответ

#### **Фоновые задачи**

##### **monitor_specialist_replies()**
```python
async def monitor_specialist_replies(self, context: ContextTypes.DEFAULT_TYPE)
```
- **Назначение**: Мониторинг ответов специалистов
- **Интервал**: Настраивается в `SCALING_CONFIG['MONITORING_INTERVAL']`
- **Логика**: Читает столбец G → отправляет пользователю → логирует → очищает

##### **monitor_new_promotions()**
```python
async def monitor_new_promotions(self, context: ContextTypes.DEFAULT_TYPE)
```
- **Назначение**: Мониторинг новых акций
- **Интервал**: Настраивается в `PROMOTIONS_CONFIG['MONITORING_INTERVAL']`
- **Логика**: Ищет "Опубликовано" → уведомляет всех → помечает "отправлено"

### 2. **Google Sheets Integration**

#### **GoogleSheetsClient (`sheets_client.py`)**

##### **Инициализация**
```python
def __init__(self, credentials_path: str, sheet_url: str, worksheet_name: str)
```

##### **Поиск пользователей**
```python
def find_user_by_id(self, user_id: int) -> tuple[int, str] | None
def find_user_by_credentials(self, code: str, phone: str) -> int | None
```

##### **Обновление авторизации**
```python
def update_user_auth_status(self, row_to_update: int, user_id: int)
```

##### **Работа с тикетами**
```python
def upsert_ticket(self, telegram_id: str, code: str, phone: str, fio: str, 
                  text: str, status: str = 'в работе', sender_type: str = 'user', 
                  handled: bool = False)
```

##### **Ответы специалистов**
```python
def set_specialist_reply(self, telegram_id: str, reply_text: str, clear_after_send: bool = True)
def extract_operator_replies(self) -> List[Dict]
```

#### **PromotionsClient (`promotions_client.py`)**

##### **Инициализация**
```python
def __init__(self, credentials_file: str, sheet_url: str)
```

##### **Подключение**
```python
def connect(self) -> bool
```

##### **Получение акций**
```python
def get_new_published_promotions(self) -> List[Dict[str, Any]]
def get_active_promotions(self) -> List[Dict[str, Any]]
```

##### **Управление уведомлениями**
```python
def mark_notification_sent(self, row: int) -> bool
```

### 3. **OpenAI Integration (`openai_client.py`)**

#### **OpenAIClient**

##### **Инициализация**
```python
def __init__(self)
```

##### **Проверка доступности**
```python
def is_available(self) -> bool
```

##### **Создание thread**
```python
async def create_thread(self) -> Optional[str]
```

##### **Отправка сообщения**
```python
async def send_message(self, thread_id: str, text: str, max_wait: int = 60) -> Optional[str]
```

##### **Управление thread**
```python
async def get_or_create_thread(self, user_data: Dict[str, Any]) -> Optional[str]
```

### 4. **Caching System**

#### **AuthCache (`auth_cache.py`)**

##### **Инициализация**
```python
def __init__(self, persistence_file: str = 'auth_cache.json')
```

##### **Управление авторизацией**
```python
def get_authorized_ids(self) -> Optional[Set[str]]
def set_authorized_ids(self, ids: Set[str])
def is_user_authorized(self, user_id: int) -> Optional[bool]
def set_user_authorized(self, user_id: int, is_authorized: bool, partner_code: str = '', phone: str = '')
```

##### **Управление блокировками**
```python
def is_user_blocked(self, user_id: int) -> Tuple[bool, int]
def add_failed_attempt(self, user_id: int) -> Tuple[bool, int]
def clear_failed_attempts(self, user_id: int)
```

#### **MCP Context (`mcp_context_v7.py`)**

##### **Инициализация**
```python
def __init__(self, max_messages: int = 200, persistence_file: Optional[str] = None)
```

##### **Управление thread**
```python
def create_thread(self, user_key: str) -> str
def register_thread(self, thread_id: str, user_key: str) -> None
def get_thread_for_user(self, user_key: str) -> str | None
```

##### **Управление сообщениями**
```python
def append_message(self, thread_id: str, role: str, text: str) -> None
def get_messages(self, thread_id: str) -> List[Tuple[str, str, float]]
def prune_thread(self, thread_id: str, keep: int = 50) -> None
```

### 5. **Configuration Management**

#### **Config (`config.py`)**

##### **Основные константы**
```python
SECTIONS = [...]  # Разделы меню
SUBSECTIONS = {...}  # Подразделы
AUTH_CONFIG = {...}  # Настройки авторизации
PROMOTIONS_CONFIG = {...}  # Настройки акций
SCALING_CONFIG = {...}  # Настройки масштабирования
```

##### **Геттеры**
```python
def get_web_app_url(key: str = 'MAIN') -> str
def get_sheet_column(column_type: str, is_ticket: bool = False) -> int
def get_ticket_status(status_type: str) -> str
def get_sheet_color(status: str) -> dict
```

#### **ConfigManager (`config_manager.py`)**

##### **Инициализация**
```python
def __init__(self, config_file: str = 'config.ini')
```

##### **Telegram настройки**
```python
def get_telegram_token(self) -> str
def get_admin_chat_id(self) -> int
```

##### **Google Sheets настройки**
```python
def get_credentials_path(self) -> str
def get_sheet_url(self) -> str
def get_tickets_sheet_url(self) -> str
```

##### **Валидация**
```python
def validate_config(self) -> Tuple[bool, List[str]]
```

### 6. **Monitoring & Performance**

#### **Performance Monitor (`performance_monitor.py`)**

##### **Декоратор мониторинга**
```python
@monitor_performance(operation_type: str)
def some_function():
    pass
```

##### **Запись метрик**
```python
def record_operation(self, operation_type: str, execution_time: float, success: bool = True)
def record_sheets_operation(self, success: bool = True)
def record_openai_operation(self, success: bool = True, tokens_used: int = 0)
```

##### **Получение статистики**
```python
def get_detailed_stats(self) -> Dict[str, Any]
def get_health_status(self) -> Dict[str, Any]
```

#### **Error Handler (`error_handler.py`)**

##### **Декоратор безопасного выполнения**
```python
@safe_execute(context_name: str = "")
def some_function():
    pass
```

##### **Обработка ошибок**
```python
def handle_sheets_error(error: Exception, operation: str) -> bool
def handle_telegram_error(error: Exception, operation: str, user_id: Optional[int] = None) -> bool
def handle_openai_error(error: Exception, operation: str) -> Optional[str]
```

## 🔄 Потоки данных

### **Авторизация**
```
User → /auth → Bot → AuthCache → SheetsClient → Google Sheets → Response
```

### **Обработка сообщения**
```
User → Message → Bot → AuthCache → OpenAI → MCP Context → Response → Tickets
```

### **Мониторинг акций**
```
Background → PromotionsClient → Google Sheets → Notification → All Users
```

### **Ответы специалистов**
```
Background → SheetsClient → Extract → Send → Log → Clear
```

## 📊 Схемы данных

### **Google Sheets - Авторизация**
| Колонка | Название | Описание |
|---------|----------|----------|
| A | код | Код партнера |
| B | телефон | Номер телефона |
| C | ФИО | Фамилия Имя Отчество |
| D | статус | Статус авторизации |
| E | telegram_id | ID пользователя в Telegram |
| F | статус_партнера | Статус партнера |

### **Google Sheets - Тикеты**
| Колонка | Название | Описание |
|---------|----------|----------|
| A | код | Код партнера |
| B | телефон | Номер телефона |
| C | ФИО | Фамилия Имя Отчество |
| D | telegram_id | ID пользователя в Telegram |
| E | текст_обращений | История обращений |
| F | статус | Статус тикета |
| G | специалист_ответ | Временное поле для ответа |
| H | время_обновления | Время последнего обновления |

### **Google Sheets - Акции**
| Колонка | Название | Описание |
|---------|----------|----------|
| A | дата_релиза | Дата релиза |
| B | название | Название акции |
| C | описание | Описание акции |
| D | статус | Статус акции |
| E | дата_начала | Дата начала |
| F | дата_окончания | Дата окончания |
| G | контент | Медиа контент |
| H | опубликовать | Кнопка публикации |
| I | уведомление | Статус уведомления |

## 🎯 Конфигурация

### **Переменные окружения**
```bash
TELEGRAM_TOKEN=your_bot_token
SHEET_URL=your_auth_sheet_url
TICKETS_SHEET_URL=your_tickets_sheet_url
PROMOTIONS_SHEET_URL=your_promotions_sheet_url
OPENAI_API_KEY=your_openai_key
OPENAI_ASSISTANT_ID=your_assistant_id
ADMIN_TELEGRAM_ID=admin_id1,admin_id2
```

### **Файлы конфигурации**
- `.env` или `bot.env` - переменные окружения
- `config.ini` - дополнительные настройки
- `credentials.json` - Google Sheets API ключи

---

**Последнее обновление**: 2025-01-03 08:57
**Версия API**: 1.0
**Статус**: В разработке
