# Технический отчёт аудита проекта MarketingBot

**Дата:** 2025  
**Версия кодовой базы:** после применения Hotfixes Фазы 1 и доработок Фаз 2–4  
**Охват:** все файлы, архитектура, модули, логика, импорты, логи

---

## 1. Обзор проекта

### 1.1 Назначение

Telegram-бот для маркетинговой автоматизации компании «Этажи» (Тюмень): чат с ИИ (Gemini), обращения, акции, авторизация через WebApp, эскалация к специалистам.

### 1.2 Стек

| Компонент | Технология |
|-----------|------------|
| Язык | Python 3.12 |
| Telegram | python-telegram-bot 21.10 |
| ИИ | Google Gemini (google-genai), модель gemini-3-flash-preview |
| Таблицы | Google Sheets (gspread), 3 таблицы: auth, appeals, promotions |
| Дополнительно | tenacity, psutil, aiohttp, cachetools, python-dotenv, google-api-python-client, google-auth-* |

### 1.3 Точка входа и запуск

- **Точка входа:** `bot.py` → `main()` → `_run_bot_main()`
- **Локальный запуск запрещён** (один токен — один инстанс). Деплой: Yandex Cloud (systemd), логи: `journalctl -u marketingbot-bot.service -f`

---

## 2. Архитектура

### 2.1 Схема модулей

```
bot.py
├── AsyncGoogleSheetsGateway (auth, appeals, promotions)
├── AuthService(auth_gateway)
├── AIService(promotions_gateway) → GeminiService
├── AppealsService(appeals_gateway)
├── ResponseMonitor(appeals_service, token)
├── PromotionsNotifier(bot, auth_service, promotions_gateway)
├── BotHealthMonitor(bot, auth_gateway, auth_service)
├── PollingWatchdog
├── task_tracker
├── preventive_guards (SingleInstanceGuard, validate_environment)
└── setup_handlers(…, promotions_gateway)
    ├── register_auth_handlers
    ├── register_chat_handlers (auth, ai, appeals)
    ├── register_appeals_handlers (auth, appeals)
    ├── register_promotions_handlers (auth, promotions_gateway)
    └── register_callback_handlers (auth, appeals)
```

### 2.2 Потоки данных

1. **Сообщение пользователя (TEXT)**  
   `chat` → auth → при ENABLE_APPEALS: `_create_appeal_entry` (gateway) → эскалация или `_is_specialist_mode` → `ai_service.ask_stream` → стриминг, `_safe_background_log` (Sheets + `logs/chat_history.jsonl`).

2. **Кнопка «Специалист»**  
   `callback` → `auth_service.gateway.get_all_records(worksheet)` → `appeals_service.create_appeal` + `set_status_in_work`.

3. **Команда /promotions**  
   `promotions` → `await is_promotions_available(gateway)` → `await get_promotions_json(gateway)` → `_send_promotions`.

4. **WebApp `action=get_promotions`**  
   `auth` (web_app_data) → `handle_promotions_request` → свой `AsyncGoogleSheetsGateway('promotions')` → `get_promotions_json` / `_send_promotions`.

5. **Фоновые циклы (post_init):**  
   ResponseMonitor (60 c), PromotionsNotifier (15 мин), BotHealthMonitor (300 c), PollingWatchdog (30 c), Knowledge Base init (Gemini).

### 2.3 Внешние зависимости

| Переменная | Назначение |
|------------|------------|
| TELEGRAM_TOKEN | Бот |
| SHEET_ID, SHEET_NAME | Авторизация |
| APPEALS_SHEET_ID, APPEALS_SHEET_NAME | Обращения |
| PROMOTIONS_SHEET_ID, PROMOTIONS_SHEET_NAME | Акции |
| GCP_SA_FILE / GCP_SA_JSON | Google API |
| GEMINI_API_KEY | Gemini (или PROXYAPI_* для прокси) |
| DRIVE_FOLDER_ID | RAG (Knowledge Base) |
| WEB_APP_URL | WebApp авторизации и меню |
| SYSTEM_PROMPT_FILE | system_prompt.txt |

---

## 3. Критические и важные замечания

### 3.1 Дублирование `utils` (средний приоритет)

