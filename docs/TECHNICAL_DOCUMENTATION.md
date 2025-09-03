# 🔧 ТЕХНИЧЕСКАЯ ДОКУМЕНТАЦИЯ ДЛЯ ПРОГРАММИСТОВ

## 📅 Последнее обновление: 2025-09-03 10:30

---

## 🎯 ОБЗОР ДЛЯ РАЗРАБОТЧИКОВ

**Marketing Bot** - это асинхронный Telegram-бот, написанный на Python 3.13, с интеграцией Google Sheets и современным веб-интерфейсом. Проект использует архитектуру с разделением ответственности между компонентами.

### 🏗️ Архитектурные принципы
- **Асинхронность** - все операции с внешними API выполняются асинхронно
- **Разделение ответственности** - каждый модуль отвечает за свою область
- **Кэширование** - агрессивное кэширование для производительности
- **Обработка ошибок** - комплексная система обработки ошибок
- **Мониторинг** - встроенный мониторинг производительности

---

## 📁 СТРУКТУРА ПРОЕКТА

```
@marketing/
├── bot.py                          # Основной файл бота
├── async_promotions_client.py      # Асинхронный клиент акций
├── promotions_client.py            # Синхронный клиент акций
├── sheets_client.py                # Клиент Google Sheets
├── auth_cache.py                   # Система кэширования авторизации
├── spa_menu.html                   # Telegram WebApp интерфейс
├── config.py                       # Конфигурация проекта
├── config.ini                      # Настройки приложения
├── .env                            # Переменные окружения
├── requirements.txt                # Зависимости Python
├── start_production_bot.py         # Production launcher
├── performance_monitor.py          # Мониторинг производительности
├── error_handler.py                # Обработка ошибок
├── network_resilience.py           # Устойчивость к сбоям сети
├── validator.py                    # Валидация данных
├── openai_client.py                # OpenAI API клиент
├── docs/                           # Документация
│   ├── TECHNICAL_DOCUMENTATION.md  # Этот файл
│   ├── PROJECT_OVERVIEW.md         # Обзор проекта
│   ├── PROJECT_JOURNAL.md          # Журнал разработки
│   └── ...                         # Другие документы
└── scripts/                        # Утилиты и скрипты
    ├── manage_bot.sh               # Управление ботом
    ├── kill_all_bot_processes.sh   # Остановка процессов
    └── ...                         # Другие скрипты
```

---

## 🔧 ОСНОВНЫЕ КОМПОНЕНТЫ

### 1. **bot.py** - Основной файл бота

#### 🎯 Назначение
Главный файл приложения, содержащий класс `Bot` и всю основную логику.

#### 📋 Ключевые классы и методы

```python
class Bot:
    def __init__(self, token: str):
        """Инициализация бота с токеном"""
        
    async def _init_clients(self):
        """Асинхронная инициализация всех клиентов"""
        
    async def run(self):
        """Запуск бота и начало polling"""
        
    async def monitor_new_promotions(self, context):
        """Мониторинг новых акций каждые 30 секунд"""
        
    async def _send_promotion_notification(self, context, promotion, users):
        """Отправка уведомлений о новых акциях"""
        
    async def web_app_data(self, update, context):
        """Обработка данных от Telegram WebApp"""
        
    async def handle_callback_query(self, update, context):
        """Обработка callback запросов от inline кнопок"""
```

#### 🔧 Конфигурация
```python
# Основные настройки
PROMOTIONS_CONFIG = {
    'SHEET_NAME': 'Акции',
    'MONITORING_INTERVAL': 30,  # секунды
    'CACHE_TTL': 300,          # секунды
    'NOTIFICATION_DELAY': 1,   # секунды
    'MAX_DESCRIPTION_LENGTH': 200
}
```

#### 🚀 Запуск
```bash
# Активация виртуального окружения
source .venv/bin/activate

# Запуск бота
python bot.py

# Или через production launcher
python start_production_bot.py
```

---

### 2. **async_promotions_client.py** - Асинхронный клиент акций

#### 🎯 Назначение
Обеспечивает асинхронную работу с Google Sheets для операций с акциями, предотвращая блокировку event loop.

#### 📋 Ключевые методы

