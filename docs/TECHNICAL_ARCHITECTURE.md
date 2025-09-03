# 🏗️ Техническая архитектура Marketing Bot

## 📋 Обзор системы

Marketing Bot - это Telegram-бот для управления маркетинговыми процессами с интеграцией AI-ассистента, системой тикетов и мониторингом акций.

### 🎯 Основные компоненты
- **Telegram Bot API** - интерфейс пользователя
- **Google Sheets** - хранение данных (авторизация, тикеты, акции)
- **OpenAI Assistants API** - AI-ассистент для ответов
- **Система кэширования** - оптимизация производительности
- **Фоновые задачи** - мониторинг и уведомления

## 🏛️ Архитектурная диаграмма

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Telegram      │    │   Bot Core       │    │   External      │
│   Users         │◄──►│   (bot.py)       │◄──►│   Services      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │   Core Modules   │
                    │                  │
                    │ • AuthCache      │
                    │ • SheetsClient   │
                    │ • OpenAIClient   │
                    │ • PromotionsClient│
                    │ • MCPContext     │
                    └──────────────────┘
```

## 🔧 Основные модули

### 1. **Bot Core (`bot.py`)**
**Назначение**: Основной класс бота, обработка команд и сообщений

**Ключевые методы**:
- `start()` - обработка команды /start
- `handle_message()` - обработка текстовых сообщений
- `web_app_data()` - обработка данных от веб-приложений
- `monitor_specialist_replies()` - мониторинг ответов специалистов
- `monitor_new_promotions()` - мониторинг новых акций

**Проблемы**:
- Слишком большой класс (1600+ строк)
- Смешивание логики авторизации, AI, тикетов
- Нужен рефакторинг на более мелкие компоненты

### 2. **Google Sheets Integration**

#### **SheetsClient (`sheets_client.py`)**
**Назначение**: Работа с таблицами авторизации и тикетов

**Ключевые методы**:
- `find_user_by_credentials()` - поиск пользователя по коду и телефону
- `update_user_auth_status()` - обновление статуса авторизации
- `upsert_ticket()` - создание/обновление тикетов
- `extract_operator_replies()` - извлечение ответов специалистов

**Схема данных**:
```
Авторизация: A=код, B=телефон, C=ФИО, D=статус, E=telegram_id, F=статус_партнера
Тикеты: A=код, B=телефон, C=ФИО, D=telegram_id, E=текст_обращений, F=статус, G=специалист_ответ, H=время_обновления
```

#### **PromotionsClient (`promotions_client.py`)**
**Назначение**: Работа с таблицей акций

**Ключевые методы**:
- `get_new_published_promotions()` - получение новых акций для уведомлений
- `get_active_promotions()` - получение активных акций
- `mark_notification_sent()` - пометка уведомления как отправленного

### 3. **OpenAI Integration (`openai_client.py`)**
**Назначение**: Интеграция с OpenAI Assistants API

**Ключевые особенности**:
- Семафор для ограничения concurrent запросов
- Exponential backoff для retry логики
- Rate limiting (минимум 1 секунда между запросами)
- Интеграция с MCP контекстом для сохранения диалогов

**Параметры**:
- `MAX_CONCURRENT`: 3 одновременных запроса
- `MAX_RETRY`: 2 попытки
- `BACKOFF_BASE`: 0.8

### 4. **Caching System**

#### **AuthCache (`auth_cache.py`)**
**Назначение**: Кэширование авторизации и блокировок

**Структура данных**:
- `authorized_ids` - кэш авторизованных пользователей
- `user_cache` - кэш данных пользователей
- `failed_attempts` - отслеживание неудачных попыток

**TTL настройки**:
- `CACHE_TTL`: 300 секунд (5 минут)
- `USER_CACHE_TTL`: 1800 секунд (30 минут)

#### **MCP Context (`mcp_context_v7.py`)**
**Назначение**: Управление контекстом диалогов с AI

**Особенности**:
- Персистентное хранение в JSON файле
- Автоматическая очистка старых диалогов (24 часа)
- Привязка диалогов к telegram_id пользователя
- Ограничение количества сообщений (200 на диалог)

### 5. **Configuration Management**

#### **Config (`config.py`)**
**Назначение**: Централизованные константы и настройки

**Основные секции**:
- `SECTIONS` - разделы меню
- `SUBSECTIONS` - подразделы
- `AUTH_CONFIG` - настройки авторизации
- `PROMOTIONS_CONFIG` - настройки акций
- `SCALING_CONFIG` - настройки масштабирования

#### **ConfigManager (`config_manager.py`)**
**Назначение**: Управление конфигурацией через INI файлы

**Особенности**:
- Подстановка переменных окружения `${VAR_NAME}`
- Валидация конфигурации
- Fallback значения

### 6. **Monitoring & Performance**

#### **Performance Monitor (`performance_monitor.py`)**
**Назначение**: Мониторинг производительности и метрик

**Метрики**:
- Время выполнения операций
- Процент успешных операций
- Статистика по типам операций
- Метрики внешних сервисов (Sheets, OpenAI, Telegram)

#### **Error Handler (`error_handler.py`)**
**Назначение**: Централизованная обработка ошибок

**Декоратор `@safe_execute`**:
- Логирование ошибок с контекстом
- Обработка специфичных ошибок (Sheets, Telegram, OpenAI)
- Graceful degradation

### 7. **Process Management**

#### **Management Scripts**
- `manage_bot.py` - CLI для управления ботом
- `run_single_bot.sh` - скрипт гарантированного единственного запуска
- `start_production_bot.py` - production launcher

#### **System Services**
- `com.marketing.telegram-bot.plist` - launchd service для macOS
- `marketing-bot.service` - systemd service для Linux

## 🔄 Потоки данных

### 1. **Авторизация пользователя**
```
User → /auth command → Bot → SheetsClient → Google Sheets → AuthCache → Response
```

### 2. **Обработка сообщения**
```
User → Text message → Bot → AuthCache → OpenAI → MCP Context → Response → Tickets
```

### 3. **Мониторинг акций**
```
Background Job → PromotionsClient → Google Sheets → Notification → All Users
```

### 4. **Ответы специалистов**
```
Background Job → SheetsClient → Extract replies → Send to users → Log to tickets
```

## 🚨 Выявленные проблемы

### 1. **Архитектурные проблемы**
- **Монолитный класс Bot** - нужно разбить на сервисы
- **Смешивание ответственности** - авторизация, AI, тикеты в одном месте
- **Отсутствие dependency injection** - жесткая связанность компонентов

### 2. **Проблемы производительности**
- **Синхронные вызовы** к Google Sheets в асинхронном контексте
- **Отсутствие connection pooling** для внешних API
- **Неэффективный кэш** - может расти бесконечно

### 3. **Проблемы надежности**
- **Race conditions** в кэше авторизации
- **Широкие exception handlers** - могут скрывать проблемы
- **Отсутствие circuit breakers** для внешних сервисов

## 🎯 Планы улучшения

### 1. **Рефакторинг архитектуры**
- Выделить отдельные сервисы: `AuthService`, `AIService`, `TicketsService`
- Внедрить dependency injection
- Создать абстракции для внешних API

### 2. **Улучшение производительности**
- Добавить connection pooling
- Реализовать proper caching strategies
- Оптимизировать запросы к Google Sheets

### 3. **Повышение надежности**
- Исправить race conditions
- Добавить circuit breakers
- Улучшить error handling

---

**Последнее обновление**: 2025-01-03 08:57
**Версия архитектуры**: 1.0
**Статус**: В разработке