**Файлы:** `utils.py` (корень) и `handlers/utils.py`

- В **handlers/utils.py** продублированы: `_validate_url`, `get_web_app_url`, `get_spa_menu_url`, `create_specialist_button`, `_is_user_escalation_request`, `_is_ai_asking_for_escalation`, `_is_escalation_confirmation`, `_should_show_specialist_button`.
- Функций `mask_phone`, `mask_telegram_id`, `mask_fio` в `handlers/utils` нет.
- Импорты идут только из корневого `utils`; `handlers.utils` нигде не используется.

**Риск:** расхождение при доработке одной копии, лишний код.

**Решение:** удалить `handlers/utils.py` и оставить единственный источник в `utils.py`. При необходимости — `from utils import ...` в handlers.

---

### 3.2 PII и шум в `get_user_auth_status` (средний)

**Файл:** `auth_service.py`, ~стр. 147–148, 165

```python
for i, row in enumerate(records):
    logger.info(f"Проверка записи {i+1} для статуса: {row}")  # row может содержать phone, fio и т.п.
    ...
    logger.info(f"Запись {i+1} не соответствует запрашиваемому Telegram ID")
```

- В `row` могут быть персональные данные (телефон, ФИО и др.).
- Для каждой строки таблицы пишется `INFO` — при большом числе записей это создаёт шум и объём логов.

**Решение:**

- Убрать или заменить на `logger.debug` с нейтральным текстом (без `row`).
- При необходимости оставить только: `logger.debug(f"Проверка записи {i+1}")`.

---

### 3.3 `auth_service.worksheet is None` при доступе к Sheets (средний)

**Файлы:** `handlers/chat.py` (`_create_appeal_entry`), `handlers/callback.py` (`_handle_specialist_request`)

Используется:

```python
records = await auth_service.gateway.get_all_records(auth_service.worksheet)
```

При `auth_service.worksheet is None` вызов дойдёт до `worksheet.get_all_records` и приведёт к `AttributeError: 'NoneType' object has no attribute 'get_all_records'`.

**Решение:** проверка до вызова:

```python
# в _create_appeal_entry и _handle_specialist_request
if not auth_service.worksheet:
    logger.warning("auth_service.worksheet не инициализирован, пропуск")
    return
```

В `_create_appeal_entry` при раннем return ничего не делать; в callback — отправить сообщение об ошибке и return.

---

### 3.4 PollingWatchdog: `monitoring_task` не заполняется (низкий)

**Файл:** `polling_watchdog.py`

- `start_monitoring()` не присваивает `self.monitoring_task`.
- Задача создаётся в `bot.py`: `task_tracker.create_tracked_task(watchdog.start_monitoring(), "watchdog_monitor")`.
- В `stop_monitoring()`:

  ```python
  if self.monitoring_task and not self.monitoring_task.done():
      self.monitoring_task.cancel()
  ```

  `self.monitoring_task` всегда `None`, отмена по таску не срабатывает. Остановка идёт только за счёт `is_monitoring = False`; цикл выйдет после следующего `asyncio.sleep(check_interval_seconds)` (до 30 с).

**Решение:** в начале `start_monitoring()`:

```python
self.monitoring_task = asyncio.current_task()
```

Тогда в `stop_monitoring` можно вызывать `self.monitoring_task.cancel()` для более быстрой остановки (и при необходимости `await` с `CancelledError`).

---

### 3.5 `is_promotions_available(gateway)`: параметр `gateway` не используется (низкий)

**Файл:** `promotions_api.py`

```python
async def is_promotions_available(gateway: AsyncGoogleSheetsGateway) -> bool:
    try:
        _get_promotions_client_and_sheet()  # свой синхронный клиент, gateway не используется
        return True
    ...
```

Проверка идёт через отдельный синхронный клиент, а не через переданный `gateway`. Сигнатура вводит в заблуждение.

**Решение (на выбор):**

- Использовать `gateway` для проверки (например, `authorize_client` + `open_spreadsheet` по `PROMOTIONS_SHEET_ID`) и при необходимости убрать вызов `_get_promotions_client_and_sheet` из этой функции, или
- Оставить логику, но переименовать: `is_promotions_available(gateway=None)` и в docstring указать, что `gateway` не используется, а проверка — через конфиг и доступность таблицы.