```python
class AsyncPromotionsClient:
    async def connect(self) -> bool:
        """Асинхронное подключение к Google Sheets"""
        
    async def get_new_published_promotions(self) -> List[Dict]:
        """Получение новых акций для уведомления"""
        
    async def get_active_promotions(self) -> List[Dict]:
        """Получение всех активных акций"""
        
    async def mark_notification_sent(self, row: int) -> bool:
        """Пометка уведомления как отправленного"""
        
    async def _run_in_executor(self, func, *args):
        """Выполнение синхронной функции в executor"""
```

#### 🔧 Использование
```python
# Инициализация
client = AsyncPromotionsClient(credentials_path, sheet_url)
await client.connect()

# Получение акций
promotions = await client.get_active_promotions()

# Пометка уведомления
await client.mark_notification_sent(row_number)
```

#### ⚙️ Конфигурация колонок
```python
# Константы колонок (соответствуют Google Apps Script)
HEADER_ROW = 1
RELEASE_DATE_COLUMN = 1    # A - Дата релиза
NAME_COLUMN = 2            # B - Название
DESCRIPTION_COLUMN = 3     # C - Описание
STATUS_COLUMN = 4          # D - Статус
START_DATE_COLUMN = 5      # E - Дата начала
END_DATE_COLUMN = 6        # F - Дата окончания
CONTENT_COLUMN = 7         # G - Контент
BUTTON_COLUMN = 8          # H - Опубликовать
NOTIFICATION_COLUMN = 9    # I - Уведомление отправлено
```

---

### 3. **auth_cache.py** - Система кэширования авторизации

#### 🎯 Назначение
Управляет кэшированием статуса авторизации пользователей с thread-safe операциями.

#### 📋 Ключевые методы

```python
class AuthCache:
    def __init__(self, cache_file: str = 'auth_cache.json'):
        """Инициализация с файлом кэша"""
        
    def is_user_authorized(self, user_id: int) -> bool:
        """Проверка авторизации пользователя"""
        
    def set_user_authorized(self, user_id: int, authorized: bool):
        """Установка статуса авторизации (thread-safe)"""
        
    def _save_to_file(self):
        """Сохранение кэша в файл"""
        
    def _load_from_file(self):
        """Загрузка кэша из файла"""
```

#### 🔧 Использование
```python
# Инициализация
cache = AuthCache('auth_cache.json')

# Проверка авторизации
if cache.is_user_authorized(user_id):
    # Пользователь авторизован
    pass

# Установка авторизации
cache.set_user_authorized(user_id, True)
```

#### 🛡️ Thread Safety
```python
# Используется threading.Lock для безопасности
with self._lock:
    self.cache[user_id] = {
        'authorized': authorized,
        'timestamp': time.time()
    }
    self._save_to_file()
```

---

### 4. **spa_menu.html** - Telegram WebApp интерфейс

#### 🎯 Назначение
Современный веб-интерфейс для взаимодействия с ботом через Telegram WebApp.

#### 📋 Ключевые функции

```javascript
// Основные функции
function goToPromotions() {
    showScreen('promotions-screen');
    loadPromotions();
}

function loadPromotions() {
    // Проверка кэша
    if (promotionsCache.data && promotionsCache.timestamp) {
        const cacheAge = Date.now() - promotionsCache.timestamp;
        if (cacheAge < promotionsCache.ttl) {
            renderPromotions(promotionsCache.data);
            return;
        }
    }
    
    // Запрос данных от бота
    const requestData = {
        type: 'get_promotions',
        timestamp: new Date().toISOString()
    };
    
    sendToBot(requestData);
}

function renderPromotions(promotions) {
    // Рендеринг акций с аккордеоном
    promotions.forEach((promotion, index) => {
        // Создание карточки акции
        // Добавление медиа контента
        // Настройка аккордеона
    });
}

function togglePromotion(index) {
    // Переключение состояния аккордеона
    const card = document.querySelectorAll('.promotion-card')[index];
    card.classList.toggle('expanded');
}
```

#### 🎨 CSS стили
```css
.promotion-card {
    border: 1px solid #ddd;
    border-radius: 8px;
    margin: 10px 0;
    overflow: hidden;
    transition: all 0.3s ease;
}

.promotion-card.expanded .promotion-content {
    max-height: 1000px;
    opacity: 1;
}

.promotion-content {
    max-height: 0;
    opacity: 0;
    transition: all 0.3s ease;
    overflow: hidden;
}
```