---

### 3.6 Остановка при рестарте polling (низкий)

**Файл:** `bot.py`, блок `except (TelegramError, ConnectionError, TimeoutError)` при `run_polling`

При исключении из `run_polling` пересоздаётся `Application` и снова вызывается `run_polling`. Неочевидно, вызывается ли `post_stop` у старого приложения (зависит от поведения python-telegram-bot при исключении). Фоновые сервисы (health, response_monitor, promotions_notifier, watchdog) имеют защиту вида `if self.is_running: return` в `start_monitoring`, поэтому повторный `post_init` не запустит второй экземпляр. Если `post_stop` не вызывался, задачи от первого запуска могут висеть.

**Рекомендация:** перед пересозданием `Application` в блоке рестарта явно вызывать аналог `post_stop` (остановка health, response_monitor, promotions_notifier, watchdog), если в документации PTB нет гарантии вызова `post_stop` при таком исключении.

---

### 3.7 Логи за последние 24 часа

- **Локально:** `logs/chat_history.jsonl` создаётся при `LOG_TO_LOCAL_FILE=True` и записи в чат. Папка `logs/` в репозитории пуста, в `.gitignore` указано `logs/` и `*.log` — в репозитории логов за 24 часа нет.
- **На сервере:** по README — `journalctl -u marketingbot-bot.service -f`; за последние 24 ч:  
  `journalctl -u marketingbot-bot.service --since "24 hours ago"`  
  (выполняется по SSH на сервере; в рамках данного аудита доступа к серверу нет).

---

## 4. Состояние после предыдущих исправлений

Проверено, что в коде присутствуют внесённые ранее правки:

| Пункт | Файл | Статус |
|-------|------|--------|
| tenacity, psutil в requirements | requirements.txt | ✅ |
| set_status_in_work вместо update_appeal_status | handlers/callback.py | ✅ |
| gateway.get_all_records вместо worksheet.get_all_records | handlers/chat.py, callback | ✅ |
| await is_promotions_available(gateway), await get_promotions_json(gateway) | handlers/promotions | ✅ |
| promotions_gateway в setup_handlers и register_promotions_handlers | bot, handlers/__init__, promotions | ✅ |
| _reconnect_sheets синхронный | bot_health_monitor | ✅ |
| Удалена мёртвая строка appeal['row'] | response_monitor | ✅ |
| Singleton aiohttp.ClientSession в PromotionsNotifier | promotions_notifier | ✅ |
| asyncio.Lock для записи в sheets_gateway | sheets_gateway | ✅ |
| Маскировка PII в логах | utils, auth, appeals, response_monitor | ✅ |
| Расширенная validate_environment | preventive_guards | ✅ |
| Замена `except: pass` на logger.debug | handlers/chat | ✅ |
| Исправление «послеPinned» в комментарии | gemini_service | ✅ |

---

## 5. Сводка по файлам

### 5.1 Ядро (production)

| Файл | Назначение | Замечания |
|------|------------|-----------|
| bot.py | Точка входа, инициализация, polling, post_init/post_stop, рестарт, error_handler | При рестарте — явный вызов post_stop (см. 3.6) |
| handlers/__init__.py | setup_handlers, promotions_gateway | — |
| handlers/auth.py | /start, WEB_APP_DATA (auth + get_promotions) | — |
| handlers/chat.py | Текст → appeal, specialist, AI stream, логи | Проверка worksheet (3.3) |
| handlers/callback.py | contact_specialist | Проверка worksheet (3.3) |
| handlers/promotions.py | /promotions, handle_promotions_request | — |
| handlers/appeals.py | /appeals | — |
| utils.py | mask_*, URL, create_specialist_button, _is_user_escalation_request, прочие | Единственный источник; handlers/utils — дубликат (3.1) |
| auth_service.py | Авторизация, кэш, gateway | Логирование row (3.2) |
| appeals_service.py | Обращения, статусы, работа с листом | — |
| ai_service.py | Прокси к Gemini | — |
| gemini_service.py | Gemini, история, tools, RAG, стриминг | — |
| knowledge_base.py | RAG, Drive, Context Caching, caches.delete | — |
| drive_service.py | Google Drive (readonly) | — |
| sheets_gateway.py | Async Gateway, retry, CB, _write_lock | — |
| sheets_utils.py | Circuit Breaker (auth, appeals, promotions) | — |
| promotions_api.py | get_active_promotions, get_promotions_json, check_new_promotions, is_promotions_available | is_promotions_available не использует gateway (3.5) |
| promotions_notifier.py | Рассылка акций, SENT, медиа, _http_session | — |
| response_monitor.py | Ответы специалистов, «Решено» | — |
| bot_health_monitor.py | getMe, переподключение Sheets (_reconnect_sheets sync) | — |
| polling_watchdog.py | Молчание getUpdates, Kill Switch | monitoring_task не задаётся (3.4) |
| task_tracker.py | Учёт фоновых задач, логирование падений | — |
| preventive_guards.py | SingleInstanceGuard, validate_environment | — |
| error_handler.py | safe_handler, safe_telegram_call | — |
| config/settings.py | ENABLE_*, LOG_* | — |