#### 🔧 Интеграция с Telegram
```javascript
// Инициализация Telegram WebApp
const tg = window.Telegram.WebApp;

// Отправка данных боту
function sendToBot(data) {
    try {
        tg.sendData(JSON.stringify(data));
        return true;
    } catch (error) {
        console.error('Ошибка отправки данных:', error);
        return false;
    }
}

// Получение данных от бота
tg.onEvent('webAppDataReceived', function(data) {
    const payload = JSON.parse(data);
    if (payload.type === 'promotions_response') {
        renderPromotions(payload.promotions);
    }
});
```

---

### 5. **config.py** - Конфигурация проекта

#### 🎯 Назначение
Централизованное хранение всех конфигурационных констант.

#### 📋 Основные конфигурации

```python
# Конфигурация акций
PROMOTIONS_CONFIG = {
    'SHEET_NAME': 'Акции',
    'MONITORING_INTERVAL': 30,      # Интервал мониторинга (секунды)
    'CACHE_TTL': 300,               # TTL кэша (секунды)
    'NOTIFICATION_DELAY': 1,        # Задержка между уведомлениями
    'MAX_DESCRIPTION_LENGTH': 200   # Максимальная длина описания
}

# URL WebApp
WEB_APP_URLS = {
    'SPA_MENU': 'https://your-domain.com/spa_menu.html'
}

# Разделы меню
SECTIONS = [
    'Личный кабинет',
    'Акции и мероприятия',
    'Поддержка',
    'Настройки'
]
```

---

### 6. **performance_monitor.py** - Мониторинг производительности

#### 🎯 Назначение
Декоратор для мониторинга производительности функций.

#### 📋 Использование

```python
from performance_monitor import monitor_performance

@monitor_performance('function_name')
async def some_function():
    # Ваша функция
    pass
```

#### 🔧 Логирование
```python
# Автоматически логирует:
# - Время выполнения
# - Память
# - Ошибки
# - Статистику
```

---

### 7. **error_handler.py** - Обработка ошибок

#### 🎯 Назначение
Декоратор для безопасного выполнения функций с обработкой ошибок.

#### 📋 Использование

```python
from error_handler import safe_execute

@safe_execute('function_name')
async def some_function():
    # Ваша функция
    pass
```

#### 🔧 Функциональность
- Автоматическое логирование ошибок
- Graceful degradation
- Retry механизмы
- Детальная диагностика

---

## 🔄 ЖИЗНЕННЫЙ ЦИКЛ АКЦИЙ

### 1. **Создание акции**
```python
# В Google Sheets создается новая строка:
# A: Дата релиза
# B: Название акции
# C: Описание
# D: Статус = "Активна"
# E: Дата начала
# F: Дата окончания
# G: Контент
# H: Кнопка "Опубликовать"
# I: Уведомление (пустое)
```

### 2. **Мониторинг**
```python
# Каждые 30 секунд выполняется:
async def monitor_new_promotions(self, context):
    # Получение новых акций
    new_promotions = await self.async_promotions_client.get_new_published_promotions()
    
    # Отправка уведомлений
    for promotion in new_promotions:
        await self._send_promotion_notification(context, promotion, authorized_users)
        await self.async_promotions_client.mark_notification_sent(promotion['row'])
```

### 3. **Отображение в WebApp**
```javascript
// Пользователь открывает WebApp
// Автоматически вызывается loadPromotions()
// Запрашиваются данные от бота
// Рендерится аккордеон с акциями
```

---

## 🚀 РАЗВЕРТЫВАНИЕ

### 📋 Требования
- Python 3.13+
- Google Sheets API credentials
- Telegram Bot Token
- Виртуальное окружение

### 🔧 Установка
```bash
# Клонирование репозитория
git clone <repository-url>
cd @marketing

# Создание виртуального окружения
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# или
.venv\Scripts\activate     # Windows

# Установка зависимостей
pip install -r requirements.txt

# Настройка конфигурации
cp .env.example .env
# Отредактируйте .env файл

# Запуск бота
python bot.py
```

### ⚙️ Конфигурация
```bash
# .env файл
TELEGRAM_BOT_TOKEN=your_bot_token
GOOGLE_CREDENTIALS_PATH=credentials.json
PROMOTIONS_SHEET_URL=your_sheet_url
OPENAI_API_KEY=your_openai_key
```

---

## 🧪 ТЕСТИРОВАНИЕ

### 🔧 Запуск тестов
```bash
# Активация окружения
source .venv/bin/activate

# Тестирование подключения к акциям
python test_promotion_creation.py

# Тестирование функциональности бота
python test_bot_functionality.py

# Тестирование Telegram соединения
python test_telegram_connection.py
```

### 📊 Мониторинг
```bash
# Просмотр логов
tail -f bot.log

# Проверка статуса бота
python manage_bot.py status

# Остановка бота
python manage_bot.py stop
```

---

## 🐛 ОТЛАДКА

### 🔍 Общие проблемы

#### 1. **Ошибка подключения к Google Sheets**
```python
# Проверьте:
# - Файл credentials.json
# - Права доступа к таблице
# - URL таблицы
# - Интернет соединение
```

#### 2. **Конфликт процессов бота**
```bash
# Найдите и остановите все процессы
ps aux | grep -i bot | grep -v grep
kill <PID>

# Или используйте скрипт
./kill_all_bot_processes.sh
```

#### 3. **Проблемы с WebApp**
```javascript
// Проверьте в консоли браузера:
// - Ошибки JavaScript
// - Доступность Telegram API
// - Корректность данных от бота
```

### 📋 Логирование
```python
# Уровни логирования
logger.debug("Детальная информация")
logger.info("Общая информация")
logger.warning("Предупреждения")
logger.error("Ошибки")
logger.critical("Критические ошибки")
```

---

## 🔧 РАЗРАБОТКА

### 📋 Добавление новой функции

1. **Создайте обработчик в bot.py**
```python
async def new_function(self, update, context):
    # Ваша логика
    pass
```

2. **Зарегистрируйте обработчик**
```python
self.application.add_handler(CommandHandler('new_command', self.new_function))
```

3. **Добавьте тесты**
```python
# Создайте test_new_function.py
```

4. **Обновите документацию**
```markdown
# Добавьте описание в docs/
```

### 🎯 Лучшие практики

#### 1. **Асинхронное программирование**
```python
# ✅ Правильно
async def async_function():
    result = await some_async_operation()
    return result

# ❌ Неправильно
def sync_function():
    result = some_sync_operation()  # Блокирует event loop
    return result
```

#### 2. **Обработка ошибок**
```python
# ✅ Правильно
@safe_execute('function_name')
async def function_with_error_handling():
    try:
        result = await risky_operation()
        return result
    except SpecificException as e:
        logger.error(f"Specific error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise
```

#### 3. **Кэширование**
```python
# ✅ Правильно
if cache.is_valid():
    return cache.get_data()
else:
    data = await fetch_data()
    cache.set_data(data)
    return data
```

---

## 📚 ДОПОЛНИТЕЛЬНЫЕ РЕСУРСЫ

### 🔗 Полезные ссылки
- **Python Telegram Bot**: https://python-telegram-bot.readthedocs.io/
- **Google Sheets API**: https://developers.google.com/sheets/api
- **Telegram Bot API**: https://core.telegram.org/bots/api
- **Telegram WebApp**: https://core.telegram.org/bots/webapps

### 📖 Документация проекта
- **PROJECT_OVERVIEW.md** - Обзор проекта
- **PROJECT_JOURNAL.md** - Журнал разработки
- **PROJECT_CHECKLIST.md** - Чек-лист задач
- **PROJECT_ROADMAP.md** - Роадмэп развития

### 🛠️ Инструменты разработки
- **VS Code** - рекомендуемый редактор
- **Python Extension** - поддержка Python
- **Git** - система контроля версий
- **Docker** - контейнеризация (планируется)

---

## 🎯 ЗАКЛЮЧЕНИЕ

Эта документация предоставляет полное техническое описание проекта Marketing Bot. Она предназначена для разработчиков, которые хотят понять архитектуру, внести изменения или расширить функциональность.

### 📋 Следующие шаги
1. Изучите структуру проекта
2. Настройте окружение разработки
3. Запустите тесты
4. Внесите изменения
5. Обновите документацию

---

*Техническая документация обновляется автоматически при каждом изменении в коде.*