### 5.2 Вспомогательные и устаревшие

| Файл | Использование | Рекомендация |
|------|---------------|--------------|
| handlers/utils.py | Не импортируется | Удалить (5.1) |
| ALL_CREDENTIALS.md | Документация/учёт | Не коммитить секреты |
| DEEP_AUDIT_REPORT.md | Предыдущий аудит | Учитывать при планировании |
| archive/*, docs/archive/* | Старый код, скрипты | Не в production-пути |
| scripts/* | Деплой, мониторинг, утилиты | По необходимости обновлять под текущий деплой |

---

## 6. План действий

### 6.1 Быстрые правки (рекомендуется в течение 1–2 дней)

1. **Удалить `handlers/utils.py`**  
   - Все импорты идут из корневого `utils`; дубликат не нужен.

2. **auth_service.get_user_auth_status**  
   - Убрать или перевести в `logger.debug` строки с `{row}` и лишние `INFO` по каждой записи.  
   - Не логировать содержимое `row` с потенциальным PII.

3. **Проверка `auth_service.worksheet`**  
   - В `handlers/chat._create_appeal_entry`: в начале добавить  
     `if not getattr(auth_service, 'worksheet', None): return`  
   - В `handlers/callback._handle_specialist_request`: перед `get_all_records`  
     `if not getattr(auth_service, 'worksheet', None):`  
     отправить «Сервис временно недоступен» и `return`.

### 6.2 Улучшения (1–2 спринта)

4. **PollingWatchdog**  
   - В `start_monitoring` после `self.is_monitoring = True` добавить  
     `self.monitoring_task = asyncio.current_task()`  
   - В `stop_monitoring` оставить `cancel` по `self.monitoring_task` (уже есть проверка `if self.monitoring_task and not self.monitoring_task.done()`).

5. **promotions_api.is_promotions_available**  
   - Либо реализовать проверку через переданный `gateway`, либо явно задокументировать, что `gateway` не используется, и при желании сделать параметр опциональным.

6. **Рестарт в bot.py**  
   - В блоке `except (TelegramError, ConnectionError, TimeoutError)` перед пересозданием `Application` вызывать те же остановки, что и в `post_stop` (health, response_monitor, promotions_notifier, watchdog), чтобы гарантированно завершать старые фоновые задачи.

### 6.3 Опционально

7. **Логи**  
   - Настроить ротацию и/или объём для `logs/chat_history.jsonl` (если пишется много).  
   - На сервере: при необходимости — `journalctl --vacuum-time=7d` или аналог, чтобы не раздувать логи.

8. **Типизация и линтеры**  
   - Включить `mypy` для основных модулей (bot, handlers, auth, appeals, sheets_gateway, promotions_*).  
   - Проверить `ruff`/`flake8` на уже включённые правила.

9. **Тесты**  
   - Юнит-тесты на `mask_*`, `normalize_phone`, `_is_user_escalation_request`, ключевые ветки в `validate_environment`.

---

## 7. Подключённые функции и импорты (кратко)

### 7.1 Цепочки импортов (ядро)

- `bot` → auth_service, handlers, ai_service, response_monitor, promotions_notifier, appeals_service, bot_health_monitor, sheets_gateway, polling_watchdog, task_tracker, preventive_guards  
- `handlers` → config.settings, auth, chat, appeals, promotions, callback  
- `handlers.auth` → utils (get_web_app_url, get_spa_menu_url)  
- `handlers.chat` → utils (create_specialist_button, _is_user_escalation_request), config, auth_service, ai_service, appeals_service, error_handler  
- `handlers.callback` → auth_service, appeals_service, error_handler  
- `handlers.promotions` → promotions_api, sheets_gateway, auth_service, error_handler  
- `auth_service` → sheets_gateway, utils (mask_phone, mask_telegram_id)  
- `appeals_service` → sheets_gateway, utils (mask_phone, mask_telegram_id, mask_fio)  
- `ai_service` → gemini_service, sheets_gateway  
- `gemini_service` → promotions_api, sheets_gateway, drive_service, knowledge_base  
- `knowledge_base` → drive_service, google.genai  
- `promotions_notifier` → promotions_api, auth_service, sheets_gateway  
- `response_monitor` → appeals_service, utils (mask_telegram_id)  
- `sheets_gateway` → gspread, tenacity, sheets_utils, dotenv  
- `promotions_api` → sheets_gateway  
- `preventive_guards` → psutil, Path, os, sys  

### 7.2 Циклических импортов не обнаружено

Зависимости идут в одну сторону; отложенные импорты (например, `from handlers.promotions import handle_promotions_request` в `handlers.auth`) не образуют циклов.

---

## 8. Примеры кода для правок

### 8.1 Проверка `worksheet` в `_create_appeal_entry` (handlers/chat.py)

```python
async def _create_appeal_entry(user, text, auth_service, appeals_service):
    """Фоновое создание записи в таблице обращений."""
    if not getattr(auth_service, 'worksheet', None):
        logger.debug("_create_appeal_entry: worksheet не инициализирован, пропуск")
        return
    try:
        records = await auth_service.gateway.get_all_records(auth_service.worksheet)
        # ... остальное без изменений
```

### 8.2 Проверка `worksheet` в `_handle_specialist_request` (handlers/callback.py)

```python
async def _handle_specialist_request(...):
    if not appeals_service or not appeals_service.is_available():
        await query.message.reply_text("Сервис временно недоступен.")
        return
    if not getattr(auth_service, 'worksheet', None):
        await query.message.reply_text("Сервис временно недоступен.")
        return
    try:
        records = await auth_service.gateway.get_all_records(auth_service.worksheet)
        # ...
```

### 8.3 Снижение шума и PII в auth_service.get_user_auth_status

```python
for i, row in enumerate(records):
    # logger.info(f"Проверка записи {i+1} для статуса: {row}")  # убрать
    telegram_id_in_sheet = row.get('Telegram ID')
    # при желании: logger.debug(f"Проверка записи {i+1}")
    if str(telegram_id_in_sheet) == str(telegram_id):
        # ...
    # else: logger.info(...) — можно оставить на debug или убрать
```

### 8.4 PollingWatchdog.start_monitoring

```python
async def start_monitoring(self):
    if self.is_monitoring:
        logger.warning("PollingWatchdog уже запущен")
        return
    self.is_monitoring = True
    self.monitoring_task = asyncio.current_task()  # добавить
    logger.info(f"🐕 PollingWatchdog запущен (проверка каждые {self.check_interval_seconds}s)")
    # ...
```

---

## 9. Заключение

Архитектура и основные потоки после внесённых hotfix’ов и доработок выглядят согласованно: один шлюз на контур Sheets, асинхронный доступ без блокировки event loop, блокировки на запись, маскировка PII, валидация окружения, превентивные механизмы и мониторинг.

Для production целесообразно в ближайшее время выполнить п. 6.1 (удаление дубликата utils, правки логов и проверка `worksheet`), затем — п. 6.2 (Watchdog, is_promotions_available, рестарт в bot.py). П. 6.3 можно планировать по приоритету доработок (логи, типизация, тесты).

Логи за последние 24 часа при необходимости смотреть на сервере через `journalctl`; в репозитории их нет из-за .gitignore и пустой `logs/`.
